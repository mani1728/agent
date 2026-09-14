from dataclasses import FrozenInstanceError, dataclass

import pytest

from agent.contracts.models import AgentConfig, HealthStatus, LifecycleState, Status
from agent.contracts.ports import MT5Port
from agent.core.agent import Agent
from agent.health.health import check


@dataclass
class FakeMT5Adapter:
    connect_result: bool = True
    connected: bool = True
    disconnect_result: bool = True
    disconnect_calls: int = 0
    connect_calls: int = 0

    def connect(self) -> bool:
        self.connect_calls += 1
        self.connected = self.connect_result
        return self.connect_result

    def disconnect(self) -> bool:
        self.disconnect_calls += 1
        self.connected = False
        return self.disconnect_result

    def is_connected(self) -> bool:
        return self.connected


def test_fake_adapter_satisfies_mt5_port_contract():
    adapter = FakeMT5Adapter()

    assert isinstance(adapter, MT5Port)


def test_contracts_are_immutable_and_config_has_expected_defaults():
    status = Status(True, "ok", "healthy")
    health = HealthStatus(True, LifecycleState.RUNNING, "healthy")
    config = AgentConfig()

    assert config.app_name == "Trading Agent"
    assert config.version == "0.0.2"

    with pytest.raises(FrozenInstanceError):
        status.ok = False
    with pytest.raises(FrozenInstanceError):
        health.ok = False
    with pytest.raises(FrozenInstanceError):
        config.version = "changed"


def test_start_success_transitions_to_running():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)

    status = agent.start()

    assert status == Status(True, "MT5 connection established.", "connected")
    assert agent.state is LifecycleState.RUNNING
    assert adapter.connect_calls == 1


def test_start_failure_transitions_to_failed():
    agent = Agent(FakeMT5Adapter(connect_result=False))

    status = agent.start()

    assert status.ok is False
    assert status.code == "connection_failed"
    assert agent.state is LifecycleState.FAILED


def test_start_is_idempotent_when_running():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)
    agent.start()

    status = agent.start()

    assert status == Status(True, "Agent is already running.", "already_running")
    assert adapter.connect_calls == 1


def test_stop_is_safe_before_start():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)

    status = agent.stop()

    assert status.ok is True
    assert agent.state is LifecycleState.STOPPED
    assert adapter.disconnect_calls == 1


def test_stop_is_idempotently_safe_after_stopped():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)
    agent.start()
    agent.stop()

    status = agent.stop()

    assert status == Status(True, "Agent stopped.", "stopped")
    assert agent.state is LifecycleState.STOPPED
    assert adapter.disconnect_calls == 2


def test_stop_transitions_running_to_stopped():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)
    agent.start()

    status = agent.stop()

    assert status == Status(True, "Agent stopped.", "stopped")
    assert agent.state is LifecycleState.STOPPED
    assert adapter.disconnect_calls == 1


def test_failed_agent_can_be_stopped():
    adapter = FakeMT5Adapter(connect_result=False)
    agent = Agent(adapter)
    agent.start()

    status = agent.stop()

    assert status.ok is True
    assert agent.state is LifecycleState.STOPPED


def test_disconnect_failure_is_reported_and_marks_agent_failed():
    adapter = FakeMT5Adapter(disconnect_result=False)
    agent = Agent(adapter)
    agent.start()

    status = agent.stop()

    assert status == Status(False, "Unable to stop the agent cleanly.", "disconnect_failed")
    assert agent.state is LifecycleState.FAILED


def test_disconnect_exception_is_converted_to_failure():
    class BrokenAdapter(FakeMT5Adapter):
        def disconnect(self) -> bool:
            raise RuntimeError("boom")

    agent = Agent(BrokenAdapter())
    agent.start()

    status = agent.stop()

    assert status.ok is False
    assert status.code == "disconnect_failed"
    assert agent.state is LifecycleState.FAILED


def test_health_requires_running_and_connected_terminal():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)

    before_start = check(agent)
    assert isinstance(before_start, HealthStatus)
    assert before_start.ok is False
    assert before_start.state is LifecycleState.CREATED

    agent.start()
    healthy = check(agent)
    assert healthy.ok is True
    assert healthy.state is LifecycleState.RUNNING

    adapter.connected = False
    unhealthy = check(agent)
    assert unhealthy.ok is False
    assert unhealthy.state is LifecycleState.RUNNING


def test_health_contains_adapter_failure_as_unhealthy():
    class BrokenHealthAdapter(FakeMT5Adapter):
        def is_connected(self) -> bool:
            raise RuntimeError("probe failed")

    agent = Agent(BrokenHealthAdapter())
    agent.start()

    health = agent.health()

    assert health.ok is False
    assert health.state is LifecycleState.RUNNING
    assert "not connected" in health.message


def test_adapter_exception_is_converted_to_connection_failure():
    class BrokenAdapter(FakeMT5Adapter):
        def connect(self) -> bool:
            raise RuntimeError("boom")

    agent = Agent(BrokenAdapter())

    status = agent.start()

    assert status.ok is False
    assert status.code == "connection_failed"
    assert agent.state is LifecycleState.FAILED


def test_restart_after_stop():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)

    assert agent.start().ok is True
    assert agent.stop().ok is True
    adapter.connected = True

    status = agent.start()

    assert status.ok is True
    assert agent.state is LifecycleState.RUNNING
    assert adapter.connect_calls == 2


def test_restart_after_connection_failure():
    adapter = FakeMT5Adapter(connect_result=False)
    agent = Agent(adapter)

    assert agent.start().ok is False
    adapter.connect_result = True

    status = agent.start()

    assert status.ok is True
    assert agent.state is LifecycleState.RUNNING
    assert adapter.connect_calls == 2
