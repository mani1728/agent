from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ConfigurationError(ValueError):
    """Raised when startup configuration violates the application contract."""


@dataclass(frozen=True)
class HTTPTransportConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    max_request_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ConfigurationError("http host must be a non-empty string")
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise ConfigurationError("http port must be an integer between 1 and 65535")
        if not isinstance(self.max_request_bytes, int) or isinstance(self.max_request_bytes, bool) or self.max_request_bytes <= 0:
            raise ConfigurationError("max_request_bytes must be a positive integer")


@dataclass(frozen=True)
class AgentConfig:
    http: HTTPTransportConfig = HTTPTransportConfig()


@runtime_checkable
class ConfigurationProvider(Protocol):
    def load(self) -> AgentConfig: ...
