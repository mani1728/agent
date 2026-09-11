"""Clock adapter compatibility layer.

Legacy adapter-style static-time helpers are preserved while delegating all
clock behavior to the canonical infrastructure clock implementation.
"""

from __future__ import annotations

from typing import Any

from agent.infrastructure.clock import SystemClock as InfrastructureSystemClock


class Clock:
    """Compatibility clock abstraction for legacy adapter imports.

    Kept for backward compatibility with call sites that import
    ``agent.adapters.clock.Clock``.

    The implementation is intentionally small and delegates to
    ``agent.infrastructure.clock.SystemClock`` to avoid duplicated
    time behavior.
    """

    _impl = InfrastructureSystemClock()

    @staticmethod
    def now() -> Any:
        """Return the current UTC-aware wall-clock datetime."""
        return Clock._impl.now()

    @classmethod
    def now_iso(cls) -> str:
        """Return the current UTC timestamp in ISO-8601 format."""
        return cls.now().isoformat()

    @staticmethod
    def unix_time() -> float:
        """Return the current Unix timestamp."""
        return Clock._impl.timestamp()

    @staticmethod
    def monotonic() -> float:
        """Return a monotonic clock value."""
        return Clock._impl.monotonic()

    @classmethod
    def elapsed(cls, started_at: float) -> float:
        """Return elapsed monotonic time in seconds."""
        if not isinstance(started_at, (int, float)):
            raise TypeError("started_at must be a number")

        return max(0.0, cls.monotonic() - float(started_at))

    @classmethod
    def deadline(cls, timeout_seconds: float) -> float:
        """Create a monotonic deadline."""
        if timeout_seconds < 0:
            raise ValueError(
                "timeout_seconds must be greater than or equal to zero"
            )

        return cls.monotonic() + float(timeout_seconds)

    @classmethod
    def remaining(cls, deadline: float) -> float:
        """Return remaining seconds until a monotonic deadline."""
        if not isinstance(deadline, (int, float)):
            raise TypeError("deadline must be a number")

        return max(0.0, float(deadline) - cls.monotonic())

    @classmethod
    def expired(cls, deadline: float) -> bool:
        """Return True when a monotonic deadline has expired."""
        return cls.remaining(deadline) <= 0.0


class SystemClock(Clock):
    """Backward-compatible alias for the system clock implementation."""


__all__ = [
    "Clock",
    "SystemClock",
]
