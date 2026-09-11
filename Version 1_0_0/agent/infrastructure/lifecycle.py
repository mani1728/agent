# Path: Version 1_0_0/agent/infrastructure/lifecycle.py

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Callable, Optional


logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class Lifecycle:
    """
    Lightweight application lifecycle coordinator.

    Responsibilities:
    - Track lifecycle state.
    - Coordinate cooperative shutdown.
    - Register startup/shutdown callbacks.
    - Provide a common stop event.

    It does not know about transports, workers, Windows Services,
    persistence, or business logic.
    """

    def __init__(
        self,
        *,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger_ or logger

        self._lock = threading.RLock()
        self._stop_event = threading.Event()

        self._state = LifecycleState.CREATED

        self._start_callbacks: list[Callable[[], None]] = []
        self._stop_callbacks: list[Callable[[], None]] = []

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    @property
    def is_running(self) -> bool:
        return self.state == LifecycleState.RUNNING

    @property
    def is_stopping(self) -> bool:
        return self.state == LifecycleState.STOPPING

    @property
    def is_stopped(self) -> bool:
        return self.state == LifecycleState.STOPPED

    def register_start(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            raise TypeError("Start callback must be callable.")

        with self._lock:
            self._start_callbacks.append(callback)

    def register_stop(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            raise TypeError("Stop callback must be callable.")

        with self._lock:
            self._stop_callbacks.append(callback)

    def start(self) -> None:
        with self._lock:
            if self._state == LifecycleState.RUNNING:
                return

            if self._state not in {
                LifecycleState.CREATED,
                LifecycleState.STOPPED,
            }:
                raise RuntimeError(
                    f"Cannot start lifecycle from state: {self._state.value}"
                )

            self._state = LifecycleState.STARTING
            self._stop_event.clear()

            callbacks = list(self._start_callbacks)

        try:
            for callback in callbacks:
                callback()

            with self._lock:
                self._state = LifecycleState.RUNNING

        except Exception:
            with self._lock:
                self._state = LifecycleState.FAILED

            self._logger.exception(
                "Lifecycle startup failed."
            )
            raise

    def request_stop(self) -> bool:
        with self._lock:
            if self._state in {
                LifecycleState.STOPPING,
                LifecycleState.STOPPED,
            }:
                return False

            if self._state == LifecycleState.CREATED:
                self._state = LifecycleState.STOPPED
                self._stop_event.set()
                return True

            self._state = LifecycleState.STOPPING
            self._stop_event.set()

            return True

    def stop(self) -> None:
        should_run_callbacks = False

        with self._lock:
            if self._state == LifecycleState.STOPPED:
                return

            if self._state != LifecycleState.STOPPING:
                self._state = LifecycleState.STOPPING

            self._stop_event.set()

            callbacks = list(reversed(self._stop_callbacks))
            should_run_callbacks = True

        if not should_run_callbacks:
            return

        first_error: Optional[BaseException] = None

        for callback in callbacks:
            try:
                callback()
            except Exception as exc:
                if first_error is None:
                    first_error = exc

                self._logger.exception(
                    "Lifecycle stop callback failed."
                )

        with self._lock:
            self._state = (
                LifecycleState.FAILED
                if first_error is not None
                else LifecycleState.STOPPED
            )

        if first_error is not None:
            raise first_error

    def wait_for_stop(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        return self._stop_event.wait(timeout)

    def reset(self) -> None:
        with self._lock:
            if self._state not in {
                LifecycleState.STOPPED,
                LifecycleState.FAILED,
            }:
                raise RuntimeError(
                    "Lifecycle can only be reset after stopping."
                )

            self._stop_event.clear()
            self._state = LifecycleState.CREATED

    def __enter__(self) -> "Lifecycle":
        self.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.stop()


__all__ = [
    "Lifecycle",
    "LifecycleState",
]