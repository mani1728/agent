# Path: Version 1_0_0/agent/core/worker.py

"""Canonical Agent worker: single orchestrator for the execution pipeline.

Canonical flow (P0/P1):

    poll_messages
    → parse (CommandParser)
    → idempotency check
    → dispatch (Dispatcher with central authorizer)
    → publish response
    → ack / nack per Ack Policy Matrix

Design notes
------------
- The worker is the ONLY component allowed to call ``transport.ack``
  and ``transport.nack``. No one else should move offsets.
- The worker never calls ``transport.ack`` unless the response has
  been successfully published (or the command is a safe duplicate).
- Parsing lives in ``CommandParser`` (core), not in the transport.
- Authorization is enforced by the ``Dispatcher`` (via ``require``).
- The worker classifies exceptions and applies the Ack Policy Matrix
  defined below.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.core.command_parser import CommandParser
from agent.core.dispatcher import (
    Dispatcher,
    UnauthorizedCommandError,
)
from agent.reliability.backoff import BackoffConfig, ExponentialBackoff
from agent.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from agent.reliability.idempotency import (
    IdempotencyError,
    IdempotencyManager,
    IdempotencyState,
    IdempotencyStore,
    fingerprint_payload,
)
from agent.reliability.retry import (
    RetryConfig,
    RetryExecutor,
    RetryPolicy,
)
from agent.transport.base import AckToken, ITransportClient, TransportMessage
from agent.core.exceptions import (
    ValidationError,
    RetryableExternalError,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Exceptions
# ======================================================================

class WorkerError(Exception):
    """Base exception for worker-related failures."""


class ValidationError(WorkerError):
    """Raised when a transport message cannot be parsed into a command.

    Permanent failure. Must NOT be retried.
    """


class RetryableExternalError(WorkerError):
    """Marker for transient external failures (network, broker, adapter).

    Retryable. Must NOT commit the offset until successful.
    """


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


# ======================================================================
# Ack Policy Matrix
# ======================================================================

# Canonical failure classification and the corresponding ack/nack action.
#
#   classification               | action                    | commit?
#   -----------------------------|---------------------------|---------
#   success                      | ack(status=SUCCESS)       | yes
#   duplicate (idempotency hit)  | ack(status=DUPLICATE)     | yes
#   authorization failure        | nack(retryable=False)     | yes (DLQ)
#   validation failure           | nack(retryable=False)     | yes (DLQ)
#   malformed payload            | nack(retryable=False)     | yes (DLQ)
#   transient external failure   | nack(retryable=True)      | no
#   unknown failure              | per config                | per config
#
# "commit" here means "advance the offset", which for the Kafka
# transport is performed by ``transport.ack`` and NOT by
# ``transport.nack`` for retryable failures.
#
# Non-retryable failures that MUST be committed (to avoid endless
# redelivery) rely on the transport's DLQ hook (see transport.nack).


# ======================================================================
# Worker
# ======================================================================

class AgentWorker:
    """Transport-agnostic Agent Worker with runtime reliability hooks."""

    _DEFAULT_RELIABILITY: dict[str, Any] = {
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
            RetryableExternalError,
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
        "ack_on_unknown_error": False,
    }

    _DEFAULT_TRANSIENT_COMMAND_EXCEPTIONS: tuple[type[BaseException], ...] = (
        RetryableExternalError,
        TimeoutError,
        ConnectionError,
        OSError,
    )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        dispatcher: Dispatcher,
        transport: ITransportClient | None = None,
        *,
        parser: CommandParser | None = None,
        poll_timeout_sec: float = 1.0,
        poll_max_records: int = 1,
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
        if not isinstance(dispatcher, Dispatcher):
            raise TypeError(
                "dispatcher must be a Dispatcher instance."
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

        if poll_max_records <= 0:
            raise ValueError(
                "poll_max_records must be greater than zero."
            )

        self._dispatcher = dispatcher
        self._transport = transport
        self._parser = parser or CommandParser()

        self._poll_timeout_sec = float(poll_timeout_sec)
        self._poll_timeout_ms = int(self._poll_timeout_sec * 1000)
        self._poll_max_records = int(poll_max_records)

        self._on_start = on_start
        self._on_stop = on_stop

        # --------------------------------------------------------------
        # Reliability config
        # --------------------------------------------------------------
        self._reliability_config = self._normalize_reliability_config(
            reliability_config or {}
        )

        self._ack_on_unknown_error = bool(
            self._reliability_config.get("ack_on_unknown_error", False)
        )

        # --------------------------------------------------------------
        # Retry executors
        # --------------------------------------------------------------
        self._retry_executor = (
            retry_executor
            if retry_executor is not None
            else self._build_retry_executor(
                section=self._reliability_section("command_retry"),
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
                section=self._reliability_section("delivery_retry"),
                retry_exceptions=self._resolve_retry_exceptions(
                    self._reliability_config.get(
                        "delivery_retry_exceptions",
                        (_TransientDeliveryError,),
                    ),
                    default=(_TransientDeliveryError,),
                ),
            )
        )

        # --------------------------------------------------------------
        # Idempotency
        # --------------------------------------------------------------
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

        # --------------------------------------------------------------
        # Circuit breaker
        # --------------------------------------------------------------
        self._circuit_breaker = (
            circuit_breaker
            if circuit_breaker is not None
            else self._build_circuit_breaker()
        )

        # --------------------------------------------------------------
        # Lifecycle state
        # --------------------------------------------------------------
        self._state = WorkerState.CREATED
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher

    @property
    def transport(self) -> ITransportClient | None:
        return self._transport

    @property
    def parser(self) -> CommandParser:
        return self._parser

    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    @property
    def is_running(self) -> bool:
        return self.state == WorkerState.RUNNING

    @property
    def is_stopping(self) -> bool:
        return self.state == WorkerState.STOPPING

    @property
    def is_stopped(self) -> bool:
        return self.state == WorkerState.STOPPED

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
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

    def execute_one_command(self) -> bool:
        """Poll one message, parse, dispatch, and apply Ack Policy.

        Returns
        -------
        bool
            True if a message was processed (whether it was acked or
            nacked), False if the poll returned no messages or the
            worker is stopping.
        """
        if not self.is_running:
            raise WorkerError("Worker is not running.")

        if self._transport is None:
            raise WorkerError("Worker has no transport configured.")

        # --------------------------------------------------------------
        # 1. Poll
        # --------------------------------------------------------------
        try:
            messages = self._transport.poll_messages(
                timeout_ms=self._poll_timeout_ms,
                max_records=self._poll_max_records,
            )
        except Exception:
            logger.exception("Transport poll failed; continuing loop")
            return False

        if not messages:
            return False

        # Process the first message only (execute_one semantics).
        # Batch semantics: caller may loop calling execute_one_command.
        msg: TransportMessage = messages[0]
        token: AckToken | None = msg.ack_token

        if token is None:
            logger.error(
                "Transport message has no AckToken; cannot ack/nack safely"
            )
            return False

        # --------------------------------------------------------------
        # 2. Parse
        # --------------------------------------------------------------
        try:
            commands = self._parser.parse(msg)
        except Exception as exc:
            self._handle_validation_failure(token, exc)
            return True

        if not commands:
            # Empty payload normalized to no commands: treat as
            # malformed but non-retryable.
            self._handle_validation_failure(
                token,
                ValueError("Transport message produced no commands"),
            )
            return True

        # --------------------------------------------------------------
        # 3. Process each parsed command (usually one)
        # --------------------------------------------------------------
        for command in commands:
            try:
                handled = self._process_one_command(command, token)
            except _WorkerStopRequested:
                logger.debug("Worker stop requested during command processing")
                return True

            if not handled:
                # The command was nacked retryable: stop processing this
                # record to avoid double-acking siblings.
                return True

        return True

    def run_once(self) -> int:
        """Poll once and process every message returned by that poll."""
        if not self.is_running:
            raise WorkerError("Worker is not running.")

        if self._transport is None:
            raise WorkerError("Worker has no transport configured.")

        try:
            messages = self._transport.poll_messages(
                timeout_ms=self._poll_timeout_ms,
                max_records=self._poll_max_records,
            )
        except Exception:
            logger.exception("Transport poll failed; continuing loop")
            return 0

        count = 0
        for msg in messages:
            count += 1
            try:
                self._process_message(msg)
            except _WorkerStopRequested:
                logger.debug("Worker stop requested while processing message")
                break
            except Exception:
                logger.exception(
                    "Unexpected message processing error; continuing loop"
                )

        return count

    def run(self) -> None:
        """Run the polling loop until stop is requested."""
        if not self.is_running:
            self.start()

        try:
            while not self._stop_event.is_set():
                self.execute_one_command()
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_message(self, msg: TransportMessage) -> None:
        """Parse and process all commands in a single transport message."""
        token = msg.ack_token
        if token is None:
            logger.error(
                "Transport message has no AckToken; cannot ack/nack safely"
            )
            return

        try:
            commands = self._parser.parse(msg)
        except Exception as exc:
            self._handle_validation_failure(token, exc)
            return

        if not commands:
            self._handle_validation_failure(
                token,
                ValueError("Transport message produced no commands"),
            )
            return

        for command in commands:
            self._process_one_command(command, token)

    def _process_one_command(
        self,
        command: CommandEnvelope,
        token: AckToken,
    ) -> bool:
        """Execute one command and apply the Ack Policy Matrix.

        Returns
        -------
        bool
            True if the message was acked or nacked (final), False if
            the message should not be further processed (e.g. transient
            nack: caller should stop and let it redeliver).
        """
        # --------------------------------------------------------------
        # 1. Idempotency check
        # --------------------------------------------------------------
        try:
            duplicate_outcome = self._check_idempotency(command)
        except _WorkerStopRequested:
            raise
        except Exception:
            logger.exception(
                "Idempotency check failed: command_id=%s",
                command.command_id,
            )
            self._nack_retryable(token, "idempotency check failure")
            return False

        if duplicate_outcome is not None:
            cached_response, was_in_progress = duplicate_outcome

            if was_in_progress:
                # Duplicate is currently executing elsewhere: do NOT
                # commit; let it redeliver.
                self._nack_retryable(
                    token, "duplicate command is in progress"
                )
                return False

            # Completed duplicate: publish cached response, then ack.
            if not self._publish_with_retry(
                response=cached_response,
                command_id=command.command_id,
            ):
                self._nack_retryable(
                    token, "failed to publish cached response"
                )
                return False

            self._ack(token, status="DUPLICATE")
            return True

        # --------------------------------------------------------------
        # 2. Dispatch (authorizer runs inside dispatcher)
        # --------------------------------------------------------------
        try:
            response = self._execute_with_retry(command)
        except UnauthorizedCommandError as exc:
            self._nack_non_retryable(token, str(exc))
            return True
        except ValidationError as exc:
            self._nack_non_retryable(token, str(exc))
            return True
        except RetryableExternalError as exc:
            self._nack_retryable(token, str(exc))
            return False
        except _WorkerStopRequested:
            raise
        except Exception as exc:
            self._handle_unknown_failure(token, exc)
            return True

        # --------------------------------------------------------------
        # 3. Mark idempotency complete
        # --------------------------------------------------------------
        try:
            self._idempotency_manager.complete(
                command.command_id,
                result=response,
            )
        except Exception:
            logger.exception(
                "Failed to record successful outcome: command_id=%s",
                command.command_id,
            )
            # We already have a valid response; do not lose it. The
            # idempotency store will treat the next redelivery as
            # unknown, which is safe (idempotent replay).
            self._nack_retryable(
                token, "idempotency store write failure"
            )
            return False

        # --------------------------------------------------------------
        # 4. Publish response
        # --------------------------------------------------------------
        if not self._publish_with_retry(
            response=response,
            command_id=command.command_id,
        ):
            self._nack_retryable(
                token, "response publish failed"
            )
            return False

        # --------------------------------------------------------------
        # 5. Ack
        # --------------------------------------------------------------
        self._ack(token, status="SUCCESS")
        return True

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _check_idempotency(
        self,
        command: CommandEnvelope,
    ) -> Optional[tuple[ResponseEnvelope, bool]]:
        """Return (cached_response, was_in_progress) or None if new."""
        key = command.command_id
        fingerprint = fingerprint_payload(command.to_dict())

        while True:
            try:
                result = self._idempotency_manager.store.begin(
                    key,
                    fingerprint=fingerprint,
                )
            except IdempotencyError:
                cached = self._idempotency_manager.get(key)
                if cached is None:
                    raise WorkerError(
                        "idempotency slot is not recoverable"
                    )
            else:
                if result.accepted:
                    return None
                cached = result.record

            if cached.state == IdempotencyState.IN_PROGRESS:
                return (
                    ResponseEnvelope.error(
                        correlation_id=command.correlation_id,
                        error_code="COMMAND_IN_PROGRESS",
                        error_message=(
                            "Duplicate command is currently being executed."
                        ),
                    ),
                    True,
                )

            if cached.state == IdempotencyState.COMPLETED:
                cached_result = cached.result
                if isinstance(cached_result, ResponseEnvelope):
                    return cached_result, False
                return (
                    ResponseEnvelope.error(
                        correlation_id=command.correlation_id,
                        error_code="COMMAND_IDEMPOTENCY_INVALID_STATE",
                        error_message=(
                            "Completed command has no cached response."
                        ),
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

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_with_retry(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """Execute with bounded retry, respecting the circuit breaker."""

        def execute_once() -> ResponseEnvelope:
            if self._circuit_breaker is None:
                return self._dispatcher.dispatch(command)
            return self._circuit_breaker.execute(
                self._dispatcher.dispatch,
                command,
            )

        try:
            result = self._retry_executor.execute(execute_once)
        except Exception as exc:
            self._handle_execution_failure(command.command_id, exc)
            raise

        return result.result

    def _handle_execution_failure(
        self,
        command_id: str,
        exc: BaseException,
    ) -> None:
        """Record a failed execution in the idempotency store."""
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
                "Failed to clear idempotency state after failure: command_id=%s",
                command_id,
                exc_info=True,
            )

    @staticmethod
    def _unwrap_retry_failure(exc: BaseException) -> BaseException:
        """Return the terminal cause if a retry wrapper nests one."""
        nested = getattr(exc, "last_exception", None)
        if isinstance(nested, BaseException):
            return nested
        return exc

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def _publish_with_retry(
        self,
        *,
        response: ResponseEnvelope,
        command_id: str,
    ) -> bool:
        """Publish a response with bounded delivery retry."""

        def send_once() -> bool:
            if self._transport is None:
                raise _TransientDeliveryError(
                    "Transport is unavailable."
                )

            try:
                accepted = bool(
                    self._transport.send_response(response)
                )
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
            result = self._delivery_retry_executor.execute(send_once)
        except _WorkerStopRequested:
            raise
        except Exception:
            logger.debug(
                "Response publish retries exhausted: command_id=%s",
                command_id,
            )
            return False

        return bool(result.result)

    # ------------------------------------------------------------------
    # Ack Policy Matrix — final actions
    # ------------------------------------------------------------------

    def _ack(self, token: AckToken, *, status: str = "SUCCESS") -> None:
        """Commit the offset. Safe to call only after response publish."""
        if self._transport is None:
            logger.error("Cannot ack: transport is unavailable")
            return

        try:
            self._transport.ack(token, status=status)
        except Exception:
            logger.exception(
                "Transport ack failed: command_id=%s status=%s",
                token.command_id,
                status,
            )

    def _nack_retryable(self, token: AckToken, reason: str) -> None:
        """Transient failure: do NOT commit; allow redelivery."""
        if self._transport is None:
            logger.error("Cannot nack: transport is unavailable")
            return

        try:
            self._transport.nack(token, reason=reason, retryable=True)
        except Exception:
            logger.exception(
                "Transport retryable-nack failed: command_id=%s",
                token.command_id,
            )

    def _nack_non_retryable(self, token: AckToken, reason: str) -> None:
        """Permanent failure: nack non-retryable (transport may DLQ)."""
        if self._transport is None:
            logger.error("Cannot nack: transport is unavailable")
            return

        try:
            self._transport.nack(token, reason=reason, retryable=False)
        except Exception:
            logger.exception(
                "Transport non-retryable-nack failed: command_id=%s",
                token.command_id,
            )

    def _handle_validation_failure(
        self,
        token: AckToken,
        exc: BaseException,
    ) -> None:
        """Malformed payload: non-retryable nack (transport may DLQ).

        Never logs the raw payload; only the error type and a short
        reason are surfaced.
        """
        reason = f"validation failure: {type(exc).__name__}"
        logger.warning(
            "Malformed transport message: command_id=%s reason=%s",
            token.command_id,
            reason,
        )
        self._nack_non_retryable(token, reason)

    def _handle_unknown_failure(
        self,
        token: AckToken,
        exc: BaseException,
    ) -> None:
        """Unknown failure: apply config-driven ack policy."""
        logger.exception(
            "Unknown command failure: command_id=%s",
            token.command_id,
        )

        reason = f"unknown failure: {type(exc).__name__}"

        if self._ack_on_unknown_error:
            self._nack_non_retryable(token, reason)
        else:
            self._nack_retryable(token, reason)

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
            "ack_on_unknown_error": bool(
                AgentWorker._DEFAULT_RELIABILITY["