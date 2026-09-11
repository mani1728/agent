# Path: agent/contracts/__init__.py

"""Public domain contracts used by the Agent application.

This package contains transport-independent typed contracts for:

- Commands
- Responses
- Heartbeats
- Shared JSON types
- Contract schema versions

No transport-specific dependencies such as Kafka, HTTP, or Redis
should be imported from this package.
"""

from .command import CommandEnvelope
from .heartbeat import HeartbeatPayload, HeartbeatStatus
from .models import JsonDict
from .response import ResponseEnvelope, ResponseStatus
from .schemas import (
    SCHEMA_VERSION_COMMAND,
    SCHEMA_VERSION_HEARTBEAT,
    SCHEMA_VERSION_RESPONSE,
)

__all__ = [
    # Command
    "CommandEnvelope",

    # Response
    "ResponseEnvelope",
    "ResponseStatus",

    # Heartbeat
    "HeartbeatPayload",
    "HeartbeatStatus",

    # Shared types
    "JsonDict",

    # Schema versions
    "SCHEMA_VERSION_COMMAND",
    "SCHEMA_VERSION_RESPONSE",
    "SCHEMA_VERSION_HEARTBEAT",
]