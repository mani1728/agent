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

### Release

- Merged into `main` at `8c686e58070f561382c8c2280a1c9ccf8ddcd8de`.
- Tagged and published as `v0.0.5`.
- Published asset: `MT5Agent-v0.0.5.exe`.
- Published asset SHA-256: `876ca0d8c238598bb47208dee1c998bdb0aed1d95d003609617966ea9b58969d`.
- Historical `version-0.0.5` branch retained for traceability.

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
