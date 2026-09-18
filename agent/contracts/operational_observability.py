from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


class OperationalEventType(str, Enum):
    APPLICATION_STARTING = "application_starting"
    APPLICATION_STARTED = "application_started"
    APPLICATION_START_FAILED = "application_start_failed"
    HOSTING_STARTED = "hosting_started"
    HOSTING_FAILED = "hosting_failed"
    APPLICATION_STOPPING = "application_stopping"
    APPLICATION_STOPPED = "application_stopped"
    APPLICATION_STOP_FAILED = "application_stop_failed"


@dataclass(frozen=True)
class OperationalEvent:
    event_id: str
    event_type: OperationalEventType
    timestamp: str
    source: str
    outcome: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("event_id", "timestamp", "source", "outcome"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def now(cls, event_id: str, event_type: OperationalEventType,
            source: str, outcome: str,
            metadata: Mapping[str, Any] | None = None) -> "OperationalEvent":
        return cls(
            event_id,
            event_type,
            datetime.now(timezone.utc).isoformat(),
            source,
            outcome,
            metadata or {},
        )


@runtime_checkable
class OperationalObservabilityPort(Protocol):
    def record(self, event: OperationalEvent) -> None: ...


class NullOperationalObservability:
    def record(self, event: OperationalEvent) -> None:
        return None
