from dataclasses import dataclass

from agent.contracts.models import HealthStatus, LifecycleState, Status
from agent.core.agent import Agent
from agent.health.health import check


@dataclass
class FakeMT5Adapter:
    connect_result: bool = True
    connected: bool = True
    disconnect_calls: int = 0
    connect_calls: int = 0

    def connect(self) -> bool:
        self.connect_calls += 1
        return self.connect_result

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected


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
