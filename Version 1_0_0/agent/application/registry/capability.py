"""In-memory capability registry implementation."""

from __future__ import annotations

from agent.application.ports.capability import CapabilityProviderPort
from agent.contracts.capability import CapabilityDescriptor


class InMemoryCapabilityRegistry(CapabilityProviderPort):
    """Immutable runtime capability registry."""

    def __init__(self, capabilities: tuple[CapabilityDescriptor, ...]) -> None:
        self._capabilities = tuple(capabilities)

    def get_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return registered capabilities."""
        return self._capabilities


__all__ = ["InMemoryCapabilityRegistry"]
