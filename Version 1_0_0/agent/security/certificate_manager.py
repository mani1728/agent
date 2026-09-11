# Path: Version 1_0_0/agent/security/certificate_manager.py

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class CertificateManagerError(RuntimeError):
    """Base error for certificate management failures."""


class CertificateConfigurationError(CertificateManagerError):
    """Raised when certificate configuration is invalid."""


class CertificateValidationError(CertificateManagerError):
    """Raised when a configured certificate file cannot be validated."""


@dataclass(frozen=True)
class CertificateConfig:
    """
    TLS/mTLS certificate configuration.

    ca_cert:
        CA certificate bundle used to validate the remote server.

    client_cert:
        Client certificate used for mTLS.

    client_key:
        Private key corresponding to client_cert.

    key_password:
        Optional private-key password. The value is intentionally never
        included in repr/logging output.

    server_hostname:
        Optional hostname used for TLS hostname verification by callers.
    """

    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    key_password: Optional[str] = None
    server_hostname: Optional[str] = None

    def __repr__(self) -> str:
        return (
            "CertificateConfig("
            f"ca_cert={self.ca_cert!r}, "
            f"client_cert={self.client_cert!r}, "
            f"client_key={self.client_key!r}, "
            "key_password=<redacted>, "
            f"server_hostname={self.server_hostname!r}"
            ")"
        )


class CertificateManager:
    """
    Validates certificate configuration and creates secure TLS contexts.

    This class does not perform network communication and does not manage
    certificate enrollment/rotation. Those concerns belong to later
    security/transport phases.
    """

    def __init__(
        self,
        config: Optional[CertificateConfig] = None,
    ) -> None:
        self._config = config or CertificateConfig()

    @property
    def config(self) -> CertificateConfig:
        return self._config

    @staticmethod
    def _path(value: Optional[str], field_name: str) -> Optional[Path]:
        if value is None:
            return None

        value = str(value).strip()
        if not value:
            raise CertificateConfigurationError(
                f"{field_name} cannot be empty when provided"
            )

        return Path(value).expanduser()

    @staticmethod
    def _validate_file(path: Path, field_name: str) -> None:
        if not path.exists():
            raise CertificateValidationError(
                f"{field_name} does not exist: {path}"
            )

        if not path.is_file():
            raise CertificateValidationError(
                f"{field_name} is not a file: {path}"
            )

        try:
            with path.open("rb"):
                pass
        except OSError as exc:
            raise CertificateValidationError(
                f"{field_name} is not readable: {path}"
            ) from exc

    def validate(self, require_mtls: bool = False) -> None:
        """
        Validate configured certificate paths.

        If require_mtls=True, both client certificate and private key
        must be configured.
        """
        ca_cert = self._path(self._config.ca_cert, "ca_cert")
        client_cert = self._path(self._config.client_cert, "client_cert")
        client_key = self._path(self._config.client_key, "client_key")

        if ca_cert is not None:
            self._validate_file(ca_cert, "ca_cert")

        if client_cert is not None:
            self._validate_file(client_cert, "client_cert")

        if client_key is not None:
            self._validate_file(client_key, "client_key")

        if require_mtls:
            if client_cert is None:
                raise CertificateConfigurationError(
                    "client_cert is required when mTLS is enabled"
                )

            if client_key is None:
                raise CertificateConfigurationError(
                    "client_key is required when mTLS is enabled"
                )

        if (client_cert is None) != (client_key is None):
            raise CertificateConfigurationError(
                "client_cert and client_key must be configured together"
            )

        if self._config.server_hostname is not None:
            hostname = self._config.server_hostname.strip()
            if not hostname:
                raise CertificateConfigurationError(
                    "server_hostname cannot be empty when provided"
                )

    def has_ca_certificate(self) -> bool:
        return bool(self._config.ca_cert)

    def has_client_certificate(self) -> bool:
        return bool(
            self._config.client_cert
            and self._config.client_key
        )

    def create_ssl_context(
        self,
        *,
        require_mtls: bool = False,
    ) -> ssl.SSLContext:
        """
        Create a secure client-side SSL context.

        Server certificate validation and hostname verification are always
        enabled. This method intentionally never creates an insecure
        verify=False equivalent.
        """
        self.validate(require_mtls=require_mtls)

        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
        )

        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        ca_cert = self._path(self._config.ca_cert, "ca_cert")

        if ca_cert is not None:
            try:
                context.load_verify_locations(
                    cafile=str(ca_cert),
                )
            except (OSError, ssl.SSLError) as exc:
                raise CertificateValidationError(
                    f"Unable to load CA certificate: {ca_cert}"
                ) from exc

        if self.has_client_certificate():
            client_cert = self._path(
                self._config.client_cert,
                "client_cert",
            )
            client_key = self._path(
                self._config.client_key,
                "client_key",
            )

            assert client_cert is not None
            assert client_key is not None

            try:
                context.load_cert_chain(
                    certfile=str(client_cert),
                    keyfile=str(client_key),
                    password=self._config.key_password,
                )
            except (OSError, ssl.SSLError) as exc:
                raise CertificateValidationError(
                    "Unable to load client certificate/private key"
                ) from exc

        logger.debug(
            "TLS context created ca_cert=%s client_certificate=%s",
            bool(ca_cert),
            self.has_client_certificate(),
        )

        return context

    def certificate_paths(self) -> dict[str, Optional[str]]:
        """
        Return non-secret certificate paths for diagnostics/configuration.

        Private-key passwords are intentionally excluded.
        """
        return {
            "ca_cert": self._config.ca_cert,
            "client_cert": self._config.client_cert,
            "client_key": self._config.client_key,
            "server_hostname": self._config.server_hostname,
        }


__all__ = [
    "CertificateConfig",
    "CertificateManager",
    "CertificateManagerError",
    "CertificateConfigurationError",
    "CertificateValidationError",
]