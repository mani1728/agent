# Path: Version 1_0_0/agent/transport/gateway/__init__.py

from __future__ import annotations

from .endpoints import (
    DEFAULT_API_PREFIX,
    ACK_PATH,
    AGENTS_PATH,
    COMMANDS_PATH,
    HEARTBEAT_PATH,
    RESULTS_PATH,
    agent_base_path,
    api_prefix,
    build_url,
    command_ack_endpoint,
    commands_endpoint,
    heartbeat_endpoint,
    normalize_agent_id,
    normalize_base_url,
    results_endpoint,
)
from .gateway_adapter import GatewayHttpTransport
from .http_client import (
    GatewayHttpClient,
    GatewayHttpError,
    GatewayHttpRequestError,
)
from .retry_policy import (
    GatewayRetryPolicy,
    RetryDecision,
)
from .security import (
    GatewaySecurity,
    GatewaySecurityError,
    GatewayTlsConfig,
    configure_mtls,
)


__all__ = [
    # Adapter
    "GatewayHttpTransport",

    # HTTP client
    "GatewayHttpClient",
    "GatewayHttpError",
    "GatewayHttpRequestError",

    # Retry
    "GatewayRetryPolicy",
    "RetryDecision",

    # Security
    "GatewaySecurity",
    "GatewaySecurityError",
    "GatewayTlsConfig",
    "configure_mtls",

    # Endpoints
    "DEFAULT_API_PREFIX",
    "AGENTS_PATH",
    "COMMANDS_PATH",
    "RESULTS_PATH",
    "HEARTBEAT_PATH",
    "ACK_PATH",
    "normalize_base_url",
    "normalize_agent_id",
    "api_prefix",
    "agent_base_path",
    "commands_endpoint",
    "results_endpoint",
    "heartbeat_endpoint",
    "command_ack_endpoint",
    "build_url",
]