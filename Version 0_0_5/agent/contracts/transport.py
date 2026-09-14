from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from agent.contracts.models import Command


class TransportValidationError(ValueError):
    """Raised when a transport-neutral request violates its contract."""


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable request context shared across application boundaries."""

    request_id: str
    correlation_id: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class TransportRequest:
    """Transport-neutral ingress envelope for an application command."""

    context: ExecutionContext
    command: Command


@dataclass(frozen=True)
class TransportResponse:
    """Transport-neutral egress envelope produced by the application."""

    request_id: str
    correlation_id: str
    command_id: str
    success: bool
    code: str
    message: str = ""
    data: Any = None


def validate_execution_context(context: ExecutionContext) -> None:
    if not isinstance(context, ExecutionContext):
        raise TransportValidationError("context must be an ExecutionContext instance")
    if not isinstance(context.request_id, str) or not context.request_id.strip():
        raise TransportValidationError("request_id must be a non-empty string")
    if not isinstance(context.correlation_id, str) or not context.correlation_id.strip():
        raise TransportValidationError("correlation_id must be a non-empty string")
    if not isinstance(context.metadata, Mapping):
        raise TransportValidationError("metadata must be a mapping")


def validate_transport_request(request: TransportRequest) -> None:
    if not isinstance(request, TransportRequest):
        raise TransportValidationError("request must be a TransportRequest instance")
    validate_execution_context(request.context)
    if not isinstance(request.command, Command):
        raise TransportValidationError("command must be a Command instance")
    if request.context.correlation_id != request.command.correlation_id:
        raise TransportValidationError("context and command correlation_id must match")
