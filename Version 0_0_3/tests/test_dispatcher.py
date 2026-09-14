import logging

from agent.application.app import GET_HEALTH, GET_STATUS, build_dispatcher
from agent.application.dispatcher import CommandDispatcher
from agent.contracts.commands import make_command
from agent.contracts.models import AgentConfig, LifecycleState
from agent.core.agent import Agent


class FakeMT5:
    def __init__(self, connected=True):
        self.connected = connected

    def connect(self):
        return self.connected

    def disconnect(self):
        return True

    def is_connected(self):
        return self.connected


def command(command_type="agent.get_status", command_id="cmd-1"):
    return make_command(command_id, command_type, "corr-1", {}, "2026-09-14T10:00:00+00:00")


def test_known_command_dispatches_and_preserves_identity():
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    dispatcher = build_dispatcher(agent)
    result = dispatcher.dispatch(command())
    assert result.success is True
    assert result.code == "ok"
    assert result.command_id == "cmd-1"
    assert result.correlation_id == "corr-1"
    assert result.data["state"] == LifecycleState.CREATED.value


def test_health_command_reports_runtime_health():
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    dispatcher = build_dispatcher(agent)
    result = dispatcher.dispatch(command(GET_HEALTH))
    assert result.success is True
    assert result.data["ok"] is False


def test_unknown_command_is_deterministic():
    dispatcher = CommandDispatcher()
    result = dispatcher.dispatch(command("agent.unknown"))
    assert result.success is False
    assert result.code == "unknown_command"


def test_unsupported_schema_is_rejected():
    dispatcher = CommandDispatcher()
    result = dispatcher.dispatch(make_command("cmd-1", GET_STATUS, "corr-1", {}, "2026-09-14T10:00:00+00:00", "2"))
    assert result.success is False
    assert result.code == "unsupported_schema"


def test_handler_exception_is_contained():
    dispatcher = CommandDispatcher()
    dispatcher.register("boom", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    result = dispatcher.dispatch(command("boom"))
    assert result.success is False
    assert result.code == "execution_failed"
