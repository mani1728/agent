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
from typing import Sequence

from ..contracts.command import CommandEnvelope
from ..contracts.heartbeat import HeartbeatPayload
from ..contracts.response import ResponseEnvelope


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
    ) -> None:
        """Acknowledge transport-level processing of a command.

        Parameters
        ----------
        command_id:
            Unique command identifier being acknowledged.

        Notes
        -----
        The exact acknowledgement semantics are transport-specific.

        For example, Kafka may map this operation to offset handling,
        while a future HTTP transport may implement it as a protocol
        acknowledgement or make it a no-op.

        The interface deliberately does not expose transport-specific
        acknowledgement details.
        """
        raise NotImplementedError


__all__ = [
    "ITransportClient",
]