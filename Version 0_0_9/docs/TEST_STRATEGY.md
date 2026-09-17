# Test Strategy — v0.1.0

## Contract tests

Verify:

- `CapabilityDescriptor` validation;
- `RuntimeInformationContract` validation;
- schema version handling;
- immutable contract behavior.

## Serialization tests

Verify JSON serialization and reconstruction of capability and runtime information contracts.

## Registry tests

Verify:

- capability registration;
- validation during registration;
- immutable runtime discovery behavior.

## Command integration tests

Verify:

- `agent.get_capabilities` execution;
- `agent.get_runtime_info` execution;
- CommandResult integration;
- deterministic error mapping.

## Architecture isolation

Reject dependencies from capability components on:

- HTTP transport;
- persistence;
- MetaTrader5 infrastructure;
- external frameworks.

## Regression

Retain v0.0.9 lifecycle, security ordering, transport behavior, error mapping, composition, and observability tests.
