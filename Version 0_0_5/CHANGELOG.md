# Changelog

## 0.0.5 — Security & Observability Boundary Foundation

### Added

- Immutable security context and authentication/authorization outcome contracts.
- Authentication and authorization ports.
- Security enforcement at the application ingress boundary.
- Deterministic security failure codes.
- Immutable execution event contract and event types.
- Observability port with non-fatal telemetry behavior.
- Correlation/request/command identity propagation through execution events.
- Boundary, security, observability, and failure-path tests.
- Windows CI and PyInstaller packaging.

### Deliberately excluded

- Concrete network transport.
- TLS/mTLS.
- JWT/OAuth/OIDC/external IAM.
- Persistence and durable idempotency.
- Retry and circuit breaker.
- Trading and order execution.
- Strategy engine.
- AI/LLM.
- Windows Service.
