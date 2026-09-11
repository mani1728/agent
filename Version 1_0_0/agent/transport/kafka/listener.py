# Path: Version 1_0_0/agent/transport/kafka/listener.py

from __future__ import annotations

import ast
import json
import logging
import threading
from typing import Any, Mapping, Optional, Sequence
from uuid import uuid4

from confluent_kafka import Consumer, KafkaError, KafkaException

from agent.contracts.command import CommandEnvelope
from agent.infrastructure.config_manager import HotReloadConfig, cfg


logger = logging.getLogger(__name__)


class KafkaListener:
    """
    Kafka command listener.

    Responsibilities:
        - Create and manage Kafka Consumer.
        - Subscribe to configured command topics.
        - Hot-reload command topics.
        - Poll Kafka messages.
        - Extract correlation/auth/transport metadata.
        - Parse JSON payloads with legacy literal fallback.
        - Normalize single-command and multi-command payloads.
        - Convert each command into CommandEnvelope.

    This class intentionally does NOT:
        - Execute Mt5_Manager methods.
        - Import MetaTrader5.
        - Dispatch business commands.
        - Retry business operations.
        - Commit offsets as part of business execution.
        - Perform HTTP/Gateway communication.
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
            return ",".join(str(item).strip() for item in value if str(item).strip())

        return str(value or "").strip()

    def _get_config_value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Read configuration using the existing dotted-access config manager.
        """
        try:
            value = self.config.get(key, default)
        except AttributeError:
            value = default

        return default if value is None else value

    def _build_consumer_config(self) -> dict[str, Any]:
        """
        Build confluent-kafka Consumer configuration.

        Existing Kafka behavior is intentionally preserved.
        """

        bootstrap_servers = self._get_config_value(
            "kafka.bootstrap_servers",
            [],
        )

        group_id = self._get_config_value(
            "kafka.group_id",
            "mt5-service",
        )

        auto_offset_reset = self._get_config_value(
            "kafka.consumer_auto_offset_reset",
            "latest",
        )

        enable_auto_commit = self._get_config_value(
            "kafka.enable_auto_commit",
            True,
        )

        session_timeout_ms = self._get_config_value(
            "kafka.session_timeout_ms",
            45000,
        )

        security_protocol = self._get_config_value(
            "kafka.security_protocol",
            "PLAINTEXT",
        )

        sasl_mechanism = self._get_config_value(
            "kafka.sasl_mechanism",
            "PLAIN",
        )

        sasl_username = self._get_config_value(
            "kafka.sasl_username",
            "",
        )

        sasl_password = self._get_config_value(
            "kafka.sasl_password",
            "",
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
        topics = self._get_config_value(
            "kafka.topics.commands",
            [],
        )

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
        """
        Create a Kafka consumer and subscribe to command topics.

        This is intentionally close to the old listener behavior.
        """

        if not bool(
            self._get_config_value(
                "kafka.enabled",
                True,
            )
        ):
            logger.info("Kafka is disabled; listener consumer will not start")
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
                logger.exception("Failed to close previous Kafka consumer")

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
    # Message parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_json_or_literal(value: Any) -> Any:
        """
        Parse JSON first.

        Legacy compatibility:
        If JSON parsing fails, ast.literal_eval() is attempted.
        """

        if isinstance(value, (dict, list)):
            return value

        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")

        if not isinstance(value, str):
            return value

        text = value.strip()

        if not text:
            return None

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            raise ValueError("Kafka message is neither valid JSON nor literal data")

    @staticmethod
    def _normalize_commands(payload: Any) -> list[dict[str, Any]]:
        """
        Normalize legacy payload formats.

        Supported:
            {"method": "...", "params": {...}}
            [{"method": "...", ...}, {...}]
        """

        if isinstance(payload, dict):
            return [payload]

        if isinstance(payload, list):
            commands: list[dict[str, Any]] = []

            for item in payload:
                if not isinstance(item, dict):
                    raise TypeError(
                        "Every command in a command list must be an object"
                    )

                commands.append(item)

            return commands

        raise TypeError(
            "Kafka command payload must be an object or a list of objects"
        )

    # ------------------------------------------------------------------
    # Kafka headers / metadata
    # ------------------------------------------------------------------

    @staticmethod
    def _headers_to_dict(
        headers: Optional[Sequence[tuple[str, Optional[bytes]]]],
    ) -> dict[str, Any]:
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

    @staticmethod
    def _extract_correlation_id(
        headers: Mapping[str, Any],
        payload: Any,
    ) -> str:
        """
        Preserve legacy correlation-id precedence:

        1. headers.corr_id
        2. headers.correlation_id
        3. payload.corr_id
        4. payload.correlation_id
        5. generated UUID
        """

        corr_id = headers.get("corr_id")

        if corr_id:
            return str(corr_id)

        corr_id = headers.get("correlation_id")

        if corr_id:
            return str(corr_id)

        if isinstance(payload, dict):
            corr_id = payload.get("corr_id")

            if corr_id:
                return str(corr_id)

            corr_id = payload.get("correlation_id")

            if corr_id:
                return str(corr_id)

        return str(uuid4())

    # ------------------------------------------------------------------
    # Envelope creation
    # ------------------------------------------------------------------

    def _build_envelope(
        self,
        command: Mapping[str, Any],
        *,
        correlation_id: str,
        headers: Mapping[str, Any],
        partition: Optional[int],
        offset: Optional[int],
        request_index: int,
    ) -> CommandEnvelope:
        """
        Convert one legacy command object into the canonical envelope.
        """

        metadata: dict[str, Any] = {
            "transport": "kafka",
            "request_index": request_index,
            "headers": dict(headers),
        }

        if partition is not None:
            metadata["partition"] = partition

        if offset is not None:
            metadata["offset"] = offset

        return CommandEnvelope.from_dict(
            dict(command),
            correlation_id=correlation_id,
            metadata=metadata,
        )

    def parse_message(
        self,
        value: Any,
        *,
        headers: Optional[Sequence[tuple[str, Optional[bytes]]]] = None,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[CommandEnvelope]:
        """
        Parse one Kafka message into one or more CommandEnvelope objects.

        This method is deliberately transport-facing and contains no
        business execution.
        """

        header_map = self._headers_to_dict(headers)

        payload = self.parse_json_or_literal(value)

        correlation_id = self._extract_correlation_id(
            header_map,
            payload,
        )

        commands = self._normalize_commands(payload)

        envelopes: list[CommandEnvelope] = []

        for index, command in enumerate(commands):
            envelope = self._build_envelope(
                command,
                correlation_id=correlation_id,
                headers=header_map,
                partition=partition,
                offset=offset,
                request_index=index,
            )

            envelopes.append(envelope)

        return envelopes

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> list[CommandEnvelope]:
        """
        Poll Kafka and return normalized CommandEnvelope objects.

        No command is executed here.
        """

        consumer = self._consumer

        if consumer is None:
            return []

        self._ensure_topics_up_to_date()

        try:
            message = consumer.poll(timeout=float(timeout_sec))

        except KafkaException:
            logger.exception("Kafka poll failed")
            return []

        except Exception:
            logger.exception("Unexpected Kafka polling error")
            return []

        if message is None:
            return []

        if message.error():
            error = message.error()

            if error.code() == KafkaError._PARTITION_EOF:
                return []

            logger.error(
                "Kafka consumer error: %s",
                error,
            )

            return []

        try:
            envelopes = self.parse_message(
                message.value(),
                headers=message.headers(),
                partition=message.partition(),
                offset=message.offset(),
            )

            logger.debug(
                "Kafka message normalized: topic=%s partition=%s offset=%s "
                "commands=%s",
                message.topic(),
                message.partition(),
                message.offset(),
                len(envelopes),
            )

            return envelopes

        except Exception:
            logger.exception(
                "Failed to parse Kafka command: topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )

            return []

    # ------------------------------------------------------------------
    # Compatibility listen loop
    # ------------------------------------------------------------------

    def listen(self) -> None:
        """
        Legacy-compatible blocking listen loop.

        IMPORTANT:
        This method currently only polls and logs normalized commands.
        Execution will be wired through CommandExecutor in the later
        worker/transport integration phase.
        """

        self.start()

        try:
            while self.running and not self._stop_event.is_set():
                envelopes = self.poll_commands(timeout_sec=1.0)

                for envelope in envelopes:
                    logger.debug(
                        "Received command: command_id=%s "
                        "target=%s.%s correlation_id=%s",
                        envelope.command_id,
                        envelope.target_class,
                        envelope.target_method,
                        envelope.correlation_id,
                    )

        finally:
            self.close()


__all__ = ["KafkaListener"]

