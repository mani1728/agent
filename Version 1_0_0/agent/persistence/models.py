# Path: Version 1_0_0/agent/persistence/models.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional


class SpoolMessageType(str, Enum):
    COMMAND = "command"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"


class SpoolStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    DEAD = "dead"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_datetime(
    value: datetime,
    field_name: str,
) -> None:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be a datetime."
        )

    if value.tzinfo is None:
        raise ValueError(
            f"{field_name} must be timezone-aware."
        )


@dataclass
class SpoolMessage:
    """
    Transport-independent persisted message.

    This model intentionally contains no SQLite or transport-specific
    behavior. Persistence implementations can map it to their own storage.
    """

    message_id: str
    correlation_id: Optional[str]
    message_type: SpoolMessageType
    payload: Any

    status: SpoolStatus = SpoolStatus.PENDING
    attempt_count: int = 0
    next_retry_time: Optional[datetime] = None

    created_time: datetime = field(
        default_factory=_utc_now
    )
    updated_time: datetime = field(
        default_factory=_utc_now
    )

    last_error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, str):
            raise TypeError(
                "message_id must be a string."
            )

        if not self.message_id.strip():
            raise ValueError(
                "message_id cannot be empty."
            )

        if self.correlation_id is not None:
            if not isinstance(self.correlation_id, str):
                raise TypeError(
                    "correlation_id must be a string or None."
                )

        if not isinstance(
            self.message_type,
            SpoolMessageType,
        ):
            self.message_type = SpoolMessageType(
                self.message_type
            )

        if not isinstance(
            self.status,
            SpoolStatus,
        ):
            self.status = SpoolStatus(
                self.status
            )

        if not isinstance(self.attempt_count, int):
            raise TypeError(
                "attempt_count must be an integer."
            )

        if self.attempt_count < 0:
            raise ValueError(
                "attempt_count cannot be negative."
            )

        _validate_datetime(
            self.created_time,
            "created_time",
        )

        _validate_datetime(
            self.updated_time,
            "updated_time",
        )

        if self.next_retry_time is not None:
            _validate_datetime(
                self.next_retry_time,
                "next_retry_time",
            )

    def mark_processing(self) -> None:
        self.status = SpoolStatus.PROCESSING
        self.updated_time = _utc_now()

    def mark_sent(self) -> None:
        self.status = SpoolStatus.SENT
        self.updated_time = _utc_now()
        self.last_error = None

    def mark_failed(
        self,
        error: Optional[str] = None,
        *,
        next_retry_time: Optional[datetime] = None,
    ) -> None:
        self.status = SpoolStatus.FAILED
        self.attempt_count += 1
        self.next_retry_time = next_retry_time
        self.last_error = error
        self.updated_time = _utc_now()

    def mark_dead(
        self,
        error: Optional[str] = None,
    ) -> None:
        self.status = SpoolStatus.DEAD
        self.last_error = error
        self.updated_time = _utc_now()

    def is_pending(self) -> bool:
        return self.status == SpoolStatus.PENDING

    def is_processing(self) -> bool:
        return self.status == SpoolStatus.PROCESSING

    def is_sent(self) -> bool:
        return self.status == SpoolStatus.SENT

    def is_failed(self) -> bool:
        return self.status == SpoolStatus.FAILED

    def is_dead(self) -> bool:
        return self.status == SpoolStatus.DEAD

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "next_retry_time": (
                self.next_retry_time.isoformat()
                if self.next_retry_time is not None
                else None
            ),
            "created_time": self.created_time.isoformat(),
            "updated_time": self.updated_time.isoformat(),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "SpoolMessage":
        if not isinstance(data, Mapping):
            raise TypeError(
                "SpoolMessage data must be a mapping."
            )

        return cls(
            message_id=str(data["message_id"]),
            correlation_id=(
                str(data["correlation_id"])
                if data.get("correlation_id") is not None
                else None
            ),
            message_type=SpoolMessageType(
                data["message_type"]
            ),
            payload=data.get("payload"),
            status=SpoolStatus(
                data.get(
                    "status",
                    SpoolStatus.PENDING.value,
                )
            ),
            attempt_count=int(
                data.get("attempt_count", 0)
            ),
            next_retry_time=_parse_datetime(
                data.get("next_retry_time")
            ),
            created_time=_parse_datetime(
                data.get("created_time")
            ) or _utc_now(),
            updated_time=_parse_datetime(
                data.get("updated_time")
            ) or _utc_now(),
            last_error=(
                str(data["last_error"])
                if data.get("last_error") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class SpoolQuery:
    """
    Query parameters for persistence implementations.

    This is intentionally storage-agnostic.
    """

    status: Optional[SpoolStatus] = None
    message_type: Optional[SpoolMessageType] = None
    correlation_id: Optional[str] = None
    limit: int = 100
    before: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.status is not None and not isinstance(
            self.status,
            SpoolStatus,
        ):
            object.__setattr__(
                self,
                "status",
                SpoolStatus(self.status),
            )

        if (
            self.message_type is not None
            and not isinstance(
                self.message_type,
                SpoolMessageType,
            )
        ):
            object.__setattr__(
                self,
                "message_type",
                SpoolMessageType(self.message_type),
            )

        if self.limit < 1:
            raise ValueError(
                "limit must be >= 1."
            )

        if self.before is not None:
            _validate_datetime(
                self.before,
                "before",
            )


def _parse_datetime(
    value: Any,
) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        _validate_datetime(
            value,
            "datetime",
        )
        return value

    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            raise ValueError(
                "Persisted datetime must include timezone information."
            )

        return parsed

    raise TypeError(
        "Datetime value must be datetime, ISO string, or None."
    )


__all__ = [
    "SpoolMessage",
    "SpoolMessageType",
    "SpoolStatus",
    "SpoolQuery",
]