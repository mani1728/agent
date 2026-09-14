# MT5 Agent v0.0.5

## Security & Observability Boundary Foundation

v0.0.5 extends the finalized v0.0.4 application boundary with transport-neutral security and execution-observability contracts. No concrete network transport, credential provider, IAM integration, telemetry backend, persistence, or trading implementation is included.

### Scope

- Immutable `SecurityContext`, `AuthenticationResult`, and `AuthorizationDecision` contracts.
- `Authenticator` and `Authorizer` ports.
- Authentication before authorization at the application ingress boundary.
- Deterministic `authentication_failed`, `authorization_failed`, and `authorization_denied` outcomes.
- Immutable `ExecutionEvent` and `ExecutionEventType` contracts.
- `ObservabilityPort` and non-invasive `NullObservability` adapter.
- Correlation/request/command identity propagation across execution events.
- Observability failures are non-fatal to application execution.
- Regression and failure-path tests.
- Windows CI and PyInstaller packaging for v0.0.5.

### Architecture

```text
External System
      |
      v
Future Transport Adapter
      |
      v
  ApplicationPort
      |
      v
Security Boundary
      |
      v
ApplicationBoundary
      |
      +------> ObservabilityPort
      |
      v
CommandDispatcher
      |
      v
Agent Runtime
      |
      v
    MT5Port
      ^
      |
  MT5Adapter
      |
      v
 MetaTrader 5
```

Security and observability remain ports/contracts. Concrete implementations stay outside the application core.

### Non-Goals

- HTTP/REST, Kafka, WebSocket, socket transport.
- TLS/mTLS.
- JWT, OAuth/OIDC, external IAM, or credential storage.
- Persistence or durable idempotency.
- Retry or circuit breaker.
- Trading/order execution, positions, or account management.
- Strategy engine.
- AI/LLM integration.
- Windows Service.

### Development

The v0.0.5 branch is created from the finalized `main` baseline at `1571681d3d696da956b04db2607d38ba0699732f`. v0.0.4 remains closed and immutable.

Local test/build commands:

```powershell
cd "Version 0_0_5"
python -m pip install -r requirements.txt
pytest -q
python make_icon.py
pyinstaller deployment/Agent.spec --clean --noconfirm
```
