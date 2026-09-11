# Path: Version 1_0_0/agent/infrastructure/clock.py

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class Clock(ABC):
    """
    Abstract clock used by the application.

    Provides:
    - Wall-clock UTC time.
    - Monotonic time for durations/timeouts.
    - Sleep abstraction for testability.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return the current UTC datetime."""
        raise NotImplementedError

    @abstractmethod
    def monotonic(self) -> float:
        """Return a monotonic timestamp suitable for durations/timeouts."""
        raise NotImplementedError

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """Sleep for the requested number of seconds."""
        raise NotImplementedError


class SystemClock(Clock):
    """
    Production clock backed by Python's system time functions.

    UTC is always returned as a timezone-aware datetime.
    """

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep duration cannot be negative.")

        time.sleep(seconds)

    def timestamp(self) -> float:
        """
        Return the current UTC Unix timestamp.
        """
        return self.now().timestamp()

    def isoformat(self) -> str:
        """
        Return the current UTC time in ISO-8601 format.
        """
        return self.now().isoformat()


__all__ = [
    "Clock",
    "SystemClock",
]