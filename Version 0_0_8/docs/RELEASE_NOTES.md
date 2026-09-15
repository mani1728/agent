# Release Notes — v0.0.7

## Agent Configuration & Composition Root Foundation

v0.0.7 formalizes startup configuration and concrete dependency assembly without introducing infrastructure coupling into Agent Core.

### Highlights

- Immutable typed `AgentConfig` / `HTTPConfig` startup contracts
- Deterministic `ConfigurationError`
- Replaceable `ConfigurationProvider` protocol
- Environment-backed configuration adapter
- Explicit composition root for MT5, application, security, observability, and HTTP wiring
- Configuration-driven HTTP host, port, and maximum request-body size
- Deterministic startup failure for malformed configuration
- Regression coverage for architecture boundaries and existing HTTP behavior
- Windows CI/CD, PyInstaller executable verification, smoke tests, and SHA-256 generation

### Compatibility and boundaries

Validation → Authentication → Authorization → Dispatch ordering is unchanged. Observability remains best-effort and injectable. Request, correlation, and command identity propagation remains unchanged. Core does not read environment variables and does not depend on HTTP, security infrastructure, observability backends, or the `MetaTrader5` Python package.

### Non-goals

No trading/order execution, position management, strategy engine, AI/LLM integration, persistence, JWT/OAuth/OIDC, TLS/mTLS, external IAM, secrets manager, remote configuration, YAML/TOML framework, Kafka/WebSocket transport, retry/circuit breaker, telemetry backend, or Windows Service is introduced.

### Merge state

PR `#39` was merged into `main` at `a93812eee78692692982b831bc2a920ab6d104f6`.

### Release artifact

`MT5Agent-v0.0.7.exe`

SHA-256:

`38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`

GitHub Actions artifact digest:

`sha256:d26b0432548a0f44962a75ff8288926b107f0cb0dc27d31c8a0e72f48857e46e`

Tests, packaging, executable verification and both smoke-test paths passed. The owner can now create tag `v0.0.7`, publish the GitHub Release, and attach the verified executable.