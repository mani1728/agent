# Architecture — v0.0.8

## Agent Hosting & Graceful Shutdown Foundation

```text
Process / OS
      ↓
Process Signal Adapter [Infrastructure]
      ↓
HostingPort ←──────────── HTTPServerHost [Infrastructure]
      ↑                         ↑
ApplicationHost [Application]   │
      │                         │
      ├── AgentLifecyclePort    │
      │        ↓                │
      │       Agent             │
      │        ↓                │
      │      MT5Port            │
      │                         │
      └──────────────── HTTPTransportAdapter
                                ↓
                       ApplicationBoundary
                                ↓
                         CommandDispatcher
```

### Ownership

`ApplicationHost` owns lifecycle ordering, not concrete server mechanics. `HTTPServerHost` owns `ThreadingHTTPServer` creation/serving/closure. Process signals are translated to `HostingPort.shutdown()` only by infrastructure. The composition root is the only concrete wiring location.

### Lifecycle

```text
agent.start()
   ↓ success
hosting.serve()  [blocking]
   ↓ normal return / graceful shutdown
agent.stop()
```

If Agent startup fails, serving does not begin. If hosting fails after successful Agent startup, Agent cleanup is still attempted. If hosting and cleanup both fail, `hosting_failed` remains the primary result and cleanup failure is logged. A cleanup-only failure returns `agent_stop_failed`.

### Isolation invariants

- Core and Contracts do not import `http.server`, process signals, sockets, or `MetaTrader5` infrastructure.
- ApplicationHost is transport/process neutral.
- HTTP server and process signal APIs remain infrastructure concerns.
- Request processing continues through ApplicationBoundary unchanged.
- No second lifecycle state machine is introduced.

### Security and observability

Security ordering remains Validation → Authentication → Authorization → Dispatch. Hosting is outside the request path. Existing request observability remains injectable and best-effort; v0.0.8 does not expand `ExecutionEvent` with process lifecycle events.
