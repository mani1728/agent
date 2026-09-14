# Changelog

All notable changes for the `Version 0_0_1` implementation are recorded here.

## [0.0.1] — MT5 Lifecycle Validation

### Added

- Minimal `Agent` lifecycle with explicit `start()` and `stop()` operations.
- `MT5Adapter` for MetaTrader 5 initialization, shutdown, and terminal readiness checks.
- Immutable `Status` contract for simple success/failure reporting.
- Health-check helper around agent readiness.
- Local transport abstraction for status output.
- Unit-test suite with a fake MT5 adapter.
- PyInstaller Windows executable specification.
- NumPy packaging safeguards, including the pinned `numpy==1.26.4` dependency and explicit hidden imports/package collection.
- High-resolution application icon renderer and preview tooling.
- GitHub Actions CI/CD workflow for Windows testing, packaging, smoke testing, and tag-based release creation.
- Final Windows artifact name: `MT5Agent-v0.0.1.exe`.

### Verified

- Source execution succeeds when MetaTrader 5 is available.
- Source execution reports a deterministic connection failure when MT5 is unavailable.
- Unit tests run without a live MT5 terminal.
- Windows executable packaging succeeds with the required native dependencies.
- Final executable was tested on Windows with MT5 available.

### Explicitly out of scope

- Trading and order execution.
- Strategy implementation.
- Account/order management.
- Kafka or HTTP transport.
- Persistence/database layer.
- Windows Service hosting.
- Remote authentication and authorization.

## Release artifact

- **Tag:** `v0.0.1`
- **Executable:** `MT5Agent-v0.0.1.exe`
- **Final verification SHA-256:** `a96f7ce0b44ad81ee64dbabd739e844c601b3f5acea1d2897ea962221b18e608`

> The checksum identifies the specific binary used for final verification. Rebuilt binaries must be checksummed independently.
