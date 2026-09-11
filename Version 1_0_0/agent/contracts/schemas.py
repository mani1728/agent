# Path: agent/contracts/schemas.py

"""Schema version constants and validation helpers.

Backward-compatible rule
------------------------
- Major version bump:
    Breaking change. Unknown major versions are rejected.

- Minor version bump:
    Additive/non-breaking change. Compatible versions may be accepted.

The current contract uses V1 schema identifiers. Validation is kept
centralized in this module so command, response, and heartbeat contracts
share the same schema-version rules.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable


# ---------------------------------------------------------------------------
# Canonical schema versions
# ---------------------------------------------------------------------------

SCHEMA_VERSION_COMMAND = "CommandV1"
SCHEMA_VERSION_RESPONSE = "Mt5ResultV1"
SCHEMA_VERSION_HEARTBEAT = "HeartbeatV1"

# Backward-compatible alias.
#
# Older code may still import SCHEMA_VERSION_RESULT, while the canonical
# public name used by ResponseEnvelope is SCHEMA_VERSION_RESPONSE.
SCHEMA_VERSION_RESULT = SCHEMA_VERSION_RESPONSE


# ---------------------------------------------------------------------------
# Known schemas
# ---------------------------------------------------------------------------

KNOWN_COMMAND_SCHEMAS: FrozenSet[str] = frozenset(
    {
        SCHEMA_VERSION_COMMAND,
    }
)

KNOWN_RESPONSE_SCHEMAS: FrozenSet[str] = frozenset(
    {
        SCHEMA_VERSION_RESPONSE,
    }
)

# Backward-compatible alias for older code.
KNOWN_RESULT_SCHEMAS: FrozenSet[str] = KNOWN_RESPONSE_SCHEMAS

KNOWN_HEARTBEAT_SCHEMAS: FrozenSet[str] = frozenset(
    {
        SCHEMA_VERSION_HEARTBEAT,
    }
)


# ---------------------------------------------------------------------------
# Generic validation
# ---------------------------------------------------------------------------

def assert_known_schema(
    version: str,
    known: Iterable[str],
    label: str,
) -> None:
    """Raise ValueError if *version* is not a known schema version."""

    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"{label} schema version must be a non-empty string"
        )

    known_set = frozenset(known)

    if version not in known_set:
        raise ValueError(
            f"Unknown {label} schema version: {version!r}. "
            f"Expected one of {sorted(known_set)!r}"
        )


# ---------------------------------------------------------------------------
# Command schema
# ---------------------------------------------------------------------------

def validate_command_schema(version: str) -> bool:
    """Validate a command schema version."""

    assert_known_schema(
        version,
        KNOWN_COMMAND_SCHEMAS,
        "command",
    )

    return True


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

def validate_response_schema(version: str) -> bool:
    """Validate a response schema version."""

    assert_known_schema(
        version,
        KNOWN_RESPONSE_SCHEMAS,
        "response",
    )

    return True


# ---------------------------------------------------------------------------
# Legacy result schema compatibility
# ---------------------------------------------------------------------------

def validate_result_schema(version: str) -> bool:
    """Backward-compatible alias for response schema validation."""

    return validate_response_schema(version)


# ---------------------------------------------------------------------------
# Heartbeat schema
# ---------------------------------------------------------------------------

def validate_heartbeat_schema(version: str) -> bool:
    """Validate a heartbeat schema version."""

    assert_known_schema(
        version,
        KNOWN_HEARTBEAT_SCHEMAS,
        "heartbeat",
    )

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "SCHEMA_VERSION_COMMAND",
    "SCHEMA_VERSION_RESPONSE",
    "SCHEMA_VERSION_HEARTBEAT",
    "SCHEMA_VERSION_RESULT",
    "KNOWN_COMMAND_SCHEMAS",
    "KNOWN_RESPONSE_SCHEMAS",
    "KNOWN_HEARTBEAT_SCHEMAS",
    "KNOWN_RESULT_SCHEMAS",
    "validate_command_schema",
    "validate_response_schema",
    "validate_result_schema",
    "validate_heartbeat_schema",
    "assert_known_schema",
]