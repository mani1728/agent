# Path: Version 1_0_0/agent/transport/kafka/serializers.py

from __future__ import annotations

import ast
import json
from typing import Any, Mapping, Optional, Sequence

from agent.contracts.command import CommandEnvelope
from agent.contracts.heartbeat import HeartbeatPayload
from agent.contracts.response import ResponseEnvelope


class KafkaSerializationError(ValueError):
    """Raised when a Kafka payload cannot be serialized or parsed."""


class KafkaSerializer:
    """
    Kafka serialization utilities.

    Responsibilities:
        - Serialize canonical transport-independent contracts.
        - Deserialize Kafka JSON payloads.
        - Preserve legacy JSON/literal parsing compatibility.
        - Normalize Kafka headers.

    This class must remain independent from:
        - Mt5_Manager
        - Dispatcher
        - CommandExecutor
        - Kafka Producer/Consumer
        - HTTP/Gateway
    """

    # ------------------------------------------------------------------
    # Generic JSON
    # ------------------------------------------------------------------

    @staticmethod
    def dumps(
        value: Any,
        *,
        compact: bool = True,
    ) -> bytes:
        """
        Serialize a Python value into UTF-8 JSON bytes.
        """

        try:
            if compact:
                text = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            else:
                text = json.dumps(
                    value,
                    ensure_ascii=False,
                )

        except (TypeError, ValueError) as exc:
            raise KafkaSerializationError(
                f"Failed to serialize value to JSON: {exc}"
            ) from exc

        return text.encode("utf-8")

    @staticmethod
    def loads(
        payload: bytes | bytearray | str,
    ) -> Any:
        """
        Deserialize UTF-8 JSON.

        JSON is the canonical format.
        """

        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = bytes(payload).decode(
                    "utf-8",
                    errors="strict",
                )
            except UnicodeDecodeError as exc:
                raise KafkaSerializationError(
                    "Kafka payload is not valid UTF-8"
                ) from exc

        if not isinstance(payload, str):
            raise KafkaSerializationError(
                "Kafka payload must be bytes, bytearray, or str"
            )

        try:
            return json.loads(payload)

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise KafkaSerializationError(
                f"Invalid JSON payload: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Legacy compatibility parser
    # ------------------------------------------------------------------

    @staticmethod
    def loads_legacy(
        payload: Any,
    ) -> Any:
        """
        Parse Kafka payload using the legacy behavior.

        Order:
            1. JSON
            2. ast.literal_eval()

        literal_eval is intentionally retained because the legacy
        Kafka listener accepted Python-literal payloads.
        """

        if isinstance(payload, (dict, list, tuple)):
            return payload

        if isinstance(payload, bytearray):
            payload = bytes(payload)

        if isinstance(payload, bytes):
            try:
                payload = payload.decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception as exc:
                raise KafkaSerializationError(
                    "Failed to decode Kafka payload"
                ) from exc

        if not isinstance(payload, str):
            return payload

        text = payload.strip()

        if not text:
            raise KafkaSerializationError(
                "Kafka payload is empty"
            )

        try:
            return json.loads(text)

        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        try:
            return ast.literal_eval(text)

        except (ValueError, SyntaxError) as exc:
            raise KafkaSerializationError(
                "Kafka payload is neither valid JSON "
                "nor a valid Python literal"
            ) from exc

    # ------------------------------------------------------------------
    # CommandEnvelope
    # ------------------------------------------------------------------

    @classmethod
    def serialize_command(
        cls,
        command: CommandEnvelope,
    ) -> bytes:
        """
        Serialize CommandEnvelope.
        """

        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "command must be CommandEnvelope"
            )

        return cls.dumps(
            command.to_dict(),
            compact=True,
        )

    @classmethod
    def deserialize_command(
        cls,
        payload: bytes | bytearray | str | Mapping[str, Any],
        *,
        correlation_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> CommandEnvelope:
        """
        Deserialize a CommandEnvelope.

        Mapping input is accepted to make adapter testing easier.
        """

        if isinstance(payload, Mapping):
            data = dict(payload)
        else:
            data = cls.loads_legacy(payload)

        if not isinstance(data, Mapping):
            raise KafkaSerializationError(
                "Command payload must be an object"
            )

        return CommandEnvelope.from_dict(
            dict(data),
            correlation_id=correlation_id,
            metadata=dict(metadata or {}),
        )

    # ------------------------------------------------------------------
    # ResponseEnvelope
    # ------------------------------------------------------------------

    @classmethod
    def serialize_response(
        cls,
        response: ResponseEnvelope,
    ) -> bytes:
        """
        Serialize ResponseEnvelope.
        """

        if not isinstance(response, ResponseEnvelope):
            raise TypeError(
                "response must be ResponseEnvelope"
            )

        return cls.dumps(
            response.to_dict(),
            compact=True,
        )

    @classmethod
    def deserialize_response(
        cls,
        payload: bytes | bytearray | str | Mapping[str, Any],
    ) -> ResponseEnvelope:
        """
        Deserialize a ResponseEnvelope.
        """

        if isinstance(payload, Mapping):
            data = dict(payload)
        else:
            data = cls.loads_legacy(payload)

        if not isinstance(data, Mapping):
            raise KafkaSerializationError(
                "Response payload must be an object"
            )

        return ResponseEnvelope.from_dict(
            dict(data)
        )

    # ------------------------------------------------------------------
    # HeartbeatPayload
    # ------------------------------------------------------------------

    @classmethod
    def serialize_heartbeat(
        cls,
        heartbeat: HeartbeatPayload,
    ) -> bytes:
        """
        Serialize HeartbeatPayload.
        """

        if not isinstance(heartbeat, HeartbeatPayload):
            raise TypeError(
                "heartbeat must be HeartbeatPayload"
            )

        return cls.dumps(
            heartbeat.to_dict(),
            compact=True,
        )

    @classmethod
    def deserialize_heartbeat(
        cls,
        payload: bytes | bytearray | str | Mapping[str, Any],
    ) -> HeartbeatPayload:
        """
        Deserialize HeartbeatPayload.
        """

        if isinstance(payload, Mapping):
            data = dict(payload)
        else:
            data = cls.loads_legacy(payload)

        if not isinstance(data, Mapping):
            raise KafkaSerializationError(
                "Heartbeat payload must be an object"
            )

        return HeartbeatPayload.from_dict(
            dict(data)
        )

    # ------------------------------------------------------------------
    # Kafka headers
    # ------------------------------------------------------------------

    @staticmethod
    def encode_header_value(
        value: Any,
    ) -> bytes:
        """
        Convert a Kafka header value into bytes.

        Strings are encoded directly.
        Other values are JSON encoded.
        """

        if value is None:
            return b""

        if isinstance(value, bytes):
            return value

        if isinstance(value, bytearray):
            return bytes(value)

        if isinstance(value, str):
            return value.encode("utf-8")

        return KafkaSerializer.dumps(
            value,
            compact=True,
        )

    @staticmethod
    def decode_header_value(
        value: Optional[bytes],
    ) -> Optional[str]:
        """
        Decode a Kafka header value as UTF-8 text.

        Binary values that cannot be decoded are returned as None
        rather than being guessed or silently transformed.
        """

        if value is None:
            return None

        try:
            return value.decode(
                "utf-8",
                errors="strict",
            )

        except UnicodeDecodeError:
            return None

    @classmethod
    def encode_headers(
        cls,
        headers: Optional[
            Mapping[str, Any]
        ],
    ) -> list[tuple[str, bytes]]:
        """
        Convert a mapping into Kafka-compatible headers.
        """

        if not headers:
            return []

        result: list[tuple[str, bytes]] = []

        for key, value in headers.items():
            result.append(
                (
                    str(key),
                    cls.encode_header_value(value),
                )
            )

        return result

    @classmethod
    def decode_headers(
        cls,
        headers: Optional[
            Sequence[
                tuple[str, Optional[bytes]]
            ]
        ],
    ) -> dict[str, Any]:
        """
        Convert Kafka headers into a regular mapping.

        If a header occurs more than once, the latest value wins,
        matching the practical behavior of the legacy listener.
        """

        result: dict[str, Any] = {}

        if not headers:
            return result

        for key, value in headers:
            decoded = cls.decode_header_value(value)

            result[str(key)] = decoded

        return result

    # ------------------------------------------------------------------
    # Correlation ID
    # ------------------------------------------------------------------

    @staticmethod
    def extract_correlation_id(
        headers: Mapping[str, Any],
        payload: Any = None,
    ) -> Optional[str]:
        """
        Extract correlation ID without generating one.

        Generation belongs to CommandEnvelope / command boundary,
        not to the generic serializer.
        """

        correlation_id = headers.get("corr_id")

        if correlation_id:
            return str(correlation_id)

        correlation_id = headers.get("correlation_id")

        if correlation_id:
            return str(correlation_id)

        if isinstance(payload, Mapping):
            correlation_id = payload.get("corr_id")

            if correlation_id:
                return str(correlation_id)

            correlation_id = payload.get("correlation_id")

            if correlation_id:
                return str(correlation_id)

        return None


# ----------------------------------------------------------------------
# Module-level compatibility helpers
# ----------------------------------------------------------------------

def dumps(
    value: Any,
    *,
    compact: bool = True,
) -> bytes:
    return KafkaSerializer.dumps(
        value,
        compact=compact,
    )


def loads(
    payload: bytes | bytearray | str,
) -> Any:
    return KafkaSerializer.loads(payload)


def loads_legacy(
    payload: Any,
) -> Any:
    return KafkaSerializer.loads_legacy(payload)


def serialize_command(
    command: CommandEnvelope,
) -> bytes:
    return KafkaSerializer.serialize_command(command)


def deserialize_command(
    payload: bytes | bytearray | str | Mapping[str, Any],
    *,
    correlation_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> CommandEnvelope:
    return KafkaSerializer.deserialize_command(
        payload,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def serialize_response(
    response: ResponseEnvelope,
) -> bytes:
    return KafkaSerializer.serialize_response(response)


def deserialize_response(
    payload: bytes | bytearray | str | Mapping[str, Any],
) -> ResponseEnvelope:
    return KafkaSerializer.deserialize_response(payload)


def serialize_heartbeat(
    heartbeat: HeartbeatPayload,
) -> bytes:
    return KafkaSerializer.serialize_heartbeat(heartbeat)


def deserialize_heartbeat(
    payload: bytes | bytearray | str | Mapping[str, Any],
) -> HeartbeatPayload:
    return KafkaSerializer.deserialize_heartbeat(payload)


__all__ = [
    "KafkaSerializationError",
    "KafkaSerializer",
    "dumps",
    "loads",
    "loads_legacy",
    "serialize_command",
    "deserialize_command",
    "serialize_response",
    "deserialize_response",
    "serialize_heartbeat",
    "deserialize_heartbeat",
]