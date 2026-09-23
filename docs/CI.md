# GitLab CI and local validation

GitLab (`origin`) is the source of truth. GitHub is a push mirror/archive only;
the obsolete Actions workflow is retired. CI produces candidate artifacts, not
merges, tags or releases. v0.1.0 and v0.1.1 remain immutable.

## Runner and safety settings

The local Windows runner is registered with `pwsh` and the tags below. A tag is
a scheduling constraint, not a substitute for verifying the machine state.

| Variable | Default | Meaning |
| --- | --- | --- |
| `WINDOWS_RUNNER_TAG` | `windows-self-hosted` | Local Windows x64 shell runner |
| `MT5_SMOKE_RUNNER_TAG` | `windows-self-hosted-no-mt5` | Local isolated no-MT5 runner |
| `PYTHON_EXECUTABLE` | `python` | Machine-installed compatible Python, or its absolute path |
| `MT5_TERMINAL_UNAVAILABLE_CONFIRMED` | `false` | Explicit operator confirmation for the manual smoke job only |

Use Python 3.11 x64 with requirements.txt (including NumPy 1.26.4). Do not use
Python 3.14/NumPy 2.x as evidence of requirements reproducibility. Python jobs
install requirements and run `pip check`; no hosted runner or setup-python is used.

For `smoke:terminal-unavailable`, open the manual job form and provide
`MT5_TERMINAL_UNAVAILABLE_CONFIRMED=true` only after verifying that its selected
runner has no accessible MT5 installation, including portable terminals.
Do not set confirmation globally or infer it from the runner tag. The helper
also refuses to proceed while terminal/terminal64 is running; absence of a
process alone does not prove isolation. Do not stop or rename a user's terminal
to make this test pass. The job remains manual and blocking (`allow_failure: false`).

## Pipeline and evidence

```text
validate -> test -> build -> smoke-invalid -> inspect-terminal -> smoke-unavailable (manual) -> package
```

Workflow rules allow stable semantic-version tags such as `v0.1.1` and `v0.2.0`,
pushes to develop/staging/main, merge requests and manual branch pipelines.
An open MR suppresses duplicate branch push pipelines. Leading-zero versions,
prerelease tags and non-version tags are excluded. The tag rule precedes branch
rules because tag pipelines have `CI_COMMIT_TAG` rather than `CI_COMMIT_BRANCH`.
See [GitLab workflow rules](https://docs.gitlab.com/ci/yaml/workflow/).

Every job reads `agent/__init__.py` as the version authority and checks HEAD
against `CI_COMMIT_SHA`. Tag builds require `CI_COMMIT_TAG == v<source version>`;
for a future v0.2.0, update source metadata before tagging. Jobs use the runner's
checkout of the pipeline commit; no script checks out a moving branch.

The PyInstaller recipe derives `MT5Agent-v<version>.exe` from that same metadata.
The build receipt records version, executable name, SHA256, source commit and
pipeline ID. Each smoke job downloads its predecessor's binary and evidence,
checks that build receipt, runs the file with a 60-second limit, and records
expected/actual exit codes, SHA256 and commit/pipeline identity. Packaging
requires both matching smoke receipts and the build receipt. It writes
sha256.txt and uploads that exact executable without rebuilding.

A tag pipeline therefore still requires explicit manual no-MT5 confirmation;
creating a tag does not bypass validation or publish a release. Existing tags
retain their original workflow; this change applies to future tagged commits.

## Local validation

From the repository root, activate a compatible environment or pass an absolute
`-PythonExecutable` path:

```powershell
python -m pip install -r requirements.txt
./deployment/ci.ps1 -Task validate
./deployment/ci.ps1 -Task test
./deployment/ci.ps1 -Task build
./deployment/ci.ps1 -Task smoke-invalid
```

Commit the candidate before its final evidence build so build.json identifies
the candidate commit. The helper restores temporary HTTP configuration values.
The optional `-ArtifactName` parameter must agree with the canonical version.
Direct PyInstaller builds work but do not create the evidence needed to package.

Only on a confirmed isolated no-MT5 machine:

```powershell
$env:MT5_TERMINAL_UNAVAILABLE_CONFIRMED = 'true'
./deployment/ci.ps1 -Task smoke-unavailable
./deployment/ci.ps1 -Task package
```

On an ordinary workstation, skip unavailable-terminal smoke and report it as
unvalidated. You may manually test the built EXE, but it is not a final package.
An independently computed test-binary SHA256 is not a substitute for smoke receipts.

## Configuration validation

Use the installed GitLab CI Lint endpoint with proposed YAML and `dry_run: false`
without creating a tag: `POST /api/v4/projects/root%2Fagent/ci/lint`.
If authentication is unavailable, record that limitation and run local YAML,
PowerShell syntax, dependency graph and artifact/evidence checks. Local checks
cannot prove runner scheduling or artifact uploads. See the
[CI Lint API](https://docs.gitlab.com/api/lint/).

## v0.1.2 CLI and no-MT5 preflight

Invalid-configuration smoke first validates packaged `--version` and
`--diagnose --json`. The automatic `smoke:inspect-terminal` job then runs the
same inspection on the no-MT5 runner. It rejects a running terminal, discovered
executable, unavailable dependency or incomplete inspection before the manual
gate. Review its diagnostic output and the intended isolated machine before
explicitly confirming the manual smoke. The manual job repeats inspection to
catch changes between jobs. Bounded discovery is not proof of exhaustive absence;
operator knowledge of other portable installations remains necessary.

Artifact handoff includes version/diagnostic logs and the original build/smoke
receipts. Packaging still verifies hash, source commit and pipeline ID and does
not rebuild. No v0.1.2 tag or release is created during development.
