# Path: agent/transport/gateway_adapter.py

"""HTTPS + mTLS transport adapter for the Edge Gateway.

This module provides the concrete HTTP transport used by the Agent to
communicate with an Edge Gateway.

Responsibilities
----------------
- Poll commands from the Gateway.
- Send command responses to the Gateway.
- Send agent heartbeat/status information.
- Acknowledge processed commands.
- Configure HTTPS and optional mutual TLS (mTLS).

The rest of the application depends only on ``ITransportClient`` and
the transport-independent contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

import requests
from requests import Response
from requests.exceptions import RequestException

from agent.transport.base import ITransportClient
from agent.contracts.command import CommandEnvelope
from agent.contracts.heartbeat import HeartbeatPayload
from agent.contracts.response import ResponseEnvelope

logger = logging.getLogger(__name__)


class GatewayHttpTransport(ITransportClient):
    """HTTP(S) transport implementation for the Edge Gateway.

    Parameters
    ----------
    gateway_url:
        Base URL of the Edge Gateway, for example:
        ``https://gateway.example.com``.

    agent_id:
        Unique identifier of this Agent.

    client_cert_path:
        Path to the client certificate used for mTLS.

    client_key_path:
        Path to the private key corresponding to ``client_cert_path``.

    ca_cert_path:
        Optional CA certificate/bundle used to verify the Gateway
        certificate. If omitted, ``requests`` uses the system CA store.

    timeout:
        Default HTTP request timeout in seconds.
    """

    def __init__(
        self,
        gateway_url: str,
        agent_id: str,
        client_cert_path: Optional[str] = None,
        client_key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        if not isinstance(gateway_url, str) or not gateway_url.strip():
            raise ValueError(
                "gateway_url must be a non-empty string"
            )

        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError(
                "agent_id must be a non-empty string"
            )

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero"
            )

        if bool(client_cert_path) != bool(client_key_path):
            raise ValueError(
                "client_cert_path and client_key_path must be provided "
                "together for mTLS"
            )

        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = float(timeout)

        self.session = requests.Session()

        # --------------------------------------------------------------
        # TLS / mTLS configuration
        # --------------------------------------------------------------

        if client_cert_path and client_key_path:
            self.session.cert = (
                client_cert_path,
                client_key_path,
            )

        if ca_cert_path:
            self.session.verify = ca_cert_path

        # --------------------------------------------------------------
        # Common HTTP headers
        # --------------------------------------------------------------

        self.session.headers.update(
            {
                "User-Agent": f"Bank-Agent/{self.agent_id}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialize/start the Gateway transport.

        ``requests.Session`` does not require an explicit network
        connection, so startup only marks the transport as active.
        """
        if self._started:
            logger.debug(
                "Gateway transport is already started."
            )
            return

        self._started = True

        logger.info(
            "Gateway transport initialized for: %s",
            self.gateway_url,
        )

    def stop(self) -> None:
        """Close the HTTP session and release transport resources."""
        if not self._started:
            # Closing a requests session more than once is harmless, but
            # keeping stop() idempotent makes lifecycle management safer.
            self.session.close()
            return

        self._started = False
        self.session.close()

        logger.info(
            "Gateway transport session closed."
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> Sequence[CommandEnvelope]:
        """Poll the Gateway for new commands.

        Invalid individual commands are logged and skipped rather than
        bringing down the polling loop.
        """
        if timeout_sec <= 0:
            raise ValueError(
                "timeout_sec must be greater than zero"
            )

        url = (
            f"{self.gateway_url}"
            f"/v1/agents/{self.agent_id}/commands"
        )

        try:
            response = self.session.get(
                url,
                timeout=float(timeout_sec),
            )
        except RequestException as exc:
            logger.error(
                "Failed to poll commands from gateway: %s",
                exc,
            )
            return []

        if response.status_code == 204:
            return []

        if response.status_code != 200:
            self._log_unexpected_response(
                operation="poll commands",
                response=response,
            )
            return []

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error(
                "Gateway returned invalid JSON while polling commands: %s",
                exc,
            )
            return []

        if not isinstance(payload, Mapping):
            logger.error(
                "Gateway command response must be a JSON object; "
                "got %s.",
                type(payload).__name__,
            )
            return []

        raw_commands = payload.get("commands", [])

        if raw_commands is None:
            return []

        if not isinstance(raw_commands, list):
            logger.error(
                "Gateway 'commands' field must be a list; "
                "got %s.",
                type(raw_commands).__name__,
            )
            return []

        envelopes: list[CommandEnvelope] = []

        for index, raw_command in enumerate(raw_commands):
            if not isinstance(raw_command, Mapping):
                logger.warning(
                    "Skipping invalid command at index %d: "
                    "expected an object, got %s.",
                    index,
                    type(raw_command).__name__,
                )
                continue

            try:
                envelope = CommandEnvelope.from_dict(
                    raw_command,
                )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping invalid command at index %d: %s",
                    index,
                    exc,
                )
                continue

            envelopes.append(envelope)

        return envelopes

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def send_response(
        self,
        response: ResponseEnvelope,
    ) -> bool:
        """Send a command execution result to the Gateway."""
        if not isinstance(response, ResponseEnvelope):
            raise TypeError(
                "response must be a ResponseEnvelope"
            )

        url = (
            f"{self.gateway_url}"
            f"/v1/agents/{self.agent_id}/results"
        )

        payload = response.to_dict()

        try:
            result = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
        except RequestException as exc:
            logger.error(
                "Failed to send result to gateway: %s",
                exc,
            )
            return False

        if result.status_code in (200, 201, 202, 204):
            return True

        self._log_unexpected_response(
            operation="send response",
            response=result,
        )
        return False

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def send_heartbeat(
        self,
        agent_status: HeartbeatPayload | Mapping[str, Any],
    ) -> bool:
        """Send Agent health/status information to the Gateway."""
        url = (
            f"{self.gateway_url}"
            f"/v1/agents/{self.agent_id}/heartbeat"
        )

        if isinstance(agent_status, HeartbeatPayload):
            payload = agent_status.to_dict()
        elif isinstance(agent_status, Mapping):
            payload = dict(agent_status)
        else:
            raise TypeError(
                "agent_status must be a HeartbeatPayload "
                "or a mapping"
            )

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
        except RequestException as exc:
            logger.error(
                "Heartbeat delivery failed: %s",
                exc,
            )
            return False

        if response.status_code in (200, 201, 202, 204):
            return True

        self._log_unexpected_response(
            operation="send heartbeat",
            response=response,
        )
        return False

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def ack_command(
        self,
        command_id: str,
    ) -> None:
        """Acknowledge processing of a command."""
        if not isinstance(command_id, str) or not command_id.strip():
            raise ValueError(
                "command_id must be a non-empty string"
            )

        url = (
            f"{self.gateway_url}"
            f"/v1/agents/{self.agent_id}"
            f"/commands/{command_id}/ack"
        )

        try:
            response = self.session.post(
                url,
                timeout=self.timeout,
            )
        except RequestException as exc:
            logger.error(
                "Failed to ack command %s: %s",
                command_id,
                exc,
            )
            return

        if response.status_code not in (
            200,
            201,
            202,
            204,
        ):
            self._log_unexpected_response(
                operation=f"ack command {command_id}",
                response=response,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_unexpected_response(
        operation: str,
        response: Response,
    ) -> None:
        """Log an unexpected HTTP response without exposing secrets."""
        body = response.text.strip()

        # Avoid flooding logs with very large Gateway responses.
        if len(body) > 500:
            body = body[:500] + "...[truncated]"

        logger.warning(
            "Gateway returned unexpected status %s during %s. "
            "Response: %s",
            response.status_code,
            operation,
            body,
        )


__all__ = [
    "GatewayHttpTransport",
]