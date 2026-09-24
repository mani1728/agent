# Current Architecture — v0.1.3 development

## Status boundary

This document describes the implemented package only. The approved product
direction and proposed production boundaries are separately documented in
[TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md); they are not implemented
features. The Agent is an MT5 access/execution worker, never an AI, strategy,
risk, capital-management, or autonomous trading-decision component.

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
- Capability registry remains in-memory.
- No second command transport is introduced.
- Existing ApplicationBoundary and Dispatcher flow remain unchanged.

## Security and observability

Security ordering remains Validation → Authentication → Authorization → Dispatch.

Capability discovery uses the existing command path and does not modify operational observability boundaries.

## Diagnostics and production observability (v0.1.2)

CLI parsing stays at the entry point. Diagnostics reuse the configuration
provider and delegate Windows inspection to infrastructure, without composing a
host. The vendor API exposes auto-discovery through initialization, which may
launch a terminal; therefore self-check uses an explicitly bounded inventory
instead of calling initialize. See the
[official initialize contract](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py).
Normal runtime selection is unchanged.

Production composition injects LoggingOperationalObservability via the existing
port. NullOperationalObservability remains available for isolated hosts/tests.
The adapter only emits allowlisted lifecycle messages, ignoring arbitrary event
metadata. Concrete MT5 and HTTP infrastructure log initialization/listening and
shutdown details through best-effort standard logging; Core remains isolated.
