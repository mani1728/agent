"""In-memory capability registry implementation."""

from __future__ import annotations

from collections.abc import Callable

from agent.application.ports.capability import CapabilityProviderPort
from agent.contracts.capability import CapabilityDescriptor
from agent.contracts.runtime_information import RuntimeInformationContract


class InMemoryCapabilityRegistry(CapabilityProviderPort):
    """Immutable runtime capability registry."""

    def __init__(
        self,
        capabilities: tuple[CapabilityDescriptor, ...],
        runtime_information: Callable[[], RuntimeInformationContract],
    ) -> None:
        self._capabilities = tuple(capabilities)
        self._runtime_information = runtime_information

    def get_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return registered capabilities."""
        return self._capabilities

    def get_runtime_information(self) -> RuntimeInformationContract:
        return self._runtime_information()


__all__ = ["InMemoryCapabilityRegistry"]
