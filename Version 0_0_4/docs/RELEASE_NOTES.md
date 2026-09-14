# v0.0.4 Release Notes

## Agent Transport Boundary & Execution Context Foundation

v0.0.4 formalizes the boundary between future external transport adapters and the existing Application Command layer.

### Added

- `ExecutionContext`
- `TransportRequest`
- `TransportResponse`
- `ApplicationPort`
- `ApplicationBoundary`
- Transport-neutral request validation
- Correlation consistency enforcement
- Contract/error/test documentation

### Not Added

No HTTP, REST, Kafka, WebSocket, socket, authentication, authorization, persistence, trading, retry, circuit breaker, AI/LLM, or Windows Service implementation is included.
