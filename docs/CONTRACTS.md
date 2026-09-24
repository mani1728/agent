# Contracts — v0.1.3 development

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

## Planned contract evolution (not implemented)

`CommandEnvelope`, response/error, transfer and capability schemas for remote
server control remain design work. They must be versioned and separately
approved before implementation; see [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md).
The current local HTTP request contract is not evidence of Kafka, persistence,
trade execution, mTLS, or durable idempotency support.

## Versioned protocol and capability manifest (implemented in v0.1.3)

`ProtocolVersion`, `CapabilityClass`, `CommandDefinition`, `CommandRegistry` and
`CapabilityManifest` form the local allowlisted protocol authority. Each command
has one registered identifier/version/class; duplicate registration is rejected.
Server input can only resolve a registered command/version. Unknown commands,
unknown versions, disabled classes and disabled commands fail closed with stable
codes `UNSUPPORTED_COMMAND`, `UNSUPPORTED_COMMAND_VERSION`,
`CAPABILITY_DISABLED` and `COMMAND_DISABLED`.

The manifest is deterministically generated from that registry and reports Agent
version, protocol version, command identifier/version, class and current enabled
state. It exposes only registered, current commands; it does not advertise future
MT5 capabilities. `agent.get_capability_manifest` is available when capability
discovery is composed.
