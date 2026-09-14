from dataclasses import dataclass
from enum import Enum


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
    version: str = "0.0.2"
