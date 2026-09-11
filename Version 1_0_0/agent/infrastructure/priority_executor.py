# Path: Version 1_0_0/agent/infrastructure/priority_executor.py

from __future__ import annotations

import heapq
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionRequest:
    """
    Immutable request submitted to the priority executor.
    """

    task: Callable[[], Any]
    priority: int = 1
    ordering_scope: Optional[str] = None
    ttl_seconds: Optional[float] = None
    deadline: Optional[float] = None
    max_exec_ms: Optional[int] = None
    request_id: Optional[str] = None


@dataclass
class _QueuedTask:
    """
    Internal queue representation.

    Lower effective priority value means higher execution priority.
    """

    sequence: int
    request: ExecutionRequest
    submitted_at: float
    future: Future = field(default_factory=Future)

    def __lt__(self, other: "_QueuedTask") -> bool:
        return (
            self.effective_priority,
            self.sequence,
        ) < (
            other.effective_priority,
            other.sequence,
        )

    @property
    def effective_priority(self) -> int:
        return self.request.priority


class PriorityExecutor:
    """
    Bounded priority executor with cooperative scheduling.

    Supported behavior:
    - Priority levels.
    - Aging toward higher priority.
    - Queue size limit.
    - Reserved slots for low-priority work.
    - Ordering scopes.
    - TTL/deadline rejection before execution.
    - Execution timeout measurement.
    - Graceful shutdown.

    Important:
    A Python worker thread cannot be forcefully killed safely. Therefore
    max_exec_ms is measured and reported, but does not terminate a running
    task.
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        levels: tuple[int, ...] | list[int] = (0, 1, 2),
        queue_maxsize: int = 100,
        reserved_low_slots: int = 1,
        aging_step_seconds: float = 5.0,
        aging_step_amount: int = 1,
        idle_sleep: float = 0.05,
        max_exec_ms_default: int = 3000,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1.")

        if queue_maxsize < 1:
            raise ValueError("queue_maxsize must be >= 1.")

        if reserved_low_slots < 0:
            raise ValueError("reserved_low_slots must be >= 0.")

        if reserved_low_slots > queue_maxsize:
            raise ValueError(
                "reserved_low_slots cannot exceed queue_maxsize."
            )

        if aging_step_seconds <= 0:
            raise ValueError("aging_step_seconds must be > 0.")

        if aging_step_amount < 1:
            raise ValueError("aging_step_amount must be >= 1.")

        if idle_sleep < 0:
            raise ValueError("idle_sleep cannot be negative.")

        if max_exec_ms_default < 0:
            raise ValueError("max_exec_ms_default cannot be negative.")

        normalized_levels = sorted(set(int(level) for level in levels))

        if not normalized_levels:
            raise ValueError("At least one priority level is required.")

        self._max_workers = max_workers
        self._levels = tuple(normalized_levels)
        self._highest_priority = self._levels[0]
        self._lowest_priority = self._levels[-1]

        self._queue_maxsize = queue_maxsize
        self._reserved_low_slots = reserved_low_slots
        self._aging_step_seconds = aging_step_seconds
        self._aging_step_amount = aging_step_amount
        self._idle_sleep = idle_sleep
        self._max_exec_ms_default = max_exec_ms_default

        self._queue: list[_QueuedTask] = []
        self._sequence = 0

        self._condition = threading.Condition(threading.RLock())
        self._stop_event = threading.Event()

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="priority-exec",
        )

        self._scheduler_thread: Optional[threading.Thread] = None
        self._started = False
        self._stopping = False

        self._active_scopes: set[str] = set()
        self._active_tasks = 0

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def queue_size(self) -> int:
        with self._condition:
            return len(self._queue)

    @property
    def active_tasks(self) -> int:
        with self._condition:
            return self._active_tasks

    @property
    def is_running(self) -> bool:
        with self._condition:
            return self._started and not self._stopping

    def start(self) -> None:
        with self._condition:
            if self._started:
                return

            if self._stopping:
                raise RuntimeError(
                    "PriorityExecutor cannot be restarted after stop."
                )

            self._started = True

            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="priority-scheduler",
                daemon=True,
            )
            self._scheduler_thread.start()

    def submit(
        self,
        task: Callable[[], Any],
        *,
        priority: int = 1,
        ordering_scope: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        deadline: Optional[float] = None,
        max_exec_ms: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> Future:
        if not callable(task):
            raise TypeError("task must be callable.")

        if ttl_seconds is not None and ttl_seconds < 0:
            raise ValueError("ttl_seconds cannot be negative.")

        if max_exec_ms is not None and max_exec_ms < 0:
            raise ValueError("max_exec_ms cannot be negative.")

        with self._condition:
            if not self._started:
                self.start()

            if self._stopping:
                raise RuntimeError(
                    "Cannot submit work while executor is stopping."
                )

            if not self._has_queue_capacity(priority):
                raise RuntimeError(
                    "Priority executor queue is full."
                )

            normalized_priority = self._normalize_priority(priority)

            request = ExecutionRequest(
                task=task,
                priority=normalized_priority,
                ordering_scope=ordering_scope,
                ttl_seconds=ttl_seconds,
                deadline=deadline,
                max_exec_ms=max_exec_ms,
                request_id=request_id,
            )

            queued = _QueuedTask(
                sequence=self._sequence,
                request=request,
                submitted_at=time.monotonic(),
            )

            self._sequence += 1
            heapq.heappush(self._queue, queued)

            self._condition.notify()

            return queued.future

    def submit_request(self, request: ExecutionRequest) -> Future:
        return self.submit(
            request.task,
            priority=request.priority,
            ordering_scope=request.ordering_scope,
            ttl_seconds=request.ttl_seconds,
            deadline=request.deadline,
            max_exec_ms=request.max_exec_ms,
            request_id=request.request_id,
        )

    def shutdown(
        self,
        *,
        wait: bool = True,
        cancel_pending: bool = False,
        timeout: Optional[float] = None,
    ) -> bool:
        with self._condition:
            if self._stopping:
                return self._scheduler_stopped()

            self._stopping = True
            self._stop_event.set()

            if cancel_pending:
                self._cancel_pending_locked()

            self._condition.notify_all()

        scheduler = self._scheduler_thread

        if scheduler is not None and wait:
            scheduler.join(timeout=timeout)

        self._executor.shutdown(
            wait=wait,
            cancel_futures=cancel_pending,
        )

        return self._scheduler_stopped()

    def cancel_pending(self) -> int:
        with self._condition:
            return self._cancel_pending_locked()

    def _cancel_pending_locked(self) -> int:
        cancelled = 0

        while self._queue:
            queued = heapq.heappop(self._queue)

            if not queued.future.done():
                queued.future.cancel()
                cancelled += 1

        return cancelled

    def _scheduler_loop(self) -> None:
        while True:
            with self._condition:
                while (
                    not self._queue
                    and not self._stop_event.is_set()
                ):
                    self._condition.wait(timeout=self._idle_sleep)

                if self._stop_event.is_set() and not self._queue:
                    return

                queued = self._select_next_task_locked()

                if queued is None:
                    self._condition.wait(timeout=self._idle_sleep)
                    continue

                if self._is_expired(queued):
                    if not queued.future.done():
                        queued.future.set_exception(
                            TimeoutError(
                                "Priority executor task expired "
                                "before execution."
                            )
                        )
                    continue

                scope = queued.request.ordering_scope

                if scope is not None:
                    self._active_scopes.add(scope)

                self._active_tasks += 1

            self._executor.submit(
                self._run_task,
                queued,
            )

    def _run_task(self, queued: _QueuedTask) -> None:
        started_at = time.monotonic()

        try:
            if self._is_expired(queued):
                if not queued.future.done():
                    queued.future.set_exception(
                        TimeoutError(
                            "Priority executor task expired "
                            "before execution."
                        )
                    )
                return

            result = queued.request.task()

            elapsed_ms = (
                time.monotonic() - started_at
            ) * 1000.0

            max_exec_ms = (
                queued.request.max_exec_ms
                if queued.request.max_exec_ms is not None
                else self._max_exec_ms_default
            )

            if (
                max_exec_ms > 0
                and elapsed_ms > max_exec_ms
            ):
                logger.warning(
                    "Task exceeded execution timeout: "
                    "request_id=%s elapsed_ms=%.2f limit_ms=%s",
                    queued.request.request_id,
                    elapsed_ms,
                    max_exec_ms,
                )

            if not queued.future.done():
                queued.future.set_result(result)

        except BaseException as exc:
            if not queued.future.done():
                queued.future.set_exception(exc)

            logger.exception(
                "Priority executor task failed: request_id=%s",
                queued.request.request_id,
            )

        finally:
            with self._condition:
                scope = queued.request.ordering_scope

                if scope is not None:
                    self._active_scopes.discard(scope)

                self._active_tasks -= 1
                self._condition.notify_all()

    def _select_next_task_locked(self) -> Optional[_QueuedTask]:
        if not self._queue:
            return None

        now = time.monotonic()

        candidates: list[tuple[int, int, _QueuedTask]] = []

        for queued in self._queue:
            if not self._ordering_scope_available(queued):
                continue

            effective_priority = self._effective_priority(
                queued,
                now,
            )

            candidates.append(
                (
                    effective_priority,
                    queued.sequence,
                    queued,
                )
            )

        if not candidates:
            return None

        _, _, selected = min(candidates)

        self._queue.remove(selected)
        heapq.heapify(self._queue)

        return selected

    def _effective_priority(
        self,
        queued: _QueuedTask,
        now: float,
    ) -> int:
        base_priority = queued.request.priority

        age_seconds = max(
            0.0,
            now - queued.submitted_at,
        )

        aging_steps = int(
            age_seconds / self._aging_step_seconds
        )

        effective_priority = (
            base_priority
            - aging_steps * self._aging_step_amount
        )

        return max(
            self._highest_priority,
            effective_priority,
        )

    def _ordering_scope_available(
        self,
        queued: _QueuedTask,
    ) -> bool:
        scope = queued.request.ordering_scope

        if scope is None:
            return True

        return scope not in self._active_scopes

    def _is_expired(self, queued: _QueuedTask) -> bool:
        now = time.monotonic()

        if queued.request.deadline is not None:
            if now >= queued.request.deadline:
                return True

        if queued.request.ttl_seconds is not None:
            if (
                now - queued.submitted_at
                >= queued.request.ttl_seconds
            ):
                return True

        return False

    def _normalize_priority(self, priority: int) -> int:
        try:
            value = int(priority)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid priority: {priority!r}"
            ) from exc

        if value <= self._highest_priority:
            return self._highest_priority

        if value >= self._lowest_priority:
            return self._lowest_priority

        return min(
            self._levels,
            key=lambda level: abs(level - value),
        )

    def _has_queue_capacity(self, priority: int) -> bool:
        if len(self._queue) < self._queue_maxsize:
            return True

        normalized = self._normalize_priority(priority)

        # When the queue is full, reserved slots remain available
        # conceptually for the lowest-priority work. Higher-priority
        # submissions may use the general queue capacity, but the
        # reserved portion is protected from being consumed by them.
        if normalized == self._lowest_priority:
            return False

        general_capacity = (
            self._queue_maxsize
            - self._reserved_low_slots
        )

        return len(self._queue) < general_capacity

    def _scheduler_stopped(self) -> bool:
        scheduler = self._scheduler_thread

        return (
            scheduler is None
            or not scheduler.is_alive()
        )

    def __enter__(self) -> "PriorityExecutor":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.shutdown(
            wait=True,
            cancel_pending=True,
            timeout=1.0,
        )


__all__ = [
    "ExecutionRequest",
    "PriorityExecutor",
]