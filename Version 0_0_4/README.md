# MT5 Agent v0.0.4 — Agent Transport Boundary & Execution Context Foundation

## Release Status

**v0.0.4 is the release candidate for the Agent Transport Boundary & Execution Context Foundation.**

- Development branch: `version-0.0.4`
- Pull Request: `#34`
- Baseline: `v0.0.3` / `78d7f37e14d44c18ec62e3b242dc6a000af34681`
- Implementation commit: `b645e9aa2eb8f652f7e5a22bd01072d000a14fbc`
- Release artifact: `MT5Agent-v0.0.4.exe`
- Verified SHA-256: `19ad9b5bead94d9a3a8a28dc4c9405335d0ad777fa0b40093c78b3fcdfabd52d`

See [`docs/FINAL_AUDIT.md`](docs/FINAL_AUDIT.md) for the release gate and final verification record.

## Overview

Version 0.0.4 formalizes the transport-neutral boundary between future external adapters and the existing v0.0.3 Application Command Foundation.

No network protocol is implemented. A future HTTP, Kafka, WebSocket, socket, or other adapter may translate its protocol into `TransportRequest` and consume `TransportResponse` through the `ApplicationPort` contract.

## Scope

### Included

- Immutable `ExecutionContext` carrying `request_id`, `correlation_id`, and metadata.
- Immutable `TransportRequest` and `TransportResponse` contracts.
- `ApplicationPort` protocol for future transport adapters.
- `ApplicationBoundary` as the transport-neutral application ingress/egress boundary.
- Correlation consistency validation between request context and command.
- Deterministic `invalid_request` boundary error code.
- Preservation of all v0.0.3 command contracts and dispatcher result codes.
- Contract, application-boundary, failure-path, and regression tests.
- Windows CI and reproducible PyInstaller packaging.

### Explicitly excluded

- HTTP, REST, Kafka, WebSocket, socket, or other network transport implementations.
- TLS/mTLS.
- Authentication and authorization.
- Persistence, deduplication storage, or durable idempotency.
- Retry and circuit-breaker infrastructure.
- Trading, order execution, position management, or account management.
- Strategy engine.
- AI/LLM integration.
- Windows Service deployment.

## Architecture

```text
External System
      |
      v
Future Transport Adapter
      |
      v
  ApplicationPort
      |
      v
TransportRequest
      |
      v
ApplicationBoundary
      |
      v
CommandDispatcher
      |
      v
Agent Runtime
      |
      v
    MT5Port
      ^
      |
  MT5Adapter
      |
      v
 MetaTrader 5
```

Dependency direction remains:

```text
Core / Application
        ↓
      Contract
        ↓
       Port
        ↑
Infrastructure Adapter
        ↓
External System
```

The Core and Application layers do not import concrete transport implementations or the MetaTrader5 API.

## Contracts

### ExecutionContext

```text
ExecutionContext
├── request_id
├── correlation_id
└── metadata
```

`metadata` is normalized to an immutable mapping. `request_id` identifies one ingress request; `correlation_id` links the command to a broader request or workflow.

### TransportRequest

```text
TransportRequest
├── context: ExecutionContext
└── command: Command
```

The context and command correlation identifiers must match.

### TransportResponse

```text
TransportResponse
├── request_id
├── correlation_id
├── command_id
├── success
├── code
├── message
└── data
```

The response remains protocol-neutral and contains no HTTP/Kafka/WebSocket semantics.

### ApplicationPort

Future transport adapters target:

```python
handle(request: TransportRequest) -> TransportResponse
```

The application owns the implementation. Transport adapters remain outside the Application dependency direction.

## Error Model

Transport/application boundary errors:

| Code | Meaning |
|---|---|
| `invalid_request` | Transport-neutral request envelope or context failed validation. |
| `ok` | Existing dispatcher handler completed successfully. |
| `invalid_command` | Existing command envelope failed validation. |
| `unsupported_schema` | Existing command schema is unsupported. |
| `unknown_command` | No application handler is registered. |
| `execution_failed` | Existing handler raised an unexpected exception. |

Concrete transport exceptions must be translated by the future adapter and must not leak into Core/Application.

## Testing

The version-level suite retains the v0.0.3 command/dispatcher coverage and adds transport/application-boundary coverage. Tests run without a live network transport or MetaTrader 5 terminal.

CI validates:

1. Dependency installation on Windows.
2. Python 3.11 test execution.
3. PyInstaller packaging.
4. Executable existence.
5. Unavailable-terminal startup behavior.
6. SHA-256 generation.
7. Artifact upload.

The v0.0.4 workflow completed successfully for the release candidate.

## Build Locally on Windows

```powershell
cd "Version 0_0_4"
python -m pip install -r requirements.txt
python make_icon.py
pyinstaller deployment/Agent.spec --clean --noconfirm
```

Expected artifact:

```text
dist\MT5Agent-v0.0.4.exe
```

The executable is expected to return exit code `1` when started without an available MetaTrader 5 terminal.

## Release Artifact Verification

Expected release asset:

```text
MT5Agent-v0.0.4.exe
```

Expected SHA-256:

```text
19ad9b5bead94d9a3a8a28dc4c9405335d0ad777fa0b40093c78b3fcdfabd52d
```

The checksum must be independently verified after downloading the release asset.

## Version Isolation

`Version 0_0_1`, `Version 0_0_2`, and `Version 0_0_3` are closed baselines. v0.0.4 is implemented under `Version 0_0_4` and does not modify previous version directories.

## Release Gate

The version is considered closed only after:

1. PR #34 is merged into `main`.
2. Tag `v0.0.4` points to the finalized release commit.
3. `MT5Agent-v0.0.4.exe` is attached to the GitHub release.
4. The published asset checksum matches the verified SHA-256.
5. The executable is manually tested on Windows.

After closure, no additional feature work should be added to `version-0.0.4`; v0.0.5 must branch from the finalized `main` baseline.
