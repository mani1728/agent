from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from agent.contracts.response import ResponseEnvelope

from agent.persistence.migrations import Migration, run_migrations


logger = logging.getLogger(__name__)


IDEMPOTENCY_MIGRATIONS = (
    Migration(
        version=1,
        name="create_idempotency_store",
        sql="""
            CREATE TABLE IF NOT EXISTS agent_idempotency_records (
                command_id TEXT PRIMARY KEY,
                fingerprint TEXT,
                state TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_agent_idempotency_records_state_updated_at
            ON agent_idempotency_records (state, updated_at);
        """,
    ),
)


def _serialize_idempotent_result(
    result: Any,
) -> Optional[str]:
    if result is None:
        return None

    if isinstance(result, ResponseEnvelope):
        payload = {
            "_agent_payload_type": "response",
            "_agent_payload": result.to_dict(),
        }
    else:
        payload = {
            "_agent_payload_type": "json",
            "_agent_payload": result,
        }

    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise IdempotencyError(
            "Failed to serialize idempotency result."
        ) from exc


def _deserialize_idempotent_result(
    value: Optional[str],
) -> Any:
    if value is None:
        return None

    try:
        payload = json.loads(
            value,
            object_hook=dict,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IdempotencyError(
            "Failed to deserialize idempotency result."
        ) from exc

    if not isinstance(payload, dict):
        return payload

    kind = payload.get("_agent_payload_type")
    raw = payload.get("_agent_payload")

    if kind == "response":
        if isinstance(raw, dict):
            try:
                return ResponseEnvelope.from_dict(
                    raw,
                )
            except Exception:
                return raw
        return raw

    return raw

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


class SQLiteIdempotencyStore:
    """
    Persistent idempotency store backed by SQLite.

    The store keeps records in a dedicated table and supports crash-recovery
    through explicit in-progress state recovery.
    """

    TABLE_NAME = "agent_idempotency_records"

    def __init__(
        self,
        database_path: str | os.PathLike[str] | sqlite3.Connection = ":memory:",
        *,
        ttl_seconds: Optional[float] = None,
        in_progress_ttl_seconds: Optional[float] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds < 0:
            raise ValueError(
                "ttl_seconds must be >= 0 or None."
            )

        if (
            in_progress_ttl_seconds is not None
            and in_progress_ttl_seconds < 0
        ):
            raise ValueError(
                "in_progress_ttl_seconds must be >= 0 or None."
            )

        self._ttl_seconds = ttl_seconds
        self._in_progress_ttl_seconds = (
            600.0
            if in_progress_ttl_seconds is None
            else float(in_progress_ttl_seconds)
        )

        self._clock = clock if clock is not None else time.time

        if not callable(self._clock):
            raise TypeError("clock must be callable.")

        self._lock = threading.RLock()
        self._closed = False

        if isinstance(database_path, sqlite3.Connection):
            self._connection = database_path
            self._owns_connection = False
        else:
            path = (
                str(database_path)
                if not isinstance(database_path, os.PathLike)
                else str(database_path)
            )
            self._connection = sqlite3.connect(
                path,
                timeout=10.0,
                check_same_thread=False,
            )
            self._owns_connection = True

        self._configure_connection()
        run_migrations(
            self._connection,
            IDEMPOTENCY_MIGRATIONS,
            logger_=logger,
        )

        if self._connection is None:
            raise IdempotencyError(
                "SQLite idempotency store connection is not initialized."
            )

        try:
            self._cleanup_stale_records()
        except Exception:
            logger.exception(
                "Failed to recover stale idempotency records on startup."
            )

    @property
    def connection(self) -> sqlite3.Connection:
        if self._closed:
            raise IdempotencyError(
                "SQLite idempotency store is closed."
            )
        if self._connection is None:
            raise IdempotencyError(
                "SQLite idempotency store is not initialized."
            )
        return self._connection

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            if not self._owns_connection:
                self._closed = True
                return

            if self._connection is not None:
                try:
                    self._connection.close()
                finally:
                    self._connection = None

            self._closed = True

    def begin(
        self,
        key: str,
        *,
        fingerprint: Optional[str] = None,
    ) -> IdempotencyResult:
        with self._lock:
            normalized_key = normalize_idempotency_key(key)
            normalized_fingerprint = (
                normalize_fingerprint(fingerprint)
                if fingerprint is not None
                else None
            )

            now = self._clock()

            record = self._get_locked(normalized_key)

            if record is not None and self._is_expired(record):
                self._delete_locked(normalized_key)
                record = None

            if record is not None:
                if (
                    normalized_fingerprint is not None
                    and record.fingerprint is not None
                    and normalized_fingerprint != record.fingerprint
                ):
                    raise IdempotencyError(
                        "Idempotency key was reused with a different "
                        f"request fingerprint: {normalized_key}"
                    )

                return IdempotencyResult(
                    accepted=False,
                    duplicate=True,
                    record=record,
                )

            self._upsert_locked(
                command_id=normalized_key,
                fingerprint=normalized_fingerprint,
                state=IdempotencyState.IN_PROGRESS,
                created_at=now,
                updated_at=now,
                result=None,
                error=None,
            )

            return IdempotencyResult(
                accepted=True,
                duplicate=False,
                record=IdempotencyRecord(
                    key=normalized_key,
                    state=IdempotencyState.IN_PROGRESS,
                    fingerprint=normalized_fingerprint,
                    result=None,
                    error=None,
                    created_at=now,
                    updated_at=now,
                ),
            )

    def complete(
        self,
        key: str,
        *,
        result: Any = None,
    ) -> IdempotencyRecord:
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            self._ensure_open()

            row = self._get_locked(normalized_key)

            if row is None:
                raise IdempotencyError(
                    f"Idempotency key is not registered: {normalized_key}"
                )

            now = self._clock()
            serialized_result = _serialize_idempotent_result(result)

            with self.connection:
                self.connection.execute(
                    f"""
                    UPDATE {self.TABLE_NAME}
                    SET state = ?,
                        result = ?,
                        error = ?,
                        updated_at = ?
                    WHERE command_id = ?
                    """,
                    (
                        IdempotencyState.COMPLETED.value,
                        serialized_result,
                        None,
                        now,
                        normalized_key,
                    ),
                )

            return IdempotencyRecord(
                key=normalized_key,
                state=IdempotencyState.COMPLETED,
                fingerprint=row.fingerprint,
                result=result,
                error=None,
                created_at=row.created_at,
                updated_at=now,
            )

    def fail(
        self,
        key: str,
        *,
        error: Optional[str] = None,
        result: Any = None,
    ) -> IdempotencyRecord:
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            self._ensure_open()

            row = self._get_locked(normalized_key)

            if row is None:
                raise IdempotencyError(
                    f"Idempotency key is not registered: {normalized_key}"
                )

            now = self._clock()
            serialized_result = _serialize_idempotent_result(result)

            with self.connection:
                self.connection.execute(
                    f"""
                    UPDATE {self.TABLE_NAME}
                    SET state = ?,
                        result = ?,
                        error = ?,
                        updated_at = ?
                    WHERE command_id = ?
                    """,
                    (
                        IdempotencyState.FAILED.value,
                        serialized_result,
                        str(error)
                        if error is not None
                        else None,
                        now,
                        normalized_key,
                    ),
                )

            return IdempotencyRecord(
                key=normalized_key,
                state=IdempotencyState.FAILED,
                fingerprint=row.fingerprint,
                result=result,
                error=(
                    str(error)
                    if error is not None
                    else row.error
                ),
                created_at=row.created_at,
                updated_at=now,
            )

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        normalized_key = normalize_idempotency_key(key)

        with self._lock:
            self._ensure_open()
            self._cleanup_stale_records()
            return self._get_locked(normalized_key)

    def remove(self, key: str) -> bool:
        with self._lock:
            self._ensure_open()
            return self._delete_locked(
                normalize_idempotency_key(key),
            )

    def clear(self) -> None:
        with self._lock:
            self._ensure_open()

            with self.connection:
                self.connection.execute(
                    f"DELETE FROM {self.TABLE_NAME}"
                )

    def size(self) -> int:
        with self._lock:
            self._ensure_open()
            self._cleanup_stale_records()

            cursor = self.connection.execute(
                f"SELECT COUNT(*) FROM {self.TABLE_NAME}"
            )
            row = cursor.fetchone()
            return int(row[0] or 0)

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def cleanup_expired(self) -> int:
        with self._lock:
            self._ensure_open()
            return self._cleanup_stale_records()

    def _ensure_open(self) -> None:
        if self._closed:
            raise IdempotencyError(
                "SQLite idempotency store is closed."
            )

        if self._connection is None:
            raise IdempotencyError(
                "SQLite idempotency store is not connected."
            )

    def _configure_connection(self) -> None:
        try:
            with self.connection:
                self.connection.execute(
                    "PRAGMA busy_timeout = 30000"
                )
                self.connection.execute(
                    "PRAGMA foreign_keys = ON"
                )
                self.connection.execute(
                    "PRAGMA journal_mode = WAL"
                )
                self.connection.execute(
                    "PRAGMA synchronous = NORMAL"
                )
        except sqlite3.Error as exc:
            raise IdempotencyError(
                "Failed to configure SQLite idempotency connection."
            ) from exc

    def _delete_locked(self, key: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE command_id = ?
                """,
                (key,),
            )

        return cursor.rowcount > 0

    def _upsert_locked(
        self,
        *,
        command_id: str,
        fingerprint: Optional[str],
        state: IdempotencyState,
        created_at: float,
        updated_at: float,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        serialized = (
            _serialize_idempotent_result(result)
            if result is not None
            else None
        )

        try:
            with self.connection:
                self.connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME} (
                        command_id,
                        fingerprint,
                        state,
                        result,
                        error,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        command_id,
                        fingerprint,
                        state.value,
                        serialized,
                        error,
                        created_at,
                        updated_at,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise IdempotencyError(
                f"Idempotency key already exists: {command_id}"
            ) from exc

        except sqlite3.Error as exc:
            raise IdempotencyError(
                "Failed to create idempotency record."
            ) from exc

    def _get_locked(self, key: str) -> Optional[IdempotencyRecord]:
        cursor = self.connection.execute(
            f"""
            SELECT
                command_id,
                fingerprint,
                state,
                result,
                error,
                created_at,
                updated_at
            FROM {self.TABLE_NAME}
            WHERE command_id = ?
            """,
            (key,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        try:
            created_at = float(row[5])
            updated_at = float(row[6])
        except (TypeError, ValueError) as exc:
            raise IdempotencyError(
                "Stored idempotency timestamp is invalid."
            ) from exc

        result = _deserialize_idempotent_result(row[3])
        record = IdempotencyRecord(
            key=str(row[0]),
            state=IdempotencyState(str(row[2])),
            fingerprint=(
                str(row[1]) if row[1] is not None else None
            ),
            result=result,
            error=(
                str(row[4])
                if row[4] is not None
                else None
            ),
            created_at=created_at,
            updated_at=updated_at,
        )

        return record

    def _cleanup_stale_records(self) -> int:
        now = self._clock()
        removed = 0

        stale_where = []
        stale_params: list[float | str | None] = []

        if self._ttl_seconds is not None:
            stale_where.append("updated_at <= ?")
            stale_params.append(now - float(self._ttl_seconds))

        if self._in_progress_ttl_seconds is not None:
            stale_where.append(
                "(state = ? AND updated_at <= ?)"
            )
            stale_params.extend(
                [
                    IdempotencyState.IN_PROGRESS.value,
                    now - float(self._in_progress_ttl_seconds),
                ]
            )

        if stale_where:
            query = (
                f"DELETE FROM {self.TABLE_NAME} WHERE "
                + " OR ".join(stale_where)
            )

            with self.connection:
                cursor = self.connection.execute(
                    query,
                    tuple(stale_params),
                )

            removed = cursor.rowcount

        return removed

    def _is_expired(
        self,
        record: IdempotencyRecord,
    ) -> bool:
        if self._ttl_seconds is None:
            if (
                self._in_progress_ttl_seconds is not None
                and record.state is IdempotencyState.IN_PROGRESS
            ):
                return (
                    self._clock() - record.updated_at
                    >= self._in_progress_ttl_seconds
                )
            return False

        if (
            self._clock() - record.updated_at
            >= self._ttl_seconds
        ):
            return True

        if (
            record.state is IdempotencyState.IN_PROGRESS
            and self._in_progress_ttl_seconds is not None
        ):
            return (
                self._clock() - record.updated_at
                >= self._in_progress_ttl_seconds
            )

        return False


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
    "SQLiteIdempotencyStore",
    "IDEMPOTENCY_MIGRATIONS",
    "fingerprint_mapping",
    "fingerprint_payload",
    "normalize_fingerprint",
    "normalize_idempotency_key",
]
