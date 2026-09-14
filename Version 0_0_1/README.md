# Agent v0.0.1

Minimal Windows agent for validating the MetaTrader 5 connection lifecycle.

## Scope

- Initialize MetaTrader 5.
- Check terminal connectivity.
- Report a simple status.
- Exit with code `0` on success and `1` on connection failure.
- Build a single Windows executable with PyInstaller.

No trading or order execution is included in v0.0.1.

## Run from source

From `Version 0_0_1`:

```powershell
python -m agent
```

## Test

```powershell
pytest
```

## Build EXE

Use the included PowerShell script:

```powershell
.\build.ps1
```

Or run PyInstaller directly:

```powershell
pyinstaller agent/deployment/Agent.spec --clean --noconfirm
```

The executable is generated as:

```text
dist/Agent.exe
```

## CI/CD

GitHub Actions runs tests on Windows and builds the EXE. Pushing a tag such as `v0.0.1` creates a GitHub Release and attaches `Agent.exe`.

## Runtime requirement

MetaTrader 5 terminal must be installed on the Windows machine where the executable is run.
