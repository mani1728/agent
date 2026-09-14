# MT5 Agent v0.0.3 — Agent Command Foundation

## Overview

Version 0.0.3 establishes the **Application Command Foundation** on top of the v0.0.2 Agent Runtime & Contract Foundation.

The new boundary is transport-neutral: a future HTTP, Kafka, WebSocket, socket, or other adapter may translate an external message into a `Command`, but v0.0.3 itself does not implement any network transport.

## Scope

### Included

- Immutable `Command` and `CommandResult` contracts.
- Command identity through `command_id`.
- Request-flow correlation through `correlation_id`.
- Explicit command `schema_version`.
- ISO-8601 timestamp validation.
- Mapping-based command payloads with immutable command-envelope storage.
- Application `CommandDispatcher`.
- Deterministic result codes:
  - `ok`
  - `invalid_command`
  - `unsupported_schema`
  - `unknown_command`
  - `execution_failed`
- Read-only status and health commands:
  - `agent.get_status`
  - `agent.get_health`
- Handler exception containment at the application boundary.
- Preservation of the v0.0.2 lifecycle and `MT5Port` dependency direction.
- Contract, dispatcher, success/failure and regression-oriented tests.
- Windows CI with Python 3.11.
- Reproducible application-icon generation.
- PyInstaller packaging and frozen-executable verification.
- Unavailable-terminal smoke testing.
- SHA-256 generation for the release artifact.

### Explicitly excluded

- HTTP, Kafka, WebSocket, socket, or other network transport implementations.
- Persistence, deduplication storage, or durable idempotency.
- Authentication and authorization.
- Trading or order execution.
- Position or account management.
- Strategy engine.
- AI/LLM integration.
- Retry and circuit-breaker infrastructure.
- Windows Service deployment.

## Architecture

```text
External System / Future Transport
            |
            v
      Transport Adapter
            |
            v
       Command Contract
            |
            v
    Application Dispatcher
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

The dependency direction remains:

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

The Core and Application layers do not import the concrete MetaTrader5 API for command processing.

## Command Contract

A `Command` contains:

| Field | Purpose |
|---|---|
| `command_id` | Unique command identity within the caller's command space. |
| `command_type` | Application operation identifier. |
| `schema_version` | Contract version used for compatibility checks. |
| `correlation_id` | Correlates the command with a broader request or workflow. |
| `timestamp` | ISO-8601 command creation timestamp. |
| `payload` | Transport-neutral mapping containing operation data. |

`Command` and `CommandResult` are frozen dataclasses. Command payload storage is normalized to an immutable mapping so changing the original input mapping does not mutate the command envelope.

Persistence-backed idempotency is intentionally deferred to a future version.

## Supported Commands

### `agent.get_status`

Returns runtime status information without changing agent state.

### `agent.get_health`

Returns lifecycle-aware health information without changing agent state.

No trading command is introduced in v0.0.3.

## Error Model

The dispatcher converts boundary failures into deterministic `CommandResult.code` values instead of leaking transport-specific or handler-specific exceptions to the caller.

| Code | Meaning |
|---|---|
| `ok` | Handler completed successfully. |
| `invalid_command` | Command envelope failed validation. |
| `unsupported_schema` | Command schema is not supported by the dispatcher. |
| `unknown_command` | No handler is registered for the command type. |
| `execution_failed` | Handler raised an unexpected exception. |

## Testing

The version-level test suite is isolated under `Version 0_0_3/tests` and runs without requiring a live MetaTrader 5 terminal.

CI validates:

1. Dependency installation on Windows.
2. Python 3.11 test execution.
3. PyInstaller packaging.
4. Executable existence.
5. Unavailable-terminal startup behavior.
6. SHA-256 generation.
7. Artifact upload.

## Build Locally on Windows

From the repository root:

```powershell
cd "Version 0_0_3"
python -m pip install -r requirements.txt
python make_icon.py
pyinstaller deployment/Agent.spec --clean --noconfirm
```

Expected artifact:

```text
dist\MT5Agent-v0.0.3.exe
```

The executable is expected to return exit code `1` when started without an available MetaTrader 5 terminal.

## Version Isolation

`Version 0_0_1` and `Version 0_0_2` are treated as closed versioned baselines. v0.0.3 adds its implementation under `Version 0_0_3` and does not modify the previous version directories.

## Release Artifact

Release tag:

```text
v0.0.3
```

Artifact:

```text
MT5Agent-v0.0.3.exe
```

The final SHA-256 must be recorded only after the final Windows CI artifact has been generated and independently verified.

## Next Version Boundary

The natural continuation from v0.0.3 is to design the next contract boundary before introducing external transport or trading behavior. v0.0.4 must begin with repository audit, architecture review, explicit scope/non-goals, contract design, and test strategy rather than assuming that a concrete transport or trading API belongs in the Core.
