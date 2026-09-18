# MT5 Agent — v0.1.1 development

The active agent provides MT5 lifecycle management, an HTTP/JSON command
boundary, capability discovery and runtime introspection. v0.1.0 is released;
v0.1.1 is the current maintenance candidate awaiting manual acceptance.
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

## Configuration

| Environment variable | Default | Constraint |
| --- | --- | --- |
| `MT5_AGENT_HTTP_HOST` | `127.0.0.1` | Non-empty string |
| `MT5_AGENT_HTTP_PORT` | `8080` | Integer 1..65535 |
| `MT5_AGENT_HTTP_MAX_REQUEST_BYTES` | `1048576` | Positive integer |

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
and dist/ are ignored. The test executable is `dist/MT5Agent-v0.1.1.exe`.
It is a maintenance candidate, not a published release.

Use [deployment/ci.ps1](deployment/ci.ps1) for the same validation and smoke
commands as CI. See [docs/CI.md](docs/CI.md) for environment prerequisites,
artifact handoff and checksum verification.

## CI status

The GitLab configuration runs validate, test, build, smoke and package stages
on registered local Windows runners using `pwsh`. Runner tags are
`windows-self-hosted` and `windows-self-hosted-no-mt5`. Branch pipelines and
stable semantic-version tags (`v0.1.1`, `v0.2.0`) use the same validation chain.
Tag pipelines reject a tag that disagrees with the source version.

Invalid-configuration smoke is automatic. Terminal-unavailable smoke remains a
blocking manual job: explicitly confirm isolation when launching that job.
Final packaging requires both smoke receipts and build evidence for the same
binary, commit and pipeline; it never rebuilds. A no-MT5 runner tag alone does
not establish that no terminal is accessible. See [CI instructions](docs/CI.md).

GitLab produced and validated v0.1.0. The obsolete GitHub Actions workflow has
been retired; GitHub is a push mirror/archive only.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [contracts](docs/CONTRACTS.md)
- [Error model](docs/ERROR_MODEL.md) and [test strategy](docs/TEST_STRATEGY.md)
- [Migration map](docs/MIGRATION.md) and [known issues](docs/KNOWN_ISSUES.md)
- [Release checklist](deployment/RELEASE_CHECKLIST.md) and [changelog](CHANGELOG.md)

## License

The previous root README designated this repository Confidential & Proprietary.
This structural migration does not change those terms or grant new permissions.
