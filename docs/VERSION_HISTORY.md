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
- finalized main/tag commit: `487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d`
- tag: `v0.0.7`
- GitHub Release: published
- artifact: `MT5Agent-v0.0.7.exe`
- canonical SHA-256: `38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`

Historical note: PR #39 references checksum/digest values from an earlier CI artifact. Those values remain part of PR history and are not canonical for the published release asset.

## v0.0.8 — Agent Hosting & Graceful Shutdown Foundation
Introduced the application hosting lifecycle needed to operate the existing HTTP transport as a long-running process without coupling Core to HTTP server or OS/process infrastructure.

- additive `AgentLifecyclePort` and `HostingPort`
- `ApplicationHost` lifecycle coordinator
- standard-library `HTTPServerHost`
- graceful process signal shutdown adapter
- deterministic startup/hosting/shutdown error precedence and lifecycle exception containment
- resource cleanup and deadlock-oriented lifecycle tests
- architecture-isolation and regression tests
- Windows CI/CD, PyInstaller packaging and executable smoke verification
- repository `.gitignore` policy modernization

Release state:
- PR: `#40` — owner approved for merge
- final reviewed implementation commit: `ec0585624c4defd30c8d368be8756a33e2d3caa5`
- tag: `v0.0.8` → `ec0585624c4defd30c8d368be8756a33e2d3caa5`
- GitHub Release: `MT5 Agent v0.0.8` — published
- artifact: `MT5Agent-v0.0.8.exe`
- canonical SHA-256: `e04f497bf3a893aa7bf5dec24bcc19d77930a50e42716dc7b1e5ace7d4641266`
- final verification workflow: `35013801830` — passed

Manual Windows/MT5 acceptance observed controlled shutdown and `INFO:agent.main:Application host stopped.` after the operator closed MetaTrader 5 and issued Ctrl+C.

Security ordering remains Validation → Authentication → Authorization → Dispatch. Request observability remains best-effort. Trading/orders/positions, strategy engine, AI/LLM, persistence, idempotency, retry/circuit breaker, TLS/mTLS, JWT/OAuth/OIDC, Kafka/WebSocket and Windows Service remain outside scope.

## Current baseline

v0.0.8 is the approved release baseline. After PR #40 is merged, future version development must branch from the resulting stable `main` baseline. The published `v0.0.8` tag and release must not be rewritten.
