from typing import Protocol, runtime_checkable

from agent.contracts.models import Command
from agent.contracts.observability import ExecutionEvent
from agent.contracts.security import Authenticator, Authorizer
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


@runtime_checkable
class AuthenticationPort(Authenticator, Protocol):
    """Application security port for authentication."""


@runtime_checkable
class AuthorizationPort(Authorizer, Protocol):
    """Application security port for command authorization."""


@runtime_checkable
class ObservabilityPort(Protocol):
    """Port for recording transport-neutral execution events."""

    def record(self, event: ExecutionEvent) -> None: ...
