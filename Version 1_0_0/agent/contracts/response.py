# Path: agent/contracts/response.py

"""Canonical outbound response contract.

This module defines the transport-independent response envelope used by the
Agent application.

Canonical response shape:

    correlation_id
    status
    data
    error_code
    error_message
    schema_version
    seq
    total
    timestamp
    metadata

Legacy Mt5ResultV1 compatibility:

    corr_id
    status = "ok" | "error"
    result
    schema
    meta

The contract is intentionally independent from Kafka, HTTP, MetaTrader5,
requests, and any concrete transport implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Optional, Union

from .command import utcnow_iso
from .models import JsonDict
from .schemas import (
    SCHEMA_VERSION_RESPONSE,
    validate_response_schema,
)


# ============================================================================
# Response status
# ============================================================================


class ResponseStatus(str, Enum):
    """Supported canonical response states."""

    OK = "ok"
    ERROR = "error"


# ============================================================================
# Sensitive metadata
# ============================================================================


_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "auth_token",
        "token",
        "authorization",
        "password",
        "secret",
        "api_key",
        "private_key",
        "access_token",
        "refresh_token",
    }
)


def _sanitize_metadata(
    value: Mapping[str, Any],
) -> JsonDict:
    """Remove sensitive fields from response metadata."""

    return {
        key: item
        for key, item in value.items()
        if key not in _SENSITIVE_KEYS
    }


# ============================================================================
# Response envelope
# ============================================================================


@dataclass(frozen=True)
class ResponseEnvelope:
    """Canonical transport-independent outbound response.

    Parameters
    ----------
    correlation_id:
        Correlation identifier used to associate the response with its
        originating command.

    status:
        Canonical response state.

        Supported values:

            "ok"
            "error"

    data:
        Response payload.

        The exact shape is intentionally not restricted because MT5
        operations can return many different data structures.

    error_code:
        Optional machine-readable error identifier.

    error_message:
        Optional human-readable error description.

    schema_version:
        Response contract schema version.

    seq:
        Zero-based sequence number for a chunked response.

        A normal, non-chunked response uses:

            seq = 0
            total = 1

    total:
        Total number of response chunks.

    timestamp:
        UTC response creation timestamp.

    metadata:
        Additional non-sensitive response metadata.

        Legacy metadata such as:

            elapsed_ms
            in_headers
            src_partition
            src_offset
            request_index

        may be carried here.

    Legacy compatibility
    ---------------------
    ``Mt5ResultV1`` compatibility is provided through ``from_dict()`` and
    ``to_legacy_dict()``.

    Legacy mappings:

        corr_id  -> correlation_id
        result   -> data
        schema   -> schema_version
        meta     -> metadata

    Security
    --------
    Authentication credentials and secrets must never be stored in this
    envelope or copied into metadata.
    """

    correlation_id: str

    status: Union[ResponseStatus, str] = ResponseStatus.OK

    data: Any = None

    error_code: Optional[str] = None
    error_message: Optional[str] = None

    schema_version: str = SCHEMA_VERSION_RESPONSE

    seq: int = 0
    total: int = 1

    timestamp: str = field(
        default_factory=utcnow_iso
    )

    metadata: JsonDict = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate and normalize the response envelope."""

        # --------------------------------------------------------------------
        # correlation_id
        # --------------------------------------------------------------------

        if (
            not isinstance(self.correlation_id, str)
            or not self.correlation_id.strip()
        ):
            raise ValueError(
                "correlation_id must be a non-empty string"
            )

        # --------------------------------------------------------------------
        # status
        #
        # Accept both:
        #
        #     ResponseStatus.OK
        #     "ok"
        #
        # and:
        #
        #     ResponseStatus.ERROR
        #     "error"
        # --------------------------------------------------------------------

        try:
            normalized_status = ResponseStatus(
                self.status
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "status must be 'ok' or 'error'"
            ) from exc

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )

        # --------------------------------------------------------------------
        # seq / total
        #
        # bool is an int subclass in Python, so explicitly reject it.
        # --------------------------------------------------------------------

        if (
            isinstance(self.seq, bool)
            or not isinstance(self.seq, int)
        ):
            raise ValueError(
                "seq must be an integer"
            )

        if (
            isinstance(self.total, bool)
            or not isinstance(self.total, int)
        ):
            raise ValueError(
                "total must be an integer"
            )

        if self.seq < 0:
            raise ValueError(
                "seq must be >= 0"
            )

        if self.total < 1:
            raise ValueError(
                "total must be >= 1"
            )

        if self.seq >= self.total:
            raise ValueError(
                "seq must be smaller than total"
            )

        # --------------------------------------------------------------------
        # timestamp
        # --------------------------------------------------------------------

        if (
            not isinstance(self.timestamp, str)
            or not self.timestamp.strip()
        ):
            raise ValueError(
                "timestamp must be a non-empty string"
            )

        # --------------------------------------------------------------------
        # schema_version
        # --------------------------------------------------------------------

        if (
            not isinstance(self.schema_version, str)
            or not self.schema_version.strip()
        ):
            raise ValueError(
                "schema_version must be a non-empty string"
            )

        # --------------------------------------------------------------------
        # metadata
        # --------------------------------------------------------------------

        if not isinstance(self.metadata, dict):
            raise ValueError(
                "metadata must be a JSON object (dict)"
            )

        # --------------------------------------------------------------------
        # Error fields
        # --------------------------------------------------------------------

        if self.error_code is not None:
            if not isinstance(self.error_code, str):
                raise ValueError(
                    "error_code must be None or a string"
                )

            if not self.error_code.strip():
                object.__setattr__(
                    self,
                    "error_code",
                    None,
                )

        if self.error_message is not None:
            if not isinstance(self.error_message, str):
                raise ValueError(
                    "error_message must be None or a string"
                )

            if not self.error_message.strip():
                object.__setattr__(
                    self,
                    "error_message",
                    None,
                )

        # --------------------------------------------------------------------
        # Successful response cannot carry error information.
        # --------------------------------------------------------------------

        if self.status is ResponseStatus.OK:
            if self.error_code is not None:
                raise ValueError(
                    "an 'ok' response cannot include error_code"
                )

            if self.error_message is not None:
                raise ValueError(
                    "an 'ok' response cannot include error_message"
                )

        # --------------------------------------------------------------------
        # Sanitize metadata
        # --------------------------------------------------------------------

        sanitized_metadata = _sanitize_metadata(
            self.metadata
        )

        if sanitized_metadata != self.metadata:
            object.__setattr__(
                self,
                "metadata",
                sanitized_metadata,
            )

        # --------------------------------------------------------------------
        # Schema validation
        # --------------------------------------------------------------------

        validate_response_schema(
            self.schema_version
        )

    # ------------------------------------------------------------------------
    # Factory: successful response
    # ------------------------------------------------------------------------

    @classmethod
    def success(
        cls,
        *,
        correlation_id: str,
        data: Any = None,
        metadata: Optional[Mapping[str, Any]] = None,
        schema_version: str = SCHEMA_VERSION_RESPONSE,
    ) -> "ResponseEnvelope":
        """Create a successful response.

        ``success()`` is kept as a convenience factory even though the
        canonical wire status is ``"ok"`` for legacy compatibility.
        """

        return cls(
            correlation_id=correlation_id,
            status=ResponseStatus.OK,
            data=data,
            error_code=None,
            error_message=None,
            schema_version=schema_version,
            metadata=_sanitize_metadata(
                metadata or {}
            ),
        )

    # ------------------------------------------------------------------------
    # Factory: error response
    # ------------------------------------------------------------------------

    @classmethod
    def error(
        cls,
        *,
        correlation_id: str,
        error_code: str,
        error_message: str,
        data: Any = None,
        metadata: Optional[Mapping[str, Any]] = None,
        schema_version: str = SCHEMA_VERSION_RESPONSE,
    ) -> "ResponseEnvelope":
        """Create an error response."""

        if (
            not isinstance(error_code, str)
            or not error_code.strip()
        ):
            raise ValueError(
                "error_code must be a non-empty string"
            )

        if (
            not isinstance(error_message, str)
            or not error_message.strip()
        ):
            raise ValueError(
                "error_message must be a non-empty string"
            )

        return cls(
            correlation_id=correlation_id,
            status=ResponseStatus.ERROR,
            data=data,
            error_code=error_code,
            error_message=error_message,
            schema_version=schema_version,
            metadata=_sanitize_metadata(
                metadata or {}
            ),
        )

    # ------------------------------------------------------------------------
    # Factory: dictionary
    # ------------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "ResponseEnvelope":
        """Deserialize canonical or legacy response data.

        Canonical fields:

            correlation_id
            status
            data
            error_code
            error_message
            schema_version
            seq
            total
            timestamp
            metadata

        Legacy Mt5ResultV1 fields:

            corr_id
            status = "ok" | "error"
            result
            schema
            meta
        """

        if not isinstance(value, Mapping):
            raise ValueError(
                "response must be a JSON object (dict)"
            )

        source = dict(value)

        # --------------------------------------------------------------------
        # Correlation ID
        # --------------------------------------------------------------------

        correlation_id = (
            source.get("correlation_id")
            or source.get("corr_id")
            or ""
        )

        if not correlation_id:
            raise ValueError(
                "response requires correlation_id "
                "(or legacy corr_id)"
            )

        # --------------------------------------------------------------------
        # Status
        #
        # Legacy and canonical status are both already:
        #
        #     ok
        #     error
        #
        # No semantic conversion is necessary.
        # --------------------------------------------------------------------

        raw_status = source.get(
            "status",
            ResponseStatus.OK.value,
        )

        if isinstance(raw_status, ResponseStatus):
            status = raw_status
        else:
            status = str(raw_status)

        # --------------------------------------------------------------------
        # Data
        #
        # Canonical:
        #
        #     data
        #
        # Legacy:
        #
        #     result
        # --------------------------------------------------------------------

        if "data" in source:
            data = source["data"]
        else:
            data = source.get("result")

        # --------------------------------------------------------------------
        # Error fields
        # --------------------------------------------------------------------

        error_code = source.get(
            "error_code"
        )

        error_message = source.get(
            "error_message"
        )

        # --------------------------------------------------------------------
        # Schema
        #
        # Canonical:
        #
        #     schema_version
        #
        # Legacy:
        #
        #     schema
        # --------------------------------------------------------------------

        schema_version = (
            source.get("schema_version")
            or source.get("schema")
            or SCHEMA_VERSION_RESPONSE
        )

        # --------------------------------------------------------------------
        # Chunk sequence
        #
        # Baseline response chunking uses seq/total.
        #
        # Normal response:
        #
        #     seq = 0
        #     total = 1
        # --------------------------------------------------------------------

        seq = source.get(
            "seq",
            0,
        )

        total = source.get(
            "total",
            1,
        )

        # --------------------------------------------------------------------
        # Timestamp
        # --------------------------------------------------------------------

        timestamp = (
            source.get("timestamp")
            or utcnow_iso()
        )

        # --------------------------------------------------------------------
        # Metadata
        #
        # Canonical:
        #
        #     metadata
        #
        # Legacy:
        #
        #     meta
        # --------------------------------------------------------------------

        if "metadata" in source:
            raw_metadata = source["metadata"]
        else:
            raw_metadata = source.get(
                "meta",
                {},
            )

        if raw_metadata is None:
            raw_metadata = {}

        if not isinstance(
            raw_metadata,
            Mapping,
        ):
            raise ValueError(
                "metadata/meta must be a JSON object (dict)"
            )

        metadata = _sanitize_metadata(
            raw_metadata
        )

        return cls(
            correlation_id=str(
                correlation_id
            ),
            status=status,
            data=data,
            error_code=(
                str(error_code)
                if error_code is not None
                else None
            ),
            error_message=(
                str(error_message)
                if error_message is not None
                else None
            ),
            schema_version=str(
                schema_version
            ),
            seq=seq,
            total=total,
            timestamp=str(
                timestamp
            ),
            metadata=metadata,
        )

    # ------------------------------------------------------------------------
    # Factory: JSON
    # ------------------------------------------------------------------------

    @classmethod
    def from_json(
        cls,
        value: Union[str, bytes],
    ) -> "ResponseEnvelope":
        """Deserialize a response from JSON."""

        try:
            raw = json.loads(value)
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                f"invalid response JSON: {exc}"
            ) from exc

        if not isinstance(raw, Mapping):
            raise ValueError(
                "response JSON must be a JSON object"
            )

        return cls.from_dict(raw)

    # ------------------------------------------------------------------------
    # Canonical serialization
    # ------------------------------------------------------------------------

    def to_dict(self) -> JsonDict:
        """Serialize to the canonical response representation."""

        return {
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "schema_version": self.schema_version,
            "seq": self.seq,
            "total": self.total,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        """Serialize to compact canonical JSON."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    # ------------------------------------------------------------------------
    # Legacy Mt5ResultV1 serialization
    # ------------------------------------------------------------------------

    def to_legacy_dict(self) -> JsonDict:
        """Serialize using the legacy Mt5ResultV1 field names.

        Mapping:

            schema_version -> schema
            correlation_id -> corr_id
            data           -> result
            metadata       -> meta

        Status remains:

            ok
            error

        This preserves the legacy Kafka response contract.
        """

        payload: JsonDict = {
            "schema": self.schema_version,
            "corr_id": self.correlation_id,
            "status": self.status.value,
            "result": self.data,
            "seq": self.seq,
            "total": self.total,
        }

        if self.error_code is not None:
            payload["error_code"] = self.error_code

        if self.error_message is not None:
            payload["error_message"] = self.error_message

        if self.metadata:
            payload["meta"] = dict(
                self.metadata
            )

        return payload

    def to_legacy_json(self) -> str:
        """Serialize to compact legacy Mt5ResultV1 JSON."""

        return json.dumps(
            self.to_legacy_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    # ------------------------------------------------------------------------
    # Chunk helper
    # ------------------------------------------------------------------------

    def with_chunk(
        self,
        *,
        seq: int,
        total: int,
    ) -> "ResponseEnvelope":
        """Return an immutable copy representing one response chunk."""

        return replace(
            self,
            seq=seq,
            total=total,
        )

    # ------------------------------------------------------------------------
    # Correlation helper
    # ------------------------------------------------------------------------

    def with_correlation_id(
        self,
        correlation_id: str,
    ) -> "ResponseEnvelope":
        """Return an immutable copy with a different correlation ID."""

        if (
            not isinstance(correlation_id, str)
            or not correlation_id.strip()
        ):
            raise ValueError(
                "correlation_id must be a non-empty string"
            )

        return replace(
            self,
            correlation_id=correlation_id,
        )


# ============================================================================
# Public exports
# ============================================================================


__all__ = [
    "ResponseStatus",
    "ResponseEnvelope",
]
