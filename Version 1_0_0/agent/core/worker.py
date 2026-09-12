# Path: Version 1_0_0/agent/core/worker.py

# -*- coding: utf-8 -*-
"""
worker.py
---------
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

import logging
import threading
from collections.abc import Callable
from typing import Any

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.core.command_executor import CommandExecutor
from agent.transport.base import ITransportClient


logger = logging.getLogger(__name__)


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
    Transport-agnostic Agent Worker.

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

    Command flow is:

        poll -> execute -> send_response -> ack_command

    The worker knows only the ITransportClient interface, never Kafka or HTTP.
    """

    def __init__(
        self,
        command_executor: CommandExecutor,
        transport: ITransportClient | None = None,
        *,
        poll_timeout_sec: float = 1.0,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        if not isinstance(command_executor, CommandExecutor):
            raise TypeError(
                "command_executor must be a CommandExecutor instance."
            )

        if transport is not None and not isinstance(transport, ITransportClient):
            raise TypeError(
                "transport must implement ITransportClient."
            )

        if poll_timeout_sec <= 0:
            raise ValueError(
                "poll_timeout_sec must be greater than zero."
            )

        self._command_executor = command_executor
        self._transport = transport
        self._poll_timeout_sec = float(poll_timeout_sec)

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
    def transport(self) -> ITransportClient | None:
        """Return the configured transport, if the worker owns one."""
        return self._transport

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

        try:
            if self._transport is not None:
                self._transport.start()

            if self._on_start is not None:
                self._on_start()

        except Exception as exc:
            self._stop_event.set()
            raise WorkerError(
                "Worker startup failed."
            ) from exc

        with self._state_lock:
            self._state = WorkerState.RUNNING

        logger.info("Agent worker started")

    def stop(self) -> None:
        """
        Request worker shutdown.

        The final bounded multi-stage shutdown sequence remains a later phase.
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
            if self._transport is not None:
                self._transport.stop()
        except Exception:
            logger.exception("Failed to stop worker transport")
        try:
            if self._on_stop is not None:
                self._on_stop()
        except Exception:
            logger.exception("Worker stop callback failed")
        finally:
            with self._state_lock:
                self._state = WorkerState.STOPPED

        logger.info("Agent worker stopped")

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run_once(self) -> int:
        """Poll once and process every command returned by that poll."""
        if not self.is_running:
            raise WorkerError("Worker is not running.")

        if self._transport is None:
            raise WorkerError("Worker has no transport configured.")

        commands = self._transport.poll_commands(
            timeout_sec=self._poll_timeout_sec,
        )

        for command in commands:
            try:
                self._process_command(command)
            except Exception:
                logger.exception(
                    "Unexpected command processing error; continuing worker loop"
                )

        return len(commands)

    def run(self) -> None:
        """Run the polling loop until a stop is requested."""
        if not self.is_running:
            self.start()

        try:
            while not self._stop_event.is_set():
                self.run_once()
        finally:
            self.stop()

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
    ) -> ResponseEnvelope:
        """
        Compatibility execution entry point.

        In the Phase 1 architecture, CommandExecutor returns the canonical
        ResponseEnvelope. Therefore this method delegates to execute()
        rather than attempting to bypass the response boundary.

        The name is retained temporarily for compatibility with callers
        that may already reference execute_raw().
        """

        return self.execute(command)

    def _process_command(
        self,
        command: CommandEnvelope,
    ) -> None:
        """Execute, publish, then acknowledge one canonical command."""
        if not isinstance(command, CommandEnvelope):
            logger.error("Transport returned a non-CommandEnvelope command")
            return

        execution_failed = False
        try:
            response = self.execute(command)
        except Exception:
            execution_failed = True
            logger.exception(
                "Command execution escaped worker boundary: command_id=%s",
                command.command_id,
            )
            response = ResponseEnvelope.error(
                correlation_id=command.correlation_id,
                error_code="WORKER_EXECUTION_ERROR",
                error_message="Command execution failed.",
                metadata={
                    "target_class": command.target_class,
                    "target_method": command.target_method,
                },
            )

        try:
            sent = bool(
                self._transport
                and self._transport.send_response(response)
            )
        except Exception:
            logger.exception(
                "Response publication failed: command_id=%s",
                command.command_id,
            )
            return

        if not sent:
            logger.error(
                "Response was not accepted by transport: command_id=%s",
                command.command_id,
            )
            return

        if execution_failed:
            logger.warning(
                "Command execution failed; response published but command will not be acknowledged: command_id=%s",
                command.command_id,
            )
            return

        try:
            if self._transport is not None:
                self._transport.ack_command(command.command_id)
        except Exception:
            logger.exception(
                "Command acknowledgement failed: command_id=%s",
                command.command_id,
            )

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
