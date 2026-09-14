# Changelog — v0.0.2

## v0.0.2 — Release Candidate

### Added

- Explicit lifecycle state model: `CREATED`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAILED`.
- `MT5Port` protocol for the core/adapter boundary, made runtime-checkable for contract-oriented tests.
- Immutable `Status`, `HealthStatus`, and typed `AgentConfig` contracts.
- Dependency injection of the MT5 port into the core `Agent`.
- Deterministic adapter/runtime exception containment for connect, disconnect, and health probes.
- Logger injection at the runtime boundary.
- Regression coverage for lifecycle, health, contract immutability/defaults, adapter exceptions, restart behavior, and the explicit disconnect contract.
- Independent v0.0.2 Windows packaging definition.
- Dedicated v0.0.2 GitHub Actions workflow with Windows test, build, executable validation, smoke test, and artifact upload.
- Version-local architecture and release documentation.

### Preserved

- v0.0.1 source and release tag remain unchanged.
- The repository root `README.md` remains outside this version scope.
- `Version 1_0_0` remains outside this version scope.
- Trading and order execution remain absent.
- Transport, persistence, security/authentication, service hosting, and AI integration remain absent.

### Verification

- GitHub Actions workflow run `34872771908` passed the v0.0.2 test job.
- GitHub Actions workflow run `34872771908` passed the v0.0.2 Windows build job.
- Packaging smoke test for the unavailable-terminal path passed with the expected exit code `1`.
- Verified artifact: `MT5Agent-v0.0.2.exe`.
- Artifact SHA-256: `eb18b139572670ab98995d6ce34681c17ce9516011e65c000b0f9934fbc92ad0`.

### Release status

The branch is ready for final review and PR merge. The GitHub Release/tag publication step is intentionally not performed from this branch workflow; publish `v0.0.2` only after merge approval.
