from typing import Protocol, runtime_checkable


@runtime_checkable
class MT5Port(Protocol):
    """Port required by the agent core for terminal lifecycle operations."""

    def connect(self) -> bool:
        """Initialize the terminal integration."""

    def disconnect(self) -> bool:
        """Release the terminal integration and report success."""

    def is_connected(self) -> bool:
        """Return whether the terminal is reachable."""
