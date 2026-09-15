# MT5 Agent — Version History

This document records finalized MT5 Agent baselines. Released version directories are historical references; future development starts from finalized `main`.

## v0.0.1 — Initial Foundation
Initial MT5 integration, lifecycle, adapter boundary, tests without live MT5, Windows packaging, CI and release artifact.

## v0.0.2 — Agent Runtime & Contract Foundation
Explicit lifecycle state machine, `MT5Port`, dependency injection, immutable runtime contracts, structured errors, health contract, logging boundary, regression tests and reproducible Windows packaging.

## v0.0.3 — Agent Command Foundation
Immutable `Command` / `CommandResult`, command/correlation identity, schema versioning, validation, `CommandDispatcher`, deterministic result codes and read-only status/health commands.

## v0.0.4 — Agent Transport Boundary & Execution Context Foundation
Transport-neutral application boundary and execution context for future concrete transports.

## v0.0.5 — Security & Observability Boundary Foundation
Security contracts and ports, mandatory Authentication-before-Authorization ordering, deterministic security failures, execution events, identity propagation and best-effort observability.

## v0.0.6 — Concrete HTTP Transport Boundary Foundation
Standard-library HTTP/JSON `POST /command` adapter, deterministic transport/error mapping, identity propagation, failure isolation, Windows CI/CD and executable packaging.

## v0.0.7 — Agent Configuration & Composition Root Foundation

Introduced formal startup configuration and a composition boundary while preserving Core independence.

- immutable `AgentConfig` / `HTTPTransportConfig`
- deterministic `ConfigurationError`
- `ConfigurationProvider` protocol and environment adapter
- explicit composition root
- configurable HTTP host, port and request-body limit
- Windows CI/CD, PyInstaller packaging and smoke verification

Release state:

- PR: `#39` — merged
- merge commit: `a93812eee78692692982b831bc2a920ab6d104f6`
- finalized main/tag commit: `487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d`
- tag: `v0.0.7`
- GitHub Release: published
- artifact: `MT5Agent-v0.0.7.exe`
- canonical SHA-256: `38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`
- final Actions artifact digest: `sha256:d26b0432548a0f44962a75ff8288926b107f0cb0dc27d31c8a0e72f48857e46e`

Historical note: PR #39 references checksum/digest values from an earlier CI artifact. Those values remain part of the PR history and are not canonical for the published release asset.

Security ordering remains Validation → Authentication → Authorization → Dispatch. Trading/orders/positions, strategy engine, AI/LLM, persistence, JWT/OAuth/OIDC, TLS/mTLS, Kafka/WebSocket, retry/circuit breaker and Windows Service remained outside scope.

## Current baseline

`main@487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d` is the finalized v0.0.7 baseline. v0.0.8 development proceeds only on `version-0.0.8` until explicit merge approval.
