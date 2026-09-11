# Path: Version 1_0_0/agent/infrastructure/config_logging.py

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import socket
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional


DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "logs/app.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3


SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "client_key",
    "authorization",
    "signature",
    "sig",
    "hmac",
}


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower()

    if normalized in SENSITIVE_KEYS:
        return True

    return any(
        marker in normalized
        for marker in (
            "password",
            "passwd",
            "secret",
            "private_key",
            "auth_token",
            "access_token",
        )
    )


def redact(value: Any) -> Any:
    """
    Recursively redact common credential/token fields.

    This is intended as a defensive logging boundary and should not be
    considered a substitute for avoiding sensitive data in log messages.
    """
    if isinstance(value, Mapping):
        return {
            str(key): (
                "***REDACTED***"
                if _is_sensitive_key(key)
                else redact(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            redact(item)
            for item in value
        ]

    if isinstance(value, bytes):
        return "<bytes>"

    return value


class JsonFormatter(logging.Formatter):
    """
    Compact structured JSON formatter.
    """

    def __init__(
        self,
        *,
        include_hostname: bool = True,
    ) -> None:
        super().__init__()
        self._hostname = (
            socket.gethostname()
            if include_hostname
            else None
        )

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc,
        ).isoformat()

        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self._hostname:
            payload["hostname"] = self._hostname

        if record.module:
            payload["module"] = record.module

        if record.funcName:
            payload["function"] = record.funcName

        if record.lineno:
            payload["line"] = record.lineno

        if record.exc_info:
            payload["exception"] = "".join(
                traceback.format_exception(
                    *record.exc_info,
                )
            )

        extra = getattr(
            record,
            "log_extra",
            None,
        )

        if isinstance(extra, Mapping):
            payload["extra"] = redact(extra)

        return json.dumps(
            redact(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


class PlainFormatter(logging.Formatter):
    """
    Human-readable formatter for console/file logs.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt=(
                "%(asctime)s | %(levelname)s | "
                "%(name)s | %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def _normalize_level(level: Any) -> int:
    if isinstance(level, int):
        return level

    normalized = str(
        level or DEFAULT_LOG_LEVEL
    ).strip().upper()

    value = getattr(
        logging,
        normalized,
        None,
    )

    if not isinstance(value, int):
        raise ValueError(
            f"Invalid logging level: {level!r}"
        )

    return value


def _as_bool(
    value: Any,
    default: bool,
) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return True

        if normalized in {
            "0",
            "false",
            "no",
            "off",
        }:
            return False

    return bool(value)


def _config_get(
    config: Any,
    path: str,
    default: Any = None,
) -> Any:
    if config is None:
        return default

    getter = getattr(
        config,
        "get",
        None,
    )

    if callable(getter):
        try:
            return getter(
                path,
                default,
            )
        except TypeError:
            try:
                return getter(path)
            except Exception:
                return default

    if isinstance(config, Mapping):
        current: Any = config

        for part in path.split("."):
            if not isinstance(current, Mapping):
                return default

            if part not in current:
                return default

            current = current[part]

        return current

    return default


def _resolve_log_path(
    path: str | os.PathLike[str],
) -> Path:
    path_obj = Path(path)

    if path_obj.is_absolute():
        return path_obj

    return Path.cwd() / path_obj


def _safe_mkdir(path: Path) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def _clear_managed_handlers(
    logger: logging.Logger,
) -> None:
    for handler in list(logger.handlers):
        if getattr(
            handler,
            "_agent_managed",
            False,
        ):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def _mark_managed(
    handler: logging.Handler,
) -> logging.Handler:
    setattr(
        handler,
        "_agent_managed",
        True,
    )
    return handler


def setup_logging(
    config: Any = None,
    *,
    logger_name: str = "",
) -> logging.Logger:
    """
    Configure application logging.

    Supported configuration paths:
        logging.level
        logging.json
        logging.file_enabled
        logging.file
        logging.max_bytes
        logging.backup_count

    The function is intentionally compatible with both ConfigManager and
    plain dictionaries.
    """
    level = _normalize_level(
        _config_get(
            config,
            "logging.level",
            DEFAULT_LOG_LEVEL,
        )
    )

    json_enabled = _as_bool(
        _config_get(
            config,
            "logging.json",
            False,
        ),
        False,
    )

    file_enabled = _as_bool(
        _config_get(
            config,
            "logging.file_enabled",
            True,
        ),
        True,
    )

    file_path = _config_get(
        config,
        "logging.file",
        DEFAULT_LOG_FILE,
    )

    max_bytes = int(
        _config_get(
            config,
            "logging.max_bytes",
            DEFAULT_MAX_BYTES,
        )
    )

    backup_count = int(
        _config_get(
            config,
            "logging.backup_count",
            DEFAULT_BACKUP_COUNT,
        )
    )

    if max_bytes < 0:
        raise ValueError(
            "logging.max_bytes cannot be negative."
        )

    if backup_count < 0:
        raise ValueError(
            "logging.backup_count cannot be negative."
        )

    root_logger = logging.getLogger(
        logger_name,
    )

    root_logger.setLevel(level)
    root_logger.propagate = False

    _clear_managed_handlers(root_logger)

    if json_enabled:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainFormatter()

    console_handler = _mark_managed(
        logging.StreamHandler()
    )

    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    if file_enabled:
        resolved_path = _resolve_log_path(
            file_path
        )

        _safe_mkdir(resolved_path)

        file_handler = _mark_managed(
            logging.handlers.RotatingFileHandler(
                filename=resolved_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        )

        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

    _configure_noisy_loggers()

    return root_logger


def _configure_noisy_loggers() -> None:
    """
    Keep third-party networking/Kafka logs quieter than application logs.
    """
    logging.getLogger(
        "confluent_kafka"
    ).setLevel(logging.WARNING)

    logging.getLogger(
        "urllib3"
    ).setLevel(logging.WARNING)


def get_logger(
    name: Optional[str] = None,
) -> logging.Logger:
    return logging.getLogger(
        name or __name__
    )


def log_extra(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    extra: Optional[Mapping[str, Any]] = None,
    exc_info: bool = False,
) -> None:
    """
    Structured logging helper.

    Extra fields are placed under `log_extra` and recursively redacted.
    """
    safe_extra = redact(
        dict(extra or {})
    )

    logger.log(
        level,
        message,
        extra={
            "log_extra": safe_extra,
        },
        exc_info=exc_info,
    )


def shutdown_logging() -> None:
    """
    Flush and close all root logging handlers.

    Intended for final application shutdown.
    """
    logging.shutdown()


__all__ = [
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_FILE",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_BACKUP_COUNT",
    "JsonFormatter",
    "PlainFormatter",
    "redact",
    "setup_logging",
    "get_logger",
    "log_extra",
    "shutdown_logging",
]