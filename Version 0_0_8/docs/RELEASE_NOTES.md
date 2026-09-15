# Release Notes — v0.0.8

## Agent Hosting & Graceful Shutdown Foundation

v0.0.8 closes the gap between the existing HTTP transport/composition foundation and a long-running application process.

### Added

- transport-neutral `AgentLifecyclePort` and `HostingPort` protocols;
- `ApplicationHost` coordinator for deterministic Agent start/serve/stop ordering;
- `HTTPServerHost` infrastructure adapter for standard-library server lifecycle ownership;
- graceful SIGINT/SIGTERM translation isolated in infrastructure;
- deferred HTTP bind so bind/serve failures are handled as hosting lifecycle failures;
- lifecycle, HTTP hosting integration, and architecture-isolation tests;
- v0.0.8 Windows CI/CD and executable packaging.

### Preserved

- `POST /command` behavior and transport contracts;
- Validation → Authentication → Authorization → Dispatch;
- request/correlation/command identity propagation;
- best-effort request observability;
- Core independence from HTTP, OS/process APIs, and concrete MetaTrader5 infrastructure.

### Repository maintenance

The root `.gitignore` now defaults to tracking source/version directories and denies generated/local artifacts instead of historically whitelisting only early version directories. v0.0.7 documentation is reconciled with its already-published tag/release state; no v0.0.7 tag, asset, or history is modified.

### Explicit non-goals

Trading, Orders/Positions, Persistence, Idempotency, Retry, Circuit Breaker, TLS/mTLS, JWT/OAuth/OIDC, Secrets Management, Kafka, WebSocket, Windows Service, AI/LLM, and Strategy Engine.

No v0.0.8 tag or GitHub Release is created as part of the pre-merge development phase.
