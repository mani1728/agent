# v0.0.2 Architecture

## Objective

v0.0.2 is the **Agent Runtime & Contract Foundation**. It hardens the lifecycle and dependency boundaries established by v0.0.1 while deliberately avoiding trading and external infrastructure.

## Dependency boundary

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

The core consumes the `MT5Port` protocol. It does not import the concrete `MetaTrader5` integration. The concrete adapter is composed at the application boundary in `agent/main.py`.

This permits deterministic test doubles and future adapters without changing core lifecycle logic.

## Lifecycle state machine

```text
CREATED
   |
   v
STARTING ---- connect failure / exception ----> FAILED
   |
   v
RUNNING
   |
   v
STOPPING ---- disconnect failure / exception -> FAILED
   |
   v
STOPPED
```

Rules:

- `start()` from `RUNNING` is idempotent and does not reconnect.
- `start()` may restart from `STOPPED` or `FAILED`.
- `start()` during `STARTING` or `STOPPING` reports `lifecycle_busy`.
- `stop()` is safe before the first start and after a failed start.
- A disconnect failure leaves the runtime in `FAILED` so the failure is observable.

## Contracts

### `MT5Port`

Required operations:

- `connect() -> bool`
- `disconnect() -> bool`
- `is_connected() -> bool`

The protocol is runtime-checkable and is the only terminal-facing contract consumed by the core.

### `Status`

Immutable operation result containing:

- `ok`: success/failure boolean.
- `message`: human-readable result.
- `code`: machine-readable result code.

### `HealthStatus`

Immutable health result containing:

- `ok`: health boolean.
- `state`: current lifecycle state.
- `message`: human-readable health information.

### `AgentConfig`

Immutable, strongly typed application identity/version boundary. It intentionally remains small in v0.0.2; configuration loading, validation frameworks, and hot reload are deferred.

## Error boundary

Integration exceptions are contained at the runtime boundary:

- `connect()` exception → `connection_failed` and `FAILED` state.
- `disconnect()` exception → `disconnect_failed` and `FAILED` state.
- health probe exception → unhealthy health result while preserving lifecycle state.

Exceptions are logged through the injected standard-library logger; raw integration exceptions do not escape the public lifecycle/health contract.

## Test strategy

Tests use a deterministic fake implementation of `MT5Port`; a real MetaTrader 5 terminal is not required.

Coverage includes:

- Port runtime contract compatibility.
- Contract immutability and configuration defaults.
- Successful and failed startup.
- Startup adapter exception.
- Idempotent startup.
- Safe and repeated stop.
- Disconnect failure and exception.
- Health before start, healthy runtime, disconnected terminal, and health-probe exception.
- Restart after stop and after connection failure.

## Packaging and CI boundary

The version has an independent PyInstaller specification and Windows build script. The dedicated workflow validates the Python test suite, generates the icon, builds `MT5Agent-v0.0.2.exe`, verifies its existence, executes the unavailable-terminal smoke test, and uploads the executable as a CI artifact.

The verified build artifact SHA-256 is:

```text
eb18b139572670ab98995d6ce34681c17ce9516011e65c000b0f9934fbc92ad0
```

## Non-goals

No trading, order execution, position/account management, network transport, persistence, authentication/authorization, Windows Service hosting, strategy engine, retry/circuit-breaker infrastructure, or AI integration is introduced in v0.0.2.
