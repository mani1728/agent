# Path: Version 1_0_0/agent/reliability/circuit_breaker.py

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class CircuitBreakerError(RuntimeError):
    """Base exception for circuit breaker failures."""


class CircuitOpenError(CircuitBreakerError):
    """Raised when execution is rejected because the circuit is open."""


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """
    Circuit breaker configuration.

    failure_threshold:
        Number of consecutive counted failures required to open the circuit.

    recovery_timeout_seconds:
        Time the circuit remains open before a probe is allowed.

    success_threshold:
        Number of successful half-open probes required to close the circuit.

    count_exceptions:
        Exception types considered failures.
    """

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    success_threshold: int = 1
    count_exceptions: tuple[type[BaseException], ...] = (
        Exception,
    )

    def __post_init__(self) -> None:
        if isinstance(self.failure_threshold, bool):
            raise ValueError(
                "failure_threshold must be an integer."
            )

        if self.failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be >= 1."
            )

        if self.recovery_timeout_seconds < 0:
            raise ValueError(
                "recovery_timeout_seconds must be >= 0."
            )

        if isinstance(self.success_threshold, bool):
            raise ValueError(
                "success_threshold must be an integer."
            )

        if self.success_threshold < 1:
            raise ValueError(
                "success_threshold must be >= 1."
            )

        if not self.count_exceptions:
            raise ValueError(
                "count_exceptions cannot be empty."
            )

        for exception_type in self.count_exceptions:
            if not isinstance(exception_type, type):
                raise TypeError(
                    "count_exceptions must contain exception types."
                )

            if not issubclass(
                exception_type,
                BaseException,
            ):
                raise TypeError(
                    "count_exceptions must contain "
                    "BaseException subclasses."
                )


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    state: CircuitState
    consecutive_failures: int
    consecutive_successes: int
    opened_at: Optional[float]
    last_failure_at: Optional[float]
    last_success_at: Optional[float]
    half_open_probe_in_flight: bool


class CircuitBreaker:
    """
    Thread-safe circuit breaker.

    State flow:

        CLOSED
           |
           | failure threshold reached
           v
        OPEN
           |
           | recovery timeout elapsed
           v
        HALF_OPEN
          /   \
     success   failure
       |          |
       v          v
     CLOSED      OPEN

    The breaker controls admission only. It does not perform retries,
    sleeps, or transport operations.
    """

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        *,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._config = config or CircuitBreakerConfig()

        self._clock = (
            clock
            if clock is not None
            else time.monotonic
        )

        if not callable(self._clock):
            raise TypeError(
                "clock must be callable."
            )

        self._lock = threading.RLock()

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0

        self._opened_at: Optional[float] = None
        self._last_failure_at: Optional[float] = None
        self._last_success_at: Optional[float] = None

        self._half_open_probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._refresh_state_locked()
            return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    @property
    def config(self) -> CircuitBreakerConfig:
        return self._config

    def snapshot(self) -> CircuitBreakerSnapshot:
        with self._lock:
            self._refresh_state_locked()

            return CircuitBreakerSnapshot(
                state=self._state,
                consecutive_failures=(
                    self._consecutive_failures
                ),
                consecutive_successes=(
                    self._consecutive_successes
                ),
                opened_at=self._opened_at,
                last_failure_at=self._last_failure_at,
                last_success_at=self._last_success_at,
                half_open_probe_in_flight=(
                    self._half_open_probe_in_flight
                ),
            )

    def allow_request(self) -> bool:
        """
        Check whether a request may execute.

        CLOSED:
            Allowed.

        OPEN:
            Rejected until recovery timeout expires.

        HALF_OPEN:
            Exactly one probe is allowed at a time.
        """
        with self._lock:
            self._refresh_state_locked()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probe_in_flight:
                    return False

                self._half_open_probe_in_flight = True
                return True

            return False

    def ensure_request_allowed(self) -> None:
        if not self.allow_request():
            snapshot = self.snapshot()

            raise CircuitOpenError(
                "Circuit breaker is not allowing requests "
                f"(state={snapshot.state.value})."
            )

    def record_success(self) -> CircuitState:
        """
        Record a successful execution.
        """
        with self._lock:
            now = self._clock()

            self._last_success_at = now

            if self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0
                self._consecutive_successes = 0
                return self._state

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_probe_in_flight = False
                self._consecutive_failures = 0
                self._consecutive_successes += 1

                if (
                    self._consecutive_successes
                    >= self._config.success_threshold
                ):
                    self._state = CircuitState.CLOSED
                    self._consecutive_successes = 0
                    self._opened_at = None

                return self._state

            # A success should not normally be recorded while OPEN.
            # Keep the circuit open and clear no state implicitly.
            return self._state

    def record_failure(
        self,
        exception: Optional[BaseException] = None,
    ) -> CircuitState:
        """
        Record a failed execution.

        If exception is supplied and does not match count_exceptions,
        it is ignored and the current state is returned.
        """
        if (
            exception is not None
            and not isinstance(
                exception,
                self._config.count_exceptions,
            )
        ):
            return self.state

        with self._lock:
            now = self._clock()

            self._last_failure_at = now

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_probe_in_flight = False
                self._open_locked(now)
                return self._state

            if self._state == CircuitState.OPEN:
                return self._state

            self._consecutive_failures += 1
            self._consecutive_successes = 0

            if (
                self._consecutive_failures
                >= self._config.failure_threshold
            ):
                self._open_locked(now)

            return self._state

    def reset(self) -> None:
        """
        Force the breaker into CLOSED state.

        Intended for controlled lifecycle/configuration operations.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._opened_at = None
            self._half_open_probe_in_flight = False

    def force_open(self) -> None:
        """
        Force the breaker into OPEN state.
        """
        with self._lock:
            self._open_locked(self._clock())

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a callable through the circuit breaker.

        Exceptions counted by the configured policy are recorded as
        failures and re-raised unchanged.

        Exceptions not configured for counting are re-raised without
        changing the breaker state.
        """
        if not callable(func):
            raise TypeError(
                "func must be callable."
            )

        self.ensure_request_allowed()

        try:
            result = func(
                *args,
                **kwargs,
            )
        except BaseException as exc:
            self.record_failure(exc)
            raise

        self.record_success()

        return result

    def time_until_probe(self) -> float:
        """
        Return seconds remaining before an OPEN circuit can transition
        to HALF_OPEN.

        Returns zero when a probe is currently allowed or the circuit
        is not OPEN.
        """
        with self._lock:
            self._refresh_state_locked()

            if self._state != CircuitState.OPEN:
                return 0.0

            if self._opened_at is None:
                return 0.0

            elapsed = (
                self._clock()
                - self._opened_at
            )

            remaining = (
                self._config.recovery_timeout_seconds
                - elapsed
            )

            return max(0.0, remaining)

    def _refresh_state_locked(self) -> None:
        if self._state != CircuitState.OPEN:
            return

        if self._opened_at is None:
            self._state = CircuitState.HALF_OPEN
            self._half_open_probe_in_flight = False
            self._consecutive_successes = 0
            return

        elapsed = (
            self._clock()
            - self._opened_at
        )

        if (
            elapsed
            >= self._config.recovery_timeout_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_probe_in_flight = False
            self._consecutive_successes = 0

    def _open_locked(
        self,
        opened_at: float,
    ) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = opened_at
        self._consecutive_successes = 0
        self._half_open_probe_in_flight = False


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerSnapshot",
    "CircuitOpenError",
    "CircuitState",
]