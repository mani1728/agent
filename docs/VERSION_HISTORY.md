# MT5 Agent — Version History

This document records finalized MT5 Agent baselines. Released version directories are historical references; future development starts from finalized `main`.

## v0.0.1 — Initial Foundation
Initial MT5 integration, lifecycle, adapter boundary, tests without live MT5, Windows packaging, CI and release artifact.

## v0.0.2 — Agent Runtime & Contract Foundation
Explicit lifecycle state machine, `MT5Port`, dependency injection, immutable runtime contracts, structured errors, health contract, logging boundary, regression tests and reproducible Windows packaging.

## v0.0.3 — Agent Command Foundation
Immutable `Command` / `CommandResult`, command/correlation identity, schema versioning, validation, `CommandDispatcher`, deterministic result codes and read-only status/health commands.

## v0.0.4 — Agent Transport Boundary & Execution Context Foundation
Transport-neutral application boundary and execution context for future concrete transports.

## v0.0.5 — Security & Observability Boundary Foundation
Security contracts and ports, mandatory Authentication-before-Authorization ordering, deterministic security failures, execution events, identity propagation and best-effort observability.

## v0.0.6 — Concrete HTTP Transport Boundary Foundation
Standard-library HTTP/JSON `POST /command` adapter, deterministic transport/error mapping, identity propagation, failure isolation, Windows CI/CD and executable packaging.

## v0.0.7 — Agent Configuration & Composition Root Foundation

Introduced a formal startup configuration and composition boundary while preserving Core independence.

### Added

- immutable `AgentConfig` / `HTTPConfig`
- deterministic `ConfigurationError`
- `ConfigurationProvider` protocol
- environment-backed configuration adapter
- explicit composition root
- configurable HTTP host, port and request-body limit
- deterministic invalid-startup behavior
- configuration/composition architecture tests
- regression coverage for HTTP, security ordering and boundary isolation
- Windows CI/CD and PyInstaller packaging
- executable and smoke-test verification

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
   ↓      ↓        ↓
MT5Port Security Observability
   \       |       /
    ApplicationBoundary
            ↓
    HTTPTransportAdapter
```

Core does not read environment variables and remains independent of HTTP implementation, security infrastructure, observability backends, external configuration frameworks and the `MetaTrader5` package.

Security ordering remains:

```text
Validation → Authentication → Authorization → Dispatch
```

### Release state

- PR: `#39`
- PR status: merged
- merge commit: `a93812eee78692692982b831bc2a920ab6d104f6`
- release artifact: `MT5Agent-v0.0.7.exe`
- verified executable SHA-256: `38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`
- GitHub Actions artifact digest: `sha256:d26b0432548a0f44962a75ff8288926b107f0cb0dc27d31c8a0e72f48857e46e`
- tag/release publication: owner handoff

### Explicitly not included

Trading/orders/positions, strategy engine, AI/LLM, persistence, JWT/OAuth/OIDC, TLS/mTLS, external IAM, secrets management, remote configuration, YAML/TOML frameworks, telemetry backend, Kafka/WebSocket, retry/circuit breaker and Windows Service.

## Current baseline

`main` contains the completed v0.0.7 implementation and release documentation. New development must branch from the latest finalized `main` after the owner completes tag/release publication and release-asset verification.