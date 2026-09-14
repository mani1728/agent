# MT5 Agent v0.0.2

Version 0.0.2 extends the v0.0.1 foundation without adding trading or external transport.

## Scope

- Explicit lifecycle state machine.
- Stable MT5 port contract.
- Structured status and health results.
- Typed configuration boundary.
- Adapter exception containment at the runtime boundary.
- Regression tests for lifecycle and health behavior.
- Reproducible Windows packaging as `MT5Agent-v0.0.2.exe`.

## Deliberate non-goals

Trading, order execution, network transport, persistence, authentication, service hosting, and AI integration remain out of scope.

## Run tests

From this directory:

```powershell
python -m pip install -r requirements.txt
pytest -q
```

## Build

On Windows:

```powershell
.\build.ps1
```

The script generates the icon, runs tests, and packages the executable with PyInstaller.
