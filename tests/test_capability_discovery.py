import json
from dataclasses import replace

import pytest

from agent.application.app import build_dispatcher
from agent.application.capability_commands import GET_CAPABILITIES, GET_RUNTIME_INFO
from agent.application.registry.capability import InMemoryCapabilityRegistry
from agent.composition import compose_agent
from agent.contracts.capability import CapabilityDescriptor
from agent.contracts.configuration import AgentConfig
from agent.contracts.models import Command
from agent.contracts.runtime_information import RuntimeInformationContract
from agent.contracts.security import AuthorizationDecision


class FakeCapabilityProvider:
    def get_capabilities(self):
        return (CapabilityDescriptor("agent.runtime.info", "0.1.0", "1", {}),)

    def get_runtime_information(self):
        return RuntimeInformationContract(
            "MT5Agent", "0.1.0", "1", "running", self.get_capabilities()
        )


class FakeMT5:
    def connect(self):
        return True

    def disconnect(self):
        return True

    def is_connected(self):
        return True


def make_command(command_type):
    return Command(
        command_id="test-command-id",
        correlation_id="test-correlation-id",
        command_type=command_type,
        schema_version="1",
        timestamp="2026-09-17T00:00:00+00:00",
        payload={},
    )


def http_payload(command_type):
    command = make_command(command_type)
    return json.dumps({
        "request_id": "req-1",
        "correlation_id": command.correlation_id,
        "command": {
            "command_id": command.command_id,
            "command_type": command.command_type,
            "schema_version": command.schema_version,
            "correlation_id": command.correlation_id,
            "timestamp": command.timestamp,
            "payload": {},
        },
    }).encode()


def test_capability_discovery_command_constants_exist():
    assert GET_CAPABILITIES == "agent.get_capabilities"
    assert GET_RUNTIME_INFO == "agent.get_runtime_info"


@pytest.mark.parametrize("command_type", [GET_CAPABILITIES, GET_RUNTIME_INFO])
def test_discovery_returns_provider_data_and_preserves_command_identity(command_type):
    provider = FakeCapabilityProvider()
    dispatcher = build_dispatcher(object(), capability_provider=provider)
    command = make_command(command_type)
    result = dispatcher.dispatch(command)
    assert result.success is True
    assert result.code == "ok"
    assert result.command_id == command.command_id
    assert result.correlation_id == command.correlation_id
    expected = (
        {"schema_version": "1", "capabilities": [c.to_dict() for c in provider.get_capabilities()]}
        if command_type == GET_CAPABILITIES else provider.get_runtime_information().to_dict()
    )
    assert json.loads(json.dumps(result.data)) == expected


@pytest.mark.parametrize("command_type", [GET_CAPABILITIES, GET_RUNTIME_INFO])
def test_discovery_is_not_registered_without_provider(command_type):
    result = build_dispatcher(object()).dispatch(make_command(command_type))
    assert not result.success
    assert result.code == "UNSUPPORTED_COMMAND"


def test_registry_copies_capabilities_and_returns_runtime_snapshot():
    provider = FakeCapabilityProvider()
    capabilities = list(provider.get_capabilities())
    registry = InMemoryCapabilityRegistry(capabilities, provider.get_runtime_information)
    capabilities.clear()
    assert registry.get_capabilities() == provider.get_capabilities()
    assert registry.get_runtime_information() == provider.get_runtime_information()


@pytest.mark.parametrize("command_type", [GET_CAPABILITIES, GET_RUNTIME_INFO])
def test_composed_discovery_round_trips_through_http(command_type):
    composition = compose_agent(AgentConfig(), mt5=FakeMT5())
    response = composition.http_transport.handle_json(http_payload(command_type))
    body = json.loads(response.body)
    assert response.status == 200
    assert body["success"] is True
    assert body["request_id"] == "req-1"
    assert body["command_id"] == "test-command-id"
    assert body["correlation_id"] == "test-correlation-id"
    assert body["data"]["capabilities"] == []
    assert body["data"]["schema_version"] == "1"


def test_composed_runtime_information_tracks_lifecycle():
    composition = compose_agent(AgentConfig(), mt5=FakeMT5())
    command = make_command(GET_RUNTIME_INFO)
    before = composition.dispatcher.dispatch(command).data
    assert before["lifecycle_state"] == "created"
    assert before["agent_name"] == composition.agent.identity.app_name
    assert before["agent_version"] == composition.agent.identity.version
    assert composition.agent.start().ok
    assert composition.dispatcher.dispatch(command).data["lifecycle_state"] == "running"
    assert composition.agent.stop().ok
    assert composition.dispatcher.dispatch(command).data["lifecycle_state"] == "stopped"
    assert before["lifecycle_state"] == "created"


@pytest.mark.parametrize("command_type", [GET_CAPABILITIES, GET_RUNTIME_INFO])
def test_discovery_respects_authorization(command_type):
    class Deny:
        def authorize(self, context, command):
            return AuthorizationDecision(False, "authorization_denied", "Denied.")

    composition = compose_agent(AgentConfig(), mt5=FakeMT5(), authorizer=Deny())
    response = composition.http_transport.handle_json(http_payload(command_type))
    assert response.status == 403
    assert json.loads(response.body)["code"] == "authorization_denied"


@pytest.mark.parametrize("command_type", [GET_CAPABILITIES, GET_RUNTIME_INFO])
def test_provider_failure_uses_existing_error_model(command_type):
    class BrokenProvider:
        def get_capabilities(self):
            raise RuntimeError("private implementation detail")

        def get_runtime_information(self):
            raise RuntimeError("private implementation detail")

    dispatcher = build_dispatcher(object(), capability_provider=BrokenProvider())
    result = dispatcher.dispatch(make_command(command_type))
    assert not result.success
    assert result.code == "execution_failed"
    assert "private" not in result.message


def test_discovery_rejects_unsupported_schema():
    dispatcher = build_dispatcher(object(), capability_provider=FakeCapabilityProvider())
    result = dispatcher.dispatch(replace(make_command(GET_CAPABILITIES), schema_version="999"))
    assert not result.success
    assert result.code == "UNSUPPORTED_COMMAND_VERSION"


@pytest.mark.parametrize("field", ["name", "version", "schema_version"])
def test_capability_contract_rejects_blank_identity(field):
    values = dict(name="runtime", version="0.1.0", schema_version="1", metadata={})
    values[field] = " "
    with pytest.raises(ValueError):
        CapabilityDescriptor(**values)


@pytest.mark.parametrize("field", ["agent_name", "agent_version", "schema_version"])
def test_runtime_contract_rejects_blank_identity(field):
    values = dict(agent_name="MT5Agent", agent_version="0.1.0", schema_version="1",
                  lifecycle_state="created", capabilities=())
    values[field] = " "
    with pytest.raises(ValueError):
        RuntimeInformationContract(**values)


def test_contracts_copy_and_protect_top_level_metadata():
    from dataclasses import FrozenInstanceError

    metadata = {"description": "runtime"}
    capability = CapabilityDescriptor("runtime", "0.1.0", "1", metadata)
    runtime = RuntimeInformationContract("MT5Agent", "0.1.0", "1", "created", [capability], metadata)
    metadata.clear()
    for contract in (capability, runtime):
        assert contract.metadata["description"] == "runtime"
        with pytest.raises(TypeError):
            contract.metadata["description"] = "changed"
        with pytest.raises(FrozenInstanceError):
            contract.schema_version = "2"
        assert json.loads(json.dumps(contract.to_dict())) == contract.to_dict()
    assert runtime.capabilities == (capability,)
