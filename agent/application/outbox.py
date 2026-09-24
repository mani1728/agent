"""Transport-neutral at-least-once delivery of already durable outbound records."""
from __future__ import annotations
from typing import Protocol

class OutboundTransport(Protocol):
    def send(self, message: dict) -> None: ...

class DurableOutboxDelivery:
    def __init__(self, state, transport: OutboundTransport): self._state=state; self._transport=transport
    def deliver_pending(self) -> tuple[str, ...]:
        """A successful send attempt remains pending until a separate acknowledgement."""
        sent=[]
        for message in self._state.pending_outbox():
            self._transport.send(message)
            self._state.mark_sent(message['message_id'])
            sent.append(message['message_id'])
        return tuple(sent)
    def acknowledge(self, message_id: str) -> None: self._state.acknowledge(message_id)
