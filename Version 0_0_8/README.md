# MT5 Agent — v0.0.7

## Agent Configuration & Composition Root Foundation

v0.0.7 formalizes deterministic startup configuration and the application composition root while preserving the v0.0.6 HTTP, security, observability, command, runtime, and MT5 boundaries.

### Architecture

```text
Environment / Process Inputs
          ↓
Configuration Adapter
          ↓
Immutable AgentConfig
          ↓
Composition Root
   ┌──────┼────────┐
 MT5Port Security Observability
   └──────┼────────┘
          ↓
ApplicationBoundary
          ↓
HTTPTransportAdapter
```

Core does not read environment variables and does not depend on HTTP, configuration infrastructure, or `MetaTrader5`. Concrete dependencies are assembled only at the composition root.

### Configuration

Supported process environment inputs:

- `MT5_AGENT_HTTP_HOST` — default `127.0.0.1`
- `MT5_AGENT_HTTP_PORT` — default `8080`, valid range `1..65535`
- `MT5_AGENT_HTTP_MAX_REQUEST_BYTES` — default `1048576`, must be positive

Invalid startup configuration fails deterministically before request processing. Configuration failures are startup/infrastructure failures and are not exposed through HTTP request error responses.

### Scope

Included: immutable configuration contracts, configuration validation, environment configuration adapter, explicit composition root, configurable HTTP request-body limit, tests, Windows CI, PyInstaller packaging, executable verification, smoke tests, and release documentation.

Excluded: trading, order execution, AI/LLM, persistence, secrets storage, JWT/OAuth/OIDC, TLS/mTLS, production IAM, remote configuration, YAML/TOML frameworks, telemetry backends, retry/circuit-breaker infrastructure, WebSocket/Kafka, and Windows Service deployment.

### Release state

Implementation is prepared on `version-0.0.7` for review. Merge, tag, release, release checksum verification, and version closure remain pending explicit approval.
