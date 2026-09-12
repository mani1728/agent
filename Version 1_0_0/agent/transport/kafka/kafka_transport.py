# Path: Version 1_0_0/agent/transport/kafka/kafka_transport.py

"""Kafka transport implementation.

Responsibilities
----------------
- Own the Kafka consumer (via ``KafkaListener``).
- Own the Kafka producer (via ``KafkaResponder``).
- Expose a thin, transport-level API:
    - ``poll_messages`` — returns raw ``TransportMessage`` objects.
    - ``ack`` — commits the offset for a given ``AckToken``.
    - ``nack`` — negatively acknowledges, with optional DLQ routing.

This module intentionally does NOT:
- Import or reference ``CommandEnvelope``, ``ResponseEnvelope``,
  ``HeartbeatPayload``, or any other domain contract.
- Parse, validate, or normalize business payloads.
- Decide business-level commit semantics (that belongs to the
  application/core layer above the transport).

Legacy ``send_response`` / ``send_heartbeat`` helpers are retained as
**non-interface** methods so that the existing responder wiring
continues to function during the P1 refactor. They are NOT part of
``ITransportClient`` and will be moved to a dedicated producer service
in a later phase.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from agent.transport.base import AckToken, ITransportClient, TransportMessage

from .listener import KafkaListener
from .responder import KafkaResponder
from .commit_policy import (
    CommandCommitTracker,
    CommitState,
    KafkaCommitPolicy,
)


logger = logging.getLogger(__name__)


class KafkaTransport(ITransportClient):
    """Kafka implementation of the transport-independent ``ITransportClient``.

    Notes
    -----
    - This class no longer accepts or returns domain contracts.
    - ``ack`` / ``nack`` operate strictly on ``AckToken``.
    - The commit lifecycle is delegated to ``KafkaListener``.
    """

    def __init__(
        self,
        config: Optional[Any] = None,
    ) -> None:
        self.config = config

        effective_config = config
        if effective_config is None:
            try:
                from agent.infrastructure.config_manager import cfg
                effective_config = cfg()
            except Exception:
                effective_config = None

        self._commit_policy = KafkaCommitPolicy.from_config(effective_config)

        configured_auto_commit = bool(
            self._get_config_value("kafka.enable_auto_commit", False)
        )
        if configured_auto_commit:
            raise ValueError(
                "Canonical Kafka runtime requires kafka.enable_auto_commit=false"
            )
        if not self._commit_policy.is_application_managed:
            raise ValueError(
                "Canonical Kafka runtime requires an application-managed commit policy"
            )

        self.listener = KafkaListener(config=config)
        self.responder = KafkaResponder(config=config)

        self._commit_trackers: dict[str, CommandCommitTracker] = {}
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle (legacy; kept for current wiring)
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return

        self.listener.start()
        self._started = True
        logger.info("Kafka transport started")

    def stop(self) -> None:
        if not self._started:
            try:
                self.listener.close()
            except Exception:
                logger.exception("Failed to close Kafka listener")

            try:
                self.responder.close()
            except Exception:
                logger.exception("Failed to close Kafka responder")

            return

        try:
            self.listener.stop()
        except Exception:
            logger.exception("Failed to stop Kafka listener")

        try:
            self.listener.close()
        except Exception:
            logger.exception("Failed to close Kafka listener")

        try:
            self.responder.close()
        except Exception:
            logger.exception("Failed to close Kafka responder")

        self._started = False
        logger.info("Kafka transport stopped")

    # ------------------------------------------------------------------
    # Polling (thin)
    # ------------------------------------------------------------------

    def poll_messages(
        self,
        timeout_ms: int = 1000,
        max_records: int = 1,
    ) -> list[TransportMessage]:
        """Poll raw ``TransportMessage`` objects from Kafka.

        No parsing, validation, or envelope construction happens here.
        Callers are expected to parse ``TransportMessage.payload`` in
        the application/core layer.
        """
        if not self._started:
            self.start()

        return self.listener.poll_messages(
            timeout_ms=timeout_ms,
            max_records=max_records,
        )

    # ------------------------------------------------------------------
    # Acknowledgement (transport-level only)
    # ------------------------------------------------------------------

    def ack(
        self,
        token: AckToken,
        status: str = "SUCCESS",
    ) -> None:
        """Commit the Kafka offset referenced by ``token``.

        Raises
        ------
        ValueError
            If ``token`` is None or lacks a usable ``transport_ref``.
        RuntimeError
            If the underlying consumer is unavailable.
        """
        if token is None:
            raise ValueError("AckToken must not be None")

        ref = token.transport_ref
        if ref is None:
            raise ValueError("AckToken.transport_ref is required")

        if not self._commit_policy.is_application_managed:
            logger.debug(
                "ack() delegated to auto-commit: command_id=%s",
                token.command_id,
            )
            return

        # Delegate the physical commit to the listener, which owns the
        # Kafka consumer and its commit semantics (including the
        # "+1" offset rule).
        self.listener.ack(token, status=status)

        # Clean up per-command tracker state so duplicate acks are
        # cheap no-ops.
        tracker = self._commit_trackers.get(token.command_id)
        if tracker is not None and tracker.state == CommitState.ACKED:
            self._commit_trackers.pop(token.command_id, None)

    def nack(
        self,
        token: AckToken,
        reason: str,
        retryable: bool = True,
    ) -> None:
        """Negatively acknowledge a message.

        Policy
        ------
        - ``retryable=True``:
            No commit is performed. The message may be redelivered by
            the broker (subject to consumer settings).
        - ``retryable=False``:
            If a DLQ hook is enabled, the payload is forwarded there
            and the offset is committed so the bad message is not
            reprocessed indefinitely. If no DLQ hook is available,
            the message is left uncommitted and a warning is logged so
            that a higher layer can pick it up.
        """
        if token is None:
            raise ValueError("AckToken must not be None")

        safe_reason = self._sanitize_reason(reason)

        if retryable:
            logger.warning(
                "nack (retryable): command_id=%s reason=%s",
                token.command_id,
                safe_reason,
            )
            self.listener.nack(token, reason=safe_reason, retryable=True)
            return

        logger.error(
            "nack (non-retryable): command_id=%s reason=%s",
            token.command_id,
            safe_reason,
        )

        if self._send_to_dlq_if_enabled(token, safe_reason):
            # DLQ succeeded -> advance the offset so we do not loop.
            self.ack(token, status="NON_RETRYABLE")
        else:
            # No DLQ available -> leave uncommitted and let a higher
            # layer decide (avoids silent data loss).
            logger.warning(
                "No DLQ available; leaving non-retryable message "
                "uncommitted: command_id=%s",
                token.command_id,
            )
            self.listener.nack(token, reason=safe_reason, retryable=False)

    # ------------------------------------------------------------------
    # Legacy helpers retained outside ITransportClient
    # ------------------------------------------------------------------

    def send_response(self, response: Any) -> bool:
        """Send a domain response via the responder.

        Kept for backward compatibility during P1. Will be moved to a
        dedicated producer service in a later phase. NOT part of
        ``ITransportClient``.
        """
        return self.responder.send_response(response)

    def send_heartbeat(self, status: Any) -> bool:
        """Send a heartbeat/status payload via the responder.

        Kept for backward compatibility during P1. Will be moved to a
        dedicated producer service in a later phase. NOT part of
        ``ITransportClient``.
        """
        producer = self.responder._ensure_producer()
        if producer is None:
            logger.warning("Cannot send heartbeat: Kafka producer unavailable")
            return False

        topic = self._get_config_value("kafka.topics.status", "clients.status")
        topic = str(topic or "").strip()
        if not topic:
            logger.error("Kafka heartbeat/status topic is empty")
            return False

        try:
            from .serializers import KafkaSerializer

            payload = KafkaSerializer.serialize_heartbeat(status)
            headers = [
                ("schema", status.schema_version.encode("utf-8")),
                ("content_type", b"application/json"),
                ("encoding", b"identity"),
            ]

            agent_id = getattr(status, "agent_id", None)
            if agent_id:
                headers.append(("client_id", agent_id.encode("utf-8")))

            producer.produce(
                topic=topic,
                key=agent_id or None,
                value=payload,
                headers=headers,
                on_delivery=self.responder._delivery_cb,
            )

            producer.poll(0)
            producer.flush()
            return True

        except BufferError:
            logger.exception("Kafka producer queue is full while sending heartbeat")
            return False
        except Exception:
            logger.exception("Failed to send Kafka heartbeat")
            return False

    # ------------------------------------------------------------------
    # DLQ hook (no-op by default)
    # ------------------------------------------------------------------

    def _send_to_dlq_if_enabled(
        self,
        token: AckToken,
        reason: str,
    ) -> bool:
        """Forward a poisoned message to a DLQ if configured.

        Returns
        -------
        bool
            True if the payload was successfully forwarded to a DLQ,
            False otherwise. Default implementation is a no-op and
            returns False; subclasses or configuration may enable an
            actual DLQ publisher.
        """
        dlq_topic = self._get_config_value("kafka.topics.dlq", None)
        if not dlq_topic:
            return False

        logger.debug(
            "DLQ forwarding not implemented in this phase "
            "(topic=%s, command_id=%s, reason=%s)",
            dlq_topic,
            token.command_id,
            reason,
        )
        return False

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _get_config_value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        config = self.config

        if config is None:
            try:
                from agent.infrastructure.config_manager import cfg
                config = cfg()
            except Exception:
                return default

        try:
            value = config.get(key, default)
        except AttributeError:
            return default

        return default if value is None else value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_reason(reason: Any) -> str:
        """Truncate and strip a reason string for safe logging."""
        if reason is None:
            return ""

        text = str(reason)
        if len(text) > 256:
            text = text[:253] + "..."

        return text

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "KafkaTransport":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_started(self) -> bool:
        return self._started


__all__ = ["KafkaTransport"]