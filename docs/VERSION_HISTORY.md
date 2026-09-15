# MT5 Agent — Version History

This document records the finalized version baselines of the MT5 Agent. Finalized versions are immutable release references; future development starts from the finalized `main` branch.

## v0.0.1 — Initial Foundation

Initial Agent foundation with MetaTrader 5 integration, lifecycle, adapter boundary, tests without a live MT5 terminal, Windows packaging, CI, and release artifact.

## v0.0.2 — Agent Runtime & Contract Foundation

Established the explicit runtime lifecycle, `MT5Port` protocol, dependency injection, immutable typed runtime contracts, structured errors, health contract, injectable logging boundary, regression tests, Windows CI/CD, and reproducible packaging.

Trading, external transport, persistence, authentication, and AI remained outside scope.

## v0.0.3 — Agent Command Foundation

Added immutable `Command` / `CommandResult`, command and correlation identity, schema versioning, validation, `CommandDispatcher`, deterministic result/error codes, and read-only status/health commands.

## v0.0.4 — Agent Transport Boundary & Execution Context Foundation

Established the transport/application boundary and execution context required for future external transports, while keeping transport technology outside Agent Core.

## v0.0.5 — Security & Observability Boundary Foundation

Established `SecurityContext`, authentication and authorization ports, mandatory authentication-before-authorization enforcement, deterministic security errors, `ExecutionEvent` contracts, `ObservabilityPort`, identity propagation, and best-effort observability.

## v0.0.6 — Concrete HTTP Transport Boundary Foundation

Released the first concrete transport implementation.

### Added

- Standard-library HTTP transport adapter
- `POST /command` endpoint
- JSON transport envelope
- Request validation and deterministic invalid-request handling
- `request_id`, `correlation_id`, and `command_id` propagation
- Transport-neutral `ApplicationPort` integration
- Validation → Authentication → Authorization → Dispatch ordering
- Deterministic HTTP error mapping
- Sanitized application/internal failures
- Response serialization failure handling
- Observer failure isolation
- Transport-focused regression and integration tests
- Windows CI/CD and PyInstaller packaging
- Executable verification and SHA-256 generation

### Explicitly Not Included

- Trading or order execution
- Positions or account management
- Strategy engine
- AI/LLM integration
- Durable persistence
- Retry engine or circuit breaker
- Kafka/WebSocket production transport
- OAuth/OIDC/JWT or external IAM
- TLS/mTLS production security infrastructure
- Windows Service or production deployment infrastructure

### Release Artifact

```text
MT5Agent-v0.0.6.exe
```

EXE SHA-256:

```text
c85032d01ddd9972de34aa95333c75e87617493b98083cfafc17d4683e090e6b
```

GitHub Actions artifact digest:

```text
dea620d995d8c02f96d03468f7075f8c227340e64c52b14d10a51430b32fbfe2
```

### Release State

- Tag: `v0.0.6`
- Release: published by the project owner
- PR: `#37`
- PR status: merged
- Merge commit: `7f961052fcd89cc46a9398285c8230849782417c`
- Finalized development branch: `version-0.0.6`
- Future versions must branch from finalized `main`, not from a historical version branch.

## Current Baseline

The current development baseline after `v0.0.6` is the finalized `main` branch at the v0.0.6 merge commit.

```text
External System
      ↓
Concrete HTTP Transport
      ↓
Transport Contract
      ↓
ApplicationPort
      ↓
Security Boundary
      ↓
Application Boundary
      ↓
Command Dispatcher
      ↓
Agent Runtime
      ↓
MT5Port
      ↓
MT5Adapter
      ↓
MetaTrader 5
```

The concrete HTTP transport is an adapter, not a dependency of the Agent Core. Future transport implementations must preserve this dependency direction.

## Development Rule

A new version starts only from the finalized `main` baseline after the previous version has completed implementation, tests, CI/CD, packaging, documentation, final audit, PR, merge, tag, release, and artifact verification.
