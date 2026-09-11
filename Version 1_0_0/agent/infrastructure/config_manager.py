# Path: Version 1_0_0/agent/infrastructure/config_manager.py

from __future__ import annotations

import copy
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Mapping, Optional


JsonDict = dict[str, Any]

_TEMPLATE_RE = re.compile(r"\$\{([^}]+)\}")


def _strip_jsonc(text: str) -> str:
    """
    Remove // and /* */ comments while preserving quoted strings.
    """
    result: list[str] = []

    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    length = len(text)

    while i < length:
        char = text[i]
        next_char = text[i + 1] if i + 1 < length else ""

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
                result.append(char)
            else:
                result.append(" ")
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                result.extend((" ", " "))
                i += 2
            else:
                result.append("\n" if char == "\n" else " ")
                i += 1
            continue

        if in_string:
            result.append(char)

            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False

            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            result.extend((" ", " "))
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            result.extend((" ", " "))
            i += 2
            continue

        result.append(char)
        i += 1

    if in_block_comment:
        raise ValueError("Unterminated block comment in JSONC configuration.")

    return "".join(result)


def _deep_merge(
    base: Mapping[str, Any],
    override: Mapping[str, Any],
) -> JsonDict:
    result: JsonDict = copy.deepcopy(dict(base))

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = _deep_merge(
                result[key],
                value,
            )
        else:
            result[key] = copy.deepcopy(value)

    return result


def _split_path(path: str) -> list[str]:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Configuration path cannot be empty.")

    return [
        part
        for part in path.strip().split(".")
        if part
    ]


def _get_dotted(
    data: Mapping[str, Any],
    path: str,
    default: Any = None,
) -> Any:
    current: Any = data

    for part in _split_path(path):
        if not isinstance(current, Mapping) or part not in current:
            return default

        current = current[part]

    return current


def _set_dotted(
    data: JsonDict,
    path: str,
    value: Any,
) -> None:
    parts = _split_path(path)

    current = data

    for part in parts[:-1]:
        existing = current.get(part)

        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing

        current = existing

    current[parts[-1]] = value


