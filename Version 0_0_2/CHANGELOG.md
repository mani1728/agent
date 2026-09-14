# Changelog — v0.0.2

## v0.0.2 — Agent Runtime & Contract Foundation

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

- Final v0.0.2 Windows workflow run `34875680757` passed the test job.
- Final v0.0.2 Windows workflow run `34875680757` passed the build job.
- Packaging smoke test for the unavailable-terminal path passed with the expected exit code `1`.
- Verified artifact: `MT5Agent-v0.0.2.exe`.
- Extracted executable SHA-256: `5ceae12da14f349cb2a3a4bd04606fdb2ca6b595e89183bb59d7a5de00dfe13f`.
- CI artifact archive digest: `sha256:359b6ae4e64d1905b5e6dc9d49fbc5efe8338106c56524879adb21852c57d893`.
- PR `#32` was merged into `main` with merge commit `0ee540ef4af08a4bdcbb90b0262997b53d34662c`.

### Release status

Implementation, testing, packaging, CI verification, architecture documentation, and release documentation are complete. The remaining release operation is to create tag `v0.0.2` on the approved final release commit and publish the GitHub Release with the executable attached.
