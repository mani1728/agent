# v0.0.3 Release Notes

## Title

**MT5 Agent v0.0.3 — Agent Command Foundation**

## Summary

v0.0.3 establishes a transport-neutral Application Command boundary on top of the v0.0.2 Agent Runtime & Contract Foundation.

The version introduces immutable command/result contracts, schema validation, correlation semantics, an application dispatcher, deterministic result codes, and read-only status/health commands. It deliberately does not introduce network transport, persistence, authentication, trading, or AI integration.

## Artifact

```text
MT5Agent-v0.0.3.exe
```

## Verification

Final Windows CI run used for the release candidate:

```text
34884671716
```

The CI build completed successfully with:

- Python 3.11
- contract and dispatcher tests: passed
- PyInstaller build: passed
- executable verification: passed
- unavailable-terminal smoke test: passed
- SHA-256 generation: passed
- artifact upload: passed

The selected executable is accompanied by `sha256.txt` in the CI artifact. The checksum in the GitHub Release description must be copied from that exact `sha256.txt` file after the exact executable is attached to the release.

## Release Scope

### Added

- `Command` / `CommandResult` contracts.
- Command validation and schema versioning.
- `command_id` and `correlation_id` semantics.
- Application `CommandDispatcher`.
- Deterministic application result/error codes.
- Read-only `agent.get_status` and `agent.get_health` commands.
- Reproducible icon generation for Windows packaging.
- CI packaging and executable smoke verification.
- Version-level architecture, command, error and release documentation.

### Not included

- Network transports.
- Persistence or durable idempotency.
- Authentication/authorization.
- Trading/order execution.
- Position/account management.
- Strategy engine.
- AI/LLM integration.
- Retry/circuit-breaker infrastructure.

## Release Procedure

The executable is ready for attachment to the final `v0.0.3` GitHub Release after the version branch is merged and the tag is created from the merged `main` commit.
