# Path: Version 1_0_0/agent/persistence/migrations.py

from __future__ import annotations

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence


logger = logging.getLogger(__name__)


@dataclass(frozen=True, order=True)
class Migration:
    """
    Immutable database migration definition.

    Parameters
    ----------
    version:
        Unique monotonically increasing migration version.

    name:
        Human-readable migration name.

    sql:
        SQL script executed when this migration is applied.
    """

    version: int
    name: str
    sql: str

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or self.version <= 0:
            raise ValueError(
                "Migration version must be a positive integer."
            )

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(
                "Migration name must be a non-empty string."
            )

        if not isinstance(self.sql, str) or not self.sql.strip():
            raise ValueError(
                "Migration SQL must be a non-empty string."
            )

    @property
    def checksum(self) -> str:
        """
        SHA-256 checksum of the migration definition.

        The checksum allows us to detect accidental modification of a
        migration that has already been applied.
        """
        source = (
            f"{self.version}\n"
            f"{self.name}\n"
            f"{self.sql}"
        ).encode("utf-8")

        return hashlib.sha256(source).hexdigest()


class MigrationError(RuntimeError):
    """Base exception for persistence migration failures."""


class MigrationIntegrityError(MigrationError):
    """
    Raised when an already-applied migration differs from its current
    definition.
    """


class MigrationRunner:
    """
    SQLite migration runner.

    Responsibilities:
    - Create the migration history table.
    - Validate migration ordering and uniqueness.
    - Apply pending migrations transactionally.
    - Detect modifications to already-applied migrations.

    The runner does not own the database connection. The caller is
    responsible for opening and closing it.
    """

    HISTORY_TABLE = "_agent_schema_migrations"

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        logger_: logging.Logger | None = None,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError(
                "connection must be an sqlite3.Connection."
            )

        self._connection = connection
        self._logger = logger_ or logger

        self._ensure_history_table()

    def migrate(
        self,
        migrations: Iterable[Migration],
    ) -> list[Migration]:
        """
        Validate and apply all pending migrations.

        Returns
        -------
        list[Migration]
            Migrations successfully applied during this invocation.
        """
        ordered = self._normalize_migrations(migrations)
        applied = self.applied_versions()

        self._validate_applied_integrity(
            migrations=ordered,
            applied=applied,
        )

        pending = [
            migration
            for migration in ordered
            if migration.version not in applied
        ]

        if not pending:
            self._logger.debug(
                "Database schema is already up to date."
            )
            return []

        completed: list[Migration] = []

        for migration in pending:
            self._apply_migration(migration)
            completed.append(migration)

        self._logger.info(
            "Applied %d database migration(s).",
            len(completed),
        )

        return completed

    def applied_versions(self) -> dict[int, str]:
        """
        Return {version: checksum} for applied migrations.
        """
        cursor = self._connection.execute(
            f"""
            SELECT version, checksum
            FROM {self.HISTORY_TABLE}
            ORDER BY version ASC
            """
        )

        return {
            int(row[0]): str(row[1])
            for row in cursor.fetchall()
        }

    def applied_migrations(
        self,
    ) -> list[tuple[int, str, str, str]]:
        """
        Return applied migration history.

        Each tuple contains:
            (version, name, checksum, applied_at)
        """
        cursor = self._connection.execute(
            f"""
            SELECT version, name, checksum, applied_at
            FROM {self.HISTORY_TABLE}
            ORDER BY version ASC
            """
        )

        return [
            (
                int(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
            )
            for row in cursor.fetchall()
        ]

    def current_version(self) -> int:
        """
        Return the highest applied migration version.

        Returns 0 when no application migration exists.
        """
        cursor = self._connection.execute(
            f"""
            SELECT COALESCE(MAX(version), 0)
            FROM {self.HISTORY_TABLE}
            """
        )

        row = cursor.fetchone()

        return int(row[0] or 0)

    def _ensure_history_table(self) -> None:
        self._connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.HISTORY_TABLE} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def _apply_migration(
        self,
        migration: Migration,
    ) -> None:
        """
        Apply one migration atomically.

        If SQL execution fails, neither the schema history entry nor the
        transaction is committed.
        """
        self._logger.info(
            "Applying migration %d: %s",
            migration.version,
            migration.name,
        )

        applied_at = datetime.now(
            timezone.utc,
        ).isoformat()

        try:
            with self._connection:
                self._connection.executescript(
                    migration.sql
                )

                self._connection.execute(
                    f"""
                    INSERT INTO {self.HISTORY_TABLE} (
                        version,
                        name,
                        checksum,
                        applied_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        applied_at,
                    ),
                )

        except sqlite3.Error as exc:
            raise MigrationError(
                "Failed to apply migration "
                f"{migration.version} ({migration.name})."
            ) from exc

    @staticmethod
    def _normalize_migrations(
        migrations: Iterable[Migration],
    ) -> Sequence[Migration]:
        result = list(migrations)

        for migration in result:
            if not isinstance(migration, Migration):
                raise TypeError(
                    "All migrations must be Migration instances."
                )

        result.sort(key=lambda item: item.version)

        seen: set[int] = set()

        for migration in result:
            if migration.version in seen:
                raise MigrationError(
                    "Duplicate migration version: "
                    f"{migration.version}"
                )

            seen.add(migration.version)

        return result

    @staticmethod
    def _validate_applied_integrity(
        *,
        migrations: Sequence[Migration],
        applied: dict[int, str],
    ) -> None:
        defined = {
            migration.version: migration
            for migration in migrations
        }

        for version, checksum in applied.items():
            migration = defined.get(version)

            if migration is None:
                continue

            if migration.checksum != checksum:
                raise MigrationIntegrityError(
                    "Applied migration has been modified: "
                    f"version={version}, "
                    f"name={migration.name!r}. "
                    "Create a new migration instead of modifying an "
                    "already-applied migration."
                )


def run_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[Migration],
    *,
    logger_: logging.Logger | None = None,
) -> list[Migration]:
    """
    Convenience helper for one-shot migration execution.
    """
    runner = MigrationRunner(
        connection,
        logger_=logger_,
    )

    return runner.migrate(migrations)


__all__ = [
    "Migration",
    "MigrationError",
    "MigrationIntegrityError",
    "MigrationRunner",
    "run_migrations",
]