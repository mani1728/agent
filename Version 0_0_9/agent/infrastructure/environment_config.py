import os
from collections.abc import Mapping

from agent.contracts.configuration import AgentConfig, ConfigurationError, ConfigurationProvider, HTTPTransportConfig


class EnvironmentConfigurationProvider(ConfigurationProvider):
    """Infrastructure adapter that translates process environment into AgentConfig."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def load(self) -> AgentConfig:
        host = self._environ.get("MT5_AGENT_HTTP_HOST", "127.0.0.1")
        port = self._integer("MT5_AGENT_HTTP_PORT", 8080)
        max_request_bytes = self._integer("MT5_AGENT_HTTP_MAX_REQUEST_BYTES", 1024 * 1024)
        return AgentConfig(HTTPTransportConfig(host, port, max_request_bytes))

    def _integer(self, name: str, default: int) -> int:
        raw = self._environ.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"{name} must be an integer") from exc
