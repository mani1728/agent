# v0.0.6 Architecture

## Dependency direction

```text
External Client
      ↓
Concrete HTTP Adapter
      ↓
Transport Contract
      ↓
ApplicationPort
      ↓
ApplicationBoundary
      ↓
CommandDispatcher
      ↓
Agent Runtime
      ↓
MT5Port
      ↓
MT5Adapter
      ↓
MetaTrader 5
```

The HTTP adapter is infrastructure. No application/core module imports HTTP server classes, HTTP request objects, or framework-specific logic.

## Concrete transport

The implementation uses Python's standard-library `http.server`. This keeps the first concrete adapter dependency-light while proving the replaceable boundary. `POST /command` is the only application endpoint in scope.

## Security invariant

`ApplicationBoundary` remains responsible for `validation → authentication → authorization → dispatch`. The HTTP adapter only constructs `TransportRequest` and calls `ApplicationPort`.

## Observability invariant

`request_id`, `correlation_id`, and `command_id` are propagated through the existing transport/application contracts. Observer failures remain non-fatal.
