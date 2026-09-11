# Path: Version 1_0_0/agent/reliability/idempotency.py

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional


class IdempotencyError(RuntimeError):
    """Base exception for idempotency failures."""


class IdempotencyKeyError(IdempotencyError):
    """Raised when an invalid idempotency key is supplied."""


class IdempotencyState(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class IdempotencyRecord:
    """
    Result record associated with an idempotency key.
    """

    key: str
    state: IdempotencyState
    fingerprint: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass(frozen=True)
class IdempotencyResult:
    """
    Result of attempting to register an idempotency key.
    """

    accepted: bool
    duplicate: bool
    record: IdempotencyRecord


class IdempotencyStore:
    """
    Thread-safe in-memory idempotency store.

    The store deliberately has no dependency on SQLite, Kafka, HTTP,
    or any other persistence/transport layer.

    A persistent implementation can later implement the same logical
    operations without changing the idempotency policy.
    """

    def __init__(
        self,
        *,
        ttl_seconds: Optional[float] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds < 0:
            raise ValueError(
                "ttl_seconds must be >= 0 or None."
            )

        self._ttl_seconds = ttl_seconds
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
        self._records: dict[str, IdempotencyRecord] = {}

    @property
    def ttl_seconds(self) -> Optional[float]:
        return self._ttl_seconds

    def get(
        self,
        key: str,
    ) -> Optional[IdempotencyRecord]:
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            record = self._records.get(
                normalized_key
            )

            if record is None:
                return None

            if self._is_expired(record):
                del self._records[normalized_key]
                return None

            return record

    def contains(
        self,
        key: str,
    ) -> bool:
        return self.get(key) is not None

    def begin(
        self,
        key: str,
        *,
        fingerprint: Optional[str] = None,
    ) -> IdempotencyResult:
        """
        Atomically register an execution as IN_PROGRESS.

        If the key already exists and has not expired, the existing
        record is returned and accepted=False.
        """
        normalized_key = normalize_idempotency_key(key)

        if fingerprint is not None:
            fingerprint = normalize_fingerprint(
                fingerprint
            )

        with self._lock:
            existing = self._records.get(
                normalized_key
            )

            if existing is not None:
                if self._is_expired(existing):
                    del self._records[
                        normalized_key
                    ]
                    existing = None

            if existing is not None:
                if (
                    fingerprint is not None
                    and existing.fingerprint is not None
                    and fingerprint
                    != existing.fingerprint
                ):
                    raise IdempotencyError(
                        "Idempotency key was reused with "
                        "a different request fingerprint: "
                        f"{normalized_key}"
                    )

                return IdempotencyResult(
                    accepted=False,
                    duplicate=True,
                    record=existing,
                )

            now = self._clock()

            record = IdempotencyRecord(
                key=normalized_key,
                state=IdempotencyState.IN_PROGRESS,
                fingerprint=fingerprint,
                created_at=now,
                updated_at=now,
            )

            self._records[normalized_key] = record

            return IdempotencyResult(
                accepted=True,
                duplicate=False,
                record=record,
            )

    def complete(
        self,
        key: str,
        *,
        result: Any = None,
    ) -> IdempotencyRecord:
        """
        Mark an existing execution as successfully completed.
        """
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            record = self._require_record(
                normalized_key
            )

            if (
                record.state
                == IdempotencyState.COMPLETED
            ):
                return record

            now = self._clock()

            updated = IdempotencyRecord(
                key=record.key,
                state=IdempotencyState.COMPLETED,
                fingerprint=record.fingerprint,
                result=result,
                error=None,
                created_at=record.created_at,
                updated_at=now,
            )

            self._records[normalized_key] = updated

            return updated

    def fail(
        self,
        key: str,
        *,
        error: Optional[str] = None,
        result: Any = None,
    ) -> IdempotencyRecord:
        """
        Mark an existing execution as failed.

        The record remains present so callers can decide whether a
        failed execution is retryable or terminal.
        """
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            record = self._require_record(
                normalized_key
            )

            now = self._clock()

            updated = IdempotencyRecord(
                key=record.key,
                state=IdempotencyState.FAILED,
                fingerprint=record.fingerprint,
                result=result,
                error=(
                    str(error)
                    if error is not None
                    else None
                ),
                created_at=record.created_at,
                updated_at=now,
            )

            self._records[normalized_key] = updated

            return updated

    def remove(
        self,
        key: str,
    ) -> bool:
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            return (
                self._records.pop(
                    normalized_key,
                    None,
                )
                is not None
            )

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def cleanup_expired(self) -> int:
        """
        Remove expired records.

        Returns the number of removed records.
        """
        if self._ttl_seconds is None:
            return 0

        removed = 0

        with self._lock:
            expired_keys = [
                key
                for key, record
                in self._records.items()
                if self._is_expired(record)
            ]

            for key in expired_keys:
                self._records.pop(
                    key,
                    None,
                )
                removed += 1

        return removed

    def size(self) -> int:
        self.cleanup_expired()

        with self._lock:
            return len(self._records)

    def _require_record(
        self,
        key: str,
    ) -> IdempotencyRecord:
        record = self._records.get(key)

        if record is None:
            raise IdempotencyError(
                f"Idempotency key is not registered: {key}"
            )

        if self._is_expired(record):
            del self._records[key]

            raise IdempotencyError(
                f"Idempotency record has expired: {key}"
            )

        return record

    def _is_expired(
        self,
        record: IdempotencyRecord,
    ) -> bool:
        if self._ttl_seconds is None:
            return False

        elapsed = (
            self._clock()
            - record.updated_at
        )

        return elapsed >= self._ttl_seconds


class IdempotencyManager:
    """
    High-level idempotency coordinator.

    This class provides the common pattern:

        begin -> execute -> complete/fail

    Duplicate requests can return the already stored result instead of
    executing the operation again.
    """

    def __init__(
        self,
        store: Optional[IdempotencyStore] = None,
    ) -> None:
        self._store = (
            store
            if store is not None
            else IdempotencyStore()
        )

    @property
    def store(self) -> IdempotencyStore:
        return self._store

    def check(
        self,
        key: str,
        *,
        fingerprint: Optional[str] = None,
    ) -> IdempotencyResult:
        return self._store.begin(
            key,
            fingerprint=fingerprint,
        )

    def execute(
        self,
        key: str,
        func: Callable[..., Any],
        *args: Any,
        fingerprint: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a callable exactly once for an active idempotency key.

        If a completed duplicate is encountered, its stored result is
        returned.

        If an in-progress duplicate is encountered, execution is rejected
        because the original operation has not completed yet.
        """
        if not callable(func):
            raise TypeError(
                "func must be callable."
            )

        registration = self._store.begin(
            key,
            fingerprint=fingerprint,
        )

        record = registration.record

        if registration.duplicate:
            if (
                record.state
                == IdempotencyState.COMPLETED
            ):
                return record.result

            if (
                record.state
                == IdempotencyState.FAILED
            ):
                raise IdempotencyError(
                    "Idempotent operation already failed: "
                    f"{record.key}"
                )

            raise IdempotencyError(
                "Idempotent operation is already in progress: "
                f"{record.key}"
            )

        try:
            result = func(
                *args,
                **kwargs,
            )

        except BaseException as exc:
            self._store.fail(
                key,
                error=str(exc),
            )
            raise

        self._store.complete(
            key,
            result=result,
        )

        return result

    def complete(
        self,
        key: str,
        *,
        result: Any = None,
    ) -> IdempotencyRecord:
        return self._store.complete(
            key,
            result=result,
        )

    def fail(
        self,
        key: str,
        *,
        error: Optional[str] = None,
        result: Any = None,
    ) -> IdempotencyRecord:
        return self._store.fail(
            key,
            error=error,
            result=result,
        )

    def get(
        self,
        key: str,
    ) -> Optional[IdempotencyRecord]:
        return self._store.get(key)

    def remove(
        self,
        key: str,
    ) -> bool:
        return self._store.remove(key)


def normalize_idempotency_key(
    key: str,
) -> str:
    if not isinstance(key, str):
        raise IdempotencyKeyError(
            "Idempotency key must be a string."
        )

    normalized = key.strip()

    if not normalized:
        raise IdempotencyKeyError(
            "Idempotency key cannot be empty."
        )

    if len(normalized) > 512:
        raise IdempotencyKeyError(
            "Idempotency key cannot exceed 512 characters."
        )

    return normalized


def fingerprint_payload(
    payload: Any,
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint for a JSON-compatible
    request payload.

    The fingerprint is useful for detecting accidental reuse of the same
    idempotency key with different request data.
    """
    try:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IdempotencyError(
            "Payload cannot be converted into a fingerprint."
        ) from exc

    return hashlib.sha256(
        serialized
    ).hexdigest()


def fingerprint_mapping(
    payload: Mapping[str, Any],
) -> str:
    if not isinstance(payload, Mapping):
        raise TypeError(
            "payload must be a mapping."
        )

    return fingerprint_payload(
        dict(payload)
    )


def normalize_fingerprint(
    fingerprint: str,
) -> str:
    if not isinstance(fingerprint, str):
        raise IdempotencyError(
            "fingerprint must be a string."
        )

    normalized = fingerprint.strip().lower()

    if not normalized:
        raise IdempotencyError(
            "fingerprint cannot be empty."
        )

    return normalized


__all__ = [
    "IdempotencyError",
    "IdempotencyKeyError",
    "IdempotencyManager",
    "IdempotencyRecord",
    "IdempotencyResult",
    "IdempotencyState",
    "IdempotencyStore",
    "fingerprint_mapping",
    "fingerprint_payload",
    "normalize_fingerprint",
    "normalize_idempotency_key",
]