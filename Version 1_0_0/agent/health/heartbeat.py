"""Health heartbeat compatibility module.

This module preserves the historical ``HeartbeatPayload``/``HeartbeatStatus``
API used by legacy health utilities while internally aligning with the
canonical contract payload from ``agent.contracts.heartbeat``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from agent.contracts.heartbeat import (
    HeartbeatPayload as ContractHeartbeatPayload,
    HeartbeatStatus as ContractHeartbeatStatus,
)


HeartbeatStatus = ContractHeartbeatStatus


@dataclass(frozen=True)
class HeartbeatPayload:
    """Compatibility heartbeat payload using historical ``client_id`` naming."""

    client_id: str
    status: HeartbeatStatus
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, str) or not self.client_id.strip():
            raise ValueError("client_id must be a non-empty string")

        object.__setattr__(
            self,
            "client_id",
            self.client_id.strip(),
        )

        normalized_status = (
            self.status
            if isinstance(self.status, HeartbeatStatus)
            else HeartbeatStatus(str(self.status))
        )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )

        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValueError("timestamp must be a non-empty string")

        if not isinstance(self.details, Mapping):
            raise TypeError("details must be a mapping")

    @property
    def agent_id(self) -> str:
        """Canonical heartbeat identifier alias."""
        return self.client_id

    @classmethod
    def create(
        cls,
        client_id: str,
        status: HeartbeatStatus = HeartbeatStatus.READY,
        details: Optional[Mapping[str, Any]] = None,
    ) -> "HeartbeatPayload":
        return cls(
            client_id=client_id,
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=dict(details or {}),
        )

    def to_contract(self) -> ContractHeartbeatPayload:
        """Return the canonical contract payload for transport consumption."""
        return ContractHeartbeatPayload(
            agent_id=self.client_id,
            status=self.status,
            timestamp=self.timestamp,
            details=dict(self.details),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the legacy heartbeat payload dictionary."""
        return {
            "schema": "HeartbeatV1",
            "client_id": self.client_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }


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
        """Build and publish the current heartbeat."""
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
        """Return the current heartbeat state as a legacy payload dict."""
        payload = self.build_payload()
        return payload.to_dict()


__all__ = [
    "HeartbeatManager",
    "HeartbeatPayload",
    "HeartbeatStatus",
]
