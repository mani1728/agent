from typing import Protocol, runtime_checkable

from agent.contracts.models import Command
from agent.contracts.transport import TransportRequest, TransportResponse


@runtime_checkable
class MT5Port(Protocol):
    """Port required by the agent core for terminal lifecycle operations."""

    def connect(self) -> bool: ...
    def disconnect(self) -> bool: ...
    def is_connected(self) -> bool: ...


@runtime_checkable
class CommandHandler(Protocol):
    """Application handler for a validated command."""

    def __call__(self, command: Command): ...


@runtime_checkable
class ApplicationPort(Protocol):
    """Port exposed by the application to future transport adapters."""

    def handle(self, request: TransportRequest) -> TransportResponse: ...
