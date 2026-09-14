# v0.0.5 Architecture

## Boundary

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
Security Boundary
      |
      v
ApplicationBoundary -----> ObservabilityPort
      |
      v
CommandDispatcher
      |
      v
Agent Runtime
      |
      v
MT5Port <----- MT5Adapter -----> MetaTrader 5
```

Security and observability are contract/port concerns. Concrete authentication, authorization policy, and telemetry backends are infrastructure adapters and are not part of v0.0.5.

## Security ordering

```text
validate request
      ↓
authenticate
      ↓
authorize
      ↓
dispatch command
```

Invalid requests never reach authentication. Authentication failures never reach authorization. Authorization denial never reaches command dispatch.

## Observability

Execution events preserve `request_id`, `correlation_id`, and `command_id`. Event recording is best-effort and must not alter successful application execution.

## Dependency rules

The application depends on contracts and ports only. No network framework, IAM SDK, telemetry SDK, persistence layer, or MetaTrader5 package is imported by the new security/observability contracts.
