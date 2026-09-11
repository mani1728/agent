# Path: Version 1_0_0/agent/reliability/retry.py

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Type

from .backoff import BackoffConfig, ExponentialBackoff


class RetryError(RuntimeError):
    """Base exception for retry failures."""


class RetryExhaustedError(RetryError):
    """
    Raised when all retry attempts are exhausted.

    The original exception is available through ``last_exception``.
    """

    def __init__(
        self,
        message: str,
        *,
        last_exception: Optional[BaseException] = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


@dataclass(frozen=True)
class RetryConfig:
    """
    Retry execution policy.

    max_attempts includes the initial execution.

    Example:
        max_attempts=1 -> no retry
        max_attempts=3 -> initial attempt + 2 retries
    """

    max_attempts: int = 3
    retry_exceptions: tuple[
        Type[BaseException], ...
    ] = (Exception,)

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool):
            raise ValueError(
                "max_attempts must be an integer."
            )

        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts must be >= 1."
            )

        if not self.retry_exceptions:
            raise ValueError(
                "retry_exceptions cannot be empty."
            )

        for exception_type in self.retry_exceptions:
            if not isinstance(exception_type, type):
                raise TypeError(
                    "retry_exceptions must contain "
                    "exception types."
                )

            if not issubclass(
                exception_type,
                BaseException,
            ):
                raise TypeError(
                    "retry_exceptions must contain "
                    "BaseException subclasses."
                )


@dataclass(frozen=True)
class RetryDecision:
    """
    Decision made after a failed attempt.
    """

    retry: bool
    attempt: int
    max_attempts: int
    delay_seconds: float
    reason: str

    @property
    def exhausted(self) -> bool:
        return (
            not self.retry
            and self.attempt >= self.max_attempts
        )


@dataclass(frozen=True)
class RetryResult:
    """
    Result of a retry operation.
    """

    result: Any
    attempts: int


class RetryPolicy:
    """
    Stateless retry policy.

    Attempt numbering:
        attempt=1 -> first execution
        attempt=2 -> first retry
        attempt=3 -> second retry

    The policy itself does not sleep and does not execute functions.
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        *,
        backoff: Optional[ExponentialBackoff] = None,
    ) -> None:
        self._config = (
            config
            if config is not None
            else RetryConfig()
        )

        self._backoff = (
            backoff
            if backoff is not None
            else ExponentialBackoff(
                BackoffConfig()
            )
        )

    @property
    def config(self) -> RetryConfig:
        return self._config

    @property
    def backoff(self) -> ExponentialBackoff:
        return self._backoff

    def should_retry(
        self,
        exception: BaseException,
        *,
        attempt: int,
    ) -> bool:
        if not isinstance(attempt, int):
            raise ValueError(
                "attempt must be an integer."
            )

        if isinstance(attempt, bool):
            raise ValueError(
                "attempt must be an integer, not bool."
            )

        if attempt < 1:
            raise ValueError(
                "attempt must be >= 1."
            )

        if attempt >= self._config.max_attempts:
            return False

        return isinstance(
            exception,
            self._config.retry_exceptions,
        )

    def decision(
        self,
        exception: BaseException,
        *,
        attempt: int,
    ) -> RetryDecision:
        retry = self.should_retry(
            exception,
            attempt=attempt,
        )

        if not retry:
            if attempt >= self._config.max_attempts:
                reason = "max_attempts_exhausted"
            else:
                reason = "exception_not_retryable"

            return RetryDecision(
                retry=False,
                attempt=attempt,
                max_attempts=self._config.max_attempts,
                delay_seconds=0.0,
                reason=reason,
            )

        # Backoff uses zero-based retry index.
        retry_index = attempt - 1

        delay = self._backoff.calculate(
            retry_index,
            apply_jitter=True,
        )

        return RetryDecision(
            retry=True,
            attempt=attempt,
            max_attempts=self._config.max_attempts,
            delay_seconds=delay,
            reason="retryable_failure",
        )


class RetryExecutor:
    """
    Executes a callable according to a RetryPolicy.

    Default behavior:
        initial execution
        -> failure
        -> backoff
        -> retry
        -> ...

    This executor deliberately does not:
    - classify HTTP/Kafka-specific errors
    - interact with circuit breakers
    - persist retry state
    - deduplicate requests
    - retry non-idempotent operations automatically
    """

    def __init__(
        self,
        policy: Optional[RetryPolicy] = None,
        *,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> None:
        self._policy = (
            policy
            if policy is not None
            else RetryPolicy()
        )

        self._sleep_fn = (
            sleep_fn
            if sleep_fn is not None
            else time.sleep
        )

        if not callable(self._sleep_fn):
            raise TypeError(
                "sleep_fn must be callable."
            )

    @property
    def policy(self) -> RetryPolicy:
        return self._policy

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        if not callable(func):
            raise TypeError(
                "func must be callable."
            )

        last_exception: Optional[
            BaseException
        ] = None

        for attempt in range(
            1,
            self._policy.config.max_attempts + 1,
        ):
            try:
                result = func(
                    *args,
                    **kwargs,
                )

                return RetryResult(
                    result=result,
                    attempts=attempt,
                )

            except BaseException as exc:
                last_exception = exc

                decision = self._policy.decision(
                    exc,
                    attempt=attempt,
                )

                if not decision.retry:
                    if (
                        attempt
                        >= self._policy.config.max_attempts
                    ):
                        raise RetryExhaustedError(
                            "Retry attempts exhausted.",
                            last_exception=exc,
                            attempts=attempt,
                        ) from exc

                    raise

                if decision.delay_seconds > 0:
                    self._sleep_fn(
                        decision.delay_seconds
                    )

        # Defensive fallback. The loop should always return or raise.
        raise RetryExhaustedError(
            "Retry execution ended unexpectedly.",
            last_exception=last_exception,
            attempts=self._policy.config.max_attempts,
        )


def retry_call(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    retry_exceptions: tuple[
        Type[BaseException], ...
    ] = (Exception,),
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    multiplier: float = 2.0,
    jitter_ratio: float = 0.0,
    sleep_fn: Optional[
        Callable[[float], None]
    ] = None,
    **kwargs: Any,
) -> RetryResult:
    """
    Convenience wrapper for retrying a callable.
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        retry_exceptions=retry_exceptions,
    )

    backoff = ExponentialBackoff(
        BackoffConfig(
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            multiplier=multiplier,
            jitter_ratio=jitter_ratio,
        )
    )

    policy = RetryPolicy(
        config=config,
        backoff=backoff,
    )

    executor = RetryExecutor(
        policy=policy,
        sleep_fn=sleep_fn,
    )

    return executor.execute(
        func,
        *args,
        **kwargs,
    )


__all__ = [
    "RetryConfig",
    "RetryDecision",
    "RetryError",
    "RetryExhaustedError",
    "RetryExecutor",
    "RetryPolicy",
    "RetryResult",
    "retry_call",
]