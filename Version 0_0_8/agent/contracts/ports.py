from typing import Protocol, runtime_checkable

from agent.contracts.models import Command, Status
from agent.contracts.observability import ExecutionEvent
from agent.contracts.security import Authenticator, Authorizer
from agent.contracts.transport import TransportRequest, TransportResponse


@runtime_checkable
class MT5Port(Protocol):
    def connect(self) -> bool: ...
    def disconnect(self) -> bool: ...
    def is_connected(self) -> bool: ...


@runtime_checkable
class CommandHandler(Protocol):
    def __call__(self, command: Command): ...


@runtime_checkable
class ApplicationPort(Protocol):
    def handle(self, request: TransportRequest) -> TransportResponse: ...


@runtime_checkable
class AuthenticationPort(Authenticator, Protocol):
    pass


@runtime_checkable
class AuthorizationPort(Authorizer, Protocol):
    pass


@runtime_checkable
class ObservabilityPort(Protocol):
    def record(self, event: ExecutionEvent) -> None: ...


@runtime_checkable
class AgentLifecyclePort(Protocol):
    """Transport-neutral lifecycle boundary required by the application host."""

    def start(self) -> Status:
        """Start the agent runtime and return a deterministic status."""
        ...

    def stop(self) -> Status:
        """Stop the agent runtime and return a deterministic status."""
        ...


@runtime_checkable
class HostingPort(Protocol):
    """Blocking hosting boundary independent of HTTP, sockets, and process APIs."""

    def serve(self) -> None:
        """Serve until graceful shutdown is requested or hosting fails."""
        ...

    def shutdown(self) -> None:
        """Request graceful termination of an active serving loop."""
        ...
