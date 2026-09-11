# Path: Version 1_0_0/agent/transport/gateway/endpoints.py

"""Gateway API endpoint definitions.

This module contains transport-level endpoint construction only.

It intentionally does not perform HTTP requests, retries, authentication,
or response handling. Those responsibilities belong to the Gateway
transport and later reliability/security layers.
"""

from __future__ import annotations


DEFAULT_API_PREFIX = "/v1"
AGENTS_PATH = "/agents"
COMMANDS_PATH = "/commands"
RESULTS_PATH = "/results"
HEARTBEAT_PATH = "/heartbeat"
ACK_PATH = "/ack"


def normalize_base_url(base_url: str) -> str:
    """Normalize a Gateway base URL."""
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(
            "base_url must be a non-empty string"
        )

    return base_url.rstrip("/")


def normalize_agent_id(agent_id: str) -> str:
    """Validate and normalize an Agent identifier."""
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError(
            "agent_id must be a non-empty string"
        )

    return agent_id.strip()


def api_prefix(prefix: str = DEFAULT_API_PREFIX) -> str:
    """Return a normalized API prefix."""
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError(
            "prefix must be a non-empty string"
        )

    normalized = "/" + prefix.strip("/")
    return normalized


def agent_base_path(
    agent_id: str,
    prefix: str = DEFAULT_API_PREFIX,
) -> str:
    """Build the base API path for an Agent."""
    normalized_agent_id = normalize_agent_id(agent_id)

    return (
        f"{api_prefix(prefix)}"
        f"{AGENTS_PATH}"
        f"/{normalized_agent_id}"
    )


def commands_endpoint(
    agent_id: str,
    prefix: str = DEFAULT_API_PREFIX,
) -> str:
    """Return the command polling endpoint."""
    return (
        f"{agent_base_path(agent_id, prefix)}"
        f"{COMMANDS_PATH}"
    )


def results_endpoint(
    agent_id: str,
    prefix: str = DEFAULT_API_PREFIX,
) -> str:
    """Return the command result endpoint."""
    return (
        f"{agent_base_path(agent_id, prefix)}"
        f"{RESULTS_PATH}"
    )


def heartbeat_endpoint(
    agent_id: str,
    prefix: str = DEFAULT_API_PREFIX,
) -> str:
    """Return the Agent heartbeat endpoint."""
    return (
        f"{agent_base_path(agent_id, prefix)}"
        f"{HEARTBEAT_PATH}"
    )


def command_ack_endpoint(
    agent_id: str,
    command_id: str,
    prefix: str = DEFAULT_API_PREFIX,
) -> str:
    """Return the command acknowledgement endpoint."""
    if not isinstance(command_id, str) or not command_id.strip():
        raise ValueError(
            "command_id must be a non-empty string"
        )

    return (
        f"{agent_base_path(agent_id, prefix)}"
        f"{COMMANDS_PATH}"
        f"/{command_id.strip()}"
        f"{ACK_PATH}"
    )


def build_url(
    base_url: str,
    endpoint: str,
) -> str:
    """Combine a Gateway base URL with an endpoint path."""
    normalized_base = normalize_base_url(base_url)

    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError(
            "endpoint must be a non-empty string"
        )

    normalized_endpoint = "/" + endpoint.strip("/")

    return f"{normalized_base}{normalized_endpoint}"


__all__ = [
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