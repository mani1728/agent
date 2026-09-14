# MT5 Agent v0.0.5 — Release Notes

## Security & Observability Boundary Foundation

v0.0.5 establishes transport-neutral security and execution-observability boundaries on top of the closed v0.0.4 Application Boundary.

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

### Next planned boundary

A future concrete transport can adapt its protocol to `ApplicationPort` without changing the application contracts. Production authentication, authorization policy, and telemetry backends can likewise be introduced as adapters.
