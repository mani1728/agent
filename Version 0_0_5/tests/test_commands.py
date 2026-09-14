import pytest

from agent.contracts.commands import CommandValidationError, make_command, validate_command
from agent.contracts.models import Command, CommandResult


def test_valid_command_is_immutable_and_typed():
    command = make_command("cmd-1", "agent.get_status", "corr-1", {"x": 1}, "2026-09-14T10:00:00+00:00")
    assert command.command_id == "cmd-1"
    assert command.schema_version == "1"
    with pytest.raises(AttributeError):
        command.command_id = "cmd-2"


def test_invalid_identity_is_rejected():
    command = Command("", "agent.get_status", "1", "corr-1", "2026-09-14T10:00:00+00:00", {})
    with pytest.raises(CommandValidationError, match="identity"):
        validate_command(command)


def test_invalid_timestamp_is_rejected():
    command = Command("cmd-1", "agent.get_status", "1", "corr-1", "not-a-date", {})
    with pytest.raises(CommandValidationError, match="ISO-8601"):
        validate_command(command)


def test_payload_must_be_mapping():
    command = Command("cmd-1", "agent.get_status", "1", "corr-1", "2026-09-14T10:00:00+00:00", [])
    with pytest.raises(CommandValidationError, match="mapping"):
        validate_command(command)


def test_result_is_immutable():
    result = CommandResult("cmd-1", "corr-1", True, "ok")
    with pytest.raises(AttributeError):
        result.success = False
