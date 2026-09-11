# Path: Version 1_0_0/agent/transport/gateway/gateway_adapter.py

"""HTTPS + mTLS transport adapter for the Edge Gateway.

This module provides the concrete HTTP transport used by the Agent to
communicate with an Edge Gateway.

The transport depends only on transport-independent contracts and the
ITransportClient interface. Retry, persistence, circuit breaking and
advanced security policies belong to later migration phases.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

import requests
from requests import Response
from requests.exceptions import RequestException

from agent.contracts.command import CommandEnvelope
from agent.contracts.heartbeat import HeartbeatPayload
from agent.contracts.response import ResponseEnvelope
from agent.transport.base import ITransportClient


logger = logging.getLogger(__name__)


class GatewayHttpTransport(ITransportClient):
    """HTTP(S) transport implementation for the Edge Gateway.

    Parameters
    ----------
    gateway_url:
        Base URL of the Edge Gateway.

    agent_id:
        Unique identifier of this Agent.

    client_cert_path:
        Path to the client certificate used for mTLS.

    client_key_path:
        Path to the private key corresponding to the client certificate.

    ca_cert_path:
        Optional CA certificate/bundle used to verify the Gateway
        certificate. If omitted, requests uses the system CA store.

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
            raise ValueError("gateway_url must be a non-empty string")

        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if bool(client_cert_path) != bool(client_key_path):
            raise ValueError(
                "client_cert_path and client_key_path must be provided "
                "together for mTLS"
            )

        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = float(timeout)

        self.session = requests.Session()

        # ------------------------------------------------------------------
        # TLS / mTLS
        # ------------------------------------------------------------------

        if client_cert_path and client_key_path:
            self.session.cert = (
                client_cert_path,
                client_key_path,
            )

        # requests verifies TLS certificates by default.
        # Never disable certificate verification here.
        if ca_cert_path:
            self.session.verify = ca_cert_path

        # ------------------------------------------------------------------
        # Common HTTP headers
        # ------------------------------------------------------------------

        self.session.headers.update(
            {
                "User-Agent": f"MT5-Agent/{self.agent_id}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Gateway transport."""
        if self._started:
            logger.debug("Gateway transport is already started.")
            return

        self._started = True

        logger.info(
            "Gateway transport initialized for: %s",
            self.gateway_url,
        )

    def stop(self) -> None:
        """Stop the Gateway transport and release HTTP resources."""
        self._started = False
        self.session.close()

        logger.info("Gateway transport session closed.")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def poll_commands(
        self,
        timeout_sec: float = 1.0,
    ) -> Sequence[CommandEnvelope]:
        """Poll the Gateway for new commands.

        Invalid individual commands are skipped so that one malformed
        command cannot terminate the polling loop.
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
                "Gateway command response must be a JSON object; got %s.",
                type(payload).__name__,
            )
            return []

        raw_commands = payload.get("commands", [])

        if raw_commands is None:
            return []

        if not isinstance(raw_commands, list):
            logger.error(
                "Gateway 'commands' field must be a list; got %s.",
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

            command_payload = dict(raw_command)

            command_metadata = command_payload.get("metadata")

            if not isinstance(command_metadata, Mapping):
                command_metadata = {}

            command_metadata.update(
                {
                    "transport": "gateway",
                    "request_index": index,
                }
            )

            command_payload.update(
                {
                    "metadata": command_metadata,
                }
            )

            command_payload.setdefault(
                "metadata",
                {},
            )

            try:
                envelope = CommandEnvelope.from_dict(
                    command_payload,
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

        try:
            result = self.session.post(
                url,
                json=response.to_dict(),
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
        status: HeartbeatPayload | Mapping[str, Any],
    ) -> bool:
        """Send Agent health/status information to the Gateway."""
        url = (
            f"{self.gateway_url}"
            f"/v1/agents/{self.agent_id}/heartbeat"
        )

        if isinstance(status, HeartbeatPayload):
            payload = status.to_dict()
        elif isinstance(status, Mapping):
            payload = dict(status)
        else:
            raise TypeError(
                "status must be a HeartbeatPayload or a mapping"
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
