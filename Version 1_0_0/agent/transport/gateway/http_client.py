# Path: Version 1_0_0/agent/transport/gateway/http_client.py

"""Low-level HTTPS client for the Edge Gateway.

This module is responsible only for HTTP session configuration and
request execution.

It intentionally does not implement:
- retry policies
- exponential backoff
- circuit breakers
- idempotency
- command/business logic
- response contract interpretation

Those responsibilities belong to higher transport/reliability layers.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

import requests
from requests import Response
from requests.exceptions import RequestException


logger = logging.getLogger(__name__)


class GatewayHttpError(Exception):
    """Base exception for Gateway HTTP client errors."""


class GatewayHttpRequestError(GatewayHttpError):
    """Raised when an HTTP request cannot be completed."""


class GatewayHttpClient:
    """Low-level HTTPS client used by the Gateway transport.

    Parameters
    ----------
    base_url:
        Base URL of the Edge Gateway.

    client_cert_path:
        Optional client certificate path used for mTLS.

    client_key_path:
        Optional private key path corresponding to the client certificate.

    ca_cert_path:
        Optional CA bundle used to verify the Gateway certificate.

    timeout:
        Default request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        client_cert_path: Optional[str] = None,
        client_key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        timeout: float = 5.0,
        user_agent: Optional[str] = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError(
                "base_url must be a non-empty string"
            )

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero"
            )

        if bool(client_cert_path) != bool(client_key_path):
            raise ValueError(
                "client_cert_path and client_key_path must be "
                "provided together for mTLS"
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

        self.session = requests.Session()

        # --------------------------------------------------------------
        # TLS / mTLS
        # --------------------------------------------------------------

        if client_cert_path and client_key_path:
            self.session.cert = (
                client_cert_path,
                client_key_path,
            )

        # requests verifies TLS certificates by default.
        # Never set this to False.
        if ca_cert_path:
            self.session.verify = ca_cert_path

        # --------------------------------------------------------------
        # Default headers
        # --------------------------------------------------------------

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if user_agent:
            headers["User-Agent"] = user_agent

        self.session.headers.update(headers)

        self._closed = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._closed:
            return

        self.session.close()
        self._closed = True

    def __enter__(self) -> "GatewayHttpClient":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    def get(
        self,
        endpoint: str,
        *,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Response:
        """Perform an HTTP GET request."""
        return self._request(
            method="GET",
            endpoint=endpoint,
            timeout=timeout,
            headers=headers,
            params=params,
        )

    def post(
        self,
        endpoint: str,
        *,
        json: Any = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Response:
        """Perform an HTTP POST request."""
        return self._request(
            method="POST",
            endpoint=endpoint,
            json=json,
            timeout=timeout,
            headers=headers,
            params=params,
        )

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        json: Any = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Response:
        """Perform a generic HTTP request."""
        return self._request(
            method=method,
            endpoint=endpoint,
            json=json,
            timeout=timeout,
            headers=headers,
            params=params,
        )

    # ------------------------------------------------------------------
    # Internal request handling
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: Any = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Response:
        """Execute one HTTP request.

        No retry is performed here. A failed request is propagated to
        the caller so that the appropriate reliability policy can decide
        whether and how it should be retried.
        """
        if self._closed:
            raise GatewayHttpRequestError(
                "Gateway HTTP client is closed"
            )

        if not isinstance(method, str) or not method.strip():
            raise ValueError(
                "method must be a non-empty string"
            )

        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError(
                "endpoint must be a non-empty string"
            )

        if timeout is not None and timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero"
            )

        url = self._build_url(endpoint)

        request_timeout = (
            self.timeout
            if timeout is None
            else float(timeout)
        )

        try:
            return self.session.request(
                method=method.upper(),
                url=url,
                json=json,
                timeout=request_timeout,
                headers=dict(headers) if headers else None,
                params=dict(params) if params else None,
            )
        except RequestException as exc:
            logger.warning(
                "Gateway HTTP request failed: method=%s endpoint=%s error=%s",
                method.upper(),
                endpoint,
                exc,
            )
            raise GatewayHttpRequestError(
                f"Gateway HTTP request failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # URL handling
    # ------------------------------------------------------------------

    def _build_url(
        self,
        endpoint: str,
    ) -> str:
        """Build an absolute URL from the configured base URL."""
        return (
            f"{self.base_url}/"
            f"{endpoint.lstrip('/')}"
        )


__all__ = [
    "GatewayHttpError",
    "GatewayHttpRequestError",
    "GatewayHttpClient",
]