"""Versioned, allowlisted protocol contracts for Agent commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping


class CapabilityClass(str, Enum):
    READ = "read"
    LOCAL_STATE = "local_state"
    TRADE_ANALYSIS = "trade_analysis"
    TRADE_EXECUTION = "trade_execution"
    CHART_TERMINAL = "chart_terminal"


@dataclass(frozen=True, order=True)
class ProtocolVersion:
    value: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("protocol version must be a non-empty string")

    def to_dict(self) -> dict[str, str]:
        return {"version": self.value}


@dataclass(frozen=True)
class CommandDefinition:
    identifier: str
    version: str
    capability_class: CapabilityClass
    handler: Callable[[Any], Any]
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("command identifier must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("command version must be a non-empty string")
        if not isinstance(self.capability_class, CapabilityClass):
            raise ValueError("capability_class must be a CapabilityClass")
        if not callable(self.handler):
            raise ValueError("command handler must be callable")

    def to_manifest_entry(self, *, class_enabled: bool) -> dict[str, Any]:
        return {"identifier": self.identifier, "version": self.version,
                "capability_class": self.capability_class.value,
                "enabled": bool(self.enabled and class_enabled)}


@dataclass(frozen=True)
class CapabilityManifest:
    agent_version: str
    protocol_version: ProtocolVersion
    commands: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.agent_version, str) or not self.agent_version.strip():
            raise ValueError("agent_version must be a non-empty string")
        object.__setattr__(self, "commands", tuple(MappingProxyType(dict(item)) for item in self.commands))

    def to_dict(self) -> dict[str, Any]:
        return {"agent_version": self.agent_version, "protocol_version": self.protocol_version.value,
                "commands": [dict(command) for command in self.commands]}


class ProtocolResolutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CommandRegistry:
    """Local registration authority; server input can only resolve entries here."""

    def __init__(self, protocol_version: ProtocolVersion | None = None,
                 class_enabled: Mapping[CapabilityClass, bool] | None = None) -> None:
        self.protocol_version = protocol_version or ProtocolVersion()
        self._commands: dict[str, CommandDefinition] = {}
        configured = dict(class_enabled or {})
        self._class_enabled = {item: bool(configured.get(item, True)) for item in CapabilityClass}

    def register(self, definition: CommandDefinition) -> None:
        if definition.identifier in self._commands:
            raise ValueError(f"command already registered: {definition.identifier}")
        self._commands[definition.identifier] = definition

    def set_class_enabled(self, capability_class: CapabilityClass, enabled: bool) -> None:
        if not isinstance(capability_class, CapabilityClass):
            raise ValueError("capability_class must be a CapabilityClass")
        self._class_enabled[capability_class] = bool(enabled)

    def set_command_enabled(self, identifier: str, enabled: bool) -> None:
        definition = self._commands.get(identifier)
        if definition is None:
            raise KeyError(identifier)
        self._commands[identifier] = CommandDefinition(definition.identifier, definition.version,
            definition.capability_class, definition.handler, bool(enabled))

    def resolve(self, identifier: str, version: str) -> CommandDefinition:
        definition = self._commands.get(identifier)
        if definition is None:
            raise ProtocolResolutionError("UNSUPPORTED_COMMAND", "Unsupported command.")
        if definition.version != version:
            raise ProtocolResolutionError("UNSUPPORTED_COMMAND_VERSION", "Unsupported command version.")
        if not self._class_enabled[definition.capability_class]:
            raise ProtocolResolutionError("CAPABILITY_DISABLED", "Capability class is disabled.")
        if not definition.enabled:
            raise ProtocolResolutionError("COMMAND_DISABLED", "Command is disabled.")
        return definition

    def manifest(self, agent_version: str) -> CapabilityManifest:
        entries = tuple(definition.to_manifest_entry(class_enabled=self._class_enabled[definition.capability_class])
                        for definition in sorted(self._commands.values(), key=lambda item: (item.identifier, item.version)))
        return CapabilityManifest(agent_version, self.protocol_version, entries)
