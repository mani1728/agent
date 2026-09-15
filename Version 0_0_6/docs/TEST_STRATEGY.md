# v0.0.6 Test Strategy

Tests are local and deterministic; no external HTTP service or MT5 terminal is required.

## Contract tests

- JSON parsing
- required identity validation
- correlation propagation
- command construction
- response serialization
- serialization failure mapping

## Security tests

- authentication precedes authorization
- authorization precedes dispatch
- authentication failure prevents authorization and dispatch
- authorization denial prevents dispatch

## Integration tests

- valid HTTP request reaches `ApplicationPort`
- application result maps to HTTP response
- application exception is sanitized

## Isolation tests

- malformed transport requests do not call the application
- observer failure does not fail valid execution
- transport/application failures do not leak internal exception details
