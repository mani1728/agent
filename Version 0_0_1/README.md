# Agent v0.0.1

Minimal Windows agent for validating the MetaTrader 5 connection lifecycle.

## Scope

- Initialize MetaTrader 5.
- Check terminal connectivity.
- Report a simple status.
- Exit with code `0` on success and `1` on connection failure.
- Build a Windows executable with PyInstaller.

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

```powershell
pyinstaller agent/deployment/Agent.spec --clean --noconfirm
```

The executable is generated as:

```text
dist/Agent.exe
```

MetaTrader 5 terminal must be installed on the Windows machine where the executable is run.
