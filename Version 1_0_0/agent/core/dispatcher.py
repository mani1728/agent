# Path: Version 1_0_0/agent/core/dispatcher.py

# -*- coding: utf-8 -*-
"""Core command dispatcher.

Responsibilities
----------------
- Receive a ``CommandEnvelope``.
- Enforce centralized authorization BEFORE method resolution.
- Validate ``target_class`` / ``target_method`` against an allowlist.
- Dispatch safely to the resolved handler.
- Preserve legacy ``Mt5_Manager`` behavior.

This module intentionally does NOT:
- Depend on Kafka, HTTP, or any transport.
- Depend on persistence, retry, or circuit-breaker logic.
- Use ``getattr`` against unvalidated user input.

Migration principle:
    Preserve behavior first, improve architecture second.

Patch 6
-------
``Dispatcher`` now accepts an optional ``CommandAuthorizer``. When a
non-None authorizer is supplied, ``dispatch`` calls
``authorizer.require(command)`` as a central guard before touching the
handler. Authorization failures surface as ``UnauthorizedCommandError``
(never silently converted into a generic error response), so that the
caller can classify the failure as permanent and skip retry.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope, ResponseStatus

from agent.adapters.mt5_adapter import Mt5Adapter

from agent.security.command_authorizer import (
    CommandAuthorizationError,
    CommandAuthorizer,
)

if TYPE_CHECKING:
    from .meta_trader_manager import Mt5_Manager


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

class DispatchError(Exception):
    """Base exception for dispatcher failures."""


class UnknownTargetError(DispatchError):
    """Raised when the requested target class is not allowed."""


class UnknownMethodError(DispatchError):
    """Raised when the requested method is not allowed."""


class UnauthorizedCommandError(DispatchError):
    """Raised when a command is not authorized by the central authorizer.

    This is a *permanent* failure: the caller must NOT retry the same
    command. Higher layers (worker) are expected to catch this and
    translate it into a non-retryable nack / error response.
    """


# ----------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------

class Dispatcher:
    """Safe allowlist-based command dispatcher.

    Legacy behavior:

        ``target_class == "Mt5_Manager"`` maps to the ``Mt5_Manager``
        adapter.

    Unlike the old implementation, ``target_method`` is never fed to
    ``getattr`` directly; it must first appear in an explicit allowlist.
    """

    DEFAULT_ALLOWED_METHODS = frozenset(
        {
            # Connection
            "manage_connection",

            # Symbols
            "manage_symbols",

            # Market book
            "manage_market_book",

            # Market data
            "fetch_data",

            # Trading
            "trade_manager",

            # Positions / history
            "manage_positions_history",
        }
    )

    def __init__(
        self,
        mt5_manager: Optional["Mt5_Manager"] = None,
        mt5_adapter: Optional[Mt5Adapter] = None,
        allowed_methods: Optional[Mapping[str, Any]] = None,
        authorizer: Optional[CommandAuthorizer] = None,
    ) -> None:
        """Create a dispatcher.

        Parameters
        ----------
        mt5_manager:
            Existing ``Mt5_Manager`` instance. When omitted, a fresh
            adapter is created internally.
        mt5_adapter:
            Optional pre-built adapter (primarily for tests).
        allowed_methods:
            Optional per-target method allowlist. When ``None``,
            ``DEFAULT_ALLOWED_METHODS`` is used for ``Mt5_Manager``.
        authorizer:
            Optional central ``CommandAuthorizer``. When provided,
            every dispatch is guarded by ``authorizer.require(command)``.

            Strongly recommended in production. When ``None``, a
            warning is logged and authorization is effectively
            skipped (legacy behavior preserved for migration).
        """
        if mt5_adapter is None:
            mt5_adapter = Mt5Adapter(manager=mt5_manager)

        self._mt5_adapter = mt5_adapter

        self._handlers: Dict[str, Any] = {
            "Mt5_Manager": self._mt5_adapter,
        }

        if allowed_methods is None:
            self._allowed_methods: Dict[str, frozenset[str]] = {
                "Mt5_Manager": self.DEFAULT_ALLOWED_METHODS
            }
        else:
            self._allowed_methods = {
                str(target): frozenset(str(method) for method in methods)
                for target, methods in allowed_methods.items()
            }

        if authorizer is None:
            logger.warning(
                "Dispatcher created without a CommandAuthorizer; "
                "authorization guard is DISABLED. This is unsafe for "
                "production and intended only for migration/tests."
            )
        self._authorizer = authorizer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """Execute one ``CommandEnvelope`` and return a ``ResponseEnvelope``.

        Order of operations:

        1. Central authorization guard (if an authorizer is configured).
        2. Target class / method normalization.
        3. Allowlist validation.
        4. Handler resolution.
        5. Method invocation.

        Authorization failures are raised as ``UnauthorizedCommandError``
        and are NOT swallowed into a generic error response. The caller
        must classify them as permanent failures (no retry).
        """
        started = time.perf_counter()

        # ----------------------------------------------------------------
        # 1. Central authorization guard
        # ----------------------------------------------------------------
        if self._authorizer is not None:
            try:
                self._authorizer.require(command)
            except CommandAuthorizationError as exc:
                logger.warning(
                    "Command rejected by authorizer: "
                    "target_class=%s target_method=%s",
                    getattr(command, "target_class", None),
                    getattr(command, "target_method", None),
                )
                # Re-raise as a dispatcher-level, permanent error so the
                # worker can distinguish it from transient failures.
                raise UnauthorizedCommandError(str(exc)) from exc

        # ----------------------------------------------------------------
        # 2..5. Route and execute
        # ----------------------------------------------------------------
        try:
            target_class = self._normalize_target_class(
                command.target_class
            )
            target_method = self._normalize_target_method(
                command.target_method
            )

            handler = self._resolve_handler(target_class)
            method = self._resolve_method(
                target_class=target_class,
                handler=handler,
                method_name=target_method,
            )

            result = method(**command.params)

            elapsed_ms = (time.perf_counter() - started) * 1000.0

            return ResponseEnvelope.success(
                correlation_id=command.correlation_id,
                data=result,
                schema_version="Mt5ResultV1",
                metadata={
                    "target_class": target_class,
                    "target_method": target_method,
                    "elapsed_ms": round(elapsed_ms, 3),
                },
            )

        except UnknownTargetError as exc:
            return self._error_response(
                command=command,
                error_code="UNKNOWN_TARGET",
                error_message=str(exc),
                started=started,
            )

        except UnknownMethodError as exc:
            return self._error_response(
                command=command,
                error_code="UNKNOWN_METHOD",
                error_message=str(exc),
                started=started,
            )

        except Exception as exc:
            logger.exception(
                "Command dispatch failed: target_class=%s target_method=%s",
                getattr(command, "target_class", None),
                getattr(command, "target_method", None),
            )

            return self._error_response(
                command=command,
                error_code="DISPATCH_ERROR",
                error_message=str(exc),
                started=started,
            )

    def dispatch_dict(
        self,
        payload: Mapping[str, Any],
        *,
        correlation_id: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> ResponseEnvelope:
        """Compatibility helper for callers that still pass raw dicts.

        Builds a ``CommandEnvelope`` at this boundary so that business
        handlers never see raw transport dicts.
        """
        command = CommandEnvelope.from_dict(
            dict(payload),
            correlation_id=correlation_id,
            priority=priority,
        )

        return self.dispatch(command)

    # ------------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_target_class(target_class: Any) -> str:
        if target_class is None:
            raise UnknownTargetError("target_class is required")

        value = str(target_class).strip()

        if not value:
            raise UnknownTargetError("target_class is empty")

        return value

    @staticmethod
    def _normalize_target_method(target_method: Any) -> str:
        if target_method is None:
            raise UnknownMethodError("target_method is required")

        value = str(target_method).strip()

        if not value:
            raise UnknownMethodError("target_method is empty")

        return value

    def _resolve_handler(self, target_class: str) -> Any:
        """Resolve a target only through the explicit allowlist.

        No dynamic import and no class-name injection from user input.
        """
        handler = self._handlers.get(target_class)

        if handler is None:
            raise UnknownTargetError(
                f"Unsupported target_class: {target_class}"
            )

        return handler

    def _resolve_method(
        self,
        *,
        target_class: str,
        handler: Any,
        method_name: str,
    ) -> Callable[[Dict[str, Any]], Any]:
        """Resolve a bound method after allowlist validation."""
        allowed = self._allowed_methods.get(target_class)

        if allowed is None:
            raise UnknownTargetError(
                f"No method allowlist for target_class: {target_class}"
            )

        if method_name not in allowed:
            raise UnknownMethodError(
                f"Unsupported method '{method_name}' "
                f"for target_class '{target_class}'"
            )

        method = getattr(handler, method_name, None)

        if method is None or not callable(method):
            raise UnknownMethodError(
                f"Handler method '{method_name}' is not available "
                f"for target_class '{target_class}'"
            )

        return method

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error_response(
        *,
        command: CommandEnvelope,
        error_code: str,
        error_message: str,
        started: float,
    ) -> ResponseEnvelope:
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return ResponseEnvelope.error(
            correlation_id=command.correlation_id,
            error_code=error_code,
            error_message=error_message,
            schema_version="Mt5ResultV1",
            metadata={
                "target_class": command.target_class,
                "target_method": command.target_method,
                "elapsed_ms": round(elapsed_ms, 3),
            },
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def authorizer(self) -> Optional[CommandAuthorizer]:
        """Return the configured authorizer (may be None)."""
        return self._authorizer


__all__ = [
    "Dispatcher",
    "DispatchError",
    "UnknownTargetError",
    "UnknownMethodError",
    "UnauthorizedCommandError",
]