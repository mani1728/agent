# Path: Version 1_0_0/agent/core/dispatcher.py

# -*- coding: utf-8 -*-
"""
dispatcher.py
-------------
Core command dispatcher.

مسئولیت:
- دریافت CommandEnvelope
- اعتبارسنجی target_class / target_method
- Dispatch امن به handler مجاز
- حفظ رفتار legacy مربوط به Mt5_Manager

این فایل عمداً:
- هیچ وابستگی به Kafka ندارد
- هیچ وابستگی به HTTP ندارد
- Transport را نمی‌شناسد
- Persistence / Retry / Circuit Breaker را پیاده‌سازی نمی‌کند
- از getattr پویا بر اساس ورودی command برای دسترسی مستقیم استفاده نمی‌کند

اصل migration:
    Preserve behavior first, improve architecture second.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope, ResponseStatus

from agent.adapters.mt5_adapter import Mt5Adapter

if TYPE_CHECKING:
    from .meta_trader_manager import Mt5_Manager


logger = logging.getLogger(__name__)


class DispatchError(Exception):
    """Base exception for dispatcher failures."""


class UnknownTargetError(DispatchError):
    """Raised when the requested target class is not allowed."""


class UnknownMethodError(DispatchError):
    """Raised when the requested method is not allowed."""


class Dispatcher:
    """
    Safe allowlist-based command dispatcher.

    Legacy behavior:
        target_class == "Mt5_Manager"
            -> Mt5_Manager instance

    برخلاف implementation قدیمی، نام متد مستقیماً از ورودی
    به getattr() داده نمی‌شود؛ ابتدا باید در allowlist قرار داشته باشد.
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
    ) -> None:
        """
        Args:
            mt5_manager:
                Existing Mt5_Manager instance.
                اگر داده نشود، Dispatcher خودش یک instance می‌سازد.

            allowed_methods:
                Optional per-target method allowlist.

                Example:
                    {
                        "Mt5_Manager": {
                            "manage_connection",
                            "manage_symbols",
                        }
                    }

                اگر None باشد، DEFAULT_ALLOWED_METHODS استفاده می‌شود.
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """
        Execute one CommandEnvelope and return ResponseEnvelope.

        Dispatcher owns command routing only.
        Response construction is kept transport-independent.
        """

        started = time.perf_counter()

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
        """
        Compatibility helper.

        برای زمانی که هنوز caller کاملاً به CommandEnvelope مهاجرت نکرده
        مفید است.

        ساخت CommandEnvelope در همین مرز انجام می‌شود تا business handler
        با dict خام transport کار نکند.
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
        """
        Resolve target only through explicit allowlist.

        مهم:
        اینجا از import پویا یا class name ورودی استفاده نمی‌کنیم.
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
        """
        Resolve a method after allowlist validation.
        """

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


__all__ = [
    "Dispatcher",
    "DispatchError",
    "UnknownTargetError",
    "UnknownMethodError",
]
