# Path: agent/contracts/capability.py

"""Capability discovery contracts.

Transport-independent immutable capability metadata models.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Immutable description of an Agent capability."""

    name: str
    version: str
    schema_version: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("capability name must not be empty")

        if not self.version or not self.version.strip():
            raise ValueError("capability version must not be empty")

        if not self.schema_version or not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
        }


__all__ = ["CapabilityDescriptor"]
