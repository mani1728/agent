# Path: Version 1_0_0/agent/persistence/sqlite_spooler.py

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .models import (
    SpoolMessage,
    SpoolMessageType,
    SpoolQuery,
    SpoolStatus,
)
from .spool_repository import SpoolRepository
from .spooler import Spooler


logger = logging.getLogger(__name__)


class SQLiteSpoolerError(RuntimeError):
    """Base exception for SQLite spooler failures."""


class SQLiteSpooler:
    """
    SQLite-backed spooler.

    Responsibilities:
    - Own the SQLite connection lifecycle.
    - Configure SQLite for safe concurrent agent usage.
    - Expose the high-level Spooler API.
    - Provide explicit close/checkpoint operations.

    This class does not implement:
    - retry policy
    - backoff/jitter
    - transport delivery
    - circuit breaker
    - idempotency
    - retention policy
    - background recovery workers
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        timeout: float = 10.0,
        wal_mode: bool = True,
        foreign_keys: bool = True,
        synchronous: str = "NORMAL",
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger_ or logger
        self._lock = threading.RLock()
        self._closed = False

        if timeout < 0:
            raise ValueError(
                "timeout must be greater than or equal to zero."
            )

        self._database_path = self._normalize_database_path(
            database_path
        )

        self._timeout = float(timeout)
        self._wal_mode = bool(wal_mode)
        self._foreign_keys = bool(foreign_keys)
        self._synchronous = self._normalize_synchronous(
            synchronous
        )

        self._connection: Optional[sqlite3.Connection] = None
        self._repository: Optional[SpoolRepository] = None
        self._spooler: Optional[Spooler] = None

        self._open()

    @classmethod
    def in_memory(
        cls,
        *,
        timeout: float = 10.0,
        logger_: Optional[logging.Logger] = None,
    ) -> "SQLiteSpooler":
        """
        Create an in-memory SQLite spooler.

        Useful for tests and isolated runtime usage.
        """
        return cls(
            ":memory:",
            timeout=timeout,
            wal_mode=False,
            logger_=logger_,
        )

    @property
    def database_path(self) -> Path | str:
        return self._database_path

    @property
    def connection(self) -> sqlite3.Connection:
        self._ensure_open()

        if self._connection is None:
            raise SQLiteSpoolerError(
                "SQLite connection is not initialized."
            )

        return self._connection

    @property
    def repository(self) -> SpoolRepository:
        self._ensure_open()

        if self._repository is None:
            raise SQLiteSpoolerError(
                "Spool repository is not initialized."
            )

        return self._repository

    @property
    def spooler(self) -> Spooler:
        self._ensure_open()

        if self._spooler is None:
            raise SQLiteSpoolerError(
                "Spooler is not initialized."
            )

        return self._spooler

    @property
    def is_closed(self) -> bool:
        return self._closed

    def enqueue(
        self,
        *,
        message_id: str,
        correlation_id: Optional[str],
        message_type: SpoolMessageType,
        payload: object,
    ) -> SpoolMessage:
        return self.spooler.enqueue(
            message_id=message_id,
            correlation_id=correlation_id,
            message_type=message_type,
            payload=payload,
        )

    def enqueue_message(
        self,
        message: SpoolMessage,
    ) -> SpoolMessage:
        return self.spooler.enqueue_message(
            message
        )

    def enqueue_many(
        self,
        messages: list[SpoolMessage],
    ) -> list[SpoolMessage]:
        return self.spooler.enqueue_many(
            messages
        )

    def get(
        self,
        message_id: str,
    ) -> Optional[SpoolMessage]:
        return self.spooler.get(message_id)

    def require(
        self,
        message_id: str,
    ) -> SpoolMessage:
        return self.spooler.require(message_id)

    def exists(
        self,
        message_id: str,
    ) -> bool:
        return self.spooler.exists(message_id)

    def find(
        self,
        query: Optional[SpoolQuery] = None,
    ) -> list[SpoolMessage]:
        return self.spooler.find(query)

    def pending(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.spooler.pending(limit)

    def processing(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.spooler.processing(limit)

    def failed(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.spooler.failed(limit)

    def mark_processing(
        self,
        message_id: str,
    ) -> SpoolMessage:
        return self.spooler.mark_processing(
            message_id
        )

    def mark_sent(
        self,
        message_id: str,
    ) -> SpoolMessage:
        return self.spooler.mark_sent(
            message_id
        )

    def mark_failed(
        self,
        message_id: str,
        *,
        error: Optional[str] = None,
        next_retry_time=None,
    ) -> SpoolMessage:
        return self.spooler.mark_failed(
            message_id,
            error=error,
            next_retry_time=next_retry_time,
        )

    def mark_dead(
        self,
        message_id: str,
        *,
        error: Optional[str] = None,
    ) -> SpoolMessage:
        return self.spooler.mark_dead(
            message_id,
            error=error,
        )

    def mark_pending(
        self,
        message_id: str,
        *,
        next_retry_time=None,
    ) -> SpoolMessage:
        return self.spooler.mark_pending(
            message_id,
            next_retry_time=next_retry_time,
        )

    def update(
        self,
        message: SpoolMessage,
    ) -> SpoolMessage:
        return self.spooler.update(message)

    def delete(
        self,
        message_id: str,
    ) -> bool:
        return self.spooler.delete(message_id)

    def delete_many(
        self,
        message_ids: list[str],
    ) -> int:
        return self.spooler.delete_many(
            message_ids
        )

    def count(
        self,
        *,
        status: Optional[SpoolStatus] = None,
        message_type: Optional[SpoolMessageType] = None,
    ) -> int:
        return self.spooler.count(
            status=status,
            message_type=message_type,
        )

    def clear(
        self,
        *,
        status: Optional[SpoolStatus] = None,
    ) -> int:
        return self.spooler.clear(
            status=status
        )

    def recover_processing(
        self,
        *,
        limit: int = 100,
    ) -> int:
        return self.spooler.recover_processing(
            limit=limit
        )

    def commit(self) -> None:
        self._ensure_open()

        with self._lock:
            try:
                self.connection.commit()
            except sqlite3.Error as exc:
                raise SQLiteSpoolerError(
                    "Failed to commit SQLite transaction."
                ) from exc

    def rollback(self) -> None:
        self._ensure_open()

        with self._lock:
            try:
                self.connection.rollback()
            except sqlite3.Error as exc:
                raise SQLiteSpoolerError(
                    "Failed to rollback SQLite transaction."
                ) from exc

    def checkpoint(
        self,
        mode: str = "PASSIVE",
    ) -> tuple[int, int, int]:
        """
        Run a SQLite WAL checkpoint.

        Returns SQLite's checkpoint result:
        (busy, log_frames, checkpointed_frames).
        """
        self._ensure_open()

        normalized_mode = str(mode).upper().strip()

        allowed_modes = {
            "PASSIVE",
            "FULL",
            "RESTART",
            "TRUNCATE",
        }

        if normalized_mode not in allowed_modes:
            raise ValueError(
                "Invalid checkpoint mode. "
                f"Expected one of: {sorted(allowed_modes)}."
            )

        with self._lock:
            try:
                cursor = self.connection.execute(
                    f"PRAGMA wal_checkpoint("
                    f"{normalized_mode}"
                    f")"
                )
                row = cursor.fetchone()

            except sqlite3.Error as exc:
                raise SQLiteSpoolerError(
                    "Failed to execute SQLite WAL checkpoint."
                ) from exc

        if row is None or len(row) != 3:
            raise SQLiteSpoolerError(
                "SQLite returned an invalid checkpoint result."
            )

        return (
            int(row[0]),
            int(row[1]),
            int(row[2]),
        )

    def vacuum(self) -> None:
        """
        Compact the SQLite database.

        This is intentionally explicit and never runs automatically.
        """
        self._ensure_open()

        with self._lock:
            try:
                self.connection.execute(
                    "VACUUM"
                )

            except sqlite3.Error as exc:
                raise SQLiteSpoolerError(
                    "Failed to vacuum SQLite database."
                ) from exc

    def close(
        self,
        *,
        checkpoint: bool = False,
    ) -> None:
        with self._lock:
            if self._closed:
                return

            if self._connection is None:
                self._closed = True
                return

            try:
                if checkpoint and self._wal_mode:
                    try:
                        self.checkpoint("PASSIVE")
                    except SQLiteSpoolerError:
                        self._logger.warning(
                            "SQLite WAL checkpoint failed during close.",
                            exc_info=True,
                        )

                try:
                    self._connection.commit()
                except sqlite3.Error:
                    self._connection.rollback()

                self._connection.close()

            except sqlite3.Error as exc:
                raise SQLiteSpoolerError(
                    "Failed to close SQLite database."
                ) from exc

            finally:
                self._connection = None
                self._repository = None
                self._spooler = None
                self._closed = True

    def __enter__(self) -> "SQLiteSpooler":
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close(
            checkpoint=False
        )

    def _open(self) -> None:
        with self._lock:
            try:
                if self._database_path != ":memory:":
                    path = Path(
                        self._database_path
                    )

                    parent = path.parent

                    if parent and not parent.exists():
                        parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                self._connection = sqlite3.connect(
                    str(self._database_path),
                    timeout=self._timeout,
                    check_same_thread=False,
                )

                self._configure_connection()

                self._repository = SpoolRepository(
                    self._connection,
                    logger_=self._logger,
                )

                self._spooler = Spooler(
                    self._connection,
                    repository=self._repository,
                    logger_=self._logger,
                )

            except (
                OSError,
                sqlite3.Error,
                TypeError,
                ValueError,
            ) as exc:
                if self._connection is not None:
                    try:
                        self._connection.close()
                    except sqlite3.Error:
                        pass

                self._connection = None
                self._repository = None
                self._spooler = None

                raise SQLiteSpoolerError(
                    "Failed to initialize SQLite spooler."
                ) from exc

    def _configure_connection(self) -> None:
        if self._connection is None:
            raise SQLiteSpoolerError(
                "SQLite connection is not initialized."
            )

        connection = self._connection

        try:
            connection.execute(
                "PRAGMA busy_timeout = ?",
                (max(0, int(self._timeout * 1000)),),
            )

            if self._foreign_keys:
                connection.execute(
                    "PRAGMA foreign_keys = ON"
                )
            else:
                connection.execute(
                    "PRAGMA foreign_keys = OFF"
                )

            connection.execute(
                f"PRAGMA synchronous = "
                f"{self._synchronous}"
            )

            if self._wal_mode:
                connection.execute(
                    "PRAGMA journal_mode = WAL"
                )
            else:
                connection.execute(
                    "PRAGMA journal_mode = DELETE"
                )

            connection.commit()

        except sqlite3.Error as exc:
            raise SQLiteSpoolerError(
                "Failed to configure SQLite connection."
            ) from exc

    @staticmethod
    def _normalize_database_path(
        database_path: str | Path,
    ) -> str | Path:
        if isinstance(database_path, Path):
            if str(database_path).strip() == "":
                raise ValueError(
                    "database_path cannot be empty."
                )

            return database_path

        if not isinstance(database_path, str):
            raise TypeError(
                "database_path must be a string or Path."
            )

        value = database_path.strip()

        if not value:
            raise ValueError(
                "database_path cannot be empty."
            )

        if value == ":memory:":
            return value

        return Path(value)

    @staticmethod
    def _normalize_synchronous(
        value: str,
    ) -> str:
        normalized = str(value).upper().strip()

        allowed = {
            "OFF",
            "NORMAL",
            "FULL",
            "EXTRA",
        }

        if normalized not in allowed:
            raise ValueError(
                "Invalid SQLite synchronous mode. "
                f"Expected one of: {sorted(allowed)}."
            )

        return normalized

    def _ensure_open(self) -> None:
        if self._closed:
            raise SQLiteSpoolerError(
                "SQLite spooler is closed."
            )


__all__ = [
    "SQLiteSpooler",
    "SQLiteSpoolerError",
]