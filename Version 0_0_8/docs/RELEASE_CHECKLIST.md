# Release Checklist — v0.0.7

## Pre-merge

- [x] Scope and architecture approved
- [x] Branch created from finalized `main` baseline `5217005509c91bb4f20647cda804aea018bb71a8`
- [x] Configuration contracts implemented
- [x] Composition root implemented
- [x] Tests added
- [x] Version-specific Windows workflow added
- [x] PyInstaller artifact named `MT5Agent-v0.0.7.exe`
- [x] Version documentation updated
- [x] GitHub Actions test job successful
- [x] GitHub Actions build job successful
- [x] Executable verification successful
- [x] Unavailable-terminal smoke test successful
- [x] Invalid-configuration smoke test successful
- [x] SHA-256 captured and independently verified: `cd62e24c5eb37b39ecb9c6579e060345fca21b525d4d0e9385e06d3069e0f1da`
- [x] GitHub Actions artifact digest recorded: `sha256:388756f977e79cd3952a8505b4235a76e0794479214353cfdde0f57f7e97af39`
- [x] Explicit merge approval received

## Merge / release handoff

- [ ] Merge PR #39 to `main`
- [ ] Verify post-merge `main` CI
- [ ] Confirm no open PR remains
- [ ] Owner creates tag `v0.0.7`
- [ ] Owner publishes release `v0.0.7`
- [ ] Owner attaches `MT5Agent-v0.0.7.exe`
- [ ] Verify release artifact SHA-256
- [ ] Confirm tag/release/main consistency
- [ ] Mark version CLOSED after owner release

The project owner requested tag and release creation as a separate handoff after merge. Therefore the version may be release-ready while tag/release verification remains pending.