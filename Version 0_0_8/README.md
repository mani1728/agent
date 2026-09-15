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

`ApplicationHost` coordinates lifecycle ordering: Agent start → blocking serve → Agent stop. It does not import HTTP server, socket, signal, Windows Service, or MetaTrader5 APIs.

### Contracts

- `AgentLifecyclePort.start() -> Status`
- `AgentLifecyclePort.stop() -> Status`
- `HostingPort.serve() -> None`
- `HostingPort.shutdown() -> None`

Contracts are additive, transport-neutral, and structurally implemented through dependency injection.

### Scope

Included: hosting contracts, runtime coordinator, concrete standard-library HTTP server host, graceful process shutdown adapter, deterministic lifecycle/error precedence and exception containment, hosting tests, architecture isolation tests, Windows CI/CD, PyInstaller packaging, repository `.gitignore` hygiene, and v0.0.7 documentation closure.

Excluded: Trading, Orders/Positions, Persistence, Idempotency, Retry, Circuit Breaker, TLS/mTLS, JWT/OAuth/OIDC, Secrets Management, Kafka, WebSocket, Windows Service, AI/LLM, and Strategy Engine.

### Compatibility

`POST /command`, request/command contracts, Validation → Authentication → Authorization → Dispatch ordering, identity propagation, and best-effort request observability remain unchanged.

### Verification and release state

Final verification workflow `35013801830` passed tests, Windows build, executable verification, unavailable-MT5 and invalid-configuration smoke tests, checksum generation, and artifact upload.

The owner performed a Windows/MT5 acceptance run and observed controlled shutdown with `INFO:agent.main:Application host stopped.`.

- PR: `#40`
- final reviewed implementation commit: `ec0585624c4defd30c8d368be8756a33e2d3caa5`
- tag: `v0.0.8` → `ec0585624c4defd30c8d368be8756a33e2d3caa5`
- GitHub Release: `MT5 Agent v0.0.8` — published
- release artifact: `MT5Agent-v0.0.8.exe`
- canonical SHA-256: `e04f497bf3a893aa7bf5dec24bcc19d77930a50e42716dc7b1e5ace7d4641266`

The version is approved for merge to `main`. The published tag/release are historical release records and must not be rewritten.
