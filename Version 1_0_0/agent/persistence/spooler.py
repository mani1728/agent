# Path: Version 1_0_0/agent/persistence/spooler.py

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    SpoolMessage,
    SpoolMessageType,
    SpoolQuery,
    SpoolStatus,
)
from .spool_repository import (
    SpoolMessageNotFoundError,
    SpoolRepository,
    SpoolRepositoryError,
)


logger = logging.getLogger(__name__)


class SpoolerError(RuntimeError):
    """Base exception for spooler failures."""


class Spooler:
    """
    High-level spool service.

    Responsibilities:
    - Persist messages before/while they are handled by higher layers.
    - Retrieve messages from the spool.
    - Manage basic spool state transitions.
    - Provide bounded access to persisted messages.

    This class deliberately does not implement:
    - retry policy
    - backoff/jitter
    - transport delivery
    - circuit breaker
    - idempotency policy
    - retention policy
    - background worker threads
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        repository: Optional[SpoolRepository] = None,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger_ or logger

        try:
            self._repository = (
                repository
                if repository is not None
                else SpoolRepository(
                    connection,
                    logger_=self._logger,
                )
            )
        except (TypeError, SpoolRepositoryError) as exc:
            raise SpoolerError(
                "Failed to initialize spooler."
            ) from exc

    @property
    def repository(self) -> SpoolRepository:
        return self._repository

    def enqueue(
        self,
        *,
        message_id: str,
        correlation_id: Optional[str],
        message_type: SpoolMessageType,
        payload: Any,
        created_time: Optional[datetime] = None,
    ) -> SpoolMessage:
        """
        Create and persist a new pending spool message.
        """
        now = created_time or datetime.now(timezone.utc)

        message = SpoolMessage(
            message_id=message_id,
            correlation_id=correlation_id,
            message_type=message_type,
            payload=payload,
            status=SpoolStatus.PENDING,
            attempt_count=0,
            next_retry_time=None,
            created_time=now,
            updated_time=now,
            last_error=None,
        )

        try:
            self._repository.save(message)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to enqueue spool message."
            ) from exc

        return message

    def enqueue_message(
        self,
        message: SpoolMessage,
    ) -> SpoolMessage:
        """
        Persist an already constructed SpoolMessage.
        """
        try:
            self._repository.save(message)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to enqueue spool message."
            ) from exc

        return message

    def enqueue_many(
        self,
        messages: list[SpoolMessage],
    ) -> list[SpoolMessage]:
        if not messages:
            return []

        try:
            self._repository.save_many(messages)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to enqueue spool messages."
            ) from exc

        return messages

    def get(
        self,
        message_id: str,
    ) -> Optional[SpoolMessage]:
        try:
            return self._repository.get(message_id)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to retrieve spool message."
            ) from exc

    def require(
        self,
        message_id: str,
    ) -> SpoolMessage:
        try:
            return self._repository.require(message_id)
        except SpoolMessageNotFoundError:
            raise
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to retrieve required spool message."
            ) from exc

    def exists(
        self,
        message_id: str,
    ) -> bool:
        try:
            return self._repository.exists(message_id)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to check spool message."
            ) from exc

    def find(
        self,
        query: Optional[SpoolQuery] = None,
    ) -> list[SpoolMessage]:
        try:
            return self._repository.find(query)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to query spool messages."
            ) from exc

    def pending(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        try:
            return self._repository.pending(limit)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to retrieve pending spool messages."
            ) from exc

    def processing(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        try:
            return self._repository.processing(limit)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to retrieve processing spool messages."
            ) from exc

    def failed(
        self,
        limit: int = 100,
    ) -> list[SpoolMessage]:
        try:
            return self._repository.failed(limit)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to retrieve failed spool messages."
            ) from exc

    def mark_processing(
        self,
        message_id: str,
    ) -> SpoolMessage:
        return self._update_state(
            message_id,
            SpoolStatus.PROCESSING,
        )

    def mark_sent(
        self,
        message_id: str,
    ) -> SpoolMessage:
        return self._update_state(
            message_id,
            SpoolStatus.SENT,
        )

    def mark_failed(
        self,
        message_id: str,
        *,
        error: Optional[str] = None,
        next_retry_time: Optional[datetime] = None,
    ) -> SpoolMessage:
        message = self.require(message_id)

        message.mark_failed(
            error=error,
            next_retry_time=next_retry_time,
        )

        self._persist_updated_message(message)

        return message

    def mark_dead(
        self,
        message_id: str,
        *,
        error: Optional[str] = None,
    ) -> SpoolMessage:
        message = self.require(message_id)

        message.mark_dead(error=error)

        self._persist_updated_message(message)

        return message

    def mark_pending(
        self,
        message_id: str,
        *,
        next_retry_time: Optional[datetime] = None,
    ) -> SpoolMessage:
        message = self.require(message_id)

        message.status = SpoolStatus.PENDING
        message.next_retry_time = next_retry_time
        message.updated_time = (
            datetime.now(timezone.utc)
        )

        self._persist_updated_message(message)

        return message

    def update(
        self,
        message: SpoolMessage,
    ) -> SpoolMessage:
        """
        Persist the complete state of an existing message.
        """
        message.updated_time = (
            datetime.now(timezone.utc)
        )

        self._persist_updated_message(message)

        return message

    def delete(
        self,
        message_id: str,
    ) -> bool:
        try:
            return self._repository.delete(message_id)
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to delete spool message."
            ) from exc

    def delete_many(
        self,
        message_ids: list[str],
    ) -> int:
        try:
            return self._repository.delete_many(
                message_ids
            )
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to delete spool messages."
            ) from exc

    def count(
        self,
        *,
        status: Optional[SpoolStatus] = None,
        message_type: Optional[SpoolMessageType] = None,
    ) -> int:
        try:
            return self._repository.count(
                status=status,
                message_type=message_type,
            )
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to count spool messages."
            ) from exc

    def clear(
        self,
        *,
        status: Optional[SpoolStatus] = None,
    ) -> int:
        try:
            return self._repository.clear(
                status=status,
            )
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to clear spool messages."
            ) from exc

    def recover_processing(
        self,
        *,
        limit: int = 100,
    ) -> int:
        """
        Move PROCESSING messages back to PENDING.

        This is a recovery primitive only. It does not decide whether
        a message should be retried or calculate any backoff.
        """
        messages = self.processing(limit)

        recovered = 0

        for message in messages:
            message.status = SpoolStatus.PENDING
            message.updated_time = (
                datetime.now(timezone.utc)
            )

            try:
                updated = self._repository.update(
                    message
                )
            except SpoolRepositoryError as exc:
                raise SpoolerError(
                    "Failed to recover processing message."
                ) from exc

            if updated:
                recovered += 1

        return recovered

    def _update_state(
        self,
        message_id: str,
        status: SpoolStatus,
    ) -> SpoolMessage:
        message = self.require(message_id)

        if status == SpoolStatus.PROCESSING:
            message.mark_processing()

        elif status == SpoolStatus.SENT:
            message.mark_sent()

        else:
            message.status = status
            message.updated_time = (
                datetime.now(timezone.utc)
            )

        self._persist_updated_message(message)

        return message

    def _persist_updated_message(
        self,
        message: SpoolMessage,
    ) -> None:
        try:
            updated = self._repository.update(
                message
            )
        except SpoolRepositoryError as exc:
            raise SpoolerError(
                "Failed to persist spool message state."
            ) from exc

        if not updated:
            raise SpoolerError(
                f"Spool message does not exist: "
                f"{message.message_id}"
            )


__all__ = [
    "Spooler",
    "SpoolerError",
]