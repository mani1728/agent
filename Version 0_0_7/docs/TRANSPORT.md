# HTTP Transport — v0.0.7

Endpoint remains `POST /command`.

The request-body limit is supplied to `HTTPTransportAdapter` by the composition root from `HTTPTransportConfig.max_request_bytes`; default is 1 MiB. The adapter does not read environment variables itself.

The adapter accepts UTF-8 JSON with `request_id`, `correlation_id`, and `command`. Existing transport validation, application handoff, identity propagation, error mapping, and serialization behavior remain unchanged.

```text
HTTP request
  ↓
JSON parse / transport validation
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

`create_server()` still returns a standard-library `ThreadingHTTPServer`; caller owns server startup/shutdown. No Windows Service or background deployment lifecycle is introduced.
