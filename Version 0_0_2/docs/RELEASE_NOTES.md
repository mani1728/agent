# MT5 Agent v0.0.2 — Release Notes

## Summary

v0.0.2, **Agent Runtime & Contract Foundation**, strengthens the runtime boundary around the v0.0.1 MT5 lifecycle foundation.

## Highlights

- Explicit lifecycle state machine.
- `MT5Port` abstraction between core and terminal adapter.
- Dependency injection at the core boundary.
- Immutable runtime status/health/config contracts.
- Deterministic connection, disconnect, and health failure handling.
- Expanded contract and lifecycle regression coverage.
- Independent Windows PyInstaller packaging.
- Dedicated Windows CI test/build/smoke pipeline.

## Not included

Trading, order execution, positions, account management, network transport, persistence, authentication/authorization, Windows Service hosting, strategy execution, retry/circuit-breaker infrastructure, and AI integration are intentionally deferred.

## Artifact

```text
MT5Agent-v0.0.2.exe
```

The verified CI artifact has SHA-256:

```text
eb18b139572670ab98995d6ce34681c17ce9516011e65c000b0f9934fbc92ad0
```

## Verification baseline

The successful Windows workflow validated unit tests, PyInstaller packaging, executable existence, and the unavailable-terminal smoke-test path. The final release build should be regenerated from the approved merge/tag commit and its checksum should be recorded with the published release.
