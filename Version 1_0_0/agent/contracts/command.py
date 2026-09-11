# Path: agent/contracts/command.py

"""Canonical inbound command contract.

Legacy Kafka inbound shape:

    topic:
        cmd.{client_id}.p{0|1|2}

    key:
        b"Mt5_Manager"

    headers:
        corr_id (optional)
        auth_token (optional)

    value:
        {"method": "...", "params": {...}}

    or:

        [
            {"method": "...", "params": {...}},
            {"method": "...", "params": {...}}
        ]

The transport layer is responsible for extracting:

    - target_class
    - priority
    - correlation_id
    - authentication information

This contract intentionally does NOT store auth_token.

Priority comes from the transport/topic and never from the JSON payload.

This module is transport-independent and must not import Kafka, HTTP,
MetaTrader5, requests, or any concrete transport implementation.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Union

from .models import JsonDict
from .schemas import SCHEMA_VERSION_COMMAND, validate_command_schema


# ============================================================================
# Helpers
# ============================================================================


def utcnow_iso() -> str:
    """Return the current UTC time as an RFC 3339-compatible string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_json_dict(value: Any, field_name: str) -> JsonDict:
    """Convert a mapping to a plain dict or raise a descriptive error."""
    if not isinstance(value, Mapping):
        raise ValueError(
            f"{field_name} must be a JSON object (dict), "
            f"got {type(value).__name__!r}"
        )

    return dict(value)


# ============================================================================
# Sensitive fields
# ============================================================================

# These values must never be copied into metadata.
#
# In particular, auth_token belongs to the transport/security layer and is
# intentionally excluded from CommandEnvelope.
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "auth_token",
        "token",
        "password",
        "authorization",
        "secret",
        "api_key",
        "private_key",
    }
)


# ============================================================================
# Known top-level command fields
# ============================================================================

_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "command_id",

        # Target
        "class",
        "target_class",
        "method",
        "target_method",

        # Parameters
        "params",

        # Transport-level priority
        "priority",

        # Correlation
        "correlation_id",
        "corr_id",

        # Timestamp
        "created_at",

        # Schema
        "schema",
        "schema_version",

        # Metadata
        "metadata",

        # Multi-command response correlation
        "request_index",
    }
)


# ============================================================================
# CommandEnvelope
# ============================================================================


