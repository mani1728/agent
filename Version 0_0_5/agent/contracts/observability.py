from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


class ExecutionEventType(str, Enum):
    REQUEST_RECEIVED = "request_received"
    REQUEST_REJECTED = "request_rejected"
    AUTHENTICATION_COMPLETED = "authentication_completed"
    AUTHORIZATION_COMPLETED = "authorization_completed"
    COMMAND_DISPATCHED = "command_dispatched"
    REQUEST_COMPLETED = "request_completed"


@dataclass(frozen=True)
class ExecutionEvent:
    """Immutable, transport-neutral execution telemetry event."""

    event_id: str
    event_type: ExecutionEventType
    request_id: str
    correlation_id: str
    command_id: str
    timestamp: str
    outcome: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("event_id", "request_id", "correlation_id", "timestamp", "outcome"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def now(
        cls,
        event_id: str,
        event_type: ExecutionEventType,
        request_id: str,
        correlation_id: str,
        command_id: str,
        outcome: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ExecutionEvent":
        return cls(
            event_id=event_id,
            event_type=event_type,
            request_id=request_id,
            correlation_id=correlation_id,
            command_id=command_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            outcome=outcome,
            metadata=metadata or {},
        )


@runtime_checkable
class ObservabilityPort(Protocol):
    """Port for recording application execution events."""

    def record(self, event: ExecutionEvent) -> None: ...


class NullObservability:
    """Safe default adapter that intentionally discards events."""

    def record(self, event: ExecutionEvent) -> None:
        return None
