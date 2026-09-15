# MT5 Agent v0.0.5 — Release Notes

## Security & Observability Boundary Foundation

`v0.0.5` establishes transport-neutral security and execution-observability boundaries on top of the closed v0.0.4 Application Boundary.

### Included

- `SecurityContext`
- `AuthenticationResult`
- `AuthorizationDecision`
- `Authenticator` / `Authorizer` ports
- Authentication-before-authorization enforcement
- Deterministic authentication and authorization errors
- `ExecutionEvent` and `ExecutionEventType`
- `ObservabilityPort`
- Best-effort, non-fatal observability
- Request/correlation/command identity propagation
- Boundary and failure-path tests
- Windows CI and version-local PyInstaller packaging

### Not Included

No HTTP/REST, Kafka, WebSocket, socket, TLS/mTLS, JWT/OAuth/OIDC, external IAM, persistence, durable idempotency, retry, circuit breaker, trading, strategy engine, AI/LLM, or Windows Service implementation.

### Release Status

- Tag: `v0.0.5`
- Release: published
- Target commit: `8c686e58070f561382c8c2280a1c9ccf8ddcd8de`
- Asset: `MT5Agent-v0.0.5.exe`
- Asset size: `41,316,750` bytes
- Asset SHA-256: `876ca0d8c238598bb47208dee1c998bdb0aed1d95d003609617966ea9b58969d`
- CI artifact: `MT5Agent-v0.0.5`

### Version Closure

The v0.0.5 implementation is merged into `main` and released. The historical `version-0.0.5` branch is intentionally retained for traceability. New development must branch from finalized `main`.

### Next planned boundary

A future version may introduce a concrete transport adapter and concrete production security/telemetry adapters, but only after explicit architecture, contract, dependency-direction, error-model, observability, security, and test-strategy review.
