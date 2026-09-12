# Path: Version 1_0_0/agent/transport/kafka/listener.py

"""Thin Kafka listener.

Responsibilities
----------------
- Create and manage the Kafka Consumer.
- Subscribe to configured command topics (with hot-reload).
- Poll Kafka messages.
- Wrap each record into a transport-agnostic ``TransportMessage``
  carrying the raw payload and a lightweight ``AckToken``.

This module intentionally does NOT:
- Parse business commands.
- Normalize legacy payload shapes.
- Build ``CommandEnvelope`` instances.
- Execute MT5 operations.
- Commit offsets as part of business execution.

All parsing/validation/normalization has been moved out of the
transport layer (see Patch 2) so that ``KafkaListener`` stays a thin
polling adapter.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from confluent_kafka import Consumer, KafkaError, KafkaException

from agent.infrastructure.config_manager import cfg
from agent.transport.base import AckToken, TransportMessage


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Kafka commit reference
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class KafkaCommitRef:
    """Immutable reference to a Kafka record for manual commit."""

    topic: str
    partition: int
    offset: int


# ----------------------------------------------------------------------
# Lightweight command-id extraction
# ----------------------------------------------------------------------

_CMD_ID_HEADER_KEYS = (
    "command_id",
    "command-id",
    "commandid",
    "corr_id",
    "correlation_id",
)


def _extract_command_id_from_headers(
    headers: Optional[Sequence[tuple[str, Optional[bytes]]]],
) -> Optional[str]:
    """Best-effort extraction of a command id from Kafka headers only.

    The listener is intentionally thin: it does NOT parse the payload
    to discover a command id. If the producer did not set a recognized
    header, the caller falls back to a synthetic, offset-based id.
    """
    if not headers:
        return None

    for key, value in headers:
        if key is None:
            continue

        normalized = str(key).strip().lower()
        if normalized not in _CMD_ID_HEADER_KEYS:
            continue

        if value is None:
            return None

        if isinstance(value, bytes):
            try:
                decoded = value.decode("utf-8")
            except UnicodeDecodeError:
                decoded = value.decode("utf-8", errors="replace")
        else:
            decoded = str(value)

        decoded = decoded.strip()
        if decoded:
            return decoded

    return None


def _build_synthetic_command_id(
    topic: Optional[str],
    partition: Optional[int],
    offset: Optional[int],
) -> str:
    """Fallback command id derived from record coordinates.

    This is NOT the canonical command id used by the application
    layer; it is only a transport-level placeholder so that ack
    tokens are never empty. The application layer will assign the
    real command id during parsing.
    """
    return (
        f"kafka:{topic or 'unknown'}:"
        f"{partition if partition is not None else -1}:"
        f"{offset if offset is not None else -1}"
    )


# ----------------------------------------------------------------------
# Listener
# ----------------------------------------------------------------------

class KafkaListener:
    """Thin Kafka command listener.

    Only polls Kafka and yields ``TransportMessage`` objects. Any
    domain-level parsing, validation, or envelope construction is the
    responsibility of the caller (application/core layer).
    """

    def __init__(
        self,
        config: Optional[Any] = None,
    ) -> None:
        self.config = config or cfg()

        self.running = False
        self._stop_event = threading.Event()
        self._consumer: Optional[Consumer] = None

        self._subscribed_topics: list[str] = []
        self._pending_lock = threading.RLock()

        self._build_consumer_and_subscribe()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the listener lifecycle."""
        if self.running:
            return

        self._stop_event.clear()
        self.running = True

        logger.info("Kafka listener started")

    def stop(self) -> None:
        """Request listener shutdown."""
        if not self.running and self._stop_event.is_set():
            return

        self.running = False
        self._stop_event.set()

        logger.info("Kafka listener stop requested")

    def close(self) -> None:
        """Close Kafka consumer resources."""
        self.stop()

        consumer = self._consumer
        self._consumer = None

        with self._pending_lock:
            # No pending state retained at the transport level.
            pass

        if consumer is not None:
            try:
                consumer.close()
            except Exception:
                logger.exception("Failed to close Kafka consumer")

    # ------------------------------------------------------------------
    # Kafka configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _servers_to_string(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ",".join(
                str(item).strip() for item in value if str(item).strip()
            )

        return str(value or "").strip()

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        try:
            value = self.config.get(key, default)
        except AttributeError:
            value = default

        return default if value is None else value

    def _build_consumer_config(self) -> dict[str, Any]:
        bootstrap_servers = self._get_config_value(
            "kafka.bootstrap_servers", []
        )
        group_id = self._get_config_value(
            "kafka.group_id", "mt5-service"
        )
        auto_offset_reset = self._get_config_value(
            "kafka.consumer_auto_offset_reset", "latest"
        )

        # Canonical AgentWorker owns the offset lifecycle. Never allow
        # Kafka to advance offsets independently when the worker path
        # is active.
        if self._get_config_value("app.use_agent_worker", True):
            enable_auto_commit = False
        else:
            enable_auto_commit = self._get_config_value(
                "kafka.enable_auto_commit", True
            )

        session_timeout_ms = self._get_config_value(
            "kafka.session_timeout_ms", 45000
        )
        security_protocol = self._get_config_value(
            "kafka.security_protocol", "PLAINTEXT"
        )
        sasl_mechanism = self._get_config_value(
            "kafka.sasl_mechanism", "PLAIN"
        )
        sasl_username = self._get_config_value(
            "kafka.sasl_username", ""
        )
        sasl_password = self._get_config_value(
            "kafka.sasl_password", ""
        )

        consumer_config: dict[str, Any] = {
            "bootstrap.servers": self._servers_to_string(bootstrap_servers),
            "group.id": str(group_id),
            "auto.offset.reset": str(auto_offset_reset),
            "enable.auto.commit": bool(enable_auto_commit),
            "session.timeout.ms": int(session_timeout_ms),
            "security.protocol": str(security_protocol),
        }

        if sasl_mechanism:
            consumer_config["sasl.mechanisms"] = str(sasl_mechanism)

        if sasl_username:
            consumer_config["sasl.username"] = str(sasl_username)

        if sasl_password:
            consumer_config["sasl.password"] = str(sasl_password)

        return consumer_config

    # ------------------------------------------------------------------
    # Topic management
    # ------------------------------------------------------------------

    def _current_command_topics(self) -> list[str]:
        topics = self._get_config_value("kafka.topics.commands", [])

        if isinstance(topics, str):
            topics = [topics]

        if not isinstance(topics, (list, tuple)):
            return []

        return [
            str(topic).strip()
            for topic in topics
            if str(topic).strip()
        ]

    def _build_consumer_and_subscribe(self) -> None:
        if not bool(self._get_config_value("kafka.enabled", True)):
            logger.info(
                "Kafka is disabled; listener consumer will not start"
            )
            return

        topics = self._current_command_topics()

        if not topics:
            logger.warning("No Kafka command topics configured")
            return

        old_consumer = self._consumer
        self._consumer = None

        if old_consumer is not None:
            try:
                old_consumer.close()
            except Exception:
                logger.exception(
                    "Failed to close previous Kafka consumer"
                )

        try:
            consumer_config = self._build_consumer_config()
            consumer = Consumer(consumer_config)
            consumer.subscribe(topics)

            self._consumer = consumer
            self._subscribed_topics = list(topics)

            logger.info(
                "Kafka consumer subscribed to topics=%s",
                self._subscribed_topics,
            )

        except KafkaException:
            logger.exception("Failed to create Kafka consumer")
            self._consumer = None

    def _ensure_topics_up_to_date(self) -> None:
        consumer = self._consumer
        if consumer is None:
            return

        current_topics = self._current_command_topics()
        if current_topics == self._subscribed_topics:
            return

        try:
            consumer.subscribe(current_topics)
            self._subscribed_topics = list(current_topics)
            logger.info(
                "Kafka command topics updated: %s",
                self._subscribed_topics,
            )
        except KafkaException:
            logger.exception("Failed to update Kafka subscriptions")

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_headers(
        headers: Optional[Sequence[tuple[str, Optional[bytes]]]],
    ) -> dict[str, Any]:
        """Decode Kafka headers into a plain dict.

        Values are decoded as UTF-8 when possible; otherwise the raw
        bytes are preserved. Missing values become ``None``.
        """
        result: dict[str, Any] = {}

        if not headers:
            return result

        for key, value in headers:
            if value is None:
                result[str(key)] = None
                continue

            try:
                result[str(key)] = value.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                result[str(key)] = value

        return result

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def poll_messages(
        self,
        timeout_ms: int = 1000,
        max_records: int = 1,
    ) -> list[TransportMessage]:
        """Poll Kafka and return thin ``TransportMessage`` objects.

        No parsing or validation is performed here. Payload is passed
        through as-is. Command-id extraction is best-effort and only
        consults Kafka headers; a synthetic offset-based id is used
        when no recognized header is present.
        """
        consumer = self._consumer
        if consumer is None:
            return []

        self._ensure_topics_up_to_date()

        try:
            records = consumer.consume(
                num_messages=int(max_records),
                timeout=float(timeout_ms) / 1000.0,
            )
        except KafkaException:
            logger.exception("Kafka poll failed")
            return []
        except Exception:
            logger.exception("Unexpected Kafka polling error")
            return []

        if not records:
            return []

        out: list[TransportMessage] = []

        for rec in records:
            if rec is None:
                continue

            error = rec.error()
            if error is not None:
                if error.code() == KafkaError._PARTITION_EOF:
                    continue

                logger.error("Kafka consumer error: %s", error)
                continue

            topic = rec.topic()
            partition = rec.partition()
            offset = rec.offset()

            headers = self._to_headers(rec.headers())
            raw_key = rec.key()
            key = (
                raw_key.decode("utf-8", errors="replace")
                if isinstance(raw_key, bytes)
                else raw_key
            )

            command_id = (
                _extract_command_id_from_headers(rec.headers())
                or _build_synthetic_command_id(topic, partition, offset)
            )

            cref = KafkaCommitRef(
                topic=str(topic),
                partition=int(partition),
                offset=int(offset),
            )

            token = AckToken(
                command_id=command_id,
                transport_ref=cref,
                topic=str(topic),
                partition=int(partition),
                offset=int(offset),
            )

            out.append(
                TransportMessage(
                    payload=rec.value(),
                    key=key,
                    headers=headers,
                    timestamp_ms=getattr(rec, "timestamp", lambda: None)()[0]
                    if callable(getattr(rec, "timestamp", None))
                    else None,
                    ack_token=token,
                )
            )

        return out

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def ack(
        self,
        token: AckToken,
        status: str = "SUCCESS",
    ) -> None:
        """Commit the Kafka record referenced by ``token``.

        Commit semantics:
        - Only records with a ``KafkaCommitRef`` in ``transport_ref``
          can be committed.
        - Commit is synchronous (``asynchronous=False``) so the caller
          can rely on commit completion before proceeding.
        """
        if token is None:
            raise ValueError("AckToken must not be None")

        ref = token.transport_ref
        if not isinstance(ref, KafkaCommitRef):
            # Transports without a Kafka ref (e.g. fake/test) simply
            # no-op. This keeps the interface uniform.
            logger.debug(
                "ack() called without a KafkaCommitRef for command_id=%s "
                "(status=%s); no commit performed",
                token.command_id,
                status,
            )
            return

        consumer = self._consumer
        if consumer is None:
            raise RuntimeError("Kafka consumer is unavailable")

        try:
            consumer.commit(
                offsets=[
                    _topic_partition_offset(ref.topic, ref.partition, ref.offset)
                ],
                asynchronous=False,
            )
        except Exception:
            logger.exception(
                "Kafka manual commit failed for command_id=%s "
                "topic=%s partition=%s offset=%s",
                token.command_id,
                ref.topic,
                ref.partition,
                ref.offset,
            )
            raise

        logger.debug(
            "Kafka record committed for command_id=%s topic=%s "
            "partition=%s offset=%s",
            token.command_id,
            ref.topic,
            ref.partition,
            ref.offset,
        )

    def nack(
        self,
        token: AckToken,
        reason: str,
        retryable: bool = True,
    ) -> None:
        """Negatively acknowledge a Kafka record.

        The transport does NOT commit the offset. It logs the reason
        and, if the record is retryable, relies on the consumer's
        ``auto.offset.reset`` / redelivery policy. Non-retryable
        nacks are logged but still not committed by default, so the
        record may be redelivered until an explicit policy is added
        (e.g. DLQ).
        """
        if token is None:
            raise ValueError("AckToken must not be None")

        safe_reason = _sanitize_reason(reason)

        logger.warning(
            "nack received for command_id=%s retryable=%s reason=%s",
            token.command_id,
            retryable,
            safe_reason,
        )

        # No offset movement here on purpose. Commit/redelivery policy
        # is owned by a higher layer.


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _topic_partition_offset(
    topic: str,
    partition: int,
    offset: int,
) -> Any:
    """Build a ``TopicPartition`` lazily to avoid import-time coupling."""
    from confluent_kafka import TopicPartition

    return TopicPartition(topic, partition, offset + 1)


_MAX_REASON_LEN = 256


def _sanitize_reason(reason: Any) -> str:
    """Truncate and strip a reason string for safe logging."""
    if reason is None:
        return ""

    text = str(reason)
    if len(text) > _MAX_REASON_LEN:
        text = text[: _MAX_REASON_LEN - 3] + "..."

    return text


__all__ = ["KafkaListener", "KafkaCommitRef"]