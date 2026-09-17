# Architecture — v0.1.0

## Agent Capability Discovery & Runtime Introspection Foundation

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

## Ownership

The Composition Root creates concrete capability dependencies and injects them into the application boundary. Capability registration is runtime-local and immutable after startup.

`CapabilityProviderPort` exposes capability discovery without coupling Core/Application layers to transport, persistence, HTTP, or MT5 infrastructure.

## Capability Lifecycle

```text
Defined
   ↓
Validated
   ↓
Registered
   ↓
Available
   ↓
Discovered
```

## Isolation invariants

- Core and Contracts do not import HTTP implementation, persistence, external APIs, or MetaTrader5 infrastructure.
- Capability registry remains in-memory for v0.1.0.
- No second command transport is introduced.
- Existing ApplicationBoundary and Dispatcher flow remain unchanged.

## Security and observability

Security ordering remains Validation → Authentication → Authorization → Dispatch.

Capability discovery uses the existing command path and does not modify operational observability boundaries.
