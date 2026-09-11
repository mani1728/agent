# Path: agent/contracts/heartbeat.py

"""Transport-independent agent heartbeat contract.

This module defines the canonical heartbeat payload shared by the Agent
core and all transport implementations.

The heartbeat contract is intentionally independent of Kafka, HTTP,
MetaTrader 5, or any other transport/infrastructure implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Union

from .command import utcnow_iso
from .models import JsonDict
from .schemas import (
    SCHEMA_VERSION_HEARTBEAT,
    validate_heartbeat_schema,
)


class HeartbeatStatus(str, Enum):
    """Supported agent health states."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


def _sanitize_details(value: Mapping[str, Any]) -> JsonDict:
    """Remove sensitive fields from heartbeat diagnostic details.

    Heartbeats may eventually contain diagnostic metadata. Secrets,
    authentication tokens, passwords, and private keys must never be
    serialized as part of the heartbeat contract.
    """

    sensitive_keys = {
        "auth_token",
        "access_token",
        "refresh_token",
        "authorization",
        "token",
        "password",
        "secret",
        "api_key",
        "private_key",
    }

    sanitized: JsonDict = {}

    for key, item in value.items():
        normalized_key = str(key).lower()

        if normalized_key in sensitive_keys:
            continue

        if isinstance(item, Mapping):
            sanitized[key] = _sanitize_details(item)
        elif isinstance(item, list):
            sanitized[key] = [
                (
                    _sanitize_details(entry)
                    if isinstance(entry, Mapping)
                    else entry
                )
                for entry in item
            ]
        else:
            sanitized[key] = item

    return sanitized


@dataclass(frozen=True)
class HeartbeatPayload:
    """Transport-independent heartbeat payload.

    Parameters
    ----------
    agent_id:
        Unique identifier of the agent sending the heartbeat.

    status:
        Agent health state. Either a ``HeartbeatStatus`` enum or one of
        its string values.

    timestamp:
        UTC timestamp. Generated automatically when omitted.

    schema_version:
        Heartbeat contract schema version.

    details:
        Optional JSON-compatible diagnostic information.

    Notes
    -----
    This class contains only transport-independent health information.
    Transport-specific metadata must be handled by the transport layer.
    """

    agent_id: str
    status: Union[HeartbeatStatus, str]
    timestamp: str = field(default_factory=utcnow_iso)
    schema_version: str = SCHEMA_VERSION_HEARTBEAT
    details: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize the heartbeat payload."""

        # --------------------------------------------------------------
        # agent_id
        # --------------------------------------------------------------
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")

        # --------------------------------------------------------------
        # status
        # --------------------------------------------------------------
        try:
            normalized_status = HeartbeatStatus(self.status)
        except (TypeError, ValueError) as exc:
            valid_values = ", ".join(
                status.value for status in HeartbeatStatus
            )

            raise ValueError(
                f"status must be one of: {valid_values}; "
                f"got {self.status!r}"
            ) from exc

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )

        # --------------------------------------------------------------
        # timestamp
        # --------------------------------------------------------------
        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValueError("timestamp must be a non-empty string")

        # --------------------------------------------------------------
        # schema_version
        # --------------------------------------------------------------
        if (
            not isinstance(self.schema_version, str)
            or not self.schema_version.strip()
        ):
            raise ValueError(
                "schema_version must be a non-empty string"
            )

        # --------------------------------------------------------------
        # details
        # --------------------------------------------------------------
        if not isinstance(self.details, dict):
            raise ValueError("details must be an object")

        # Remove sensitive information before the object can be
        # serialized or transported.
        object.__setattr__(
            self,
            "details",
            _sanitize_details(self.details),
        )

        # --------------------------------------------------------------
        # Contract schema validation
        # --------------------------------------------------------------
        validate_heartbeat_schema(self.schema_version)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "HeartbeatPayload":
        """Create a heartbeat payload from a dictionary.

        Both canonical field names and a small set of safe compatibility
        aliases are accepted where useful.
        """

        if not isinstance(payload, Mapping):
            raise ValueError("heartbeat payload must be an object")

        agent_id = payload.get("agent_id")

        status = payload.get("status")

        timestamp = payload.get("timestamp")

        schema_version = payload.get(
            "schema_version",
            (
                payload.get("schema")
                if isinstance(payload, Mapping)
                else None
            )
            or SCHEMA_VERSION_HEARTBEAT,
        )

        details = payload.get(
            "details",
            {},
        )

        if not isinstance(details, Mapping):
            raise ValueError("details must be an object")

        return cls(
            agent_id=agent_id,
            status=status,
            timestamp=timestamp or utcnow_iso(),
            schema_version=schema_version,
            details=dict(details),
        )

    @classmethod
    def from_json(
        cls,
        payload: str,
    ) -> "HeartbeatPayload":
        """Create a heartbeat payload from a JSON string."""

        try:
            decoded = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "invalid heartbeat JSON payload"
            ) from exc

        if not isinstance(decoded, Mapping):
            raise ValueError(
                "heartbeat JSON payload must contain an object"
            )

        return cls.from_dict(decoded)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> JsonDict:
        """Serialize the heartbeat payload to a plain dictionary."""

        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    def to_json(self) -> str:
        """Serialize the heartbeat payload to compact JSON."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        )
