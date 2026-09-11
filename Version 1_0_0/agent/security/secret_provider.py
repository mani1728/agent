# Path: Version 1_0_0/agent/security/secret_provider.py

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional


logger = logging.getLogger(__name__)


class SecretProviderError(RuntimeError):
    """Base error for secret-provider failures."""


class SecretNotFoundError(SecretProviderError):
    """Raised when a requested secret does not exist."""


class InvalidSecretNameError(SecretProviderError):
    """Raised when a secret name is invalid."""


def _validate_secret_name(name: str) -> str:
    if not isinstance(name, str):
        raise InvalidSecretNameError(
            "Secret name must be a string"
        )

    normalized = name.strip()

    if not normalized:
        raise InvalidSecretNameError(
            "Secret name cannot be empty"
        )

    if "\x00" in normalized:
        raise InvalidSecretNameError(
            "Secret name contains an invalid null character"
        )

    return normalized


class SecretProvider(ABC):
    """
    Transport- and storage-independent secret provider interface.

    Implementations may later use:
      - environment variables
      - Windows Credential Manager
      - an external secret manager
      - another OS-native secure store

    Callers should never log returned secret values.
    """

    @abstractmethod
    def get(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Return a secret or default when it is unavailable."""

    def require(self, name: str) -> str:
        """Return a secret or raise SecretNotFoundError."""
        value = self.get(name)

        if value is None:
            raise SecretNotFoundError(
                f"Required secret is not available: {name}"
            )

        return value

    def exists(self, name: str) -> bool:
        """Return whether a secret is available."""
        return self.get(name) is not None


@dataclass(frozen=True)
class EnvironmentSecretProvider(SecretProvider):
    """
    Read-only secret provider backed by environment variables.

    This is intentionally simple and dependency-free. It does not persist,
    modify, or print environment secrets.
    """

    prefix: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.prefix, str):
            raise TypeError("prefix must be a string")

    def _environment_name(self, name: str) -> str:
        normalized = _validate_secret_name(name)

        if not self.prefix:
            return normalized

        return f"{self.prefix}{normalized}"

    def get(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        environment_name = self._environment_name(name)

        value = os.environ.get(environment_name)

        if value is None:
            return default

        # Treat an explicitly empty environment variable as absent.
        if value == "":
            return default

        return value


class MappingSecretProvider(SecretProvider):
    """
    Read-only provider backed by an in-memory mapping.

    Intended primarily for dependency injection and tests. It does not copy
    or expose secrets through repr/logging.
    """

    def __init__(
        self,
        secrets: Mapping[str, str],
    ) -> None:
        if not isinstance(secrets, Mapping):
            raise TypeError("secrets must be a mapping")

        self._secrets = dict(secrets)

    def get(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        normalized = _validate_secret_name(name)

        value = self._secrets.get(normalized)

        if value is None:
            return default

        if not isinstance(value, str):
            raise SecretProviderError(
                f"Secret value for '{normalized}' must be a string"
            )

        if value == "":
            return default

        return value

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(secret_count={len(self._secrets)})"
        )


class ChainedSecretProvider(SecretProvider):
    """
    Try multiple providers in order.

    This enables a gradual migration from environment/config-based secrets
    to a secure OS/external provider without changing consumers.
    """

    def __init__(
        self,
        providers: list[SecretProvider] | tuple[SecretProvider, ...],
    ) -> None:
        if not providers:
            raise ValueError(
                "At least one secret provider is required"
            )

        if any(
            not isinstance(provider, SecretProvider)
            for provider in providers
        ):
            raise TypeError(
                "All providers must implement SecretProvider"
            )

        self._providers = tuple(providers)

    @property
    def providers(self) -> tuple[SecretProvider, ...]:
        return self._providers

    def get(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        normalized = _validate_secret_name(name)

        for provider in self._providers:
            value = provider.get(normalized)

            if value is not None:
                return value

        return default

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(provider_count={len(self._providers)})"
        )


def get_secret(
    provider: SecretProvider,
    name: str,
    *,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Convenience function for dependency-injected secret retrieval.
    """
    if not isinstance(provider, SecretProvider):
        raise TypeError(
            "provider must implement SecretProvider"
        )

    return provider.get(
        name,
        default=default,
    )


def require_secret(
    provider: SecretProvider,
    name: str,
) -> str:
    """
    Convenience function for required secret retrieval.
    """
    if not isinstance(provider, SecretProvider):
        raise TypeError(
            "provider must implement SecretProvider"
        )

    return provider.require(name)


__all__ = [
    "ChainedSecretProvider",
    "EnvironmentSecretProvider",
    "InvalidSecretNameError",
    "MappingSecretProvider",
    "SecretNotFoundError",
    "SecretProvider",
    "SecretProviderError",
    "get_secret",
    "require_secret",
]