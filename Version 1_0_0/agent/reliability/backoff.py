# Path: Version 1_0_0/agent/reliability/backoff.py

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


class BackoffError(ValueError):
    """Raised when an invalid backoff configuration is provided."""


@dataclass(frozen=True)
class BackoffConfig:
    """
    Configuration for exponential backoff with optional jitter.
    """

    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    multiplier: float = 2.0
    jitter_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.base_delay_seconds < 0:
            raise BackoffError(
                "base_delay_seconds must be >= 0."
            )

        if self.max_delay_seconds < 0:
            raise BackoffError(
                "max_delay_seconds must be >= 0."
            )

        if self.max_delay_seconds < self.base_delay_seconds:
            raise BackoffError(
                "max_delay_seconds must be >= "
                "base_delay_seconds."
            )

        if self.multiplier < 1.0:
            raise BackoffError(
                "multiplier must be >= 1.0."
            )

        if not 0.0 <= self.jitter_ratio <= 1.0:
            raise BackoffError(
                "jitter_ratio must be between 0.0 and 1.0."
            )


class ExponentialBackoff:
    """
    Stateless exponential backoff calculator.

    Attempt numbering is zero-based:
        attempt=0 -> base delay
        attempt=1 -> base * multiplier
        attempt=2 -> base * multiplier^2

    The calculated delay is always bounded by max_delay_seconds.

    Jitter is positive-only:
        delay <= jittered_delay <= delay * (1 + jitter_ratio)

    and the final result is bounded by max_delay_seconds.
    """

    def __init__(
        self,
        config: Optional[BackoffConfig] = None,
        *,
        random_fn=None,
    ) -> None:
        self._config = config or BackoffConfig()

        self._random_fn = (
            random_fn
            if random_fn is not None
            else random.random
        )

        if not callable(self._random_fn):
            raise BackoffError(
                "random_fn must be callable."
            )

    @property
    def config(self) -> BackoffConfig:
        return self._config

    def calculate(
        self,
        attempt: int,
        *,
        apply_jitter: bool = True,
    ) -> float:
        """
        Calculate the delay for a retry attempt.

        attempt=0 represents the first retry delay.
        """
        if not isinstance(attempt, int):
            raise BackoffError(
                "attempt must be an integer."
            )

        if isinstance(attempt, bool):
            raise BackoffError(
                "attempt must be an integer, not bool."
            )

        if attempt < 0:
            raise BackoffError(
                "attempt must be >= 0."
            )

        config = self._config

        if config.base_delay_seconds == 0:
            return 0.0

        exponential_delay = (
            config.base_delay_seconds
            * (
                config.multiplier ** attempt
            )
        )

        delay = min(
            exponential_delay,
            config.max_delay_seconds,
        )

        if (
            apply_jitter
            and config.jitter_ratio > 0
            and delay > 0
        ):
            jitter = (
                self._random_fn()
                * config.jitter_ratio
            )

            if jitter < 0:
                jitter = 0.0

            delay = min(
                delay * (1.0 + jitter),
                config.max_delay_seconds,
            )

        return max(0.0, float(delay))

    def next_delay(
        self,
        attempt: int,
    ) -> float:
        return self.calculate(
            attempt,
            apply_jitter=True,
        )

    def delay_without_jitter(
        self,
        attempt: int,
    ) -> float:
        return self.calculate(
            attempt,
            apply_jitter=False,
        )


def calculate_backoff(
    attempt: int,
    *,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    multiplier: float = 2.0,
    jitter_ratio: float = 0.0,
    apply_jitter: bool = True,
) -> float:
    """
    Convenience function for one-off backoff calculation.
    """
    backoff = ExponentialBackoff(
        BackoffConfig(
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            multiplier=multiplier,
            jitter_ratio=jitter_ratio,
        )
    )

    return backoff.calculate(
        attempt,
        apply_jitter=apply_jitter,
    )


def calculate_exponential_delay(
    attempt: int,
    *,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    multiplier: float = 2.0,
) -> float:
    """
    Calculate deterministic exponential delay without jitter.
    """
    return calculate_backoff(
        attempt,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        multiplier=multiplier,
        jitter_ratio=0.0,
        apply_jitter=False,
    )


__all__ = [
    "BackoffConfig",
    "BackoffError",
    "ExponentialBackoff",
    "calculate_backoff",
    "calculate_exponential_delay",
]