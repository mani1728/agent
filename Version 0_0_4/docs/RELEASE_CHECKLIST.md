# v0.0.4 Release Checklist

## Development

- [x] Audit v0.0.3 Git, architecture, tests, CI, packaging and documentation baseline
- [x] Define v0.0.4 scope and non-goals
- [x] Create `version-0.0.4` from final `main` commit `78d7f37e14d44c18ec62e3b242dc6a000af34681`
- [x] Define transport-neutral request/response contracts
- [x] Define immutable execution context
- [x] Define `ApplicationPort`
- [x] Add application boundary over the existing dispatcher
- [x] Preserve v0.0.3 command semantics and error codes
- [x] Add contract and failure-path tests

## Verification

- [ ] Full version-level pytest suite green on Windows CI
- [ ] PyInstaller executable built successfully
- [ ] Frozen executable verified
- [ ] Unavailable-terminal smoke test green
- [ ] SHA-256 generated from final CI artifact
- [ ] Final diff and dependency-direction audit completed

## Release Gate

- [ ] PR opened against `main`
- [ ] PR approved and merged
- [ ] Tag `v0.0.4` created after merge
- [ ] GitHub Release published
- [ ] Release artifact attached
- [ ] Artifact checksum independently verified

No merge, tag, or release operation is permitted before the applicable verification gates are complete.
