# v0.0.4 Release Notes

## Agent Transport Boundary & Execution Context Foundation

v0.0.4 formalizes the boundary between future external transport adapters and the existing Application Command layer.

This release introduces immutable execution-context and transport contracts without implementing any concrete network transport.

### Added

- `ExecutionContext`
- `TransportRequest`
- `TransportResponse`
- `ApplicationPort`
- `ApplicationBoundary`
- Transport-neutral request validation
- Correlation consistency enforcement
- Contract/error/test documentation
- Regression and failure-path tests
- Windows CI and PyInstaller packaging
- Executable verification and unavailable-terminal smoke testing

### Not Added

No HTTP, REST, Kafka, WebSocket, socket, authentication, authorization, persistence, trading, retry, circuit breaker, AI/LLM, or Windows Service implementation is included.

### Final Release Verification

- Release tag: `v0.0.4`
- Final merge commit: `1f1a88632fd023439b5451b19c5851ff4f275bd3`
- Release asset: `MT5Agent-v0.0.4.exe`
- Published SHA-256: `52a6e79823d1737cd6a6f2d8511db3038e3a7dafd71a418c45ae50b2fcfe908a`
- Windows manual execution: passed
- Development branch `version-0.0.4`: deleted

v0.0.4 is closed. Future development must continue from the finalized `main` baseline under a new version branch.
