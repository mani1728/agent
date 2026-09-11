# Path: Version 1_0_0/agent/health/heartbeat.py

"""Agent heartbeat management.

Provides a small, transport-independent heartbeat manager for reporting
the Agent's current operational state.

This module does not perform Kafka/HTTP communication directly. The caller
provides a publisher callback when heartbeat delivery is required.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional


class HeartbeatStatus(str, Enum):
    """Operational status reported by the Agent."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HeartbeatPayload:
    """Serializable heartbeat payload."""

    client_id: str
    status: HeartbeatStatus
    timestamp: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "HeartbeatV1",
            "client_id": self.client_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }

    @classmethod
    def create(
        cls,
        client_id: str,
        status: HeartbeatStatus = HeartbeatStatus.READY,
        details: Optional[Mapping[str, Any]] = None,
    ) -> "HeartbeatPayload":
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be a non-empty string")

        return cls(
            client_id=client_id.strip(),
            status=(
                status
                if isinstance(status, HeartbeatStatus)
                else HeartbeatStatus(str(status))
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=dict(details or {}),
        )


HeartbeatPublisher = Callable[[HeartbeatPayload], Any]


class HeartbeatManager:
    """Thread-safe heartbeat state manager."""

    def __init__(
        self,
        client_id: str,
        publisher: Optional[HeartbeatPublisher] = None,
    ) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be a non-empty string")

        self._client_id = client_id.strip()
        self._publisher = publisher
        self._lock = threading.RLock()

        self._status = HeartbeatStatus.READY
        self._details: dict[str, Any] = {}
        self._last_payload: Optional[HeartbeatPayload] = None

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def status(self) -> HeartbeatStatus:
        with self._lock:
            return self._status

    @property
    def last_payload(self) -> Optional[HeartbeatPayload]:
        with self._lock:
            return self._last_payload

    def set_status(
        self,
        status: HeartbeatStatus,
        *,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not isinstance(status, HeartbeatStatus):
            status = HeartbeatStatus(str(status))

        with self._lock:
            self._status = status

            if details is not None:
                self._details = dict(details)

    def update_details(
        self,
        details: Mapping[str, Any],
    ) -> None:
        if not isinstance(details, Mapping):
            raise TypeError("details must be a mapping")

        with self._lock:
            self._details.update(details)

    def clear_details(self) -> None:
        with self._lock:
            self._details.clear()

    def build_payload(self) -> HeartbeatPayload:
        with self._lock:
            payload = HeartbeatPayload.create(
                client_id=self._client_id,
                status=self._status,
                details=self._details,
            )

            self._last_payload = payload

            return payload

    def publish(self) -> HeartbeatPayload:
        """
        Build and publish the current heartbeat.

        Raises RuntimeError when no publisher has been configured.
        """
        if self._publisher is None:
            raise RuntimeError(
                "Heartbeat publisher is not configured"
            )

        payload = self.build_payload()
        self._publisher(payload)

        return payload

    def set_publisher(
        self,
        publisher: Optional[HeartbeatPublisher],
    ) -> None:
        if publisher is not None and not callable(publisher):
            raise TypeError("publisher must be callable or None")

        with self._lock:
            self._publisher = publisher

    def snapshot(self) -> dict[str, Any]:
        """Return the current heartbeat state."""
        payload = self.build_payload()
        return payload.to_dict()


__all__ = [
    "HeartbeatManager",
    "HeartbeatPayload",
    "HeartbeatStatus",
]