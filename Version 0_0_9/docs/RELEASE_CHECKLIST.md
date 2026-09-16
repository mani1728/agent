# Release Checklist — v0.0.8

## Pre-merge / verification

- [x] Scope and architecture approved
- [x] Development completed on `version-0.0.8`
- [x] Hosting contracts implemented
- [x] `ApplicationHost` lifecycle coordinator implemented
- [x] Concrete `HTTPServerHost` implemented
- [x] Graceful process shutdown implemented
- [x] Deterministic lifecycle failure precedence implemented
- [x] Lifecycle exception containment implemented
- [x] Hosting and architecture-isolation tests added
- [x] Version-specific Windows CI/CD completed
- [x] PyInstaller artifact named `MT5Agent-v0.0.8.exe`
- [x] Executable verification successful
- [x] Unavailable-MT5 smoke test successful
- [x] Invalid-configuration smoke test successful
- [x] Final verification workflow `35013801830` successful
- [x] Manual Windows/MT5 graceful-shutdown acceptance completed
- [x] Canonical SHA-256 captured and verified: `e04f497bf3a893aa7bf5dec24bcc19d77930a50e42716dc7b1e5ace7d4641266`

## Merge / release closure

- [x] PR #40 merged to `main`
- [x] Merge commit: `a181b6364eb87597de10b0a781bbf45892d6cec9`
- [x] Tag `v0.0.8` published
- [x] Tag target verified: `ec0585624c4defd30c8d368be8756a33e2d3caa5`
- [x] GitHub Release `MT5 Agent v0.0.8` published
- [x] Release asset `MT5Agent-v0.0.8.exe` attached
- [x] Release asset SHA-256 verified against the canonical SHA-256
- [x] Historical tag/release state intentionally preserved
- [x] Version marked CLOSED

## Historical release state

The `v0.0.8` tag and GitHub Release intentionally point to the final reviewed implementation commit `ec0585624c4defd30c8d368be8756a33e2d3caa5`, while `main` advanced to merge commit `a181b6364eb87597de10b0a781bbf45892d6cec9` after closure documentation and merge processing. This is an accepted historical state. The tag must not be moved or rewritten.
