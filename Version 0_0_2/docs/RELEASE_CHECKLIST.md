# v0.0.2 Release Checklist

## Scope control

- [x] Development branch is `version-0.0.2` from `main`.
- [x] v0.0.1 source files are unchanged.
- [x] v0.0.1 tag remains unchanged.
- [x] Root `README.md` is unchanged.
- [x] `Version 1_0_0` is unchanged.
- [x] No trading or order-execution code is introduced.

## Implementation

- [x] Explicit lifecycle state is implemented.
- [x] MT5 port contract is explicit and runtime-checkable.
- [x] Status and health contracts are typed and immutable.
- [x] Adapter failures are contained at the integration boundary.
- [x] Configuration has a typed boundary.
- [x] Logging is injectable at the runtime boundary.
- [x] Lifecycle/health/contract regression tests are present.

## Verification

- [x] Deterministic fake adapter is used for unit tests; real MT5 is not required.
- [x] Windows GitHub Actions test job passed on the verified build baseline.
- [x] Windows packaging job produced `MT5Agent-v0.0.2.exe` on the verified build baseline.
- [x] Packaging smoke test passed for the unavailable-terminal path with exit code `1`.
- [x] Final branch diff contains only the approved v0.0.2 files.
- [x] No changes were made to v0.0.1, the root README, or `Version 1_0_0`.
- [ ] Final CI rerun after the final documentation/test commits passes.
- [ ] Final PR review completed.
- [ ] PR merged into `main`.
- [ ] Tag `v0.0.2` created from the approved merge commit.
- [ ] GitHub Release `v0.0.2` published with `MT5Agent-v0.0.2.exe`.

## Release artifact

Verified build artifact from the successful CI baseline:

```text
MT5Agent-v0.0.2.exe
SHA-256: eb18b139572670ab98995d6ce34681c17ce9516011e65c000b0f9934fbc92ad0
```

The final release artifact must be generated from the final approved commit and its checksum recorded in the release notes.
