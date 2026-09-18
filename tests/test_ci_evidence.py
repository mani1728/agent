"""Exercise CI gates in isolated repositories; never launch MT5 or a binary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from agent import __version__


ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(not PWSH or not shutil.which("git"), reason="Requires pwsh and git")


@pytest.fixture
def checkout(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "agent").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "reports").mkdir()
    shutil.copyfile(ROOT / "deployment/ci.ps1", tmp_path / "deployment/ci.ps1")
    shutil.copyfile(ROOT / "agent/__init__.py", tmp_path / "agent/__init__.py")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=CI Test", "-c", "user.email=ci@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
    commit = git("rev-parse", "HEAD")
    binary_name = f"MT5Agent-v{__version__}.exe"
    binary = tmp_path / "dist" / binary_name
    binary.write_bytes(b"inert fixture, not an executable")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    evidence = dict(executable=binary_name, sha256=digest, source_commit=commit, pipeline_id="123")
    (tmp_path / "reports/build.json").write_text(json.dumps(dict(evidence, version=__version__)))
    for name, code in [("invalid-configuration", 2), ("terminal-unavailable", 1)]:
        (tmp_path / f"reports/{name}.json").write_text(json.dumps(dict(
            evidence, test=name, expected_exit=code, actual_exit=code)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("CI_")
           and k not in ("ARTIFACT_NAME", "MT5_TERMINAL_UNAVAILABLE_CONFIRMED")}
    env.update(CI_COMMIT_SHA=commit, CI_PIPELINE_ID="123")
    return tmp_path, env


def run_task(checkout, task, **variables):
    path, env = checkout
    return subprocess.run([PWSH, "-NoProfile", "-File", str(path / "deployment/ci.ps1"),
                           "-Task", task], env=dict(env, **variables), text=True,
                          capture_output=True, timeout=30)


def test_metadata_accepts_matching_tag(checkout):
    result = run_task(checkout, "metadata", CI_COMMIT_TAG=f"v{__version__}")
    assert result.returncode == 0, result.stderr
    assert f"MT5Agent-v{__version__}.exe" in result.stdout


@pytest.mark.parametrize("variables", [
    {"CI_COMMIT_TAG": "v9.9.9"}, {"CI_COMMIT_SHA": "0" * 40},
])
def test_metadata_rejects_wrong_tag_or_commit(checkout, variables):
    assert run_task(checkout, "metadata", **variables).returncode != 0


def test_package_preserves_validated_binary(checkout):
    path, _ = checkout
    binary = path / f"dist/MT5Agent-v{__version__}.exe"
    before = binary.read_bytes()
    result = run_task(checkout, "package")
    assert result.returncode == 0, result.stderr
    assert binary.read_bytes() == before
    assert (path / "sha256.txt").read_text(encoding="utf-8-sig").strip() == (
        "SHA256=" + hashlib.sha256(before).hexdigest())


@pytest.mark.parametrize("receipt, field, value", [
    ("build", "source_commit", "stale"), ("build", "pipeline_id", "old-pipeline"),
    ("build", "version", "0.0.0"), ("build", "sha256", "tampered"),
    ("invalid-configuration", "sha256", "tampered"),
    ("terminal-unavailable", "source_commit", "stale"),
    ("terminal-unavailable", "pipeline_id", "old-pipeline"),
    ("terminal-unavailable", "actual_exit", 0),
])
def test_package_rejects_mismatched_evidence(checkout, receipt, field, value):
    path, _ = checkout
    receipt_path = path / f"reports/{receipt}.json"
    evidence = json.loads(receipt_path.read_text())
    evidence[field] = value
    receipt_path.write_text(json.dumps(evidence))
    assert run_task(checkout, "package").returncode != 0
    assert not (path / "sha256.txt").exists()


def test_package_requires_both_smokes(checkout):
    path, _ = checkout
    (path / "sha256.txt").write_text("stale checksum")
    (path / "reports/terminal-unavailable.json").unlink()
    assert run_task(checkout, "package").returncode != 0
    assert not (path / "sha256.txt").exists()


def test_unavailable_smoke_requires_explicit_confirmation(checkout):
    path, _ = checkout
    result = run_task(checkout, "smoke-unavailable")
    assert result.returncode != 0
    assert "MT5_TERMINAL_UNAVAILABLE_CONFIRMED=true" in result.stderr
    assert not (path / "reports/terminal-unavailable.json").exists()
