# Path: agent/core/command.py

"""Canonical command parser (core layer).

Responsibilities
----------------
- Convert a transport-level ``TransportMessage`` into one or more
  canonical ``CommandEnvelope`` objects.
- Perform JSON / literal decoding of the raw payload.
- Extract correlation id, target class, and priority.
- Normalize legacy single-command and multi-command payload shapes.

This module is the ONLY place in the codebase that knows how to turn
raw transport bytes into business commands. It intentionally lives in
the core layer so that:

- ``agent.transport.*`` stays thin (Patch 2).
- ``agent.contracts.command`` stays a pure contract with no transport
  dependency.
- Parsing bugs are contained in one testable location.
"""

from __future__ import annotations

import ast
import json
import logging
import uuid
from typing import Any, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.transport.base import AckToken, TransportMessage


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Header key sets
# ----------------------------------------------------------------------

_CORR_ID_HEADER_KEYS = (
    "corr_id",
    "correlation_id",
    "correlation-id",
)

_CMD_ID_HEADER_KEYS = (
    "command_id",
    "command-id",
    "commandid",
)


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------

class CommandParser:
    """Parse ``TransportMessage`` into canonical ``CommandEnvelope``.

    Design notes
    ------------
    - Stateless. Safe to share across threads.
    - Does NOT know about Kafka specifically; works with any
      ``TransportMessage`` regardless of the underlying transport.
    - Priority is derived from the topic suffix ``.p0`` / ``.p1`` /
      ``.p2`` when available, otherwise defaults to ``1``.
    - Correlation id precedence:
        1. header ``corr_id``
        2. header ``correlation_id``
        3. payload ``corr_id``
        4. payload ``correlation_id``
        5. generated UUID
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(
        self,
        msg: TransportMessage,
        *,
        default_target_class: Optional[str] = None,
    ) -> list[CommandEnvelope]:
        """Parse a single ``TransportMessage`` into command envelopes.

        Parameters
        ----------
        msg:
            The transport-level message. ``msg.payload`` may be bytes,
            str, or an already-decoded dict/list.
        default_target_class:
            Optional fallback target class. When ``None``, the parser
            falls back to ``msg.key`` (legacy Kafka behavior).

        Returns
        -------
        list[CommandEnvelope]
            One envelope for a single-command payload; multiple
            envelopes for a list payload. Order matches the payload.

        Raises
        ------
        ValueError
            If the payload cannot be decoded or fails validation.
        """
        if msg is None:
            raise ValueError("TransportMessage must not be None")

        raw = msg.payload

        # ----------------------------------------------------------------
        # Decode payload
        # ----------------------------------------------------------------

        decoded = self._decode_payload(raw)

        # ----------------------------------------------------------------
        # Normalize to list of command dicts
        # ----------------------------------------------------------------

        items = self._normalize_to_list(decoded)

        # ----------------------------------------------------------------
        # Resolve transport-derived fields
        # ----------------------------------------------------------------

        target_class = (
            default_target_class
            or self._decode_key(msg.key)
        )

        correlation_id = self._extract_correlation_id(
            msg.headers, decoded
        )

        priority = self._priority_from_topic(msg.ack_token)

        command_id_from_header = self._extract_command_id_from_headers(
            msg.headers
        )

        # ----------------------------------------------------------------
        # Build envelopes
        # ----------------------------------------------------------------

        envelopes: list[CommandEnvelope] = []

        for index, item in enumerate(items):
            envelope = self._build_envelope(
                item,
                default_target_class=target_class,
                priority=priority,
                correlation_id=correlation_id,
                request_index=index,
                command_id_hint=command_id_from_header if index == 0 else None,
            )
            envelopes.append(envelope)

        logger.debug(
            "Parsed %d command(s) from transport message (topic=%s)",
            len(envelopes),
            getattr(msg.ack_token, "topic", None),
        )

        return envelopes

    # ------------------------------------------------------------------
    # Payload decoding
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_payload(raw: Any) -> Any:
        """Decode bytes/str JSON payload; pass dict/list through.

        Legacy compatibility
        --------------------
        If ``json.loads`` fails, ``ast.literal_eval`` is attempted.
        This mirrors the old ``KafkaListener.parse_json_or_literal``
        behavior for backward compatibility with producers that
        emitted Python-literal payloads.
        """
        if isinstance(raw, (dict, list)):
            return raw

        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    "payload bytes are not valid UTF-8"
                ) from exc

        if not isinstance(raw, str):
            raise ValueError(
                f"payload must be bytes, str, dict, or list; "
                f"got {type(raw).__name__!r}"
            )

        text = raw.strip()
        if not text:
            raise ValueError("payload is empty")

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(
                "payload is neither valid JSON nor a valid Python literal"
            ) from exc

    @staticmethod
    def _normalize_to_list(decoded: Any) -> list[Mapping[str, Any]]:
        """Normalize a decoded payload into a list of command dicts.

        Accepts:
            - a single dict (single command)
            - a list of dicts (multi-command)
        """
        if isinstance(decoded, Mapping):
            return [decoded]

        if isinstance(decoded, list):
            items: list[Mapping[str, Any]] = []
            for idx, entry in enumerate(decoded):
                if not isinstance(entry, Mapping):
                    raise ValueError(
                        f"command at index {idx} must be a JSON object, "
                        f"got {type(entry).__name__!r}"
                    )
                items.append(entry)
            return items

        raise ValueError(
            "payload must decode to an object or a list of objects"
        )

    # ------------------------------------------------------------------
    # Transport-metadata extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_key(key: Any) -> Optional[str]:
        """Decode the transport message key into a target class string."""
        if key is None:
            return None

        if isinstance(key, bytes):
            try:
                key = key.decode("utf-8")
            except UnicodeDecodeError:
                key = key.decode("utf-8", errors="replace")

        text = str(key).strip()
        return text or None

    @staticmethod
    def _priority_from_topic(token: Optional[AckToken]) -> int:
        """Map the ``.pN`` topic suffix to a priority level.

        Legacy Kafka topics look like ``cmd.<client_id>.p0|p1|p2``.
        Unknown or missing suffixes default to ``1`` (normal).
        """
        if token is None or not token.topic:
            return 1

        topic = str(token.topic)
        parts = topic.rsplit(".p", 1)
        if len(parts) != 2:
            return 1

        try:
            priority = int(parts[1])
        except ValueError:
            return 1

        return priority if priority in (0, 1, 2) else 1

    @staticmethod
    def _extract_correlation_id(
        headers: Mapping[str, Any],
        decoded: Any,
    ) -> str:
        """Resolve the correlation id using the documented precedence."""
        if headers:
            for key in _CORR_ID_HEADER_KEYS:
                value = headers.get(key)
                if value:
                    return str(value)

        if isinstance(decoded, Mapping):
            for key in _CORR_ID_HEADER_KEYS:
                value = decoded.get(key)
                if value:
                    return str(value)

        if isinstance(decoded, list):
            # For a batch, prefer the first item's corr_id if present.
            for entry in decoded:
                if not isinstance(entry, Mapping):
                    continue
                for key in _CORR_ID_HEADER_KEYS:
                    value = entry.get(key)
                    if value:
                        return str(value)

        return str(uuid.uuid4())

    @staticmethod
    def _extract_command_id_from_headers(
        headers: Mapping[str, Any],
    ) -> Optional[str]:
        """Extract an explicit command_id from headers, if any."""
        if not headers:
            return None

        for key in _CMD_ID_HEADER_KEYS:
            value = headers.get(key)
            if value:
                return str(value)

        return None

    # ------------------------------------------------------------------
    # Envelope building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_envelope(
        item: Mapping[str, Any],
        *,
        default_target_class: Optional[str],
        priority: int,
        correlation_id: str,
        request_index: int,
        command_id_hint: Optional[str],
    ) -> CommandEnvelope:
        """Build one ``CommandEnvelope`` from a single command dict."""
        source = dict(item)

        # Inject transport-derived fields without overriding caller
        # intent unless the field is absent.
        if request_index is not None:
            source.setdefault("request_index", request_index)

        if command_id_hint:
            source.setdefault("command_id", command_id_hint)

        return CommandEnvelope.from_dict(
            source,
            default_target_class=default_target_class,
            priority=priority,
            correlation_id=correlation_id,
        )


__all__ = ["CommandParser"]