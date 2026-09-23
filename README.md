# MT5 Agent — v0.1.3 development

The active agent provides MT5 lifecycle management, an HTTP/JSON command
boundary, capability discovery and runtime introspection. v0.1.2 is released;
v0.1.3 is active development.
See [CHANGELOG.md](CHANGELOG.md) for released and unreleased changes.

GitLab (`origin`) is the source of truth. GitHub is a downstream mirror.
Development flows through `develop`, `staging`, then `main` after review.

## Runtime

```text
python -m agent / python main.py
  -> environment configuration
  -> composition root
  -> ApplicationHost
  -> MT5 lifecycle + HTTPServerHost

POST /command
  -> HTTPTransportAdapter
  -> ApplicationBoundary
  -> CommandDispatcher
  -> command handlers / capability provider
```

The application boundary preserves Validation -> Authentication -> Authorization
-> Dispatch ordering and best-effort request/operational observability. Default
composition uses AllowAll authentication/authorization implementations; it is a
foundation boundary, not a production IAM or TLS/mTLS deployment.

Commands include health, status, `agent.get_capabilities` and
`agent.get_runtime_info`. The default capability registry is empty and runtime
information and `agent.get_status` reflect the active identity/lifecycle.
See [known issues](docs/KNOWN_ISSUES.md) for remaining limitations.

This active runtime does not include trading/order execution, Kafka, Gateway,
SQLite persistence, retry/circuit-breaker infrastructure, Windows Service hosting
or file-based JSONC configuration. The historical runtime containing those
modules is retained in Git history and is not merged into this package.

## Layout

```text
agent/
  __init__.py, __main__.py, main.py, composition.py
  adapters/, application/, contracts/, core/, health/, infrastructure/
tests/
deployment/        # Agent.spec, make_icon.py, ci.ps1, RELEASE_CHECKLIST.md
docs/
main.py            # thin console wrapper
requirements.txt
pyproject.toml
.gitlab-ci.yml
CHANGELOG.md
```

Historical version directories are no longer development locations. Recover old
files through commits/tags; the exact move map is in [docs/MIGRATION.md](docs/MIGRATION.md).

## Setup and execution

Use Windows x64 with a Python interpreter compatible with requirements.txt and
MetaTrader5. Python 3.11 x64 supports the pinned NumPy 1.26.4 requirement.
Use a dedicated environment; Python 3.14/NumPy 2.x is not an exact requirements
installation. `agent/__init__.py` is the version authority for package metadata,
default AgentIdentity and executable naming. Custom identities remain supported.

