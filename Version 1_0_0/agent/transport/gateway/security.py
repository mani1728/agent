# Path: Version 1_0_0/agent/transport/gateway/security.py

"""Security configuration helpers for the Gateway transport.

This module contains transport-level security configuration for HTTPS
and mutual TLS (mTLS).

Responsibilities
----------------
- Validate TLS/mTLS configuration.
- Configure requests.Session TLS settings.
- Build safe HTTP security headers.
- Prevent accidental TLS certificate verification disabling.

This module does not implement:
- token issuance or refresh
- command authorization
- certificate rotation
- secret storage
- retry policies
- application-level authentication
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import requests


class GatewaySecurityError(ValueError):
    """Raised when Gateway security configuration is invalid."""


@dataclass(frozen=True)
class GatewayTlsConfig:
    """TLS/mTLS configuration for Gateway communication."""

    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None

    def __post_init__(self) -> None:
        if bool(self.client_cert_path) != bool(self.client_key_path):
            raise GatewaySecurityError(
                "client_cert_path and client_key_path must be provided "
                "together for mTLS"
            )

        if self.ca_cert_path is not None:
            if not isinstance(self.ca_cert_path, str):
                raise GatewaySecurityError(
                    "ca_cert_path must be a string or None"
                )

            if not self.ca_cert_path.strip():
                raise GatewaySecurityError(
                    "ca_cert_path cannot be empty"
                )

        if self.client_cert_path is not None:
            if not isinstance(self.client_cert_path, str):
                raise GatewaySecurityError(
                    "client_cert_path must be a string or None"
                )

            if not self.client_cert_path.strip():
                raise GatewaySecurityError(
                    "client_cert_path cannot be empty"
                )

        if self.client_key_path is not None:
            if not isinstance(self.client_key_path, str):
                raise GatewaySecurityError(
                    "client_key_path must be a string or None"
                )

            if not self.client_key_path.strip():
                raise GatewaySecurityError(
                    "client_key_path cannot be empty"
                )


class GatewaySecurity:
    """Apply Gateway HTTPS/mTLS security configuration."""

    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    def __init__(
        self,
        tls: Optional[GatewayTlsConfig] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.tls = tls or GatewayTlsConfig()
        self.user_agent = user_agent

    # ------------------------------------------------------------------
    # Session configuration
    # ------------------------------------------------------------------

    def configure_session(
        self,
        session: requests.Session,
    ) -> requests.Session:
        """Apply TLS and default headers to a requests session."""
        if not isinstance(session, requests.Session):
            raise TypeError(
                "session must be a requests.Session"
            )

        # requests verifies TLS certificates by default.
        #
        # Never set session.verify=False.
        if self.tls.ca_cert_path:
            session.verify = self.tls.ca_cert_path
        else:
            session.verify = True

        if (
            self.tls.client_cert_path
            and self.tls.client_key_path
        ):
            session.cert = (
                self.tls.client_cert_path,
                self.tls.client_key_path,
            )

        session.headers.update(
            self.build_headers(
                user_agent=self.user_agent,
            )
        )

        return session

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def build_headers(
        self,
        *,
        user_agent: Optional[str] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> dict[str, str]:
        """Build safe default Gateway HTTP headers."""
        headers = dict(self.DEFAULT_HEADERS)

        if user_agent:
            headers["User-Agent"] = user_agent

        if extra_headers:
            for key, value in extra_headers.items():
                if not isinstance(key, str):
                    raise TypeError(
                        "HTTP header names must be strings"
                    )

                if not isinstance(value, str):
                    raise TypeError(
                        "HTTP header values must be strings"
                    )

                headers[key] = value

        return headers

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_tls_config(
        tls: GatewayTlsConfig,
    ) -> None:
        """Validate a TLS configuration object."""
        if not isinstance(tls, GatewayTlsConfig):
            raise TypeError(
                "tls must be a GatewayTlsConfig"
            )

        # Construction already validates the fields. This explicit
        # method provides a stable validation entry point for callers.
        if (
            bool(tls.client_cert_path)
            != bool(tls.client_key_path)
        ):
            raise GatewaySecurityError(
                "mTLS requires both client certificate and private key"
            )

    @staticmethod
    def ensure_tls_verification_enabled(
        session: requests.Session,
    ) -> None:
        """Reject a session with TLS certificate verification disabled."""
        if not isinstance(session, requests.Session):
            raise TypeError(
                "session must be a requests.Session"
            )

        if session.verify is False:
            raise GatewaySecurityError(
                "TLS certificate verification must not be disabled"
            )


def configure_mtls(
    session: requests.Session,
    *,
    ca_cert_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None,
) -> requests.Session:
    """Convenience helper for applying HTTPS/mTLS configuration."""
    security = GatewaySecurity(
        tls=GatewayTlsConfig(
            ca_cert_path=ca_cert_path,
            client_cert_path=client_cert_path,
            client_key_path=client_key_path,
        )
    )

    return security.configure_session(session)


__all__ = [
    "GatewaySecurityError",
    "GatewayTlsConfig",
    "GatewaySecurity",
    "configure_mtls",
]