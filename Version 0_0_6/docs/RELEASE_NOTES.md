# MT5 Agent v0.0.6

## Concrete Transport Boundary Foundation

v0.0.6 introduces the first concrete HTTP/JSON transport adapter while preserving the transport-neutral application boundary from v0.0.5.

### Included

- `POST /command` HTTP/JSON adapter
- transport request parsing and validation
- request/correlation/command identity propagation
- deterministic application-to-HTTP error mapping
- security ordering preservation
- observer failure isolation
- Windows CI and PyInstaller packaging

### Not included

Trading, order execution, AI/LLM, Kafka, WebSocket, JWT/OAuth/OIDC, TLS/mTLS, external IAM, persistence, retries, circuit breakers, Windows Service, and production deployment infrastructure.
