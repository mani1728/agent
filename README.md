# MT5 Agent — v0.1.0 development

The active agent provides MT5 lifecycle management, an HTTP/JSON command
boundary, capability discovery and runtime introspection. v0.1.0 is unreleased;
see [CHANGELOG.md](CHANGELOG.md) for historical releases and current work.

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
information reflects the active identity/lifecycle. The existing status handler
has a config/identity defect; see [known issues](docs/KNOWN_ISSUES.md).

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
MetaTrader5. Keep the existing NumPy 1.26.4 constraint; the pre-existing local
Python 3.14/NumPy 2.5 environment is not an exact requirements installation.
The package version, AgentIdentity version and executable name are currently
inconsistent and intentionally unchanged by the layout migration.

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
python deployment/make_icon.py
python -m PyInstaller deployment/Agent.spec --clean --noconfirm
```

Pytest collects `tests/` only by default. The active test files and source package
were preserved from the development baseline. Generated icon, reports, build/
and dist/ are ignored. The executable remains `dist/MT5Agent-v0.1.0.exe`.

Use [deployment/ci.ps1](deployment/ci.ps1) for the same validation and smoke
commands as CI. See [docs/CI.md](docs/CI.md) for environment prerequisites,
artifact handoff and checksum verification.

## CI status

The GitLab configuration defines validate, test, build, smoke and package stages
on local Windows runners. Registration is pending. `windows-self-hosted` and
`windows-self-hosted-no-mt5` are configurable placeholder tags, not registered
runners. No isolated unavailable-terminal VM is currently available.

Invalid-configuration smoke is automatic. Unavailable-terminal smoke is a
blocking manual job requiring a confirmed isolated VM. Final packaging requires
both smoke receipts for the exact same binary. The configuration is not evidence
of a completed GitLab pipeline.

The legacy GitHub workflow is retained until GitLab CI is operational. It still
uses historical paths and can run only against a pre-migration ref containing
them; it is not a working fallback for this canonical tree.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [contracts](docs/CONTRACTS.md)
- [Error model](docs/ERROR_MODEL.md) and [test strategy](docs/TEST_STRATEGY.md)
- [Migration map](docs/MIGRATION.md) and [known issues](docs/KNOWN_ISSUES.md)
- [Release checklist](deployment/RELEASE_CHECKLIST.md) and [changelog](CHANGELOG.md)

## License

The previous root README designated this repository Confidential & Proprietary.
This structural migration does not change those terms or grant new permissions.
