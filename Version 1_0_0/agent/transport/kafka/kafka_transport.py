# Path: Version 1_0_0/agent/transport/kafka/kafka_transport.py

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from agent.contracts.command import CommandEnvelope
from agent.contracts.heartbeat import HeartbeatPayload
from agent.contracts.response import ResponseEnvelope
from agent.transport.base import AckToken, ITransportClient

from .listener import KafkaListener
from .responder import KafkaResponder
from .commit_policy import (
    CommandCommitTracker,
    CommitState,
    KafkaCommitPolicy,
)


logger = logging.getLogger(__name__)


class KafkaTransport(ITransportClient):
    """
    Kafka implementation of the transport-independent ITransportClient.
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
    # Lifecycle
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
    # Command polling
    # ------------------------------------------------------------------

    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> Sequence[CommandEnvelope]:
        if not self._started:
            self.start()

        commands = self.listener.poll_commands(timeout_sec=timeout_sec)

        if self._commit_policy.is_application_managed:
            for command in commands:
                # Try to capture commit reference from listener if available.
                # This keeps commit logic transport-safe and future-proof.
                commit_ref = None
                try:
                    if hasattr(self.listener, "get_commit_ref"):
                        commit_ref = self.listener.get_commit_ref(command.command_id)
                except Exception:
                    logger.debug(
                        "Failed to fetch commit ref for command_id=%s",
                        command.command_id,
                        exc_info=True,
                    )

                self._commit_trackers[command.command_id] = CommandCommitTracker(
                    command.command_id,
                    commit_ref=commit_ref,
                )
        else:
            for command in commands:
                self.listener.release_pending_record(command.command_id)

        return commands

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def send_response(
        self,
        response: ResponseEnvelope,
    ) -> bool:
        if not isinstance(response, ResponseEnvelope):
            raise TypeError("response must be ResponseEnvelope")

        return self.responder.send_response(response)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def send_heartbeat(
        self,
        status: HeartbeatPayload,
    ) -> bool:
        if not isinstance(status, HeartbeatPayload):
            raise TypeError("status must be HeartbeatPayload")

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

            if status.agent_id:
                headers.append(("client_id", status.agent_id.encode("utf-8")))

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
            logger.exception("Kafka producer queue is full while sending heartbeat")
            return False
        except Exception:
            logger.exception("Failed to send Kafka heartbeat")
            return False

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def ack_command(
        self,
        command_id: str,
        *,
        ack_token: Optional[AckToken] = None,
    ) -> None:
        """
        Acknowledge command consumption (application-managed path).

        Safe usage:
            call only after:
                - response publication success (after_response), OR
                - spool persistence success (after_spool; later phase)
        """
        if not command_id:
            raise ValueError("command_id must not be empty")

        if ack_token is not None and ack_token.command_id != command_id:
            raise ValueError(
                "ack_token.command_id must match command_id"
            )

        if not self._commit_policy.is_application_managed:
            logger.debug(
                "Kafka acknowledgement delegated to auto-commit: command_id=%s",
                command_id,
            )
            return

        tracker = self._commit_trackers.get(command_id)
        if tracker is None:
            logger.debug(
                "Ignoring duplicate/stale Kafka acknowledgement: command_id=%s",
                command_id,
            )
            return

        if tracker.state == CommitState.ACKED:
            return

        if tracker.state == CommitState.FAILED:
            logger.debug(
                "Skipping ACK for failed command: command_id=%s",
                command_id,
            )
            return

        # If caller provides a concrete transport token, prefer it.
        if ack_token is not None and ack_token.ref is not None:
            tracker.commit_ref = ack_token.ref

        # Current phase target: AFTER_RESPONSE
        # (worker must invoke ack only after successful response send)
        tracker.mark_response_sent()

        decision = self._commit_policy.evaluate(tracker)
        if not decision:
            logger.debug(
                "Kafka acknowledgement not committed: command_id=%s reason=%s state=%s",
                command_id,
                decision.reason,
                decision.state.value if decision.state else None,
            )
            return

        related_command_ids = self.listener.related_command_ids(command_id)
        committed = self.listener.commit_command(command_id)
        if not committed:
            # Batched record: keep tracker state until last sibling can advance offset.
            return

        for tracked_command_id in related_command_ids:
            tracked_tracker = self._commit_trackers.pop(tracked_command_id, None)
            if tracked_tracker is not None:
                tracked_tracker.mark_acked()

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
            value = config.get(key, default)
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
