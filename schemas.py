"""Schema version constants and validators."""
from __future__ import annotations

from typing import FrozenSet, Iterable

SCHEMA_VERSION_COMMAND = "CommandV1"
SCHEMA_VERSION_RESULT = "Mt5ResultV1"
SCHEMA_VERSION_HEARTBEAT = "HeartbeatV1"

KNOWN_COMMAND_SCHEMAS: FrozenSet[str] = frozenset({SCHEMA_VERSION_COMMAND, "CommandV1 frozenset({SCHEMA_VERSION_COMMAND, "CommandV1"})
KNOWN({SCHEMA_VERSION_RESULT, "Mt5ResultV1"})
KNOWN_HEARTBEAT_SCHEMAS: FrozenSet[str] = frozenset({SCHEMA_VERSION_HEARTBEAT, "HeartbeatV1"})

def validate_command_schema(version: str) -> bool:
    return version in KNOWN_COMMAND_SCHEMAS

def validate_result_schema(version: str) -> bool:
    return version in KNOWN_RESULT_SCHEMAS

def validate_heartbeat_schema(version: str) -> bool:
    return version in KNOWN_HEARTBEAT_SCHEMAS

def assert_known_schema(version: str, known: Iterable[str], label: str) -> None:
    """Raise ValueError with a clear message if the schema version is unknown."""
    known_set = frozenset(known)
    if version not in known_set:
        raise ValueError(
            "Unknown " + label + " schema version: %r. Expected one of %s"
            % (version, sorted(known_set))
        )
