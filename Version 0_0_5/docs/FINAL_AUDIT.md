# v0.0.5 Final Audit

## Baseline

- Source baseline: finalized `main` at `1571681d3d696da956b04db2607d38ba0699732f` (v0.0.4 baseline).
- v0.0.4 merge commit: `1f1a88632fd023439b5451b19c5851ff4f275bd3`.
- v0.0.4 remains closed and immutable.
- v0.0.5 implementation commit before merge: `f8c3d6a287492b525e0c802608d0ee8008cfc6c2`.
- v0.0.5 merge commit on `main`: `8c686e58070f561382c8c2280a1c9ccf8ddcd8de`.

## Scope verification

Included: security contracts, authentication/authorization ports, application security enforcement, execution-event contract, observability port, identity propagation, deterministic security errors, tests, CI and packaging updates.

Excluded: concrete network transport, TLS/mTLS, external IAM, persistence, durable idempotency, retry, circuit breaker, trading, strategy engine, AI/LLM and Windows Service.

## Architectural verification

- Core does not depend on concrete transport.
- Security is represented through contracts/ports.
- Observability is represented through a port.
- Telemetry failures are isolated from application execution.
- No concrete security or telemetry backend was introduced.
- v0.0.4 files were preserved as the baseline; v0.0.4 itself was not modified.
- v0.0.5 remains isolated under `Version 0_0_5`.

## Verification and CI

- Windows CI workflow `Version 0.0.5` completed successfully.
- Automated tests passed.
- PyInstaller build passed.
- Executable verification passed.
- Unavailable-terminal smoke test passed with exit code `1`.
- CI artifact `MT5Agent-v0.0.5` was produced.
- Final release executable was independently published and its release-asset SHA-256 recorded below.

## Release verification

- Tag: `v0.0.5`
- Release: `MT5 Agent v0.0.5`
- Release state: published (non-draft, non-prerelease).
- Release target: `main` / merge commit `8c686e58070f561382c8c2280a1c9ccf8ddcd8de`.
- Release asset: `MT5Agent-v0.0.5.exe`
- Release asset size: `41,316,750` bytes.
- Release asset SHA-256: `876ca0d8c238598bb47208dee1c998bdb0aed1d95d003609617966ea9b58969d`.
- The SHA-256 above identifies the published EXE itself; it is distinct from the GitHub Actions artifact archive digest.

## Release gate

All v0.0.5 release gates are complete: implementation, tests, CI, packaging, final audit, PR merge, tag/release publication, asset checksum verification, and documentation finalization.

The historical branch `version-0.0.5` is intentionally retained for traceability and is not required for v0.0.6 development. Future development must start from finalized `main`, not from the v0.0.5 branch.
