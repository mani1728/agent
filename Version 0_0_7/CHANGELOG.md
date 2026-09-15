# Changelog — v0.0.7

## 0.0.7

- Added immutable `AgentConfig` and `HTTPTransportConfig` startup contracts.
- Added deterministic `ConfigurationError` validation.
- Added `ConfigurationProvider` protocol.
- Added environment-based configuration infrastructure adapter.
- Added explicit application composition root for MT5, security, observability, application, and HTTP dependencies.
- Made the HTTP request-body limit configurable without coupling Core to HTTP configuration.
- Added configuration, composition, boundary, and regression tests.
- Added Windows CI/CD, PyInstaller packaging for `MT5Agent-v0.0.7.exe`, executable verification, smoke tests, and SHA-256 generation.

## Deliberately excluded

Trading, orders, positions, AI/LLM, persistence, secrets management, JWT/OAuth/OIDC, TLS/mTLS, external IAM, remote configuration, YAML/TOML frameworks, telemetry backends, retries, circuit breakers, Kafka/WebSocket, Windows Service, and production deployment infrastructure.
