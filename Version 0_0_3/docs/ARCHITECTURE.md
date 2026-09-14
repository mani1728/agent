# v0.0.3 Architecture

## Boundary

```text
External System / Future Transport
            |
            v
      Transport Message
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

## Responsibilities

- **Command contract:** defines immutable application semantics.
- **Validation:** rejects malformed commands before handler execution.
- **Dispatcher:** resolves a command type to an application handler and returns a transport-neutral result.
- **Agent:** retains the v0.0.2 lifecycle boundary.
- **MT5Port:** remains the only Core-facing terminal integration abstraction.
- **Adapter:** contains the concrete MetaTrader 5 dependency.

## Dependency Rule

Core and application code must not import transport implementations, persistence frameworks, authentication frameworks, PyInstaller, or concrete external API SDKs.

## Lifecycle

The v0.0.2 lifecycle state machine is preserved unchanged:

`CREATED → STARTING → RUNNING → STOPPING → STOPPED`, with failure transitions to `FAILED` from `STARTING` and `STOPPING`.

## Security

Authentication and authorization are not implemented. No trust boundary is silently assumed at the command dispatcher; a future transport/security layer must establish caller identity and authorization before commands are admitted.
