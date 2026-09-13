from agent.contracts.models import Status
from agent.core.agent import Agent
from agent.health.health import check


class FakeMT5Adapter:
    def __init__(self, connect_result=True, connected=True):
        self.connect_result = connect_result
        self.connected = connected
        self.disconnected = False

    def connect(self):
        return self.connect_result

    def disconnect(self):
        self.disconnected = True

    def is_connected(self):
        return self.connected


def test_agent_start_success():
    agent = Agent(FakeMT5Adapter())

    status = agent.start()

    assert status == Status(True, "MT5 connection established.")


def test_agent_start_failure():
    agent = Agent(FakeMT5Adapter(connect_result=False))

    status = agent.start()

    assert status == Status(False, "Unable to connect to MT5.")


def test_health_check():
    agent = Agent(FakeMT5Adapter(connected=True))

    status = check(agent)

    assert status.ok is True


def test_agent_stop():
    adapter = FakeMT5Adapter()
    agent = Agent(adapter)

    agent.stop()

    assert adapter.disconnected is True
