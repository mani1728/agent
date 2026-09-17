from agent.application.app import build_dispatcher
from agent.application.capability_commands import GET_CAPABILITIES, GET_RUNTIME_INFO
from agent.contracts.models import Command


class FakeCapabilityProvider:
    def get_capabilities(self):
        return [
            {
                "name": "agent.runtime.info",
                "version": "1.0.0",
                "schema_version": "1",
                "metadata": {},
            }
        ]

    def get_runtime_information(self):
        return {
            "agent_name": "MT5Agent",
            "agent_version": "0.1.0",
            "schema_version": "1",
            "lifecycle_state": "running",
            "capabilities": [],
        }


def make_command(command_type: str):
    return Command(
        command_id="test-command-id",
        correlation_id="test-correlation-id",
        command_type=command_type,
        schema_version="1",
        payload={},
    )


def test_capability_discovery_command_constants_exist():
    assert GET_CAPABILITIES == "agent.get_capabilities"
    assert GET_RUNTIME_INFO == "agent.get_runtime_info"


def test_capability_command_dispatch_returns_success():
    dispatcher = build_dispatcher(
        type("Agent", (), {"state": type("State", (), {"value": "running"})(), "config": type("Config", (), {"version": "0.1.0", "app_name": "MT5Agent"})()})()
    )

    result = dispatcher.dispatch(make_command(GET_CAPABILITIES))

    assert result.success is True


def test_runtime_information_command_dispatch_returns_success():
    dispatcher = build_dispatcher(
        type("Agent", (), {"state": type("State", (), {"value": "running"})(), "config": type("Config", (), {"version": "0.1.0", "app_name": "MT5Agent"})()})()
    )

    result = dispatcher.dispatch(make_command(GET_RUNTIME_INFO))

    assert result.success is True
