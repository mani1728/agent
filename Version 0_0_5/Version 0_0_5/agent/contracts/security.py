from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


class AuthenticationError(ValueError):
    """Raised when an ingress request cannot be authenticated."""


class AuthorizationError(ValueError):
    """Raised when an authenticated principal is not permitted."""


@dataclass(frozen=True)
class SecurityContext:
    """Immutable authenticated principal context."""

    principal_id: str
    authentication_method: str
    permissions: frozenset[str]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id must be a non-empty string")
        if not isinstance(self.authentication_method, str) or not self.authentication_method.strip():
            raise ValueError("authentication_method must be a non-empty string")
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class AuthenticationResult:
    """Deterministic authentication outcome."""

    success: bool
    context: SecurityContext | None = None
    code: str = "ok"
    message: str = ""


@dataclass(frozen=True)
class AuthorizationDecision:
    """Deterministic authorization outcome."""

    allowed: bool
    code: str = "ok"
    message: str = ""


@runtime_checkable
class Authenticator(Protocol):
    """Port for transport/application authentication adapters."""

    def authenticate(self, request: Any) -> AuthenticationResult: ...


@runtime_checkable
class Authorizer(Protocol):
    """Port for command authorization policy adapters."""

    def authorize(self, context: SecurityContext, command: Any) -> AuthorizationDecision: ...


class AllowAllAuthenticator:
    """Explicit development adapter; never provides real authentication."""

    def authenticate(self, request: Any) -> AuthenticationResult:
        return AuthenticationResult(
            success=True,
            context=SecurityContext("anonymous", "none", frozenset(), {}),
        )


class AllowAllAuthorizer:
    """Explicit development policy that permits every command."""

    def authorize(self, context: SecurityContext, command: Any) -> AuthorizationDecision:
        return AuthorizationDecision(True)
