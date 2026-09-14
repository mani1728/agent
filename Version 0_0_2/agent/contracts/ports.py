from typing import Protocol


class MT5Port(Protocol):
    def connect(self) -> bool:
        """Initialize the terminal integration."""

    def disconnect(self) -> None:
        """Release the terminal integration."""

    def is_connected(self) -> bool:
        """Return whether the terminal is reachable."""
