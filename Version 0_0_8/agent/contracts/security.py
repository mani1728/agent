from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class SecurityContext:
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
    success: bool
    context: SecurityContext | None = None
    code: str = ""
    message: str = ""


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    code: str = ""
    message: str = ""


@runtime_checkable
class Authenticator(Protocol):
    def authenticate(self, request: Any) -> AuthenticationResult: ...


@runtime_checkable
class Authorizer(Protocol):
    def authorize(self, context: SecurityContext, command: Any) -> AuthorizationDecision: ...


class AllowAllAuthenticator:
    def authenticate(self, request: Any) -> AuthenticationResult:
        return AuthenticationResult(True, SecurityContext("anonymous", "none", frozenset(), {}))


class AllowAllAuthorizer:
    def authorize(self, context: SecurityContext, command: Any) -> AuthorizationDecision:
        return AuthorizationDecision(True)
