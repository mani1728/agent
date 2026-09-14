# v0.0.3 Release Checklist

## Development

- [x] Audit v0.0.2 baseline from GitHub
- [x] Define v0.0.3 scope and non-goals
- [x] Create `version-0.0.3` from final `main`
- [x] Implement command contracts
- [x] Implement application dispatcher
- [x] Preserve v0.0.2 lifecycle and MT5Port direction
- [x] Remove development-only handler wrapper
- [x] Collapse development history to one version commit before merge

## Verification

- [x] Contract validation tests added
- [x] Dispatcher success/failure tests added
- [x] Lifecycle regression boundary preserved
- [x] CI workflow added
- [x] Windows CI test job green
- [x] Windows executable built and verified
- [x] Unavailable-terminal smoke test green
- [x] SHA-256 generated from final CI artifact

Final artifact:

```text
MT5Agent-v0.0.3.exe
```

The executable checksum is supplied beside the executable in the CI artifact as `sha256.txt`. The checksum must be copied to the GitHub Release description only after the exact executable selected for release has been uploaded.

## Release Gate

- [x] Final diff audit completed
- [x] PR opened against `main`
- [ ] PR approved and merged
- [ ] Annotated tag `v0.0.3` created after merge
- [ ] GitHub Release published
- [ ] Release artifact attached
- [ ] Artifact checksum independently verified after release upload

No release/tag operation is permitted before all applicable post-merge gates are complete.

## Repository CI Note

The v0.0.3 pull request also triggers the historical v0.0.1 and v0.0.2 workflows because those workflows listen to pull requests targeting `main`. These historical workflows are protected and are not modified by v0.0.3.
