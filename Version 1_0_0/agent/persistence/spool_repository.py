# Path: Version 1_0_0/agent/persistence/spool_repository.py

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    SpoolMessage,
    SpoolMessageType,
    SpoolQuery,
    SpoolStatus,
)


logger = logging.getLogger(__name__)


class SpoolRepositoryError(RuntimeError):
    """Base exception for spool repository failures."""


class SpoolMessageNotFoundError(SpoolRepositoryError):
    """Raised when a requested spool message does not exist."""


class SpoolRepository:
    """
    SQLite repository for persisted spool messages.

    Responsibilities:
    - Store spool messages.
    - Retrieve messages by ID/correlation/status/type.
    - Update message state.
    - Delete messages.
    - Provide bounded queries for recovery/retry layers.

    This class does not implement retry policy, backoff, circuit breakers,
    transport delivery, or business logic.
    """

    TABLE_NAME = "agent_spool_messages"

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError(
                "connection must be an sqlite3.Connection."
            )

        self._connection = connection
        self._logger = logger_ or logger
        self._lock = threading.RLock()

        self._configure_connection()
        self._ensure_table()

    def save(
        self,
        message: SpoolMessage,
    ) -> None:
        """
        Insert a new spool message.

        Raises SpoolRepositoryError if the message ID already exists.
        """
        self._validate_message(message)

        payload = self._serialize_payload(
            message.payload
        )

        with self._lock:
            try:
                with self._connection:
                    self._connection.execute(
                        f"""
                        INSERT INTO {self.TABLE_NAME} (
                            message_id,
                            correlation_id,
                            message_type,
                            payload,
                            status,
                            attempt_count,
                            next_retry_time,
                            created_time,
                            updated_time,
                            last_error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._message_values(
                            message,
                            payload,
                        ),
                    )

            except sqlite3.IntegrityError as exc:
                raise SpoolRepositoryError(
                    f"Spool message already exists: "
                    f"{message.message_id}"
                ) from exc

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to save spool message."
                ) from exc

    def save_many(
        self,
        messages: list[SpoolMessage],
    ) -> None:
        """
        Insert multiple messages atomically.
        """
        for message in messages:
            self._validate_message(message)

        if not messages:
            return

        rows = [
            self._message_values(
                message,
                self._serialize_payload(
                    message.payload
                ),
            )
            for message in messages
        ]

        with self._lock:
            try:
                with self._connection:
                    self._connection.executemany(
                        f"""
                        INSERT INTO {self.TABLE_NAME} (
                            message_id,
                            correlation_id,
                            message_type,
                            payload,
                            status,
                            attempt_count,
                            next_retry_time,
                            created_time,
                            updated_time,
                            last_error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )

            except sqlite3.IntegrityError as exc:
                raise SpoolRepositoryError(
                    "One or more spool message IDs "
                    "already exist."
                ) from exc

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to save spool messages."
                ) from exc

    def get(
        self,
        message_id: str,
    ) -> Optional[SpoolMessage]:
        if not message_id:
            raise ValueError(
                "message_id cannot be empty."
            )

        with self._lock:
            try:
                cursor = self._connection.execute(
                    f"""
                    SELECT
                        message_id,
                        correlation_id,
                        message_type,
                        payload,
                        status,
                        attempt_count,
                        next_retry_time,
                        created_time,
                        updated_time,
                        last_error
                    FROM {self.TABLE_NAME}
                    WHERE message_id = ?
                    """,
                    (message_id,),
                )

                row = cursor.fetchone()

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to retrieve spool message."
                ) from exc

        if row is None:
            return None

        return self._row_to_message(row)

    def require(
        self,
        message_id: str,
    ) -> SpoolMessage:
        message = self.get(message_id)

        if message is None:
            raise SpoolMessageNotFoundError(
                f"Spool message not found: {message_id}"
            )

        return message

    def exists(
        self,
        message_id: str,
    ) -> bool:
        if not message_id:
            raise ValueError(
                "message_id cannot be empty."
            )

        with self._lock:
            try:
                cursor = self._connection.execute(
                    f"""
                    SELECT 1
                    FROM {self.TABLE_NAME}
                    WHERE message_id = ?
                    LIMIT 1
                    """,
                    (message_id,),
                )

                return cursor.fetchone() is not None

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to check spool message."
                ) from exc

    def find(
        self,
        query: Optional[SpoolQuery] = None,
    ) -> list[SpoolMessage]:
        query = query or SpoolQuery()

        conditions: list[str] = []
        parameters: list[Any] = []

        if query.status is not None:
            conditions.append("status = ?")
            parameters.append(
                query.status.value
            )

        if query.message_type is not None:
            conditions.append("message_type = ?")
            parameters.append(
                query.message_type.value
            )

        if query.correlation_id is not None:
            conditions.append("correlation_id = ?")
            parameters.append(
                query.correlation_id
            )

        if query.before is not None:
            conditions.append("created_time < ?")
            parameters.append(
                query.before.isoformat()
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE " + " AND ".join(conditions)
            )

        sql = f"""
            SELECT
                message_id,
                correlation_id,
                message_type,
                payload,
                status,
                attempt_count,
                next_retry_time,
                created_time,
                updated_time,
                last_error
            FROM {self.TABLE_NAME}
            {where_clause}
            ORDER BY created_time ASC
            LIMIT ?
        """

        parameters.append(query.limit)

        with self._lock:
            try:
                cursor = self._connection.execute(
                    sql,
                    tuple(parameters),
                )

                rows = cursor.fetchall()

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to query spool messages."
                ) from exc

        return [
            self._row_to_message(row)
            for row in rows
        ]

    def pending(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.find(
            SpoolQuery(
                status=SpoolStatus.PENDING,
                limit=limit,
            )
        )

    def failed(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.find(
            SpoolQuery(
                status=SpoolStatus.FAILED,
                limit=limit,
            )
        )

    def processing(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        return self.find(
            SpoolQuery(
                status=SpoolStatus.PROCESSING,
                limit=limit,
            )
        )

    def update(
        self,
        message: SpoolMessage,
    ) -> bool:
        """
        Persist the complete current state of a message.

        Returns True when a row was updated, False when it did not exist.
        """
        self._validate_message(message)

        payload = self._serialize_payload(
            message.payload
        )

        with self._lock:
            try:
                with self._connection:
                    cursor = self._connection.execute(
                        f"""
                        UPDATE {self.TABLE_NAME}
                        SET
                            correlation_id = ?,
                            message_type = ?,
                            payload = ?,
                            status = ?,
                            attempt_count = ?,
                            next_retry_time = ?,
                            created_time = ?,
                            updated_time = ?,
                            last_error = ?
                        WHERE message_id = ?
                        """,
                        (
                            message.correlation_id,
                            message.message_type.value,
                            payload,
                            message.status.value,
                            message.attempt_count,
                            self._datetime_to_string(
                                message.next_retry_time
                            ),
                            self._datetime_to_string(
                                message.created_time
                            ),
                            self._datetime_to_string(
                                message.updated_time
                            ),
                            message.last_error,
                            message.message_id,
                        ),
                    )

                return cursor.rowcount > 0

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to update spool message."
                ) from exc

    def delete(
        self,
        message_id: str,
    ) -> bool:
        if not message_id:
            raise ValueError(
                "message_id cannot be empty."
            )

        with self._lock:
            try:
                with self._connection:
                    cursor = self._connection.execute(
                        f"""
                        DELETE FROM {self.TABLE_NAME}
                        WHERE message_id = ?
                        """,
                        (message_id,),
                    )

                return cursor.rowcount > 0

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to delete spool message."
                ) from exc

    def delete_many(
        self,
        message_ids: list[str],
    ) -> int:
        if not message_ids:
            return 0

        normalized = [
            message_id
            for message_id in message_ids
            if message_id
        ]

        if not normalized:
            return 0

        with self._lock:
            try:
                with self._connection:
                    cursor = self._connection.executemany(
                        f"""
                        DELETE FROM {self.TABLE_NAME}
                        WHERE message_id = ?
                        """,
                        [
                            (message_id,)
                            for message_id in normalized
                        ],
                    )

                return cursor.rowcount

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to delete spool messages."
                ) from exc

    def count(
        self,
        *,
        status: Optional[SpoolStatus] = None,
        message_type: Optional[SpoolMessageType] = None,
    ) -> int:
        conditions: list[str] = []
        parameters: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)

        if message_type is not None:
            conditions.append("message_type = ?")
            parameters.append(message_type.value)

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE " + " AND ".join(conditions)
            )

        with self._lock:
            try:
                cursor = self._connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {self.TABLE_NAME}
                    {where_clause}
                    """,
                    tuple(parameters),
                )

                row = cursor.fetchone()

                return int(row[0] or 0)

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to count spool messages."
                ) from exc

    def clear(
        self,
        *,
        status: Optional[SpoolStatus] = None,
    ) -> int:
        """
        Delete messages, optionally restricted by status.

        This is intentionally explicit; no automatic retention policy is
        applied here.
        """
        if status is None:
            sql = f"DELETE FROM {self.TABLE_NAME}"
            parameters: tuple[Any, ...] = ()
        else:
            sql = (
                f"DELETE FROM {self.TABLE_NAME} "
                "WHERE status = ?"
            )
            parameters = (status.value,)

        with self._lock:
            try:
                with self._connection:
                    cursor = self._connection.execute(
                        sql,
                        parameters,
                    )

                return cursor.rowcount

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to clear spool messages."
                ) from exc

    def _ensure_table(self) -> None:
        with self._lock:
            try:
                self._connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                        message_id TEXT PRIMARY KEY,
                        correlation_id TEXT,
                        message_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL,
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        next_retry_time TEXT,
                        created_time TEXT NOT NULL,
                        updated_time TEXT NOT NULL,
                        last_error TEXT
                    )
                    """
                )

                self._connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS
                    idx_{self.TABLE_NAME}_status
                    ON {self.TABLE_NAME} (status)
                    """
                )

                self._connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS
                    idx_{self.TABLE_NAME}_correlation
                    ON {self.TABLE_NAME} (correlation_id)
                    """
                )

                self._connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS
                    idx_{self.TABLE_NAME}_retry
                    ON {self.TABLE_NAME} (next_retry_time)
                    """
                )

                self._connection.commit()

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to initialize spool repository."
                ) from exc

    def _configure_connection(self) -> None:
        with self._lock:
            try:
                self._connection.execute(
                    "PRAGMA foreign_keys = ON"
                )

            except sqlite3.Error as exc:
                raise SpoolRepositoryError(
                    "Failed to configure SQLite connection."
                ) from exc

    @staticmethod
    def _validate_message(
        message: SpoolMessage,
    ) -> None:
        if not isinstance(message, SpoolMessage):
            raise TypeError(
                "message must be a SpoolMessage."
            )

    @staticmethod
    def _serialize_payload(
        payload: Any,
    ) -> str:
        try:
            return json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

        except (TypeError, ValueError) as exc:
            raise SpoolRepositoryError(
                "Spool payload is not JSON serializable."
            ) from exc

    @staticmethod
    def _deserialize_payload(
        payload: str,
    ) -> Any:
        try:
            return json.loads(payload)

        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SpoolRepositoryError(
                "Persisted spool payload is invalid JSON."
            ) from exc

    @classmethod
    def _message_values(
        cls,
        message: SpoolMessage,
        payload: str,
    ) -> tuple[Any, ...]:
        return (
            message.message_id,
            message.correlation_id,
            message.message_type.value,
            payload,
            message.status.value,
            message.attempt_count,
            cls._datetime_to_string(
                message.next_retry_time
            ),
            cls._datetime_to_string(
                message.created_time
            ),
            cls._datetime_to_string(
                message.updated_time
            ),
            message.last_error,
        )

    @staticmethod
    def _datetime_to_string(
        value: Optional[datetime],
    ) -> Optional[str]:
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError(
                "Persisted datetime must be timezone-aware."
            )

        return value.isoformat()

    @classmethod
    def _string_to_datetime(
        cls,
        value: Optional[str],
    ) -> Optional[datetime]:
        if value is None:
            return None

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise SpoolRepositoryError(
                "Persisted datetime is invalid."
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    @classmethod
    def _row_to_message(
        cls,
        row: tuple[Any, ...],
    ) -> SpoolMessage:
        if len(row) != 10:
            raise SpoolRepositoryError(
                "Invalid spool database row."
            )

        return SpoolMessage(
            message_id=str(row[0]),
            correlation_id=(
                str(row[1])
                if row[1] is not None
                else None
            ),
            message_type=SpoolMessageType(
                row[2]
            ),
            payload=cls._deserialize_payload(
                row[3]
            ),
            status=SpoolStatus(
                row[4]
            ),
            attempt_count=int(row[5]),
            next_retry_time=cls._string_to_datetime(
                row[6]
            ),
            created_time=(
                cls._string_to_datetime(row[7])
                or datetime.now(timezone.utc)
            ),
            updated_time=(
                cls._string_to_datetime(row[8])
                or datetime.now(timezone.utc)
            ),
            last_error=(
                str(row[9])
                if row[9] is not None
                else None
            ),
        )


__all__ = [
    "SpoolRepository",
    "SpoolRepositoryError",
    "SpoolMessageNotFoundError",
]