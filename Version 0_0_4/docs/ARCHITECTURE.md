# v0.0.4 Architecture — Transport Boundary Foundation

## Boundary

```text
External System
      |
      v
Future Transport Adapter
      |
      v
Transport Contract
      |
      v
Execution Context
      |
      v
Command Contract
      |
      v
Application Boundary
      |
      v
Command Dispatcher
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

- **Transport Contract:** defines transport-neutral ingress and egress envelopes without implementing a network protocol.
- **Execution Context:** carries `request_id`, `correlation_id`, and immutable metadata across the application boundary.
- **Command Contract:** retains v0.0.3 command semantics and validation.
- **Application Boundary:** accepts a `TransportRequest`, delegates the contained command to the dispatcher, and returns a `TransportResponse`.
- **Dispatcher:** resolves command types to application handlers and returns deterministic `CommandResult` values.
- **Agent:** retains the established lifecycle boundary.
- **MT5Port:** remains the only Core-facing terminal integration abstraction.
- **Adapter:** contains the concrete MetaTrader 5 dependency.

## Dependency Rule

Core and application code must not import transport implementations, persistence frameworks, authentication frameworks, PyInstaller, or concrete external API SDKs.

Future transport adapters may depend on the `ApplicationPort` contract. The application must not depend on those adapters.

## Identity Invariants

The application boundary preserves three identifiers:

- `request_id` identifies one ingress request.
- `command_id` identifies the command being executed.
- `correlation_id` links the request and command to a broader workflow.

A `TransportRequest` is rejected when its context correlation identifier does not match the command correlation identifier.

## Error Model

Transport-neutral contract errors are represented as deterministic response codes at the application boundary:

- `invalid_request` — request envelope/context is invalid.
- Existing dispatcher codes remain unchanged: `ok`, `invalid_command`, `unsupported_schema`, `unknown_command`, `execution_failed`.

No transport-specific status code or exception is introduced.

## Security

Authentication and authorization remain outside this version. The transport contract does not establish caller trust. A future security boundary must establish identity and authorization before a transport adapter admits commands to the application port.

## Lifecycle

The v0.0.2 lifecycle remains unchanged:

`CREATED → STARTING → RUNNING → STOPPING → STOPPED`, with failure transitions to `FAILED` from `STARTING` and `STOPPING`.
