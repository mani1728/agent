# v0.0.2 Release Checklist

## Scope control

- [x] Development branch was `version-0.0.2` from `main`.
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
- [x] Final Windows GitHub Actions test job passed (`34875680757`).
- [x] Final Windows packaging job produced `MT5Agent-v0.0.2.exe` (`34875680757`).
- [x] Packaging smoke test passed for the unavailable-terminal path with exit code `1`.
- [x] Final branch diff contained only the approved v0.0.2 files.
- [x] No changes were made to v0.0.1, the root README, or `Version 1_0_0`.
- [x] PR `#32` merged into `main` as `0ee540ef4af08a4bdcbb90b0262997b53d34662c`.
- [x] Final documentation record completed after merge.

## Release operation

- [ ] Create annotated tag `v0.0.2` on the final approved release commit.
- [ ] Publish GitHub Release `v0.0.2` with `MT5Agent-v0.0.2.exe` attached.
- [ ] Record the published artifact checksum in the GitHub Release.

## Release artifact

Verified CI executable:

```text
MT5Agent-v0.0.2.exe
SHA-256: 5ceae12da14f349cb2a3a4bd04606fdb2ca6b595e89183bb59d7a5de00dfe13f
```

CI artifact archive:

```text
sha256:359b6ae4e64d1905b5e6dc9d49fbc5efe8338106c56524879adb21852c57d893
```

## Handoff to v0.0.3

Once the release tag and GitHub Release are published, v0.0.2 is considered closed. New development must start from the resulting `main` state on a dedicated `version-0.0.3` branch.
