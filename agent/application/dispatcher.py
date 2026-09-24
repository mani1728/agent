from collections.abc import Callable
import logging
from typing import Any

from agent.contracts.commands import CommandValidationError, validate_command
from agent.contracts.models import Command, CommandResult
from agent.contracts.protocol import CapabilityClass, CommandDefinition, CommandRegistry, ProtocolResolutionError


class ApplicationError(Exception):
    pass


class UnknownCommandError(ApplicationError):
    pass


class UnsupportedSchemaError(ApplicationError):
    pass


class CommandDispatcher:
    def __init__(self, logger: logging.Logger | None = None, supported_schema: str = "1",
                 registry: CommandRegistry | None = None) -> None:
        self._registry = registry or CommandRegistry()
        self._logger = logger or logging.getLogger(__name__)
        self._supported_schema = supported_schema

    def register(self, command_type: str, handler: Callable[[Command], Any], *, version: str = "1",
                 capability_class: CapabilityClass = CapabilityClass.READ, enabled: bool = True) -> None:
        self._registry.register(CommandDefinition(command_type, version, capability_class, handler, enabled))

    def capability_manifest(self, agent_version: str):
        return self._registry.manifest(agent_version)

    def register_capability_handlers(self, capability_provider: Any) -> None:
        from agent.application.capability_commands import build_capability_handlers

        for command_type, handler in build_capability_handlers(capability_provider).items():
            self.register(command_type, handler)

    def dispatch(self, command: Command) -> CommandResult:
        try:
            validate_command(command)
            definition = self._registry.resolve(command.command_type, command.schema_version)
            data = definition.handler(command)
            return CommandResult(command.command_id, command.correlation_id, True, "ok", "Command completed.", data)
        except CommandValidationError as exc:
            return CommandResult(command.command_id if isinstance(command, Command) else "", command.correlation_id if isinstance(command, Command) else "", False, "invalid_command", str(exc))
        except ProtocolResolutionError as exc:
            return CommandResult(command.command_id, command.correlation_id, False, exc.code, str(exc))
        except Exception:
            self._logger.exception("Command handler failed")
            return CommandResult(command.command_id, command.correlation_id, False, "execution_failed", "Command execution failed.")
