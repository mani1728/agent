# v0.0.5 Test Strategy

## Contract

- SecurityContext immutability and normalization.
- ExecutionEvent immutability and required identity fields.

## Boundary

- Invalid request rejection before authentication.
- Authentication failure and exception translation.
- Authorization allow/deny/failure.
- Denied commands are not dispatched.
- Successful dispatch preserves request/correlation/command identity.

## Observability

- Event ordering for successful execution.
- Identity propagation on every event.
- Observer exceptions do not fail application execution.

## Regression

The complete v0.0.4 suite remains part of the version-local test suite. Tests require neither a live network transport nor a live MetaTrader 5 terminal.

## CI

Windows + Python 3.11 runs pytest, PyInstaller packaging, executable verification, unavailable-terminal smoke test and SHA-256 generation.
