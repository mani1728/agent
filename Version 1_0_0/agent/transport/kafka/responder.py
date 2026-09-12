# Path: Version 1_0_0/agent/transport/kafka/responder.py

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping, Optional, Sequence

from confluent_kafka import Producer

from agent.contracts.response import ResponseEnvelope
from agent.infrastructure.config_manager import cfg


logger = logging.getLogger(__name__)


class KafkaResponder:
    """
    Kafka response adapter.

    Responsibilities:
        - Create and maintain the Kafka Producer.
        - Hot-reload producer configuration.
        - Serialize ResponseEnvelope objects.
        - Preserve legacy response chunking.
        - Publish responses to the configured reply topic.

    This class intentionally does NOT:
        - Execute commands.
        - Know about Mt5_Manager.
        - Perform business retries.
        - Implement transport-independent reliability.
        - Persist failed responses.
    """

    def __init__(
        self,
        config: Optional[Any] = None,
    ) -> None:
        self.config = config or cfg()

        self._producer: Optional[Producer] = None
        self._producer_signature: Optional[tuple[Any, ...]] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _get_config_value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        try:
            value = self.config.get(key, default)
        except AttributeError:
            value = default

        return default if value is None else value

    @staticmethod
    def _servers_to_string(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ",".join(
                str(item).strip()
                for item in value
                if str(item).strip()
            )

        return str(value or "").strip()

    def _current_producer_config(self) -> dict[str, Any]:
        bootstrap_servers = self._get_config_value(
            "kafka.bootstrap_servers",
            [],
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

        acks = self._get_config_value(
            "kafka.acks",
            "all",
        )

        retries = self._get_config_value(
            "kafka.retries",
            3,
        )

        linger_ms = self._get_config_value(
            "kafka.linger_ms",
            5,
        )

        request_timeout_ms = self._get_config_value(
            "kafka.request_timeout_ms",
            30000,
        )

        compression_type = self._get_config_value(
            "kafka.compression_type",
            "",
        )

        producer_config: dict[str, Any] = {
            "bootstrap.servers": self._servers_to_string(
                bootstrap_servers
            ),
            "acks": str(acks),
            "retries": int(retries),
            "linger.ms": int(linger_ms),
            "request.timeout.ms": int(request_timeout_ms),

            # Preserve legacy idempotent producer behavior.
            "enable.idempotence": True,

            "security.protocol": str(security_protocol),
        }

        if sasl_mechanism:
            producer_config["sasl.mechanisms"] = str(sasl_mechanism)

        if sasl_username:
            producer_config["sasl.username"] = str(sasl_username)

        if sasl_password:
            producer_config["sasl.password"] = str(sasl_password)

        if compression_type:
            producer_config["compression.type"] = str(
                compression_type
            )

        return producer_config

    def _current_topic(self) -> str:
        topic = self._get_config_value(
            "kafka.topics.replies",
            "server.replies",
        )

        return str(topic).strip()

    def _current_chunk_size(self) -> int:
        value = self._get_config_value(
            "kafka.response_max_part_bytes",
            900 * 1024,
        )

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 900 * 1024

        # Kafka message chunks must always have a usable positive size.
        return max(1, value)

    # ------------------------------------------------------------------
    # Producer lifecycle
    # ------------------------------------------------------------------

    def _make_signature(
        self,
        producer_config: Mapping[str, Any],
        topic: str,
        chunk_size: int,
    ) -> tuple[Any, ...]:
        """
        Build a producer configuration signature.

        Password is intentionally not included in logs or diagnostics.
        """

        return (
            producer_config.get("bootstrap.servers"),
            producer_config.get("security.protocol"),
            producer_config.get("sasl.mechanisms"),
            producer_config.get("sasl.username"),
            producer_config.get("acks"),
            producer_config.get("retries"),
            producer_config.get("linger.ms"),
            producer_config.get("request.timeout.ms"),
            producer_config.get("compression.type"),
            producer_config.get("enable.idempotence"),
            topic,
            chunk_size,
        )

    def _ensure_producer(self) -> Optional[Producer]:
        if not bool(
            self._get_config_value(
                "kafka.enabled",
                True,
            )
        ):
            return None

        producer_config = self._current_producer_config()
        topic = self._current_topic()
        chunk_size = self._current_chunk_size()

        signature = self._make_signature(
            producer_config,
            topic,
            chunk_size,
        )

        if (
            self._producer is not None
            and self._producer_signature == signature
        ):
            return self._producer

        old_producer = self._producer
        self._producer = None
        self._producer_signature = None

        if old_producer is not None:
            try:
                old_producer.flush()
            except Exception:
                logger.exception(
                    "Failed to flush previous Kafka producer"
                )

        try:
            producer = Producer(producer_config)

            self._producer = producer
            self._producer_signature = signature

            logger.info(
                "Kafka response producer initialized: "
                "bootstrap=%s topic=%s",
                producer_config.get("bootstrap.servers"),
                topic,
            )

            return producer

        except Exception:
            logger.exception(
                "Failed to initialize Kafka response producer"
            )

            self._producer = None
            self._producer_signature = None

            return None

    def close(self) -> None:
        """Flush and release the Kafka producer."""

        producer = self._producer
        self._producer = None
        self._producer_signature = None

        if producer is None:
            return

        try:
            producer.flush()
        except Exception:
            logger.exception(
                "Failed to flush Kafka response producer during close"
            )

        close = getattr(producer, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                logger.exception(
                    "Failed to close Kafka response producer"
                )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_response(
        response: ResponseEnvelope | Mapping[str, Any],
    ) -> bytes:
        if isinstance(response, ResponseEnvelope):
            payload = response.to_dict()
        elif isinstance(response, Mapping):
            payload = dict(response)
        else:
            raise TypeError(
                "response must be ResponseEnvelope or mapping"
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_bytes(
        payload: bytes,
        chunk_size: int,
    ) -> list[bytes]:
        """
        Split a serialized response into bounded byte chunks.

        Legacy behavior:
            - At least one chunk is always returned.
        """

        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        if not payload:
            return [b""]

        return [
            payload[index:index + chunk_size]
            for index in range(0, len(payload), chunk_size)
        ]

    # ------------------------------------------------------------------
    # Delivery callback
    # ------------------------------------------------------------------

    @staticmethod
    def _delivery_cb(
        err: Any,
        message: Any,
    ) -> None:
        if err is not None:
            logger.error(
                "Kafka response delivery failed: %s",
                err,
            )
            return

        try:
            logger.debug(
                "Kafka response delivered: topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
        except Exception:
            logger.debug(
                "Kafka response delivered successfully"
            )

    # ------------------------------------------------------------------
    # Response publishing
    # ------------------------------------------------------------------

    def send_result(
        self,
        response: ResponseEnvelope | Mapping[str, Any],
        *,
        correlation_id: Optional[str] = None,
        headers: Optional[
            Sequence[tuple[str, bytes]]
        ] = None,
        key: Optional[str] = None,
        flush: bool = True,
    ) -> bool:
        """
        Publish a response to Kafka.

        ResponseEnvelope is the canonical input, while Mapping remains
        supported for legacy compatibility.
        """

        producer = self._ensure_producer()

        if producer is None:
            logger.warning(
                "Kafka response producer is unavailable"
            )
            return False

        topic = self._current_topic()

        if not topic:
            logger.error(
                "Kafka response topic is empty"
            )
            return False

        chunk_size = self._current_chunk_size()

        try:
            payload = self._serialize_response(response)
        except Exception:
            logger.exception(
                "Failed to serialize Kafka response"
            )
            return False

        chunks = self._chunk_bytes(
            payload,
            chunk_size,
        )

        if isinstance(response, ResponseEnvelope):
            response_dict = response.to_dict()

            schema_version = str(
                response_dict.get(
                    "schema_version",
                    "Mt5ResultV1",
                )
            )

            response_corr_id = response_dict.get(
                "correlation_id"
            )

        else:
            response_dict = dict(response)

            schema_version = str(
                response_dict.get(
                    "schema_version",
                    response_dict.get(
                        "schema",
                        "Mt5ResultV1",
                    ),
                )
            )

            response_corr_id = response_dict.get(
                "correlation_id",
                response_dict.get("corr_id"),
            )

        effective_corr_id = (
            correlation_id
            or response_corr_id
        )

        extra_headers: list[tuple[str, bytes]] = []

        if headers:
            for header_key, header_value in headers:
                if isinstance(header_value, str):
                    header_value = header_value.encode("utf-8")

                extra_headers.append(
                    (
                        str(header_key),
                        bytes(header_value),
                    )
                )

        total = len(chunks)
        delivery_errors: list[Any] = []
        delivery_successes = 0

        def _delivery_result(err: Any, message: Any) -> None:
            nonlocal delivery_successes
            if err is not None:
                delivery_errors.append(err)
            else:
                delivery_successes += 1
            self._delivery_cb(err, message)

        try:
            for sequence, chunk in enumerate(chunks):
                kafka_headers: list[tuple[str, bytes]] = [
                    (
                        "schema",
                        schema_version.encode("utf-8"),
                    ),
                    (
                        "seq",
                        str(sequence).encode("ascii"),
                    ),
                    (
                        "total",
                        str(total).encode("ascii"),
                    ),
                    (
                        "content_type",
                        b"application/json",
                    ),
                    (
                        "encoding",
                        b"identity",
                    ),
                ]

                if effective_corr_id:
                    kafka_headers.append(
                        (
                            "corr_id",
                            str(effective_corr_id).encode("utf-8"),
                        )
                    )

                kafka_headers.extend(extra_headers)

                producer.produce(
                    topic=topic,
                    key=key,
                    value=chunk,
                    headers=kafka_headers,
                    on_delivery=_delivery_result,
                )

                # Allow librdkafka to serve delivery callbacks and
                # maintain the producer queue.
                producer.poll(0)

            if flush:
                remaining = producer.flush()
                if remaining not in (None, 0):
                    logger.error(
                        "Kafka response delivery did not complete; pending_messages=%s",
                        remaining,
                    )
                    return False

            if delivery_errors:
                logger.error(
                    "Kafka response delivery failed for %s message(s)",
                    len(delivery_errors),
                )
                return False

            if flush and delivery_successes != total:
                logger.error(
                    "Kafka response delivery could not be confirmed: confirmed=%s expected=%s",
                    delivery_successes,
                    total,
                )
                return False

            if not flush:
                logger.warning(
                    "Kafka response publication is asynchronous; delivery cannot be confirmed before ACK"
                )
                return False

            return True

        except BufferError:
            logger.exception(
                "Kafka producer local queue is full"
            )
            return False

        except Exception:
            logger.exception(
                "Failed to publish Kafka response"
            )
            return False

    # ------------------------------------------------------------------
    # Canonical API
    # ------------------------------------------------------------------

    def send_response(
        self,
        response: ResponseEnvelope,
        *,
        flush: bool = True,
    ) -> bool:
        """
        Canonical transport-facing response method.
        """

        return self.send_result(
            response,
            flush=flush,
        )


__all__ = ["KafkaResponder"]