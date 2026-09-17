"""Capability provider boundary contracts.

This module defines transport-independent boundaries for capability discovery.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent.contracts.capability import CapabilityDescriptor


class CapabilityProviderPort(ABC):
    """Application boundary for capability discovery."""

    @abstractmethod
    def get_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return immutable registered capabilities."""
        raise NotImplementedError


__all__ = ["CapabilityProviderPort"]
