# Path: Version 1_0_0/agent/adapters/clock.py

"""Clock adapter.

Provides a small abstraction over system time so that core components do
not depend directly on the Python time/datetime modules.

The adapter distinguishes between:

- wall-clock time: timestamps, logging and protocol payloads
- monotonic time: timeouts, deadlines and elapsed-time measurement

No transport, persistence or business logic belongs here.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional


class Clock:
    """System clock abstraction."""

    # ------------------------------------------------------------------
    # Wall clock
    # ------------------------------------------------------------------

    @staticmethod
    def now() -> datetime:
        """Return the current UTC-aware wall-clock datetime."""
        return datetime.now(timezone.utc)

    @classmethod
    def now_iso(cls) -> str:
        """Return the current UTC timestamp in ISO-8601 format."""
        return cls.now().isoformat()

    @staticmethod
    def unix_time() -> float:
        """Return the current Unix timestamp."""
        return time.time()

    # ------------------------------------------------------------------
    # Monotonic clock
    # ------------------------------------------------------------------

    @staticmethod
    def monotonic() -> float:
        """Return a monotonic clock value.

        This value must only be used for measuring elapsed time and
        calculating deadlines. It must not be interpreted as a timestamp.
        """
        return time.monotonic()

    @classmethod
    def elapsed(
        cls,
        started_at: float,
    ) -> float:
        """Return elapsed monotonic time in seconds."""
        if not isinstance(started_at, (int, float)):
            raise TypeError(
                "started_at must be a number"
            )

        return max(
            0.0,
            cls.monotonic() - float(started_at),
        )

    @classmethod
    def deadline(
        cls,
        timeout_seconds: float,
    ) -> float:
        """Create a monotonic deadline."""
        if timeout_seconds < 0:
            raise ValueError(
                "timeout_seconds must be greater than or equal to zero"
            )

        return cls.monotonic() + float(timeout_seconds)

    @classmethod
    def remaining(
        cls,
        deadline: float,
    ) -> float:
        """Return remaining seconds until a monotonic deadline."""
        if not isinstance(deadline, (int, float)):
            raise TypeError(
                "deadline must be a number"
            )

        return max(
            0.0,
            float(deadline) - cls.monotonic(),
        )

    @classmethod
    def expired(
        cls,
        deadline: float,
    ) -> bool:
        """Return True when a monotonic deadline has expired."""
        return cls.remaining(deadline) <= 0.0


class SystemClock(Clock):
    """Backward-compatible semantic alias for the system clock."""


__all__ = [
    "Clock",
    "SystemClock",
]