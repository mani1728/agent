# v0.0.2 Release Checklist

## Scope control

- [x] Development branch is `version-0.0.2` from `main`.
- [x] v0.0.1 source files are unchanged.
- [x] Root `README.md` is unchanged.
- [x] `Version 1_0_0` is unchanged.
- [x] No trading or order-execution code is introduced.

## Implementation

- [x] Explicit lifecycle state is implemented.
- [x] MT5 port contract is explicit.
- [x] Status and health contracts are typed and immutable.
- [x] Adapter failures are contained at the integration boundary.
- [x] Configuration has a typed boundary.
- [x] Lifecycle/health regression tests are present.

## Verification before merge

- [x] Local syntax/test verification performed with a deterministic terminal stub.
- [ ] Windows GitHub Actions test job passes.
- [ ] Windows packaging job produces `MT5Agent-v0.0.2.exe`.
- [ ] Packaging smoke test passes.
- [ ] Final branch diff contains only approved v0.0.2 changes.
- [ ] Final review completed before opening/merging the PR.
- [ ] Tag `v0.0.2` is created only after merge approval.
