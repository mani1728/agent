"""
فایل: agent/transport/gateway_adapter.py
مسئولیت: اتصال امن به Edge Gateway از طریق HTTPS + mTLS
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
import requests

from .base import ITransportClient
from .models import CommandEnvelope, ResponseEnvelope

logger = logging.getLogger(__name__)


class GatewayHttpTransport(ITransportClient):
    def __init__(
            self,
            gateway_url: str,
            agent_id: str,
            client_cert_path: Optional[str] = None,
            client_key_path: Optional[str] = None,
            ca_cert_path: Optional[str] = None,
            timeout: float = 5.0
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = timeout

        self.session = requests.Session()
        if client_cert_path and client_key_path:
            self.session.cert = (client_cert_path, client_key_path)
        if ca_cert_path:
            self.session.verify = ca_cert_path

        self.session.headers.update({
            "User-Agent": f"Bank-Agent/{agent_id}",
            "Content-Type": "application/json"
        })

    def start(self) -> None:
        logger.info("Gateway Transport Initialized for: %s", self.gateway_url)

    def stop(self) -> None:
        self.session.close()
        logger.info("Gateway Transport Session closed.")

    def poll_commands(self, timeout_sec: float = 1.0) -> List[CommandEnvelope]:
        url = f"{self.gateway_url}/v1/agents/{self.agent_id}/commands"
        try:
            resp = self.session.get(url, timeout=timeout_sec)
            if resp.status_code == 200:
                raw_commands = resp.json().get("commands", [])
                envelopes: List[CommandEnvelope] = []
                for cmd in raw_commands:
                    envelopes.append(CommandEnvelope(
                        command_id=cmd["command_id"],
                        target_class=cmd["target_class"],
                        target_method=cmd["target_method"],
                        params=cmd.get("params", {}),
                        priority=cmd.get("priority", 1),
                        correlation_id=cmd.get("correlation_id", ""),
                        auth_token=cmd.get("auth_token")
                    ))
                return envelopes
            elif resp.status_code == 204:
                return []
            else:
                logger.warning("Gateway returned status %s on polling", resp.status_code)
                return []
        except requests.exceptions.RequestException as ex:
            logger.error("Failed to poll commands from gateway: %s", ex)
            return []

    def send_response(self, response: ResponseEnvelope) -> bool:
        url = f"{self.gateway_url}/v1/agents/{self.agent_id}/results"
        payload = {
            "correlation_id": response.correlation_id,
            "status": response.status,
            "data": response.data,
            "error_message": response.error_message,
            "schema_version": response.schema_version,
            "seq": response.seq,
            "total": response.total,
            "timestamp": response.timestamp
        }
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            return resp.status_code in (200, 202)
        except requests.exceptions.RequestException as ex:
            logger.error("Failed to send result to gateway: %s", ex)
            return False

    def send_heartbeat(self, agent_status: Dict[str, Any]) -> bool:
        url = f"{self.gateway_url}/v1/agents/{self.agent_id}/heartbeat"
        try:
            resp = self.session.post(url, json=agent_status, timeout=self.timeout)
            return resp.status_code == 200
        except requests.exceptions.RequestException as ex:
            logger.error("Heartbeat delivery failed: %s", ex)
            return False

    def ack_command(self, command_id: str) -> None:
        url = f"{self.gateway_url}/v1/agents/{self.agent_id}/commands/{command_id}/ack"
        try:
            self.session.post(url, timeout=self.timeout)
        except requests.exceptions.RequestException as ex:
            logger.error("Failed to ack command %s: %s", command_id, ex)

