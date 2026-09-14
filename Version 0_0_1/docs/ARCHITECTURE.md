# v0.0.1 Architecture

## Design objective

The architecture of v0.0.1 is intentionally small. Its purpose is to establish a testable boundary between the agent core and MetaTrader 5 before adding trading, transport, persistence, or service concerns.

## Runtime flow

```text
┌───────────────┐
│   agent.main  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│     Agent     │
│   core/agent  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  MT5Adapter   │
│ adapters/mt5  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ MetaTrader 5  │
└───────────────┘
```

## Responsibilities

### `agent/main.py`

Application entry-point logic. Starts the agent, reports the status, and guarantees shutdown after the lifecycle completes.

### `agent/core/agent.py`

Owns the agent lifecycle. It depends on the adapter abstraction rather than directly coupling the core to the MetaTrader 5 Python module.

### `agent/adapters/mt5_adapter.py`

Contains the only direct dependency on `MetaTrader5`. It provides three operations:

- `connect()` — initialize the MT5 integration.
- `disconnect()` — shut down the integration.
- `is_connected()` — check terminal information availability.

### `agent/contracts/models.py`

Defines the immutable `Status` result object used across the minimal lifecycle.

### `agent/health/health.py`

Provides a small readiness-oriented helper around `Agent.is_ready()`.

### `agent/transport/local.py`

Defines the minimal local status output boundary. It is deliberately not a network transport.

## Testability

The core accepts an optional adapter instance:

```python
Agent(mt5_adapter=fake_adapter)
```

Tests therefore replace the real MT5 integration with a deterministic fake adapter. This keeps unit tests independent of terminal availability and makes connection success/failure behavior directly testable.

## Failure semantics

Connection failure is represented by `Status(ok=False, ...)` and by process exit code `1` in the application entry point. A successful lifecycle returns exit code `0`.

## Architectural boundary for future versions

Later versions may add strategy, execution, transport, persistence, security, and service-hosting layers. These should be introduced behind explicit interfaces rather than bypassing the `Agent`/adapter boundary established here.
