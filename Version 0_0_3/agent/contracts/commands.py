from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from agent.contracts.models import Command


class CommandValidationError(ValueError):
    """Raised when a command violates its transport-neutral contract."""


def validate_command(command: Command) -> None:
    """Validate command identity and envelope invariants before dispatch."""
    if not isinstance(command, Command):
        raise CommandValidationError("command must be a Command instance")
    for field in (command.command_id, command.command_type, command.schema_version, command.correlation_id):
        if not isinstance(field, str) or not field.strip():
            raise CommandValidationError("command identity fields must be non-empty strings")
    if not isinstance(command.timestamp, str) or not command.timestamp.strip():
        raise CommandValidationError("timestamp must be a non-empty string")
    try:
        datetime.fromisoformat(command.timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommandValidationError("timestamp must be ISO-8601") from exc
    if not isinstance(command.payload, Mapping):
        raise CommandValidationError("payload must be a mapping")


def make_command(command_id: str, command_type: str, correlation_id: str,
                 payload: Mapping[str, Any] | None = None,
                 timestamp: str | None = None, schema_version: str = "1") -> Command:
    """Build a validated command envelope without coupling to a transport."""
    command = Command(
        command_id=command_id,
        command_type=command_type,
        schema_version=schema_version,
        correlation_id=correlation_id,
        timestamp=timestamp or datetime.now().astimezone().isoformat(),
        payload=payload or {},
    )
    validate_command(command)
    return command
