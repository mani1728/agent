# Changelog — v0.0.8

## Added

- `AgentLifecyclePort` for application-level lifecycle coordination.
- `HostingPort` for transport-neutral blocking serving and graceful shutdown.
- `ApplicationHost` runtime coordinator.
- `HTTPServerHost` standard-library infrastructure adapter with deferred bind and deterministic socket cleanup.
- process-signal adapter isolated in infrastructure.
- lifecycle, hosting integration, and architecture-isolation tests.
- Windows v0.0.8 CI/CD and `MT5Agent-v0.0.8.exe` packaging definition.

## Changed

- executable runtime now enters the hosting coordinator after valid configuration instead of dispatching startup status and immediately stopping.
- composition root now wires hosting explicitly and supports injected hosting for tests.
- root `.gitignore` changed from historical whitelist behavior to generated/local-artifact deny rules.
- v0.0.7 documentation reconciled with the already-published tag/release state without modifying release history or assets.

## Preserved

- Validation → Authentication → Authorization → Dispatch ordering.
- request/correlation/command identity propagation.
- best-effort request observability.
- existing transport/application/command/MT5 boundaries.

## Not included

Trading, Orders/Positions, Persistence, Idempotency, Retry, Circuit Breaker, TLS/mTLS, JWT/OAuth/OIDC, Secrets Management, Kafka, WebSocket, Windows Service, AI/LLM, and Strategy Engine.
