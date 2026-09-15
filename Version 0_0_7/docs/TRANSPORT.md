# HTTP Transport

## Endpoint

`POST /command`

Maximum accepted request body: 1 MiB.

The adapter accepts UTF-8 JSON with `request_id`, `correlation_id`, and `command`. The command contains `command_id`, `command_type`, `schema_version`, `timestamp`, and `payload`.

## Lifecycle

```text
HTTP request
  ↓
JSON parse
  ↓
Transport validation
  ↓
TransportRequest
  ↓
ApplicationPort.handle()
  ↓
TransportResponse
  ↓
JSON serialization
  ↓
HTTP response
```

The adapter does not dispatch commands directly and has no access to MT5 internals.

## Lifecycle behavior

`create_server()` returns a standard-library `ThreadingHTTPServer`. The caller owns server startup and shutdown. No background service or deployment lifecycle is introduced by this version.
