# Path: Version 1_0_0/agent/core/worker.py
"""
Agent worker lifecycle.

Phase 1 responsibility:
- Provide a small, transport-agnostic worker lifecycle.
- Start and stop the worker safely.
- Expose running/stopping state.
- Provide a single command execution entry point through CommandExecutor.

This is intentionally NOT the final AgentWorker implementation.

Future phases will add:
- transport polling
- priority execution
- command acknowledgement
- heartbeat
- persistence/spooling
- retry/reliability
- graceful shutdown sequencing
- observability
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.core.command_executor import CommandExecutor


class WorkerError(Exception):
    """Base exception for worker-related failures."""


class WorkerState:
    """Worker lifecycle states."""

    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class AgentWorker:
    """
    Minimal transport-independent Agent Worker.

    Phase 1 lifecycle:

        CREATED
           |
         start()
           |
           v
        RUNNING
           |
         stop()
           |
           v
        STOPPING
           |
           v
        STOPPED

    The worker does not know whether commands originate from Kafka,
    HTTP, or another transport.
    """

    def __init__(
        self,
        command_executor: CommandExecutor,
        *,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        if not isinstance(command_executor, CommandExecutor):
            raise TypeError(
                "command_executor must be a CommandExecutor instance."
            )

        self._command_executor = command_executor

        self._on_start = on_start
        self._on_stop = on_stop

        self._state = WorkerState.CREATED

        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def command_executor(self) -> CommandExecutor:
        """Return the configured command executor."""

        return self._command_executor

    @property
    def state(self) -> str:
        """Return the current worker state."""

        with self._state_lock:
            return self._state

    @property
    def is_running(self) -> bool:
        """Return True when the worker is running."""

        return self.state == WorkerState.RUNNING

    @property
    def is_stopping(self) -> bool:
        """Return True when the worker is stopping."""

        return self.state == WorkerState.STOPPING

    @property
    def is_stopped(self) -> bool:
        """Return True when the worker has stopped."""

        return self.state == WorkerState.STOPPED

    @property
    def stop_event(self) -> threading.Event:
        """
        Return the worker stop event.

        Later lifecycle infrastructure can wait on this event instead of
        introducing another shutdown primitive.
        """

        return self._stop_event

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the worker.

        Phase 1 does not start a polling thread yet.
        """

        with self._state_lock:
            if self._state == WorkerState.RUNNING:
                return

            if self._state == WorkerState.STOPPING:
                raise WorkerError(
                    "Worker cannot be started while it is stopping."
                )

            if self._state == WorkerState.STOPPED:
                raise WorkerError(
                    "Worker cannot be restarted after it has stopped."
                )

            self._stop_event.clear()

            if self._on_start is not None:
                self._on_start()

            self._state = WorkerState.RUNNING

    def stop(self) -> None:
        """
        Request worker shutdown.

        The actual bounded graceful shutdown sequence will be introduced
        by the lifecycle/reliability phases.
        """

        with self._state_lock:
            if self._state == WorkerState.STOPPED:
                return

            if self._state == WorkerState.CREATED:
                self._stop_event.set()
                self._state = WorkerState.STOPPED
                return

            if self._state == WorkerState.STOPPING:
                return

            self._state = WorkerState.STOPPING
            self._stop_event.set()

        try:
            if self._on_stop is not None:
                self._on_stop()
        finally:
            with self._state_lock:
                self._state = WorkerState.STOPPED

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """
        Execute a command through the configured CommandExecutor.

        Transport acknowledgement/delivery is deliberately outside
        the worker at this stage.
        """

        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "execute() expects a CommandEnvelope instance."
            )

        if not self.is_running:
            raise WorkerError(
                "Worker is not running."
            )

        return self._command_executor.execute(command)

    def execute_raw(
        self,
        command: CommandEnvelope,
    ) -> Any:
        """
        Execute a command and return the raw target result.

        This is intended for internal callers and tests.
        """

        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "execute_raw() expects a CommandEnvelope instance."
            )

        if not self.is_running:
            raise WorkerError(
                "Worker is not running."
            )

        return self._command_executor.execute_or_raise(command)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def wait_for_stop(
        self,
        timeout: float | None = None,
    ) -> bool:
        """
        Wait until stop has been requested.

        Returns True when the stop event is set, otherwise False on timeout.
        """

        return self._stop_event.wait(timeout)

    def request_stop(self) -> None:
        """
        Request shutdown without performing additional lifecycle work.

        Useful for signal/service-host integration in later phases.
        """

        self._stop_event.set()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> AgentWorker:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.stop()


__all__ = [
    "AgentWorker",
    "WorkerError",
    "WorkerState",
]