def _resolve_templates(
    value: Any,
    root: Mapping[str, Any],
    *,
    max_depth: int = 10,
) -> Any:
    if max_depth <= 0:
        return value

    if isinstance(value, Mapping):
        return {
            key: _resolve_templates(
                item,
                root,
                max_depth=max_depth - 1,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_templates(
                item,
                root,
                max_depth=max_depth - 1,
            )
            for item in value
        ]

    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        expression = match.group(1).strip()

        # Environment variable:
        # ${ENV:NAME}
        if expression.startswith("ENV:"):
            env_name = expression[4:].strip()
            return os.environ.get(env_name, "")

        # Configuration path:
        # ${kafka.bootstrap_servers}
        resolved = _get_dotted(
            root,
            expression,
            default=match.group(0),
        )

        if resolved is match.group(0):
            return match.group(0)

        if isinstance(resolved, (dict, list)):
            return json.dumps(
                resolved,
                ensure_ascii=False,
            )

        return str(resolved)

    resolved = _TEMPLATE_RE.sub(replace, value)

    if resolved == value:
        return resolved

    return _resolve_templates(
        resolved,
        root,
        max_depth=max_depth - 1,
    )


class ConfigManager:
    """
    Thread-safe application configuration manager.

    Supported legacy behavior:
    - JSON / JSONC configuration files.
    - Defaults.
    - Deep merge.
    - Dotted-path access.
    - Template resolution.
    - File modification detection.
    - Explicit reload.
    """

    def __init__(
        self,
        path: Optional[str | os.PathLike[str]] = None,
        *,
        defaults: Optional[Mapping[str, Any]] = None,
        hot_reload_check_sec: float = 2.0,
    ) -> None:
        self._lock = threading.RLock()

        self._path = Path(path) if path else self._default_path()
        self._defaults: JsonDict = copy.deepcopy(
            dict(defaults or {})
        )

        self._hot_reload_check_sec = max(
            0.0,
            float(hot_reload_check_sec),
        )

        self._data: JsonDict = {}
        self._mtime_ns: Optional[int] = None
        self._last_check_monotonic = 0.0
        self._loaded = False

    @staticmethod
    def _default_path() -> Path:
        return Path(__file__).resolve().parents[1] / "config.json"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def data(self) -> JsonDict:
        self._maybe_reload()

        with self._lock:
            return copy.deepcopy(self._data)

    def load(self, *, force: bool = False) -> JsonDict:
        with self._lock:
            if self._loaded and not force:
                self._maybe_reload_locked()

                return copy.deepcopy(self._data)

            file_data = self._read_file()
            self._data = _deep_merge(
                self._defaults,
                file_data,
            )

            self._data = _resolve_templates(
                self._data,
                self._data,
            )

            self._mtime_ns = self._get_mtime_ns()
            self._last_check_monotonic = self._monotonic()
            self._loaded = True

            return copy.deepcopy(self._data)

    def reload(self) -> JsonDict:
        return self.load(force=True)

    def get(
        self,
        path: str,
        default: Any = None,
    ) -> Any:
        self._maybe_reload()

        with self._lock:
            value = _get_dotted(
                self._data,
                path,
                default,
            )

            return copy.deepcopy(value)

    def require(self, path: str) -> Any:
        value = self.get(
            path,
            default=None,
        )

        if value is None:
            raise KeyError(
                f"Required configuration value is missing: {path}"
            )

        return value

    def set(
        self,
        path: str,
        value: Any,
    ) -> None:
        with self._lock:
            _set_dotted(
                self._data,
                path,
                copy.deepcopy(value),
            )

    def update(
        self,
        values: Mapping[str, Any],
    ) -> None:
        if not isinstance(values, Mapping):
            raise TypeError("Configuration update must be a mapping.")

        with self._lock:
            self._data = _deep_merge(
                self._data,
                values,
            )

    def contains(self, path: str) -> bool:
        self._maybe_reload()

        with self._lock:
            marker = object()

            return (
                _get_dotted(
                    self._data,
                    path,
                    marker,
                )
                is not marker
            )

    def check_for_changes(self) -> bool:
        with self._lock:
            return self._check_for_changes_locked()

    def _maybe_reload(self) -> None:
        with self._lock:
            self._maybe_reload_locked()

    def _maybe_reload_locked(self) -> None:
        if not self._loaded:
            self.load()
            return

        if self._hot_reload_check_sec <= 0:
            return

        now = self._monotonic()

        if (
            now - self._last_check_monotonic
            < self._hot_reload_check_sec
        ):
            return

        self._last_check_monotonic = now

        if self._check_for_changes_locked():
            self._reload_locked()

    def _check_for_changes_locked(self) -> bool:
        current_mtime = self._get_mtime_ns()

        return current_mtime != self._mtime_ns

    def _reload_locked(self) -> None:
        file_data = self._read_file()

        self._data = _deep_merge(
            self._defaults,
            file_data,
        )

        self._data = _resolve_templates(
            self._data,
            self._data,
        )

        self._mtime_ns = self._get_mtime_ns()
        self._loaded = True

    def _read_file(self) -> JsonDict:
        if not self._path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self._path}"
            )

        if not self._path.is_file():
            raise ValueError(
                f"Configuration path is not a file: {self._path}"
            )

        text = self._path.read_text(
            encoding="utf-8",
        )

        if not text.strip():
            return {}

        try:
            parsed = json.loads(
                _strip_jsonc(text),
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON/JSONC configuration: {self._path}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Root configuration value must be an object."
            )

        return parsed

    def _get_mtime_ns(self) -> Optional[int]:
        try:
            return self._path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    @staticmethod
    def _monotonic() -> float:
        import time

        return time.monotonic()

    def __getitem__(self, path: str) -> Any:
        value = self.get(
            path,
            default=None,
        )

        if value is None and not self.contains(path):
            raise KeyError(path)

        return value

    def __contains__(self, path: str) -> bool:
        return self.contains(path)


_config_manager: Optional[ConfigManager] = None
_config_lock = threading.RLock()


def cfg(
    path: Optional[str | os.PathLike[str]] = None,
    *,
    defaults: Optional[Mapping[str, Any]] = None,
    hot_reload_check_sec: float = 2.0,
) -> ConfigManager:
    """
    Return the process-wide configuration singleton.

    A path/defaults supplied on the first call initializes the singleton.
    Subsequent calls return the same instance.
    """
    global _config_manager

    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigManager(
                path=path,
                defaults=defaults,
                hot_reload_check_sec=hot_reload_check_sec,
            )
            _config_manager.load()

        return _config_manager


def reset_cfg() -> None:
    """
    Reset the process-wide configuration singleton.

    Intended for tests and controlled application reinitialization.
    """
    global _config_manager

    with _config_lock:
        _config_manager = None


__all__ = [
    "ConfigManager",
    "cfg",
    "reset_cfg",
]