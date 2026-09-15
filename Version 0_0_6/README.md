# MT5 Agent — v0.0.6

## Concrete Transport Boundary Foundation

v0.0.6 adds the first concrete HTTP/JSON transport adapter on top of the transport-neutral contracts and `ApplicationPort` established in v0.0.5.

### Architecture

```text
External Client
      ↓
HTTP/JSON Adapter
      ↓
Transport Contract
      ↓
ApplicationPort
      ↓
Validation → Authentication → Authorization → Dispatch
      ↓
Agent Runtime
      ↓
MT5Port → MT5Adapter → MetaTrader 5
```

HTTP and the Python standard-library HTTP server exist only in the adapter layer. Core/application contracts remain transport-neutral.

### Endpoint

`POST /command`

JSON request envelope:

```json
{
  "request_id": "req-1",
  "correlation_id": "corr-1",
  "command": {
    "command_id": "cmd-1",
    "command_type": "agent.get_status",
    "schema_version": "1",
    "correlation_id": "corr-1",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "payload": {}
  }
}
```

The response preserves `request_id`, `correlation_id`, and `command_id`.

### Scope

Included: HTTP/JSON parsing and serialization, deterministic transport/application error mapping, security-order preservation, identity propagation, failure isolation, tests, Windows CI, and PyInstaller packaging.

Excluded: trading, AI/LLM, Kafka, WebSocket, JWT/OAuth/OIDC, TLS/mTLS, external IAM, persistence, retries, circuit breakers, production deployment, and broker business logic.
