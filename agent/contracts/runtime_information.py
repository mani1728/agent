# Path: agent/contracts/runtime_information.py

"""Runtime information contract.

Immutable transport-independent runtime snapshot model.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .capability import CapabilityDescriptor


@dataclass(frozen=True)
class RuntimeInformationContract:
    """Immutable runtime information snapshot."""

    agent_name: str
    agent_version: str
    schema_version: str
    lifecycle_state: str
    capabilities: tuple[CapabilityDescriptor, ...]
    metadata: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise ValueError("agent_name must not be empty")

        if not self.agent_version.strip():
            raise ValueError("agent_version must not be empty")

        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")

        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "schema_version": self.schema_version,
            "lifecycle_state": self.lifecycle_state,
            "capabilities": [item.to_dict() for item in self.capabilities],
            "metadata": dict(self.metadata),
        }


__all__ = ["RuntimeInformationContract"]
