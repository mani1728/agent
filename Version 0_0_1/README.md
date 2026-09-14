# MT5 Agent v0.0.1

Minimal Windows agent for validating the MetaTrader 5 (MT5) terminal connection lifecycle.

> **Release status:** v0.0.1 is a lifecycle-validation release. It does **not** execute trades or submit orders.

## Scope

v0.0.1 intentionally implements only the smallest reliable runtime path:

```text
Agent
  │
  ▼
MT5Adapter
  │
  ▼
MetaTrader 5
```

Lifecycle:

```text
initialize MT5
      ↓
check connection
      ↓
success / failure
      ↓
clean shutdown
```

Included:

- MetaTrader 5 initialization through the official Python package.
- MT5 terminal reachability/readiness check.
- Small immutable `Status` contract.
- Explicit agent start/stop lifecycle.
- Health-check helper.
- Local status transport abstraction.
- Unit tests using a fake MT5 adapter; tests do not require a live terminal.
- Windows single-file executable packaging with PyInstaller.
- Dedicated application icon generated from the repository icon renderer.
- GitHub Actions test, build, smoke-test, and tag-triggered release pipeline.

Not included:

- Trading or order execution.
- Account management.
- Strategy logic.
- Kafka/HTTP transport.
- Database persistence.
- Windows Service installation.
- Authentication, authorization, or remote control plane.

Those concerns belong to later versions and must not be assumed to exist in v0.0.1.

## Requirements

| Component | Requirement |
|---|---|
| Operating system | Windows 10/11, 64-bit |
| Python | 3.11, 64-bit for the supported build environment |
| MetaTrader 5 | Installed terminal on the runtime machine |
| Python dependencies | `agent/requirements.txt` |
| Build system | PyInstaller |

The dependency set pins `numpy==1.26.4` to keep the Windows packaging path compatible with the tested Python 3.11 environment and the MetaTrader 5 dependency chain.

## Repository layout

```text
Version 0_0_1/
├── agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   ├── adapters/
│   │   └── mt5_adapter.py
│   ├── contracts/
│   │   └── models.py
│   ├── core/
│   │   └── agent.py
│   ├── deployment/
│   │   ├── Agent.spec
│   │   └── MT5Agent.ico
│   ├── health/
│   │   └── health.py
│   ├── infrastructure/
│   │   └── config.py
│   ├── transport/
│   │   └── local.py
│   └── requirements.txt
├── tests/
│   └── test_agent.py
├── build.ps1
├── make_icon.py
├── make_icon_preview.py
├── CHANGELOG.md
└── README.md
```

## Run from source

From the `Version 0_0_1` directory:

```powershell
python -m agent
```

Expected behavior when MT5 is available:

```text
MT5 connection established.
```

When MT5 is unavailable, the process reports:

```text
Unable to connect to MT5.
```

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | MT5 connection established and the lifecycle completed successfully. |
| `1` | MT5 connection could not be established. |

## Testing

Run the complete unit-test suite:

```powershell
pytest
```

The tests inject a fake adapter, so they validate the agent lifecycle without requiring MetaTrader 5 to be installed or running.

The CI pipeline runs these tests on `windows-latest` with Python 3.11 before packaging.

## Build the Windows EXE

The supported local build command is:

```powershell
.\build.ps1
```

The script:

1. Installs the pinned dependencies.
2. Regenerates `MT5Agent.ico` from `make_icon.py`.
3. Runs `pytest`.
4. Builds the executable with the versioned PyInstaller spec.
5. Verifies the expected output exists.

Final output:

```text
dist\MT5Agent-v0.0.1.exe
```

Direct PyInstaller invocation:

```powershell
pyinstaller agent/deployment/Agent.spec --clean --noconfirm
```

The PyInstaller spec explicitly collects NumPy and MetaTrader 5 package data/binaries and disables UPX compression to reduce native-dependency packaging risk.

## Application icon

The source renderer is:

```text
make_icon.py
```

Preview tooling is available in:

```text
make_icon_preview.py
```

The generated Windows icon is:

```text
agent/deployment/MT5Agent.ico
```

The icon is regenerated during both the local build script and GitHub Actions build so the packaged application is reproducible from repository sources.

## CI/CD

Workflow:

```text
.github/workflows/version-0.0.1.yml
```

The workflow performs:

```text
push / pull request
       ↓
install dependencies
       ↓
pytest
       ↓
build EXE
       ↓
verify artifact name
       ↓
smoke test
       ↓
GitHub Actions artifact
       ↓
(tag v0.0.1)
GitHub Release
```

The release artifact name is:

```text
MT5Agent-v0.0.1.exe
```

## Runtime

The executable requires a MetaTrader 5 terminal to be installed on the Windows host. For a successful runtime check, the terminal must be available to the MT5 Python integration.

v0.0.1 does not require broker credentials, strategy configuration, or a trading account for its unit tests. A live terminal is required only for the real connection test.

## Verification record

The v0.0.1 implementation was verified through:

- Windows/Python unit tests.
- GitHub Actions build and smoke test.
- A real Windows execution with MetaTrader 5 available, producing `MT5 connection established.`.
- Final Windows executable packaging with the versioned filename `MT5Agent-v0.0.1.exe`.

The release executable used for final verification was approximately 39.5 MB. Its SHA-256 checksum was:

```text
a96f7ce0b44ad81ee64dbabd739e844c601b3f5acea1d2897ea962221b18e608
```

> Checksum values identify a specific binary build. If a later release asset is rebuilt, calculate and publish its checksum again rather than reusing this value.

## Release

The intended Git tag is:

```text
v0.0.1
```

The release asset is:

```text
MT5Agent-v0.0.1.exe
```

Release title:

```text
MT5 Agent v0.0.1 — MT5 Lifecycle Validation
```

See `CHANGELOG.md` for the version-level change record and release notes.

## Development policy for v0.0.1

v0.0.1 is frozen as a minimal foundation. Changes that introduce trading logic, remote transports, persistence, security infrastructure, or service hosting should be implemented in the next version rather than expanding this release retrospectively.
