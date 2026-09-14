# v0.0.2 Architecture

## Objective

v0.0.2 hardens the runtime foundation established by v0.0.1. The core owns lifecycle state and depends on the `MT5Port` protocol rather than the concrete terminal integration.

## Boundary

```text
Application entry point
        |
        v
      Agent  ------------------> Lifecycle / Status / Health
        |
        v
     MT5Port <---------------- MT5Adapter
                                  |
                                  v
                            MetaTrader 5
```

The dependency direction is intentional: the core consumes a protocol; the adapter implements it.

## Lifecycle states

`CREATED -> STARTING -> RUNNING -> STOPPING -> STOPPED`

A failed connection moves the agent to `FAILED`. A failed disconnect also moves it to `FAILED`. A stopped or failed agent can be started again.

`start()` is idempotent while `RUNNING`; it does not reconnect the terminal. `stop()` is safe before a first start and after a failed start.

## Contracts

- `MT5Port`: `connect()`, `disconnect()`, and `is_connected()`.
- `Status`: immutable operation result with `ok`, human-readable `message`, and machine-readable `code`.
- `HealthStatus`: immutable health result carrying `ok`, lifecycle `state`, and message.
- `AgentConfig`: typed configuration boundary for application identity/version.

## Error boundary

The adapter and runtime probe catch integration exceptions and convert them to deterministic failure behavior. The core never imports terminal APIs directly for business behavior.

## Testing strategy

Unit tests inject a deterministic fake adapter. They cover success/failure, invalid runtime conditions, idempotent start, safe stop, health transitions, adapter exceptions, and restart after stop.

## Non-goals

No trading, order execution, transport, persistence, security/authentication, service hosting, or AI integration is introduced in this version.
