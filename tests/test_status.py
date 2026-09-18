import json

import pytest

from agent import __version__
from agent.application.app import GET_STATUS, build_dispatcher
from agent.composition import compose_agent
from agent.contracts.configuration import AgentConfig
from agent.contracts.models import AgentIdentity, Command
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


def status_command():
    return Command("status-1", GET_STATUS, "1", "corr-1",
                   "2026-09-18T00:00:00+00:00", {})


@pytest.mark.parametrize("transition, expected_state", [
    (None, "created"), ("start", "running"), ("stop", "stopped"),
])
def test_status_uses_custom_identity_and_current_lifecycle(transition, expected_state):
    agent = Agent(FakeMT5(), identity=AgentIdentity("Custom Agent", "9.8.7"))
    dispatcher = build_dispatcher(agent)
    if transition:
        assert getattr(agent, transition)().ok
    command = status_command()
    result = dispatcher.dispatch(command)
    assert result.success is True
    assert result.code == "ok"
    assert result.command_id == command.command_id
    assert result.correlation_id == command.correlation_id
    assert result.data == {"state": expected_state, "version": "9.8.7", "app_name": "Custom Agent"}


def test_status_reports_failed_start_without_changing_lifecycle():
    agent = Agent(FakeMT5(connected=False))
    assert not agent.start().ok
    result = build_dispatcher(agent).dispatch(status_command())
    assert result.success
    assert result.data == {"state": "failed", "version": __version__, "app_name": agent.identity.app_name}
    assert agent.state.value == "failed"


def test_composed_status_round_trips_through_http_with_canonical_version():
    composition = compose_agent(AgentConfig(), mt5=FakeMT5())
    command = status_command()
    response = composition.http_transport.handle_json(json.dumps({
        "request_id": "req-status", "correlation_id": command.correlation_id,
        "command": {
            "command_id": command.command_id, "command_type": command.command_type,
            "schema_version": command.schema_version, "correlation_id": command.correlation_id,
            "timestamp": command.timestamp, "payload": {},
        },
    }).encode())
    body = json.loads(response.body)
    assert response.status == 200
    assert body["success"] is True
    assert body["request_id"] == "req-status"
    assert body["command_id"] == command.command_id
    assert body["correlation_id"] == command.correlation_id
    assert body["data"] == {"state": "created", "version": __version__,
                            "app_name": composition.agent.identity.app_name}
