# Changelog

## 0.0.3 — Agent Command Foundation

### Added

- Transport-neutral immutable command contracts.
- Command validation and schema version checking.
- Correlation and command identity propagation.
- Application command dispatcher.
- Deterministic application error/result codes.
- Read-only status and health commands.
- Command contract and dispatcher failure tests.
- CI packaging, executable verification, smoke testing and SHA-256 generation.

### Deliberately excluded

- Network transport implementations.
- Persistence.
- Authentication/authorization.
- Trading/order execution.
- Strategy engine.
- AI/LLM integration.
- Retry/circuit breaker infrastructure.
