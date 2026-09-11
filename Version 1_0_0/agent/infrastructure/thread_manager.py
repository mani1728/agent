# Path: Version 1_0_0/agent/infrastructure/thread_manager.py

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


logger = logging.getLogger(__name__)


@dataclass
class ManagedThread:
    name: str
    thread: threading.Thread
    daemon: bool = True

    @property
    def is_alive(self) -> bool:
        return self.thread.is_alive()


class ThreadManager:
    """
    Lightweight lifecycle manager for application threads.

    Responsibilities:
    - Create and track named threads.
    - Start individual or all managed threads.
    - Request cooperative shutdown through a shared Event.
    - Join threads with a bounded timeout.
    - Remove finished threads from the registry.

    This class does not forcibly terminate threads. Python threads must
    cooperate with shutdown through events or their own lifecycle logic.
    """

    def __init__(
        self,
        *,
        shutdown_event: Optional[threading.Event] = None,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._shutdown_event = shutdown_event or threading.Event()
        self._logger = logger_ or logger

        self._lock = threading.RLock()
        self._threads: dict[str, ManagedThread] = {}

    @property
    def shutdown_event(self) -> threading.Event:
        return self._shutdown_event

    def create(
        self,
        name: str,
        target: Callable[..., object],
        *,
        args: Iterable[object] = (),
        kwargs: Optional[dict[str, object]] = None,
        daemon: bool = True,
        start: bool = False,
    ) -> threading.Thread:
        if not name or not name.strip():
            raise ValueError("Thread name cannot be empty.")

        if not callable(target):
            raise TypeError("target must be callable.")

        with self._lock:
            existing = self._threads.get(name)
            if existing is not None and existing.is_alive:
                raise ValueError(f"Thread '{name}' is already running.")

            thread = threading.Thread(
                name=name,
                target=target,
                args=tuple(args),
                kwargs=dict(kwargs or {}),
                daemon=daemon,
            )

            self._threads[name] = ManagedThread(
                name=name,
                thread=thread,
                daemon=daemon,
            )

        if start:
            thread.start()

        return thread

    def start(self, name: str) -> None:
        with self._lock:
            managed = self._threads.get(name)

        if managed is None:
            raise KeyError(f"Unknown managed thread: {name}")

        if managed.thread.is_alive():
            return

        managed.thread.start()

    def start_all(self) -> None:
        with self._lock:
            names = list(self._threads.keys())

        for name in names:
            self.start(name)

    def request_shutdown(self) -> None:
        self._shutdown_event.set()

    def clear_shutdown(self) -> None:
        self._shutdown_event.clear()

    def stop(
        self,
        name: str,
        *,
        timeout: Optional[float] = None,
    ) -> bool:
        with self._lock:
            managed = self._threads.get(name)

        if managed is None:
            return True

        thread = managed.thread

        if not thread.is_alive():
            self.remove(name)
            return True

        thread.join(timeout=timeout)

        if thread.is_alive():
            return False

        self.remove(name)
        return True

    def stop_all(
        self,
        *,
        timeout: Optional[float] = None,
    ) -> bool:
        self.request_shutdown()

        with self._lock:
            names = list(self._threads.keys())

        all_stopped = True

        for name in names:
            if not self.stop(name, timeout=timeout):
                all_stopped = False
                self._logger.warning(
                    "Managed thread did not stop within timeout: %s",
                    name,
                )

        return all_stopped

    def join(
        self,
        name: str,
        *,
        timeout: Optional[float] = None,
    ) -> bool:
        with self._lock:
            managed = self._threads.get(name)

        if managed is None:
            return True

        managed.thread.join(timeout=timeout)
        return not managed.thread.is_alive()

    def join_all(
        self,
        *,
        timeout: Optional[float] = None,
    ) -> bool:
        with self._lock:
            threads = list(self._threads.values())

        all_finished = True

        for managed in threads:
            managed.thread.join(timeout=timeout)

            if managed.thread.is_alive():
                all_finished = False

        return all_finished

    def is_alive(self, name: str) -> bool:
        with self._lock:
            managed = self._threads.get(name)

        return managed is not None and managed.thread.is_alive()

    def get(self, name: str) -> Optional[threading.Thread]:
        with self._lock:
            managed = self._threads.get(name)

        return managed.thread if managed is not None else None

    def names(self) -> list[str]:
        with self._lock:
            return list(self._threads.keys())

    def active_names(self) -> list[str]:
        with self._lock:
            return [
                name
                for name, managed in self._threads.items()
                if managed.thread.is_alive()
            ]

    def remove(self, name: str) -> bool:
        with self._lock:
            managed = self._threads.get(name)

            if managed is None:
                return False

            if managed.thread.is_alive():
                raise RuntimeError(
                    f"Cannot remove active thread: {name}"
                )

            del self._threads[name]
            return True

    def cleanup_finished(self) -> int:
        removed = 0

        with self._lock:
            finished = [
                name
                for name, managed in self._threads.items()
                if not managed.thread.is_alive()
            ]

            for name in finished:
                del self._threads[name]
                removed += 1

        return removed

    def __enter__(self) -> "ThreadManager":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop_all(timeout=1.0)


__all__ = [
    "ManagedThread",
    "ThreadManager",
]