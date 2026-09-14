# v0.0.1 Release Checklist

This checklist freezes the release process for the minimal MT5 lifecycle agent.

## Source

- [x] `Version 0_0_1/agent` contains the minimal lifecycle implementation.
- [x] `Version 0_0_1/tests` contains adapter-injected unit tests.
- [x] `Version 0_0_1/agent/requirements.txt` pins `numpy==1.26.4`.
- [x] `Agent.spec` packages NumPy and MetaTrader 5 dependencies explicitly.
- [x] UPX compression is disabled.

## Build

- [x] Application icon is generated from `make_icon.py`.
- [x] PyInstaller output is named `MT5Agent-v0.0.1.exe`.
- [x] Local build script validates the expected output.
- [x] GitHub Actions builds on Windows.
- [x] CI smoke test verifies the expected MT5-unavailable exit path.

## Runtime verification

- [x] Unit tests pass without a live MT5 terminal.
- [x] Windows execution succeeds when MT5 is available.
- [x] Connection failure returns exit code `1` when MT5 is unavailable.

## Git state

- [x] v0.0.1 implementation was merged into `main`.
- [ ] The `v0.0.1` tag must point to the final release commit on `main`.
- [ ] The GitHub Release must be created for tag `v0.0.1`.
- [ ] Upload `MT5Agent-v0.0.1.exe` to that release.
- [ ] Verify the uploaded asset checksum if the binary is rebuilt.
- [ ] Delete the obsolete `version-0.0.1` branch after confirming no remaining work.

## Release acceptance

The release is complete only when the tag, release page, and uploaded executable all refer to the same final source state.
