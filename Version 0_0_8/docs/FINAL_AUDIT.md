# Final Audit — v0.0.8

Release-candidate status: OWNER-ACCEPTED — READY FOR MERGE.

Baseline main commit before merge: `487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d`.
Development branch: `version-0.0.8`.
Final reviewed implementation commit before closure docs: `ec0585624c4defd30c8d368be8756a33e2d3caa5`.

Implemented scope: hosting contracts, ApplicationHost coordinator, HTTP server hosting adapter, graceful shutdown, deterministic lifecycle failure handling, lifecycle tests, architecture isolation tests, Windows CI/CD, packaging, repository ignore-policy cleanup, and v0.0.7 documentation closure.

Final verification workflow `35013801830` passed the Windows test suite, build, executable verification, unavailable-MT5 smoke test, invalid-configuration smoke test, SHA-256 generation, and artifact upload.

Release artifact: `MT5Agent-v0.0.8.exe`.
Canonical SHA-256: `e04f497bf3a893aa7bf5dec24bcc19d77930a50e42716dc7b1e5ace7d4641266`.

Manual Windows/MT5 acceptance observed controlled shutdown and the process reported `INFO:agent.main:Application host stopped.` after the operator closed MetaTrader 5 and used Ctrl+C.

Tag `v0.0.8` was published by the owner and points to `ec0585624c4defd30c8d368be8756a33e2d3caa5`. GitHub Release `MT5 Agent v0.0.8` is published with `MT5Agent-v0.0.8.exe`; the release asset digest matches the canonical SHA-256 above.

Trading, Orders/Positions, Persistence, Idempotency, Retry, Circuit Breaker, TLS/mTLS, JWT/OAuth/OIDC, Secrets Management, Kafka, WebSocket, Windows Service, AI/LLM, and Strategy Engine remain outside scope.

Security ordering remains Validation → Authentication → Authorization → Dispatch. Request observability remains best-effort. Core remains isolated from HTTP server, process APIs, and concrete MetaTrader5 infrastructure.

PR #40 is approved for merge into `main`. No tag rewrite, history rewrite, or force push is permitted.
