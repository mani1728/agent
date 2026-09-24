"""Deterministic command lifecycle, expiry and safe cancellation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable


class CommandState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"


class RequestedPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BULK = "bulk"


_TERMINAL = frozenset({CommandState.SUCCEEDED, CommandState.FAILED, CommandState.EXPIRED,
                       CommandState.CANCELLED, CommandState.AMBIGUOUS})
_ALLOWED = {
    CommandState.RECEIVED: {CommandState.VALIDATED, CommandState.EXPIRED, CommandState.CANCELLED},
    CommandState.VALIDATED: {CommandState.QUEUED, CommandState.EXPIRED, CommandState.CANCELLED},
    CommandState.QUEUED: {CommandState.RUNNING, CommandState.EXPIRED, CommandState.CANCELLED},
    CommandState.RUNNING: {CommandState.SUCCEEDED, CommandState.FAILED, CommandState.AMBIGUOUS},
}


def parse_utc(value: datetime | str) -> datetime:
    value = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CommandLifecycle:
    server_command_id: str
    command_identifier: str
    command_version: str
    received_at: datetime
    expires_at: datetime | None = None
    requested_priority: RequestedPriority = RequestedPriority.NORMAL
    state: CommandState = CommandState.RECEIVED
    point_of_no_return: bool = False

    def __post_init__(self) -> None:
        for field in (self.server_command_id, self.command_identifier, self.command_version):
            if not isinstance(field, str) or not field.strip():
                raise ValueError("command identity must be non-empty")
        object.__setattr__(self, "received_at", parse_utc(self.received_at))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", parse_utc(self.expires_at))

    @classmethod
    def with_ttl(cls, *, ttl: timedelta | None, default_ttl: timedelta | None = None, **kwargs):
        chosen = ttl if ttl is not None else default_ttl
        received_at = parse_utc(kwargs["received_at"])
        return cls(expires_at=received_at + chosen if chosen is not None else None, **kwargs)

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and parse_utc(now) >= self.expires_at

    def transition(self, target: CommandState, now: datetime) -> "CommandLifecycle":
        if self.state in _TERMINAL or target not in _ALLOWED.get(self.state, set()):
            raise ValueError("INVALID_STATE_TRANSITION")
        if target is CommandState.RUNNING and self.is_expired(now):
            return self._replace(CommandState.EXPIRED)
        return self._replace(target)

    def cancel(self) -> "CommandLifecycle":
        if self.state in (CommandState.RECEIVED, CommandState.VALIDATED, CommandState.QUEUED):
            return self._replace(CommandState.CANCELLED)
        if self.state is CommandState.RUNNING and not self.point_of_no_return:
            return self._replace(CommandState.CANCELLED)
        raise ValueError("COMMAND_CANCELLED")

    def mark_point_of_no_return(self) -> "CommandLifecycle":
        if self.state is not CommandState.RUNNING:
            raise ValueError("INVALID_STATE_TRANSITION")
        return CommandLifecycle(**{**self.__dict__, "point_of_no_return": True})

    def _replace(self, state: CommandState) -> "CommandLifecycle":
        return CommandLifecycle(**{**self.__dict__, "state": state})
