from collections.abc import Callable
import logging
from typing import Any

from agent.contracts.commands import CommandValidationError, validate_command
from agent.contracts.models import Command, CommandResult


class ApplicationError(Exception):
    pass


class UnknownCommandError(ApplicationError):
    pass


class UnsupportedSchemaError(ApplicationError):
    pass


class CommandDispatcher:
    def __init__(self, logger: logging.Logger | None = None, supported_schema: str = "1") -> None:
        self._handlers: dict[str, Callable[[Command], Any]] = {}
        self._logger = logger or logging.getLogger(__name__)
        self._supported_schema = supported_schema

    def register(self, command_type: str, handler: Callable[[Command], Any]) -> None:
        if not isinstance(command_type, str) or not command_type.strip():
            raise ValueError("command_type must be a non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")
        self._handlers[command_type] = handler

    def dispatch(self, command: Command) -> CommandResult:
        try:
            validate_command(command)
            if command.schema_version != self._supported_schema:
                raise UnsupportedSchemaError(f"Unsupported command schema: {command.schema_version}")
            handler = self._handlers.get(command.command_type)
            if handler is None:
                raise UnknownCommandError(f"Unknown command type: {command.command_type}")
            data = handler(command)
            return CommandResult(command.command_id, command.correlation_id, True, "ok", "Command completed.", data)
        except CommandValidationError as exc:
            return CommandResult(command.command_id if isinstance(command, Command) else "", command.correlation_id if isinstance(command, Command) else "", False, "invalid_command", str(exc))
        except UnsupportedSchemaError as exc:
            return CommandResult(command.command_id, command.correlation_id, False, "unsupported_schema", str(exc))
        except UnknownCommandError as exc:
            return CommandResult(command.command_id, command.correlation_id, False, "unknown_command", str(exc))
        except Exception:
            self._logger.exception("Command handler failed")
            return CommandResult(command.command_id, command.correlation_id, False, "execution_failed", "Command execution failed.")
