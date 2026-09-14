# Changelog

## 0.0.4 — Agent Transport Boundary & Execution Context Foundation

### Added

- Immutable `ExecutionContext`, `TransportRequest`, and `TransportResponse` contracts.
- `ApplicationPort` for future transport adapters.
- `ApplicationBoundary` over the existing command dispatcher.
- Request, command, and correlation identity preservation.
- Correlation consistency validation at the application ingress boundary.
- Deterministic `invalid_request` error handling.
- Transport/application contract, error-model, and test-strategy documentation.
- Regression tests covering successful and invalid application requests.
- Windows CI, PyInstaller packaging, executable verification, unavailable-terminal smoke testing, and SHA-256 generation.

### Deliberately excluded

- HTTP, REST, Kafka, WebSocket, socket, or other network transport implementations.
- Authentication and authorization.
- Persistence or durable idempotency.
- Retry and circuit-breaker infrastructure.
- Trading, order execution, position management, or account management.
- Strategy engine.
- AI/LLM integration.
- Windows Service deployment.
