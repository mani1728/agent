# Test Strategy — v0.0.8

## Unit lifecycle tests

Use injected fake Agent lifecycle and Hosting ports to verify:

- start → serve → stop ordering;
- startup failure prevents serving;
- hosting failure still triggers cleanup;
- hosting failure remains primary when cleanup also fails;
- cleanup-only failure is deterministic.

## Hosting integration

Run a standard-library HTTP server on loopback with an ephemeral port, send a valid `POST /command`, request `HostingPort.shutdown()`, and verify the serving thread exits and the listening resource is closed.

## Architecture isolation

Source-level isolation tests reject HTTP server, signal, socket, and MetaTrader5 infrastructure imports from Core/Contracts and reject process/transport dependencies from `ApplicationHost`.

## Regression

Retain v0.0.7 configuration/composition and HTTP transport tests, including security ordering, identity propagation, request-size validation, failure sanitization, and best-effort observer isolation.

## Windows CI / packaging

The v0.0.8 workflow runs pytest on Python 3.11, builds `MT5Agent-v0.0.8.exe` with PyInstaller, verifies the executable, verifies deterministic unavailable-MT5 and invalid-configuration exit paths, calculates SHA-256, and uploads the executable plus checksum as a workflow artifact.
