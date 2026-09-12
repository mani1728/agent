# Path: Version 1_0_0/agent/core/worker.py

"""Canonical Agent worker lifecycle and execution pipeline."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.core.command_executor import CommandExecutor
from agent.reliability.backoff import BackoffConfig, ExponentialBackoff
from agent.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from agent.reliability.idempotency import (
    IdempotencyError,
    IdempotencyStore,
    IdempotencyManager,
    IdempotencyState,
    fingerprint_payload,
)
from agent.reliability.retry import (
    RetryConfig,
    RetryExecutor,
    RetryPolicy,
)
from agent.transport.base import AckToken, ITransportClient


logger = logging.getLogger(__name__)


class WorkerError(Exception):
    """Base exception for worker-related failures."""


class WorkerState:
    """Worker lifecycle states."""

    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class _WorkerStopRequested(WorkerError):
    """Raised when stop is requested during retry/backoff."""


class _TransientDeliveryError(WorkerError):
    """Marker for retryable transport delivery failures."""


class AgentWorker:
    """
    Transport-agnostic Agent Worker with runtime reliability hooks.

    Canonical flow:
        poll -> execute -> publish response -> ack
    """

    _DEFAULT_RELIABILITY = {
        "command_retry": {
            "max_attempts": 3,
            "base_delay_seconds": 0.05,
            "max_delay_seconds": 1.0,
            "multiplier": 2.0,
            "jitter_ratio": 0.0,
        },
        "delivery_retry": {
            "max_attempts": 3,
            "base_delay_seconds": 0.05,
            "max_delay_seconds": 1.0,
            "multiplier": 2.0,
            "jitter_ratio": 0.0,
        },
        "command_retry_exceptions": (
            TimeoutError,
            ConnectionError,
            OSError,
        ),
        "delivery_retry_exceptions": (
            _TransientDeliveryError,
        ),
        "circuit_breaker": {
            "enabled": False,
            "failure_threshold": 5,
            "recovery_timeout_seconds": 30.0,
            "success_threshold": 1,
        },
    }

    _DEFAULT_TRANSIENT_COMMAND_EXCEPTIONS: tuple[type[BaseException], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    )

    def __init__(
        self,
        command_executor: CommandExecutor,
        transport: ITransportClient | None = None,
        *,
        poll_timeout_sec: float = 1.0,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        reliability_config: Optional[Mapping[str, Any]] = None,
        retry_executor: RetryExecutor | None = None,
        delivery_retry_executor: RetryExecutor | None = None,
        idempotency_store: IdempotencyStore | None = None,
        idempotency_manager: IdempotencyManager | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        close_idempotency_store: bool = False,
    ) -> None:
        if not isinstance(command_executor, CommandExecutor):
            raise TypeError(
                "command_executor must be a CommandExecutor instance."
            )

        if transport is not None and not isinstance(
            transport,
            ITransportClient,
        ):
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

        self._reliability_config = self._normalize_reliability_config(
            reliability_config or {}
        )

        self._retry_executor = (
            retry_executor
            if retry_executor is not None
            else self._build_retry_executor(
                section=self._reliability_section(
                    "command_retry"
                ),
                retry_exceptions=self._resolve_retry_exceptions(
                    self._reliability_config.get(
                        "command_retry_exceptions",
                        self._DEFAULT_TRANSIENT_COMMAND_EXCEPTIONS,
                    ),
                    default=self._DEFAULT_TRANSIENT_COMMAND_EXCEPTIONS,
                ),
            )
        )

        self._delivery_retry_executor = (
            delivery_retry_executor
            if delivery_retry_executor is not None
            else self._build_retry_executor(
                section=self._reliability_section(
                    "delivery_retry"
                ),
                retry_exceptions=self._resolve_retry_exceptions(
                    self._reliability_config.get(
                        "delivery_retry_exceptions",
                        (_TransientDeliveryError,),
                    ),
                    default=(_TransientDeliveryError,),
                ),
            )
        )

        self._idempotency_manager = (
            idempotency_manager
            if idempotency_manager is not None
            else IdempotencyManager(store=idempotency_store)
        )
        self._idempotency_store = (
            idempotency_manager.store
            if idempotency_manager is not None
            else idempotency_store
        )
        self._close_idempotency_store = (
            close_idempotency_store
            and self._idempotency_store is not None
            and idempotency_manager is None
        )

        self._circuit_breaker = circuit_breaker or self._build_circuit_breaker()

        self._state = WorkerState.CREATED
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()

    @property
    def command_executor(self) -> CommandExecutor:
        """Return the configured command executor."""

        return self._command_executor

    @property
    def transport(self) -> ITransportClient | None:
        """Return the configured transport, if any."""

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
        """Return True when stopping."""

        return self.state == WorkerState.STOPPING

    @property
    def is_stopped(self) -> bool:
        """Return True when stopped."""

        return self.state == WorkerState.STOPPED

    @property
    def stop_event(self) -> threading.Event:
        """Return the worker stop event."""

        return self._stop_event

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start worker lifecycle."""

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
            raise WorkerError("Worker startup failed.") from exc

        with self._state_lock:
            self._state = WorkerState.RUNNING

        logger.info("Agent worker started")

    def stop(self) -> None:
        """Request worker shutdown."""

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

        self._close_persistence_if_needed()

        logger.info("Agent worker stopped")

    def _close_persistence_if_needed(self) -> None:
        if not self._close_idempotency_store:
            return

        store = self._idempotency_store

        if store is None:
            return

        close_method = getattr(store, "close", None)

        if callable(close_method):
            try:
                close_method()
            except Exception:
                logger.debug(
                    "Failed to close idempotency store.",
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Main loop
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
            except _WorkerStopRequested:
                logger.debug(
                    "Worker stop requested while processing command"
                )
                break
            except Exception:
                logger.exception(
                    "Unexpected command processing error; continuing worker loop"
                )

        return len(commands)

    def run(self) -> None:
        """Run the polling loop until stop is requested."""
        if not self.is_running:
            self.start()

        try:
            while not self._stop_event.is_set():
                self.run_once()
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """Execute a command through the configured CommandExecutor."""

        if not isinstance(command, CommandEnvelope):
            raise TypeError("execute() expects a CommandEnvelope instance.")

        if not self.is_running:
            raise WorkerError("Worker is not running.")

        return self._command_executor.execute(command)

    def execute_raw(self, command: CommandEnvelope) -> ResponseEnvelope:
        """Compatibility wrapper."""

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
            response, allow_ack = self._process_command_outcome(command)
        except _WorkerStopRequested:
            raise
        except Exception:
            execution_failed = True
            allow_ack = False
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
                and self._publish_with_retry(
                    response=response,
                    command_id=command.command_id,
                )
            )
        except _WorkerStopRequested:
            return
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

        if execution_failed or not allow_ack:
            if execution_failed:
                logger.warning(
                    "Command execution failed; response published but command will not be acknowledged: command_id=%s",
                    command.command_id,
                )
            return

        try:
            if self._transport is not None:
                ack_token = AckToken(
                    command_id=command.command_id,
                    ref=getattr(command, "transport_ref", None),
                )
                self._transport.ack_command(
                    command.command_id,
                    ack_token=ack_token,
                )
        except Exception:
            logger.exception(
                "Command acknowledgement failed: command_id=%s",
                command.command_id,
            )

    def _process_command_outcome(
        self,
        command: CommandEnvelope,
    ) -> tuple[ResponseEnvelope, bool]:
        """
        Return response and whether transport ack is allowed.
        """
        key = command.command_id
        fingerprint = fingerprint_payload(command.to_dict())

        replay = self._acquire_idempotent_outcome(
            key=key,
            fingerprint=fingerprint,
            command=command,
        )

        if replay is not None:
            return replay

        def execute_once() -> ResponseEnvelope:
            return self._execute_command(command)

        try:
            result = self._retry_executor.execute(
                execute_once,
            )
            response = result.result
        except Exception as exc:
            self._handle_execution_failure(key, exc)
            raise

        self._idempotency_manager.complete(
            key,
            result=response,
        )
        return response, True

    @staticmethod
    def _unwrap_retry_failure(exc: BaseException) -> BaseException:
        """
        Convert retry-wrapper errors into their terminal cause when available.

        RetryExecutor wraps only after final failed attempt, while other
        wrappers (such as custom transports) may nest exceptions.
        """
        candidate = exc

        if hasattr(candidate, "last_exception"):
            nested = getattr(candidate, "last_exception")

            if isinstance(nested, BaseException):
                return nested

        return candidate

    def _execute_command(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        if self._circuit_breaker is None:
            return self._command_executor.execute(command)

        return self._circuit_breaker.execute(
            self._command_executor.execute,
            command,
        )

    def _handle_execution_failure(
        self,
        command_id: str,
        exc: BaseException,
    ) -> None:
        cause = self._unwrap_retry_failure(exc)

        try:
            self._idempotency_manager.fail(
                command_id,
                error=str(cause),
            )
        except Exception:
            logger.debug(
                "Failed to mark idempotency failure: command_id=%s",
                command_id,
                exc_info=True,
            )

        try:
            self._idempotency_manager.remove(command_id)
        except Exception:
            logger.debug(
                "Failed to clear idempotency state after execution failure: command_id=%s",
                command_id,
                exc_info=True,
            )

    def _acquire_idempotent_outcome(
        self,
        *,
        key: str,
        fingerprint: str,
        command: CommandEnvelope,
    ) -> tuple[ResponseEnvelope, bool] | None:
        while True:
            try:
                result = self._idempotency_manager.store.begin(
                    key,
                    fingerprint=fingerprint,
                )

                if result.accepted:
                    return None

                cached = result.record

            except IdempotencyError:
                cached = self._idempotency_manager.get(key)

                if cached is None:
                    raise WorkerError(
                        "idempotency slot is not recoverable"
                    )

            if cached.state == IdempotencyState.IN_PROGRESS:
                return (
                    ResponseEnvelope.error(
                        correlation_id=command.correlation_id,
                        error_code="COMMAND_IN_PROGRESS",
                        error_message="Duplicate command is currently being executed.",
                    ),
                    False,
                )

            if cached.state == IdempotencyState.COMPLETED:
                cached_result = cached.result

                if isinstance(cached_result, ResponseEnvelope):
                    return cached_result, True

                return (
                    ResponseEnvelope.error(
                        correlation_id=command.correlation_id,
                        error_code="COMMAND_IDEMPOTENCY_INVALID_STATE",
                        error_message="Completed command has no cached response.",
                    ),
                    False,
                )

            if cached.state == IdempotencyState.FAILED:
                removed = self._idempotency_manager.remove(key)

                if removed:
                    continue

                raise WorkerError(
                    "failed command can no longer be retried"
                )

            raise WorkerError(
                f"Unknown idempotency state for command_id={key!r}"
            )

    def _publish_with_retry(
        self,
        *,
        response: ResponseEnvelope,
        command_id: str,
    ) -> bool:
        def send_once() -> bool:
            if self._transport is None:
                raise _TransientDeliveryError("Transport is unavailable.")

            try:
                accepted = bool(self._transport.send_response(response))
            except _TransientDeliveryError:
                raise
            except Exception as exc:
                raise _TransientDeliveryError(
                    "Transport response send failed."
                ) from exc

            if not accepted:
                raise _TransientDeliveryError(
                    "Transport response publish returned False."
                )

            return True

        try:
            result = self._delivery_retry_executor.execute(
                send_once,
            )
        except Exception as exc:
            if isinstance(exc, _WorkerStopRequested):
                raise

            logger.debug(
                "Response publish retries exhausted: command_id=%s",
                command_id,
            )
            return False

        return bool(result.result)

    # ------------------------------------------------------------------
    # Reliability helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_reliability_config(
        raw: Optional[Mapping[str, Any]],
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "command_retry": dict(
                AgentWorker._DEFAULT_RELIABILITY["command_retry"]
            ),
            "delivery_retry": dict(
                AgentWorker._DEFAULT_RELIABILITY["delivery_retry"]
            ),
            "circuit_breaker": dict(
                AgentWorker._DEFAULT_RELIABILITY["circuit_breaker"]
            ),
        }

        if raw is None:
            return config

        for key, value in raw.items():
            if key in (
                "command_retry",
                "delivery_retry",
                "circuit_breaker",
            ) and isinstance(value, Mapping):
                section = config.setdefault(key, {})
                section.update(dict(value))
                continue

            config[key] = value

        return config

    def _reliability_section(
        self,
        name: str,
    ) -> Mapping[str, Any]:
        section = self._reliability_config.get(name)
        return section if isinstance(section, Mapping) else {}

    def _resolve_retry_exceptions(
        self,
        value: Any,
        *,
        default: tuple[type[BaseException], ...],
    ) -> tuple[type[BaseException], ...]:
        if value is None:
            return default

        if isinstance(value, tuple):
            candidates = value
        elif isinstance(value, list):
            candidates = tuple(value)
        else:
            candidates = (value,)

        resolved: list[type[BaseException]] = [
            exception_type
            for exception_type in candidates
            if isinstance(exception_type, type)
            and issubclass(exception_type, BaseException)
        ]

        return tuple(resolved) if resolved else default

    @staticmethod
    def _coerce_int(
        value: Any,
        *,
        default: int,
        minimum: int,
    ) -> int:
        try:
            value_int = int(value)
        except Exception:
            return default

        if value_int < minimum:
            return minimum

        return value_int

    @staticmethod
    def _coerce_float(
        value: Any,
        *,
        default: float,
        minimum: float,
        maximum: Optional[float] = None,
    ) -> float:
        try:
            value_float = float(value)
        except Exception:
            return default

        if value_float < minimum:
            return minimum

        if maximum is not None and value_float > maximum:
            return float(maximum)

        return float(value_float)

    def _build_retry_executor(
        self,
        *,
        section: Mapping[str, Any],
        retry_exceptions: tuple[type[BaseException], ...],
    ) -> RetryExecutor:
        return RetryExecutor(
            policy=RetryPolicy(
                config=RetryConfig(
                    max_attempts=self._coerce_int(
                        section.get("max_attempts", 3),
                        default=3,
                        minimum=1,
                    ),
                    retry_exceptions=retry_exceptions,
                ),
                backoff=ExponentialBackoff(
                    BackoffConfig(
                        base_delay_seconds=self._coerce_float(
                            section.get("base_delay_seconds", 0.05),
                            default=0.05,
                            minimum=0.0,
                        ),
                        max_delay_seconds=self._coerce_float(
                            section.get("max_delay_seconds", 1.0),
                            default=1.0,
                            minimum=0.0,
                        ),
                        multiplier=self._coerce_float(
                            section.get("multiplier", 2.0),
                            default=2.0,
                            minimum=1.0,
                        ),
                        jitter_ratio=self._coerce_float(
                            section.get("jitter_ratio", 0.0),
                            default=0.0,
                            minimum=0.0,
                            maximum=1.0,
                        ),
                    )
                ),
            ),
            sleep_fn=self._stop_aware_sleep,
        )

    def _build_circuit_breaker(self) -> Optional[CircuitBreaker]:
        section = self._reliability_section("circuit_breaker")

        if not bool(section.get("enabled", False)):
            return None

        try:
            return CircuitBreaker(
                config=CircuitBreakerConfig(
                    failure_threshold=self._coerce_int(
                        section.get("failure_threshold", 5),
                        default=5,
                        minimum=1,
                    ),
                    recovery_timeout_seconds=self._coerce_float(
                        section.get(
                            "recovery_timeout_seconds",
                            30.0,
                        ),
                        default=30.0,
                        minimum=0.0,
                    ),
                    success_threshold=self._coerce_int(
                        section.get("success_threshold", 1),
                        default=1,
                        minimum=1,
                    ),
                )
            )
        except Exception:
            logger.exception("Failed to build circuit breaker")
            return None

    def _stop_aware_sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return

        if self._stop_event.wait(seconds):
            raise _WorkerStopRequested(
                "Worker shutdown requested."
            )

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def wait_for_stop(self, timeout: float | None = None) -> bool:
        """Wait until stop has been requested."""

        return self._stop_event.wait(timeout)

    def request_stop(self) -> None:
        """Request shutdown without extra lifecycle actions."""

        self._stop_event.set()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "AgentWorker":
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
