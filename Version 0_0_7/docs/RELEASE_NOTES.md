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

### Artifact

`MT5Agent-v0.0.7.exe`

SHA-256:

`cd62e24c5eb37b39ecb9c6579e060345fca21b525d4d0e9385e06d3069e0f1da`

GitHub Actions artifact digest:

`sha256:388756f977e79cd3952a8505b4235a76e0794479214353cfdde0f57f7e97af39`

CI test/build/package/smoke verification passed. Tag and GitHub Release publication are the owner handoff after merge.