@dataclass(frozen=True)
class CommandEnvelope:
    """Canonical transport-independent inbound command.

    Canonical fields
    ----------------
    command_id:
        Unique identifier for this command instance.

    target_class:
        Target class used by the dispatcher.

        Legacy Kafka behavior:
            Kafka message key -> target_class

        Example:
            "Mt5_Manager"

    target_method:
        Method that should be executed.

        Legacy Kafka behavior:
            JSON "method" -> target_method

    params:
        Keyword parameters passed to the target method.

    priority:
        Priority level.

        0 = highest
        1 = normal
        2 = lowest

        IMPORTANT:
            Priority is supplied by the transport layer. For legacy Kafka,
            it is derived from cmd.*.p0/p1/p2.

    correlation_id:
        Identifier used to associate a command with its response.

    created_at:
        RFC 3339 / ISO-8601 UTC timestamp.

    schema_version:
        Contract schema version.

    metadata:
        Non-sensitive metadata associated with the command.

    Security
    --------
    auth_token is deliberately NOT part of this model.

    Authentication information belongs to the transport/security layer and
    must never be copied into metadata.
    """

    command_id: str
    target_class: str
    target_method: str

    params: JsonDict = field(default_factory=dict)

    priority: int = 1

    correlation_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    created_at: str = field(
        default_factory=utcnow_iso
    )

    schema_version: str = SCHEMA_VERSION_COMMAND

    metadata: JsonDict = field(default_factory=dict)

    # ------------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate the command envelope."""

        # --------------------------------------------------------------------
        # Required string fields
        # --------------------------------------------------------------------

        for field_name in (
            "command_id",
            "target_class",
            "target_method",
            "correlation_id",
            "created_at",
            "schema_version",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field_name!r} must be a non-empty string, "
                    f"got {value!r}"
                )

        # --------------------------------------------------------------------
        # Priority
        # --------------------------------------------------------------------
        #
        # bool is technically an int subclass in Python, so explicitly reject
        # True / False.
        # --------------------------------------------------------------------

        if isinstance(self.priority, bool) or not isinstance(
            self.priority,
            int,
        ):
            raise ValueError(
                "priority must be an int (0, 1, or 2)"
            )

        if self.priority not in (0, 1, 2):
            raise ValueError(
                f"priority must be 0, 1, or 2; "
                f"got {self.priority!r}"
            )

        # --------------------------------------------------------------------
        # Params
        # --------------------------------------------------------------------

        if not isinstance(self.params, dict):
            raise ValueError(
                "params must be a JSON object (dict)"
            )

        # --------------------------------------------------------------------
        # Metadata
        # --------------------------------------------------------------------

        if not isinstance(self.metadata, dict):
            raise ValueError(
                "metadata must be a JSON object (dict)"
            )

        # --------------------------------------------------------------------
        # Schema validation
        # --------------------------------------------------------------------

        validate_command_schema(self.schema_version)

    # ------------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------------

    def to_dict(self) -> JsonDict:
        """Return a plain dictionary representation.

        This method performs contract-level serialization only.

        It does not perform transport-specific serialization such as Kafka
        message encoding or HTTP serialization.
        """

        return {
            "command_id": self.command_id,
            "target_class": self.target_class,
            "target_method": self.target_method,
            "params": dict(self.params),
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
        }

    # ------------------------------------------------------------------------
    # Factory: dictionary
    # ------------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        default_target_class: Optional[str] = None,
        priority: int = 1,
        correlation_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "CommandEnvelope":
        """Create a CommandEnvelope from a dictionary.

        Supports both canonical and legacy command shapes.

        Legacy:

            {
                "method": "fetch_data",
                "params": {
                    ...
                }
            }

        Canonical:

            {
                "target_class": "Mt5_Manager",
                "target_method": "fetch_data",
                "params": {
                    ...
                }
            }

        Resolution rules
        ----------------
        target_class:

            1. default_target_class supplied by transport
            2. payload target_class
            3. payload class

        target_method:

            1. target_method
            2. method

        correlation_id:

            1. transport-provided correlation_id
            2. payload correlation_id
            3. payload corr_id
            4. generated UUID

        priority:

            ALWAYS the explicit priority argument.

            payload["priority"] is intentionally ignored.
        """

        source = _as_json_dict(
            value,
            "command dict",
        )

        # --------------------------------------------------------------------
        # Target class
        # --------------------------------------------------------------------

        target_class = (
            default_target_class
            or source.get("target_class")
            or source.get("class")
        )

        if not target_class:
            raise ValueError(
                "command requires target_class — supply it through "
                "default_target_class or as 'target_class'/'class'"
            )

        # --------------------------------------------------------------------
        # Target method
        # --------------------------------------------------------------------

        target_method = (
            source.get("target_method")
            or source.get("method")
        )

        if not target_method:
            raise ValueError(
                "command requires target_method "
                "(or legacy 'method')"
            )

        # --------------------------------------------------------------------
        # Metadata
        # --------------------------------------------------------------------

        source_metadata = _as_json_dict(
            source.get("metadata", {}),
            "metadata",
        )

        # Remove sensitive fields from explicit metadata.
        normalized_metadata = {
            key: item
            for key, item in source_metadata.items()
            if key not in _SENSITIVE_KEYS
        }
        if metadata is not None:
            explicit_metadata = _as_json_dict(
                metadata,
                "metadata",
            )

            normalized_metadata.update(
                {
                    key: item
                    for key, item in explicit_metadata.items()
                    if key not in _SENSITIVE_KEYS
                }
            )

        # --------------------------------------------------------------------
        # Preserve unknown non-sensitive top-level fields as metadata.
        #
        # This provides forward compatibility without leaking secrets.
        # --------------------------------------------------------------------

        for key, item in source.items():

            if key in _KNOWN_KEYS:
                continue

            if key in _SENSITIVE_KEYS:
                continue

            normalized_metadata[key] = item

        # --------------------------------------------------------------------
        # Correlation ID
        # --------------------------------------------------------------------

        resolved_correlation_id = (
            correlation_id
            or source.get("correlation_id")
            or source.get("corr_id")
            or str(uuid.uuid4())
        )

        # --------------------------------------------------------------------
        # Command ID
        # --------------------------------------------------------------------

        command_id = source.get("command_id")

        if not command_id:
            command_id = str(uuid.uuid4())

        # --------------------------------------------------------------------
        # Timestamp
        # --------------------------------------------------------------------

        created_at = source.get("created_at")

        if not created_at:
            created_at = utcnow_iso()

        # --------------------------------------------------------------------
        # Schema version
        # --------------------------------------------------------------------

        schema_version = (
            source.get("schema_version")
            or source.get("schema")
            or SCHEMA_VERSION_COMMAND
        )

        # --------------------------------------------------------------------
        # Build immutable envelope
        # --------------------------------------------------------------------

        return cls(
            command_id=str(command_id),
            target_class=str(target_class),
            target_method=str(target_method),
            params=_as_json_dict(
                source.get("params", {}),
                "params",
            ),
            priority=priority,
            correlation_id=str(resolved_correlation_id),
            created_at=str(created_at),
            schema_version=str(schema_version),
            metadata=normalized_metadata,
        )

    # ------------------------------------------------------------------------
    # Factory: JSON
    # ------------------------------------------------------------------------

    @classmethod
    def from_json(
        cls,
        value: Union[str, bytes],
        *,
        default_target_class: Optional[str] = None,
        priority: int = 1,
        correlation_id: Optional[str] = None,
    ) -> "CommandEnvelope":
        """Create a single CommandEnvelope from JSON.

        The JSON payload must represent one object.

        Batch/list payloads should be handled by
        :meth:`from_legacy_message`.
        """

        try:
            raw = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"invalid command JSON: {exc}"
            ) from exc

        if not isinstance(raw, Mapping):
            raise ValueError(
                "command JSON must be a single JSON object, "
                "not a list or scalar"
            )

        return cls.from_dict(
            raw,
            default_target_class=default_target_class,
            priority=priority,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------------
    # Factory: Legacy Kafka message
    # ------------------------------------------------------------------------

    @classmethod
    def from_legacy_message(
        cls,
        value: Any,
        *,
        target_class: str,
        priority: int = 1,
        correlation_id: Optional[str] = None,
    ) -> list["CommandEnvelope"]:
        """Convert a legacy Kafka message into command envelopes.

        Legacy Kafka supports:

            {
                "method": "...",
                "params": {...}
            }

        or:

            [
                {
                    "method": "...",
                    "params": {...}
                },
                {
                    "method": "...",
                    "params": {...}
                }
            ]

        Each item becomes an independent CommandEnvelope.

        For multi-command messages, request_index is stored in metadata so
        the response layer can preserve the original request order.
        """

        # --------------------------------------------------------------------
        # Validate transport-provided target class
        # --------------------------------------------------------------------

        if not isinstance(target_class, str) or not target_class.strip():
            raise ValueError(
                "target_class must be a non-empty string"
            )

        # --------------------------------------------------------------------
        # Normalize single command -> list of commands
        # --------------------------------------------------------------------

        items: Iterable[Any]

        if isinstance(value, list):
            items = value
        else:
            items = [value]

        envelopes: list[CommandEnvelope] = []

        # --------------------------------------------------------------------
        # Convert each command
        # --------------------------------------------------------------------

        for index, item in enumerate(items):

            if not isinstance(item, Mapping):
                raise ValueError(
                    f"command list item at index {index} must be "
                    f"a JSON object, got {type(item).__name__!r}"
                )

            item_with_index = dict(item)

            # Preserve an explicitly supplied request_index.
            item_with_index.setdefault(
                "request_index",
                index,
            )

            envelopes.append(
                cls.from_dict(
                    item_with_index,
                    default_target_class=target_class,
                    priority=priority,
                    correlation_id=correlation_id,
                )
            )

        return envelopes

    # ------------------------------------------------------------------------
    # Factory: Legacy single item
    # ------------------------------------------------------------------------

    @classmethod
    def from_legacy_item(
        cls,
        item: Mapping[str, Any],
        *,
        target_class: str,
        priority: int = 1,
        correlation_id: Optional[str] = None,
    ) -> "CommandEnvelope":
        """Convert one legacy command item into an envelope."""

        return cls.from_dict(
            item,
            default_target_class=target_class,
            priority=priority,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------------
    # Immutable update helper
    # ------------------------------------------------------------------------

    def _with_correlation_id(
        self,
        correlation_id: Optional[str],
    ) -> "CommandEnvelope":
        """Return a copy with a different correlation ID.

        Because the dataclass is frozen, dataclasses.replace() is used.
        """

        if not correlation_id:
            return self

        return replace(
            self,
            correlation_id=str(correlation_id),
        )
