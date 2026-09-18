# Contracts — v0.1.1 development

## CapabilityDescriptor

Immutable capability metadata contract.

Fields:

- `name`
- `version`
- `schema_version`
- `metadata`

Validation guarantees deterministic capability identification and serialization.

## RuntimeInformationContract

Immutable runtime snapshot contract containing:

- agent identity;
- runtime version;
- schema version;
- lifecycle state;
- available capabilities.

## CapabilityProviderPort

Application/Core boundary contract responsible for capability discovery.

It must not depend on:

- HTTP;
- persistence;
- MetaTrader5 package;
- external APIs.

## Commands

Capability discovery is exposed through existing command contracts:

- `agent.get_capabilities`
- `agent.get_runtime_info`

Responses continue to use `CommandResult` with versioned payload schemas.

## Compatibility

Existing Command, Security, Transport, Observability, Configuration, and MT5Port contracts remain unchanged.
