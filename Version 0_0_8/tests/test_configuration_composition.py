import pytest

from agent.composition import compose_agent
from agent.contracts.configuration import AgentConfig, ConfigurationError, HTTPTransportConfig
from agent.infrastructure.environment_config import EnvironmentConfigurationProvider


class FakeMT5:
    def connect(self) -> bool:
        return True

    def disconnect(self) -> bool:
        return True

    def is_connected(self) -> bool:
        return True


class RecordingOperationalObservability:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def test_http_config_defaults_are_deterministic():
    config = AgentConfig()
    assert config.http.host == "127.0.0.1"
    assert config.http.port == 8080
    assert config.http.max_request_bytes == 1024 * 1024


@pytest.mark.parametrize("port", [0, 65536, -1, True, "8080"])
def test_invalid_port_is_rejected(port):
    with pytest.raises(ConfigurationError):
        HTTPTransportConfig(port=port)


@pytest.mark.parametrize("limit", [0, -1, True, "1024"])
def test_invalid_request_limit_is_rejected(limit):
    with pytest.raises(ConfigurationError):
        HTTPTransportConfig(max_request_bytes=limit)


def test_environment_provider_translates_inputs():
    provider = EnvironmentConfigurationProvider({
        "MT5_AGENT_HTTP_HOST": "localhost",
        "MT5_AGENT_HTTP_PORT": "9090",
        "MT5_AGENT_HTTP_MAX_REQUEST_BYTES": "4096",
    })
    config = provider.load()
    assert config.http == HTTPTransportConfig("localhost", 9090, 4096)


def test_environment_provider_rejects_non_integer_values():
    with pytest.raises(ConfigurationError):
        EnvironmentConfigurationProvider({"MT5_AGENT_HTTP_PORT": "bad"}).load()


def test_composition_injects_mt5_and_transport_configuration():
    fake = FakeMT5()
    config = AgentConfig(HTTPTransportConfig(max_request_bytes=1234))
    composition = compose_agent(config, mt5=fake)
    assert composition.agent.mt5 is fake
    assert composition.config is config
    assert composition.http_transport._max_request_bytes == 1234


def test_composition_injects_operational_observability_into_host():
    observer = RecordingOperationalObservability()
    composition = compose_agent(AgentConfig(), mt5=FakeMT5(), operational_observability=observer)

    assert composition.host._operational_observability is observer


def test_core_does_not_import_environment_or_http_adapter():
    from pathlib import Path
    core = (Path(__file__).parents[1] / "agent" / "core" / "agent.py").read_text(encoding="utf-8")
    assert "os.environ" not in core
    assert "http_transport" not in core
    assert "MetaTrader5" not in core
