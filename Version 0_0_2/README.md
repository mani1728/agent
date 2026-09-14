# MT5 Agent v0.0.2

**Agent Runtime & Contract Foundation**

Version 0.0.2 hardens the runtime foundation established by v0.0.1 without introducing trading, order execution, transport, persistence, security, service hosting, or AI integration.

## Release status

- Version: `0.0.2`
- Merge commit: `0ee540ef4af08a4bdcbb90b0262997b53d34662c`
- PR: `#32`
- CI: Windows test and build jobs passed
- Artifact: `MT5Agent-v0.0.2.exe`
- Release tag: `v0.0.2` should point to the final approved release commit.

## Scope

### Included

- Explicit lifecycle state machine: `CREATED`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAILED`.
- Explicit `MT5Port` protocol between the core runtime and terminal adapter.
- Dependency injection of the MT5 port into `Agent`.
- Immutable `Status`, `HealthStatus`, and typed `AgentConfig` contracts.
- Deterministic handling of adapter connection, disconnect, and health-probe failures.
- Logger injection at the runtime boundary without introducing a logging framework abstraction.
- Lifecycle, health, contract, exception, restart, and adapter-port regression tests.
- Independent Windows packaging that produces `MT5Agent-v0.0.2.exe`.
- Dedicated v0.0.2 GitHub Actions workflow and Windows smoke test.

### Deliberate non-goals

The following remain outside v0.0.2:

- Trading and order execution.
- Position/account management.
- Network transport or HTTP/Kafka APIs.
- Persistence or databases.
- Authentication and authorization.
- Windows Service hosting.
- Strategy engine.
- AI/model integration.
- Retry/circuit-breaker infrastructure.

## Architecture

```text
Application Entry Point
        |
        v
      Agent
        |
        v
     MT5Port  <----------------  MT5Adapter
                                  |
                                  v
                             MetaTrader 5
```

The core depends on the `MT5Port` protocol, not on the concrete `MetaTrader5` package. The concrete adapter is composed only at the application boundary.

## Lifecycle

```text
CREATED
   |
   v
STARTING ---- connection failure ----> FAILED
   |
   v
RUNNING
   |
   v
STOPPING ---- disconnect failure ---> FAILED
   |
   v
STOPPED
```

Additional behavior:

- `start()` is idempotent while `RUNNING`.
- `start()` can restart an agent from `STOPPED` or `FAILED`.
- `stop()` is safe before the first start and after a failed start.
- Adapter exceptions are converted into deterministic `Status`/health failures and logged.

## Repository layout

```text
Version 0_0_2/
├── agent/
│   ├── adapters/          # MetaTrader5 integration
│   ├── contracts/         # Ports and immutable runtime contracts
│   ├── core/              # Agent lifecycle and runtime state
│   ├── health/            # Health boundary
│   ├── infrastructure/   # Typed application configuration
│   └── main.py            # Composition root
├── tests/                 # Unit and contract-oriented tests
├── deployment/            # PyInstaller specification
├── docs/                  # Architecture and release documentation
├── build.ps1              # Reproducible local Windows build
├── make_icon.py           # Application icon generation
├── pytest.ini             # Test import configuration
└── requirements.txt       # Build/test dependencies
```

## Test

From `Version 0_0_2`:

```powershell
python -m pip install -r requirements.txt
pytest -q
```

The test suite uses a deterministic fake implementation of `MT5Port`; a real MetaTrader 5 terminal is not required for unit tests.

## Windows build

From this directory on Windows:

```powershell
.\build.ps1
```

The script installs dependencies, generates the icon, runs the test suite, builds with PyInstaller, and verifies the expected executable path.

Expected output:

```text
dist\MT5Agent-v0.0.2.exe
```

## CI verification

The dedicated workflow is:

```text
.github/workflows/version-0.0.2.yml
```

The verified pipeline performs:

```text
Windows runner
    -> Python 3.11
    -> dependency installation
    -> pytest
    -> icon generation
    -> PyInstaller build
    -> executable existence check
    -> unavailable-terminal smoke test
    -> artifact upload
```

The final v0.0.2 workflow run completed successfully for both test and build jobs. The CI artifact was produced from commit `c7ac9d7c0925584962171d2ab95b558005b98439`; the merge commit preserves the same source tree.

## Release artifact

Artifact:

```text
MT5Agent-v0.0.2.exe
```

SHA-256 of the extracted CI executable:

```text
5ceae12da14f349cb2a3a4bd04606fdb2ca6b595e89183bb59d7a5de00dfe13f
```

CI artifact archive digest:

```text
sha256:359b6ae4e64d1905b5e6dc9d49fbc5efe8338106c56524879adb21852c57d893
```

## Release policy

v0.0.2 is complete at the implementation and verification level. The repository release operation consists of creating tag `v0.0.2` on the approved final release commit and publishing the GitHub Release with `MT5Agent-v0.0.2.exe` attached.

v0.0.1 remains untouched. The root `README.md` and `Version 1_0_0` remain outside this version's implementation scope.
