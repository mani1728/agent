from typing import Protocol, runtime_checkable


@runtime_checkable
class MT5Port(Protocol):
    """Port required by the agent core for terminal lifecycle operations."""

    def connect(self) -> bool: ...
    def disconnect(self) -> bool: ...
    def is_connected(self) -> bool: ...


@runtime_checkable
class CommandHandler(Protocol):
    """Application handler for a validated command."""

    def __call__(self, command): ...
