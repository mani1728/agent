# Path: Version 1_0_0/agent/transport/kafka/kafka_transport.py

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from agent.contracts.command import CommandEnvelope
from agent.contracts.heartbeat import HeartbeatPayload
from agent.contracts.response import ResponseEnvelope
from agent.transport.base import ITransportClient

from .listener import KafkaListener
from .responder import KafkaResponder


logger = logging.getLogger(__name__)


class KafkaTransport(ITransportClient):
    """
    Kafka implementation of the transport-independent ITransportClient.

    Responsibilities:
        - Start/stop Kafka transport resources.
        - Poll incoming commands.
        - Send responses.
        - Send heartbeat payloads.
        - Provide the transport boundary for command acknowledgements.

    Important:
        This class does not execute commands.
        It does not know about Mt5_Manager, Dispatcher, or CommandExecutor.

    Reliability features such as:
        - retry
        - persistent spool
        - circuit breaker
        - idempotency
        - durable acknowledgement
        - recovery after process crash

    belong to later migration phases.
    """

    def __init__(
        self,
        config: Optional[Any] = None,
    ) -> None:
        self.config = config

        self.listener = KafkaListener(
            config=config,
        )

        self.responder = KafkaResponder(
            config=config,
        )

        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the Kafka transport.

        The listener itself remains polling-driven. No permanent
        listener thread is created here.
        """

        if self._started:
            return

        self.listener.start()

        self._started = True

        logger.info("Kafka transport started")

    def stop(self) -> None:
        """
        Stop Kafka transport resources.

        Shutdown order:
            1. Stop listener.
            2. Close listener consumer.
            3. Flush/close responder producer.
        """

        if not self._started:
            # Still make shutdown idempotent in case resources were
            # partially initialized.
            try:
                self.listener.close()
            except Exception:
                logger.exception(
                    "Failed to close Kafka listener"
                )

            try:
                self.responder.close()
            except Exception:
                logger.exception(
                    "Failed to close Kafka responder"
                )

            return

        try:
            self.listener.stop()
        except Exception:
            logger.exception(
                "Failed to stop Kafka listener"
            )

        try:
            self.listener.close()
        except Exception:
            logger.exception(
                "Failed to close Kafka listener"
            )

        try:
            self.responder.close()
        except Exception:
            logger.exception(
                "Failed to close Kafka responder"
            )

        self._started = False

        logger.info("Kafka transport stopped")

    # ------------------------------------------------------------------
    # Command polling
    # ------------------------------------------------------------------

    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> Sequence[CommandEnvelope]:
        """
        Poll Kafka for incoming commands.

        Returns:
            A sequence of canonical CommandEnvelope objects.

        No command execution occurs here.
        """

        if not self._started:
            self.start()

        return self.listener.poll_commands(
            timeout_sec=timeout_sec,
        )

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def send_response(
        self,
        response: ResponseEnvelope,
    ) -> bool:
        """
        Send a canonical ResponseEnvelope through Kafka.
        """

        if not isinstance(response, ResponseEnvelope):
            raise TypeError(
                "response must be ResponseEnvelope"
            )

        return self.responder.send_response(
            response,
        )

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def send_heartbeat(
        self,
        status: HeartbeatPayload,
    ) -> bool:
        """
        Send a HeartbeatPayload through Kafka.

        Phase 1:
            Heartbeat is serialized and sent to the configured status
            topic using the existing Kafka Producer.

        The actual ClientAuth heartbeat flow remains untouched for now.
        This method provides the transport-independent boundary needed
        by the target architecture.
        """

        if not isinstance(status, HeartbeatPayload):
            raise TypeError(
                "status must be HeartbeatPayload"
            )

        producer = self.responder._ensure_producer()

        if producer is None:
            logger.warning(
                "Cannot send heartbeat: Kafka producer unavailable"
            )
            return False

        topic = self._get_config_value(
            "kafka.topics.status",
            "clients.status",
        )

        topic = str(topic or "").strip()

        if not topic:
            logger.error(
                "Kafka heartbeat/status topic is empty"
            )
            return False

        try:
            from .serializers import KafkaSerializer

            payload = KafkaSerializer.serialize_heartbeat(
                status,
            )

            headers = [
                (
                    "schema",
                    status.schema_version.encode("utf-8"),
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

            if status.agent_id:
                headers.append(
                    (
                        "client_id",
                        status.agent_id.encode("utf-8"),
                    )
                )

            producer.produce(
                topic=topic,
                key=status.agent_id or None,
                value=payload,
                headers=headers,
                on_delivery=self.responder._delivery_cb,
            )

            producer.poll(0)
            producer.flush()

            return True

        except BufferError:
            logger.exception(
                "Kafka producer queue is full while sending heartbeat"
            )
            return False

        except Exception:
            logger.exception(
                "Failed to send Kafka heartbeat"
            )
            return False

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def ack_command(
        self,
        command_id: str,
    ) -> None:
        """
        Acknowledge command consumption.

        IMPORTANT:
        Phase 1 deliberately does not change Kafka offset semantics.

        The legacy configuration currently uses:
            enable.auto.commit = true

        Therefore there is no durable/manual commit implementation here.

        A real acknowledgement policy must later map:

            consumed
                ↓
            execution started
                ↓
            execution finished
                ↓
            response published
                ↓
            Kafka offset committed

        against crash/restart behavior before changing auto-commit.
        """

        if not command_id:
            raise ValueError(
                "command_id must not be empty"
            )

        logger.debug(
            "Kafka command acknowledgement requested: command_id=%s",
            command_id,
        )

        # Intentionally no manual Kafka commit in Phase 1.

    # ------------------------------------------------------------------
    # Helpers
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
            value = config.get(
                key,
                default,
            )
        except AttributeError:
            return default

        return default if value is None else value

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