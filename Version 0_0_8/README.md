# MT5 Agent — v0.0.8

## Agent Hosting & Graceful Shutdown Foundation

v0.0.8 adds the application hosting boundary required to run the existing HTTP transport as a long-lived process while preserving Core isolation and all v0.0.7 request/security contracts.

### Architecture

```text
Process / OS
    ↓
Process Signal Adapter [Infrastructure]
    ↓
HostingPort
    ↑
HTTPServerHost [Infrastructure]
    ↑
ApplicationHost [Application]
   / \
  ↓   ↓
Agent HTTP Transport
  ↓       ↓
MT5Port ApplicationBoundary
```

`ApplicationHost` coordinates ordering only: Agent start → blocking serve → Agent stop. It does not import HTTP server, socket, signal, Windows Service, or MetaTrader5 APIs.

### Contracts

- `AgentLifecyclePort.start() -> Status`
- `AgentLifecyclePort.stop() -> Status`
- `HostingPort.serve() -> None`
- `HostingPort.shutdown() -> None`

Contracts are additive, transport-neutral, and structurally implemented through dependency injection.

### Scope

Included: hosting contracts, runtime coordinator, concrete standard-library HTTP server host, graceful process shutdown adapter, lifecycle/error ordering, hosting tests, architecture isolation tests, Windows CI/CD, PyInstaller packaging, repository `.gitignore` hygiene, and v0.0.7 documentation closure.

Excluded: Trading, Orders/Positions, Persistence, Idempotency, Retry, Circuit Breaker, TLS/mTLS, JWT/OAuth/OIDC, Secrets Management, Kafka, WebSocket, Windows Service, AI/LLM, and Strategy Engine.

### Compatibility

`POST /command`, request/command contracts, Validation → Authentication → Authorization → Dispatch ordering, identity propagation, and best-effort request observability remain unchanged.

### Development state

Development occurs only on `version-0.0.8`. No v0.0.8 tag or release is created before explicit owner approval after PR review.
