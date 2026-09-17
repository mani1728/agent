# MT5 Agent — v0.1.0

## Agent Capability Discovery & Runtime Introspection Foundation

v0.1.0 extends the stable v0.0.9 baseline with capability discovery and runtime information contracts while preserving existing Core isolation, security ordering, transport behavior, and observability boundaries.

## Architecture

```text
External System
      ↓
Command Boundary
      ↓
Capability Commands
      ↓
CapabilityProviderPort
      ↓
InMemoryCapabilityRegistry
      ↓
Agent Runtime
```

Capability discovery is implemented through the existing command execution path. No new transport boundary or parallel API surface is introduced.

## Contracts

Added:

- `CapabilityDescriptor`
- `RuntimeInformationContract`
- `CapabilityProviderPort`

Properties:

- immutable models;
- schema versioning support;
- deterministic validation;
- JSON serialization compatibility.

## Commands

Added:

- `agent.get_capabilities`
- `agent.get_runtime_info`

Commands use the existing `Command` and `CommandResult` contracts.

## Scope

Included: capability contracts, runtime information contract, capability provider boundary, in-memory registry, command integration, composition injection, and capability discovery tests.

Excluded: Trading, Order Execution, Position Management, Strategy Engine, AI/LLM integration, Persistence, and Broker Business Logic.

## Compatibility

Preserved:

- Validation → Authentication → Authorization → Dispatch ordering;
- existing transport contracts;
- MT5Port and adapter boundaries;
- best-effort observability behavior.
