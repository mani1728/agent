# Path: agent/transport/base.py

"""Transport interface definitions.

This module defines the transport-independent interface used by the
Agent application to communicate with external systems.

Concrete implementations may use Kafka, HTTP, WebSocket, or any other
transport, but the rest of the application should depend only on
ITransportClient.

No concrete transport implementation belongs in this module.

Design notes
------------
- The transport layer must NOT know about CommandEnvelope,
  ResponseEnvelope, HeartbeatPayload, or any other domain contract.
  It deals only with opaque payloads and ack tokens.
- Messages are exchanged as TransportMessage instances; parsing,
  validation, and deserialization are the responsibility of the
  caller (application layer), not the transport.
- Acknowledgement is expressed via AckToken so that the transport
  can be swapped (Kafka, HTTP, ...) without changing domain code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class AckToken:
    """Transport-agnostic acknowledgement token.

    Fields
    ------
    command_id:
        Canonical command identifier.
    transport_ref:
        Optional transport-specific commit/ack reference.
        Examples:
            - Kafka message object
            - (topic, partition, offset)
            - opaque broker delivery handle
    topic:
        Optional topic/queue name, when the transport exposes one.
    partition:
        Optional partition index, when applicable.
    offset:
        Optional offset/index, when applicable.
    """

    command_id: str
    transport_ref: Any = None
    topic: str | None = None
    partition: int | None = None
    offset: int | None = None


@dataclass(frozen=True)
class TransportMessage:
    """A single message received from a transport.

    The transport MUST NOT interpret ``payload``. It is delivered as-is
    (bytes, str, or already-deserialized dict) so that the application
    layer can perform parsing and validation.
    """

    payload: bytes | str | dict
    key: str | None
    headers: Mapping[str, Any] = field(default_factory=dict)
    timestamp_ms: int | None = None
    ack_token: AckToken | None = None


class ITransportClient(Protocol):
    """Abstract interface for Agent communication transports.

    A transport implementation is responsible for:

    - polling messages from the underlying broker/transport
    - acknowledging successfully processed messages
    - negatively acknowledging messages that could not be processed

    The Agent business/domain layer must not depend on the concrete
    transport implementation. Lifecycle concerns (start/stop) and
    domain-specific operations (send_response, send_heartbeat) are
    intentionally kept OUT of this interface and are expected to live
    in higher-level components that use the transport.
    """

    def poll_messages(
        self,
        timeout_ms: int = 1000,
        max_records: int = 1,
    ) -> list[TransportMessage]:
        """Poll for newly available messages.

        Parameters
        ----------
        timeout_ms:
            Maximum amount of time (in milliseconds) to wait for new
            messages before returning.
        max_records:
            Maximum number of messages to return in a single call.

        Returns
        -------
        list[TransportMessage]
            Zero or more transport messages. Parsing/validation is the
            caller's responsibility.
        """
        ...

    def ack(
        self,
        token: AckToken,
        status: str = "SUCCESS",
    ) -> None:
        """Acknowledge successful processing of a message.

        Parameters
        ----------
        token:
            Transport-agnostic token identifying the message and
            carrying any transport-specific commit reference.
        status:
            Optional status label for diagnostics/logging. Does not
            change the commit semantics.
        """
        ...

    def nack(
        self,
        token: AckToken,
        reason: str,
        retryable: bool = True,
    ) -> None:
        """Negatively acknowledge a message.

        Parameters
        ----------
        token:
            Transport-agnostic token identifying the message and
            carrying any transport-specific commit reference.
        reason:
            Human-readable reason for the failure. Must NOT contain
            secrets, credentials, or sensitive payload contents.
        retryable:
            Whether the transport is allowed to redeliver the message.
            Non-retryable nacks should not be retried by the transport.
        """
        ...


__all__ = [
    "AckToken",
    "TransportMessage",
    "ITransportClient",
]