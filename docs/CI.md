# GitLab CI and local validation

GitLab (`origin`) is the source of truth. GitHub (`github`) is a downstream
mirror. This configuration creates CI artifacts only: it does not push, merge,
deploy, create tags, publish releases, or configure mirroring.

## Infrastructure status

No GitLab Windows runner is registered yet, and no isolated unavailable-MT5 VM
is available. The following values are placeholders, not verified capabilities:

| Variable | Placeholder | Required setup |
| --- | --- | --- |
| `WINDOWS_RUNNER_TAG` | `windows-self-hosted` | Local Windows x64 runner, shell executor with `shell = "pwsh"` |
| `MT5_SMOKE_RUNNER_TAG` | `windows-self-hosted-no-mt5` | Isolated Windows VM without an accessible MT5 terminal |
| `PYTHON_EXECUTABLE` | `python` | Runner-installed interpreter compatible with unchanged requirements.txt |
| `MT5_TERMINAL_UNAVAILABLE_CONFIRMED` | `false` | Set to `true` only after verifying that isolated VM |

Override these variables in GitLab with the actual registered runner tags.
Prepare a compatible Python environment; the repository's pre-existing local
Python 3.14 environment has NumPy 2.5.3, whereas requirements.txt pins 1.26.4.
Do not treat a test pass in that environment as dependency reproducibility.

## Pipeline and evidence

```text
validate:windows
  -> test:windows
  -> build:windows
  -> smoke:invalid-configuration
  -> smoke:terminal-unavailable (manual, blocking)
  -> package:windows
```

Stages are `validate`, `test`, `build`, `smoke`, `package`. Merge-request
pipelines, pushes to develop/staging/main, and manual branch pipelines are
supported. A branch push with an open MR is suppressed to avoid duplicate
push/MR pipelines. Tag/release pipelines are not enabled.

All jobs use local Windows runners. Each Python job checks installation of the
unchanged requirements and dependency consistency. Native command exit codes
are checked explicitly. Test results are uploaded as JUnit reports.

The build job uploads the executable. Each smoke job downloads its predecessor's
artifact, runs that exact file with a 60-second bound, and records the exit code
and SHA-256. The final job verifies both receipts against the current binary,
generates sha256.txt, and uploads the same executable without rebuilding it.
Successful build alone cannot reach the final package artifact.

The unavailable-terminal smoke is deliberately manual with `allow_failure:
false`. It must remain pending until suitable infrastructure exists. Do not set
the confirmation variable on an ordinary workstation, stop a user's terminal,
or accept an arbitrary startup failure as evidence of an unavailable terminal.

## Local commands (from repository root)

```powershell
python -m pip install -r requirements.txt
./deployment/ci.ps1 -Task validate
./deployment/ci.ps1 -Task test
./deployment/ci.ps1 -Task build
./deployment/ci.ps1 -Task smoke-invalid
```

Pass `-PythonExecutable 'C:\path\to\python.exe'` when Python is not on PATH.
The script restores environment variables used for the invalid-config smoke.
Run `smoke-unavailable` only on the confirmed isolated VM. `package` requires
both real smoke receipts and refuses to generate a final package without them.

## Lint and infrastructure acceptance

Use the installed GitLab's CI Lint endpoint with the proposed YAML content:
`POST /api/v4/projects/root%2Fagent/ci/lint` and `dry_run: false`.
This validates configuration without creating a pipeline. If authentication is
unavailable, record that limitation and perform local YAML/schema, PowerShell
syntax, dependency-graph and artifact-path checks. Local checks do not prove
runner scheduling, artifact upload, or a successful GitLab pipeline.

References: [GitLab CI Lint API](https://docs.gitlab.com/api/lint/),
[CI YAML](https://docs.gitlab.com/ci/yaml/),
[Runner shells](https://docs.gitlab.com/runner/shells/).

## Retained GitHub workflow

`.github/workflows/ci.yml` remains with its original operational content and a
legacy comment. It references the old version directory and is usable only on
historical refs that contain that directory. It is not a working fallback for
the migrated root tree. Its retirement is deferred until GitLab CI has actually
passed. No direct GitHub changes are part of this migration.
