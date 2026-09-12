# Path: agent/transport/base.py

"""Transport interface definitions.

This module defines the transport-independent interface used by the
Agent application to communicate with external systems.

Concrete implementations may use Kafka, HTTP, WebSocket, or any other
transport, but the rest of the application should depend only on
ITransportClient.

No concrete transport implementation belongs in this module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from ..contracts.command import CommandEnvelope
from ..contracts.heartbeat import HeartbeatPayload
from ..contracts.response import ResponseEnvelope


@dataclass(slots=True)
class AckToken:
    """Transport-agnostic acknowledgement token.

    Fields
    ------
    command_id:
        Canonical command identifier.
    ref:
        Optional transport-specific commit/ack reference.
        Examples:
            - Kafka message object
            - (topic, partition, offset)
            - opaque broker delivery handle
    meta:
        Optional diagnostic metadata for logging/tracing only.
    """

    command_id: str
    ref: Optional[Any] = None
    meta: Optional[dict[str, Any]] = None


class ITransportClient(ABC):
    """Abstract interface for Agent communication transports.

    A transport implementation is responsible for:

    - starting and stopping its communication resources
    - receiving commands
    - sending command responses
    - sending heartbeat/health information
    - acknowledging processed commands

    The Agent business/domain layer must not depend on the concrete
    transport implementation.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def start(self) -> None:
        """Start transport resources.

        Implementations may establish connections, initialize consumers,
        producers, sessions, or other transport-specific resources.
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop the transport and release its resources cleanly."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @abstractmethod
    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> Sequence[CommandEnvelope]:
        """Poll for newly available commands.

        Parameters
        ----------
        timeout_sec:
            Maximum amount of time the transport should wait for new
            commands before returning.

        Returns
        -------
        Sequence[CommandEnvelope]
            Zero or more validated command envelopes.

        Notes
        -----
        The returned commands must already satisfy the canonical
        CommandEnvelope contract. Transport-specific parsing,
        deserialization, and validation belong inside the concrete
        transport implementation.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    @abstractmethod
    def send_response(
        self,
        response: ResponseEnvelope,
    ) -> bool:
        """Send the result of a processed command.

        Parameters
        ----------
        response:
            Canonical transport-independent response envelope.

        Returns
        -------
        bool
            True when the transport accepted the response for sending;
            otherwise False.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    @abstractmethod
    def send_heartbeat(
        self,
        heartbeat: HeartbeatPayload,
    ) -> bool:
        """Send the current Agent health/status information.

        Parameters
        ----------
        heartbeat:
            Canonical transport-independent heartbeat payload.

        Returns
        -------
        bool
            True when the transport accepted the heartbeat for sending;
            otherwise False.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    @abstractmethod
    def ack_command(
        self,
        command_id: str,
        *,
        ack_token: Optional[AckToken] = None,
    ) -> None:
        """Acknowledge transport-level processing of a command.

        Parameters
        ----------
        command_id:
            Unique command identifier being acknowledged.
        ack_token:
            Optional transport-agnostic token that can carry
            transport-specific acknowledgement reference.

            - For Kafka manual commit: this SHOULD include offset/message
              reference required to commit safely.
            - For transports without explicit ack semantics: may be None.

        Notes
        -----
        The exact acknowledgement semantics are transport-specific.

        The interface remains transport-agnostic while allowing concrete
        adapters to receive commit metadata when needed.
        """
        raise NotImplementedError


__all__ = [
    "AckToken",
    "ITransportClient",
]
