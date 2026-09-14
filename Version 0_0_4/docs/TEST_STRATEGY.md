# v0.0.4 Test Strategy

## Contract Tests

Validate:

- immutable request context
- immutable metadata normalization
- non-empty request/correlation identifiers
- command type requirements
- correlation consistency between context and command
- invalid request handling

## Application Boundary Tests

Validate:

- successful request dispatch
- request/command identity preservation
- deterministic dispatcher error propagation
- handler exception containment
- no dependency on a concrete transport

## Regression Tests

The existing v0.0.3 command and dispatcher tests remain part of the version-level suite.

## Integration Boundary

No live network transport and no live MetaTrader 5 terminal are required. The application boundary is tested with an in-memory fake MT5 implementation where runtime health behavior is relevant.
