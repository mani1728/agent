# Path: agent/core/exceptions.py  (فایل جدید)

"""Typed exceptions for the core execution layer.

Centralized so that worker, dispatcher, and command_executor can all
import from one place without circular dependencies.
"""

from __future__ import annotations


class CoreError(Exception):
    """Base error for the core execution layer."""


class ValidationError(CoreError):
    """Permanent failure: malformed, invalid, or unauthorized input.

    MUST NOT be retried.
    """


class RetryableExternalError(CoreError):
    """Transient failure from an external dependency.

    Examples: MT5 timeout, network hiccup, broker unreachable.
    MAY be retried within bounded limits.
    """


class PermanentExternalError(CoreError):
    """Permanent failure from an external dependency.

    Examples: MT5 returned an invalid symbol, order rejected.
    MUST NOT be retried.
    """


__all__ = [
    "CoreError",
    "ValidationError",
    "RetryableExternalError",
    "PermanentExternalError",
]