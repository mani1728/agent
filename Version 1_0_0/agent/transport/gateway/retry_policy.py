# Path: Version 1_0_0/agent/transport/gateway/retry_policy.py

"""Retry policy for Gateway transport operations.

This module provides transport-independent retry decisions and backoff
calculation.

The policy does not perform HTTP requests. The caller is responsible for
executing the retry when ``should_retry()`` returns True.

Important:
- Connection/timeouts are considered retryable.
- HTTP 408, 429 and transient 5xx responses are retryable.
- Authentication, authorization, validation and most 4xx responses are
  not retryable.
- Retry behavior is bounded by ``max_attempts``.
- Exponential backoff includes optional jitter.
- Non-idempotent operations should not be blindly retried.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from requests import Response
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    RequestException,
    Timeout,
)


@dataclass(frozen=True)
class RetryDecision:
    """Result of a retry-policy evaluation."""

    retry: bool
    attempt: int
    max_attempts: int
    delay_seconds: float
    reason: str

    @property
    def exhausted(self) -> bool:
        """Return True when no further retry is allowed."""
        return self.attempt >= self.max_attempts


class GatewayRetryPolicy:
    """Bounded retry policy with exponential backoff and jitter.

    Parameters
    ----------
    max_attempts:
        Total number of attempts, including the initial request.

    base_delay:
        Initial backoff delay in seconds.

    max_delay:
        Maximum calculated delay in seconds.

    jitter_ratio:
        Random jitter ratio applied to the calculated delay.

    retry_on_5xx:
        Whether transient server errors should be retried.

    retry_on_429:
        Whether HTTP 429 should be retried.
    """

    RETRYABLE_STATUS_CODES = frozenset(
        {
            408,
            429,
            500,
            502,
            503,
            504,
        }
    )

    NON_RETRYABLE_STATUS_CODES = frozenset(
        {
            400,
            401,
            403,
            404,
            405,
            409,
            410,
            422,
        }
    )

    IDEMPOTENT_METHODS = frozenset(
        {
            "GET",
            "HEAD",
            "OPTIONS",
            "PUT",
            "DELETE",
        }
    )

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        jitter_ratio: float = 0.20,
        retry_on_5xx: bool = True,
        retry_on_429: bool = True,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )

        if base_delay < 0:
            raise ValueError(
                "base_delay must be greater than or equal to zero"
            )

        if max_delay < 0:
            raise ValueError(
                "max_delay must be greater than or equal to zero"
            )

        if max_delay < base_delay:
            raise ValueError(
                "max_delay must be greater than or equal to base_delay"
            )

        if not 0 <= jitter_ratio <= 1:
            raise ValueError(
                "jitter_ratio must be between 0 and 1"
            )

        self.max_attempts = int(max_attempts)
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)
        self.jitter_ratio = float(jitter_ratio)
        self.retry_on_5xx = bool(retry_on_5xx)
        self.retry_on_429 = bool(retry_on_429)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_retry(
        self,
        *,
        method: str,
        attempt: int,
        response: Optional[Response] = None,
        exception: Optional[BaseException] = None,
        idempotent: Optional[bool] = None,
    ) -> RetryDecision:
        """Evaluate whether an operation should be retried.

        ``attempt`` is one-based:

        - 1 = initial attempt
        - 2 = first retry
        - 3 = second retry

        The policy never retries beyond ``max_attempts``.
        """
        normalized_method = self._normalize_method(method)

        if attempt < 1:
            raise ValueError(
                "attempt must be at least 1"
            )

        if attempt >= self.max_attempts:
            return RetryDecision(
                retry=False,
                attempt=attempt,
                max_attempts=self.max_attempts,
                delay_seconds=0.0,
                reason="maximum retry attempts exhausted",
            )

        is_operation_idempotent = (
            self.is_idempotent_method(normalized_method)
            if idempotent is None
            else bool(idempotent)
        )

        if not is_operation_idempotent:
            return RetryDecision(
                retry=False,
                attempt=attempt,
                max_attempts=self.max_attempts,
                delay_seconds=0.0,
                reason=(
                    "operation is non-idempotent; "
                    "automatic retry is disabled"
                ),
            )

        reason = self._retry_reason(
            response=response,
            exception=exception,
        )

        if reason is None:
            return RetryDecision(
                retry=False,
                attempt=attempt,
                max_attempts=self.max_attempts,
                delay_seconds=0.0,
                reason="operation is not retryable",
            )

        delay = self.backoff_delay(attempt)

        return RetryDecision(
            retry=True,
            attempt=attempt,
            max_attempts=self.max_attempts,
            delay_seconds=delay,
            reason=reason,
        )

    def backoff_delay(
        self,
        attempt: int,
    ) -> float:
        """Calculate exponential backoff with bounded jitter."""
        if attempt < 1:
            raise ValueError(
                "attempt must be at least 1"
            )

        exponential_delay = min(
            self.max_delay,
            self.base_delay * (2 ** (attempt - 1)),
        )

        if exponential_delay <= 0 or self.jitter_ratio <= 0:
            return exponential_delay

        jitter = random.uniform(
            0.0,
            exponential_delay * self.jitter_ratio,
        )

        return min(
            self.max_delay,
            exponential_delay + jitter,
        )

    # ------------------------------------------------------------------
    # Retry classification
    # ------------------------------------------------------------------

    def is_retryable_status(
        self,
        status_code: int,
    ) -> bool:
        """Return whether an HTTP status code is transient."""
        if status_code == 429:
            return self.retry_on_429

        if 500 <= status_code <= 599:
            return self.retry_on_5xx

        return status_code in self.RETRYABLE_STATUS_CODES

    @staticmethod
    def is_idempotent_method(
        method: str,
    ) -> bool:
        """Return whether an HTTP method is normally idempotent."""
        return (
            isinstance(method, str)
            and method.upper() in GatewayRetryPolicy.IDEMPOTENT_METHODS
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _retry_reason(
        self,
        *,
        response: Optional[Response],
        exception: Optional[BaseException],
    ) -> Optional[str]:
        """Classify a failed operation."""
        if exception is not None:
            if isinstance(exception, Timeout):
                return "request timeout"

            if isinstance(exception, RequestsConnectionError):
                return "connection error"

            if isinstance(exception, RequestException):
                return "transient HTTP request exception"

            return None

        if response is not None:
            status_code = response.status_code

            if self.is_retryable_status(status_code):
                return f"retryable HTTP status {status_code}"

            if status_code in self.NON_RETRYABLE_STATUS_CODES:
                return f"non-retryable HTTP status {status_code}"

        return None

    @staticmethod
    def _normalize_method(
        method: str,
    ) -> str:
        """Normalize and validate an HTTP method."""
        if not isinstance(method, str) or not method.strip():
            raise ValueError(
                "method must be a non-empty string"
            )

        return method.strip().upper()


__all__ = [
    "RetryDecision",
    "GatewayRetryPolicy",
]