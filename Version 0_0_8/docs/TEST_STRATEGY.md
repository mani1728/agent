# Test Strategy — v0.0.7

The v0.0.7 suite retains v0.0.6 HTTP regression tests and adds configuration/composition coverage.

Required coverage:

- immutable/default configuration behavior
- invalid host/port/request-limit rejection
- environment-to-contract translation
- deterministic malformed environment failure
- dependency injection through the composition root
- configurable HTTP request-body limit
- Core isolation from environment variables, HTTP adapter code, and `MetaTrader5`
- regression of Validation → Authentication → Authorization → Dispatch ordering
- identity propagation for request/correlation/command IDs
- observer failure isolation
- sanitized internal failures

CI runs `pytest` on Windows/Python 3.11, builds the PyInstaller executable, verifies the expected executable, smoke-tests the unavailable-MT5 path, smoke-tests invalid configuration, generates SHA-256, and uploads the executable/checksum artifact.
