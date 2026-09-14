# MT5 Agent v0.0.2 — Release Notes

## Summary

v0.0.2, **Agent Runtime & Contract Foundation**, strengthens the runtime boundary around the v0.0.1 MT5 lifecycle foundation.

## Highlights

- Explicit lifecycle state machine.
- `MT5Port` abstraction between core and terminal adapter.
- Dependency injection at the core boundary.
- Immutable runtime status/health/config contracts.
- Deterministic connection, disconnect, and health failure handling.
- Injectable runtime logging boundary.
- Expanded contract and lifecycle regression coverage.
- Independent Windows PyInstaller packaging.
- Dedicated Windows CI test/build/smoke pipeline.

## Not included

Trading, order execution, positions, account management, network transport, persistence, authentication/authorization, Windows Service hosting, strategy execution, retry/circuit-breaker infrastructure, and AI integration are intentionally deferred.

## Release artifact

```text
MT5Agent-v0.0.2.exe
```

Extracted executable SHA-256:

```text
5ceae12da14f349cb2a3a4bd04606fdb2ca6b595e89183bb59d7a5de00dfe13f
```

CI artifact archive digest:

```text
sha256:359b6ae4e64d1905b5e6dc9d49fbc5efe8338106c56524879adb21852c57d893
```

## Verification

GitHub Actions workflow run `34875680757` completed successfully. The Windows pipeline validated dependency installation, unit tests, icon generation, PyInstaller packaging, executable existence, unavailable-terminal smoke behavior, and artifact upload.

The v0.0.2 PR (`#32`) was merged into `main` as commit `0ee540ef4af08a4bdcbb90b0262997b53d34662c`. Subsequent documentation-only commits finalize the release record; the release tag should point to the final approved documentation commit.

## Release contents

The v0.0.2 release consists of the isolated `Version 0_0_2` implementation, its dedicated Windows CI workflow, unit/contract tests, packaging configuration, architecture documentation, release checklist, release notes, and the Windows executable artifact.
