from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class LifecycleState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class Status:
    ok: bool
    message: str = ""
    code: str = ""


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    state: LifecycleState
    message: str


@dataclass(frozen=True)
class AgentConfig:
    app_name: str = "Trading Agent"
    version: str = "0.0.4"


@dataclass(frozen=True)
class Command:
    command_id: str
    command_type: str
    schema_version: str
    correlation_id: str
    timestamp: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.payload, Mapping):
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    correlation_id: str
    success: bool
    code: str
    message: str = ""
    data: Any = None
