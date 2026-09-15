# Changelog — v0.0.6

## 0.0.6

- Added a concrete HTTP/JSON transport adapter.
- Preserved the transport-neutral `ApplicationPort` boundary.
- Added deterministic HTTP mapping for validation, authentication, authorization, application, and transport failures.
- Preserved request/correlation/command identity propagation.
- Added transport, security-ordering, application-integration, and failure-isolation tests.
- Added Windows CI, PyInstaller packaging, executable verification, smoke testing, and SHA-256 generation.

## Deliberately excluded

Trading, order execution, AI/LLM, Kafka, WebSocket, JWT/OAuth/OIDC, TLS/mTLS, external IAM, persistence, distributed idempotency, retry, circuit breaker, Windows Service, and production deployment infrastructure.
