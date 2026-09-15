# Contracts — v0.0.8

v0.0.8 preserves all v0.0.7 contracts and adds two transport-neutral runtime protocols.

## AgentLifecyclePort

```python
@runtime_checkable
class AgentLifecyclePort(Protocol):
    def start(self) -> Status: ...
    def stop(self) -> Status: ...
```

Invariants:

- returns existing immutable `Status` values;
- exposes no MT5 implementation details;
- exposes no HTTP, signal, socket, process, or deployment APIs;
- the existing `Agent` satisfies the protocol structurally.

## HostingPort

```python
@runtime_checkable
class HostingPort(Protocol):
    def serve(self) -> None: ...
    def shutdown(self) -> None: ...
```

Invariants:

- `serve()` represents a blocking serving loop;
- `shutdown()` requests graceful termination of an active or pending serving loop;
- no HTTP/server/socket/signal type is part of the contract;
- concrete hosting is injected through the composition root.

## ApplicationHost

`ApplicationHost` is an application service/coordinator, not a Port and not a second domain state machine. `run() -> Status` enforces Agent start → serve → Agent stop ordering and deterministic failure precedence.

No existing Command, Transport, Security, Observability, Configuration, ApplicationPort, or MT5Port contract is broken or replaced.