From the repository root, using a compatible Python installation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m agent
# Equivalent console entry point:
python main.py
```

Runtime startup may initialize a locally installed MT5 terminal. Exit codes are:

| Code | Meaning |
| --- | --- |
| 0 | Normal graceful termination |
| 1 | MT5 startup, hosting or shutdown failure |
| 2 | Invalid startup configuration |

## Diagnostic and version CLI

```powershell
.\dist\MT5Agent-v0.1.3.exe --version
.\dist\MT5Agent-v0.1.3.exe --diagnose
.\dist\MT5Agent-v0.1.3.exe --diagnose --json
```

`--version` prints the canonical version and exits 0 without importing the MT5
integration or constructing the host. Diagnostics reuse environment configuration
validation and perform inspection only: no MT5 initialization, terminal launch,
HTTP binding or log-file creation. JSON output includes identity, configuration,
terminal paths, process presence, dependency availability and readiness.

Diagnostic exit 0 means required inspection checks passed; exit 1 means not
ready (including invalid configuration, missing terminal/dependency, unsupported
platform or incomplete inspection). Invalid CLI syntax exits 2. A terminal need
not already be running. Readiness does not prove account login, MT5 connectivity
or HTTP port availability.

Discovery checks standard installation directories, registered installations,
MetaQuotes origin records, drive roots and immediate portable subdirectories,
Desktop/Downloads/Documents and executable/current directories. Unlisted deeper
portable locations can be missed; no exhaustive absence claim is made. Normal
startup retains the vendor's `initialize()` automatic selection and may launch
MT5. Inspection never substitutes a different path into that call.

## Logging

Production composition uses the existing operational-observability port with a
standard-library logging adapter. INFO covers startup/version, validated config,
MT5 discovery and initialization, lifecycle, HTTP listening and shutdown request.
DEBUG adds safe technical diagnostics. Event metadata, account data, passwords,
tokens and raw MT5 exception details are omitted. Paths appear in explicit
self-check output so the user can identify installations.

Set `MT5_AGENT_LOG_LEVEL` to DEBUG, INFO (default), WARNING or ERROR. Values are
case-insensitive; unsupported values fail configuration validation. Optional
`MT5_AGENT_LOG_FILE` appends UTF-8 logs alongside console output; its parent must
already exist. An unavailable file or broken logging sink does not stop the
Agent. Diagnostics validate these settings without opening the file.

## Configuration

| Environment variable | Default | Constraint |
| --- | --- | --- |
| `MT5_AGENT_HTTP_HOST` | `127.0.0.1` | Non-empty string |
| `MT5_AGENT_HTTP_PORT` | `8080` | Integer 1..65535 |
| `MT5_AGENT_HTTP_MAX_REQUEST_BYTES` | `1048576` | Positive integer |
| `MT5_AGENT_LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `MT5_AGENT_LOG_FILE` | Unset | Optional log file path; existing parent directory |

There is no active config.json/config.jsonc loader or service_host.py in this
stage. See [configuration](docs/CONFIGURATION.md) and [transport](docs/TRANSPORT.md).

## Tests and executable

Run from repository root:

```powershell
python -m pytest -q
./deployment/ci.ps1 -Task validate
./deployment/ci.ps1 -Task build
./deployment/ci.ps1 -Task smoke-invalid
```

Pytest collects `tests/` only by default. Generated icon, reports, build/
and dist/ are ignored. The test executable is `dist/MT5Agent-v0.1.3.exe`.
It is a maintenance candidate, not a published release.

Use [deployment/ci.ps1](deployment/ci.ps1) for the same validation and smoke
commands as CI. See [docs/CI.md](docs/CI.md) for environment prerequisites,
artifact handoff and checksum verification.

## CI status

The GitLab configuration runs validate, test, build, smoke and package stages
on registered local Windows runners using `pwsh`. Runner tags are
`windows-self-hosted`, `windows-self-hosted-no-mt5`, and
`windows-self-hosted-mt5`. Branch pipelines and
stable semantic-version tags (`v0.1.1`, `v0.2.0`) use the same validation chain.
Tag pipelines reject a tag that disagrees with the source version.

Version/diagnostic CLI checks and invalid-configuration smoke are automatic.
The no-MT5 runner must prove terminal absence before its automatic unavailable
smoke runs. The reference-MT5 runner proves the expected installation/data mapping
and records session/process ownership evidence without starting or terminating MT5.
Final packaging requires both terminal-validation receipts, the runtime-probe
receipt, and build evidence for the same binary, commit and pipeline; it never
rebuilds. See [CI instructions](docs/CI.md).

GitLab produced and validated v0.1.1. The obsolete GitHub Actions workflow has
been retired; GitHub is a push mirror/archive only.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [contracts](docs/CONTRACTS.md)
- [Error model](docs/ERROR_MODEL.md) and [test strategy](docs/TEST_STRATEGY.md)
- [Migration map](docs/MIGRATION.md) and [known issues](docs/KNOWN_ISSUES.md)
- [Release checklist](deployment/RELEASE_CHECKLIST.md) and [changelog](CHANGELOG.md)

## License

The previous root README designated this repository Confidential & Proprietary.
This structural migration does not change those terms or grant new permissions.
