# Path: Version 1_0_0/agent/security/redaction.py

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence, Set
from typing import Any


DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "authorization",
        "proxy_authorization",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "client_key",
        "key_password",
        "hmac_secret",
        "signature",
        "sig",
        "credential",
        "credentials",
    }
)

DEFAULT_SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "auth_token",
        "access_token",
        "refresh_token",
        "x-api-key",
        "x-auth-token",
        "x-signature",
    }
)

REDACTED_VALUE = "<redacted>"


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _normalized_sensitive_keys(
    sensitive_keys: Sequence[str] | Set[str] | None,
) -> frozenset[str]:
    if sensitive_keys is None:
        return DEFAULT_SENSITIVE_KEYS

    return frozenset(
        _normalize_key(key)
        for key in sensitive_keys
    )


def _is_sensitive_key(
    key: Any,
    sensitive_keys: frozenset[str],
) -> bool:
    normalized = _normalize_key(key)

    if normalized in sensitive_keys:
        return True

    # Catch common compound names such as:
    # db_password, bearer_token, signing_private_key.
    for sensitive in sensitive_keys:
        if not sensitive:
            continue

        if (
            normalized.endswith(f"_{sensitive}")
            or normalized.startswith(f"{sensitive}_")
            or f"_{sensitive}_" in normalized
        ):
            return True

    return False


def redact(
    value: Any,
    *,
    sensitive_keys: Sequence[str] | Set[str] | None = None,
    replacement: str = REDACTED_VALUE,
    max_depth: int = 20,
) -> Any:
    """
    Recursively redact sensitive values.

    Supported structures:
      - mappings/dicts
      - lists
      - tuples
      - sets/frozensets
      - JSON-compatible scalar values

    Unknown objects are returned unchanged rather than converted implicitly.
    """
    if max_depth < 0:
        return replacement

    keys = _normalized_sensitive_keys(sensitive_keys)

    return _redact_value(
        value,
        sensitive_keys=keys,
        replacement=replacement,
        depth=0,
        max_depth=max_depth,
    )


def _redact_value(
    value: Any,
    *,
    sensitive_keys: frozenset[str],
    replacement: str,
    depth: int,
    max_depth: int,
) -> Any:
    if depth > max_depth:
        return replacement

    if isinstance(value, Mapping):
        result: dict[Any, Any] = {}

        for key, item in value.items():
            if _is_sensitive_key(
                key,
                sensitive_keys,
            ):
                result[key] = replacement
            else:
                result[key] = _redact_value(
                    item,
                    sensitive_keys=sensitive_keys,
                    replacement=replacement,
                    depth=depth + 1,
                    max_depth=max_depth,
                )

        return result

    if isinstance(value, list):
        return [
            _redact_value(
                item,
                sensitive_keys=sensitive_keys,
                replacement=replacement,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _redact_value(
                item,
                sensitive_keys=sensitive_keys,
                replacement=replacement,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in value
        )

    if isinstance(value, set):
        return {
            _redact_value(
                item,
                sensitive_keys=sensitive_keys,
                replacement=replacement,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in value
        }

    if isinstance(value, frozenset):
        return frozenset(
            _redact_value(
                item,
                sensitive_keys=sensitive_keys,
                replacement=replacement,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in value
        )

    return value


def redact_mapping(
    value: Mapping[str, Any],
    *,
    sensitive_keys: Sequence[str] | Set[str] | None = None,
    replacement: str = REDACTED_VALUE,
) -> dict[str, Any]:
    """
    Convenience wrapper for dictionary-like values.
    """
    result = redact(
        value,
        sensitive_keys=sensitive_keys,
        replacement=replacement,
    )

    return dict(result)


def redact_headers(
    headers: Mapping[Any, Any],
    *,
    sensitive_headers: Sequence[str] | Set[str] | None = None,
    replacement: str = REDACTED_VALUE,
) -> dict[Any, Any]:
    """
    Redact HTTP/Kafka-style headers.

    Header names are compared case-insensitively and with '-'/'_' treated
    equivalently.
    """
    configured = (
        DEFAULT_SENSITIVE_HEADERS
        if sensitive_headers is None
        else frozenset(
            _normalize_key(header)
            for header in sensitive_headers
        )
    )

    result: dict[Any, Any] = {}

    for key, value in headers.items():
        if _normalize_key(key) in configured:
            result[key] = replacement
        else:
            result[key] = value

    return result


def redact_text(
    text: str,
    *,
    sensitive_keys: Sequence[str] | Set[str] | None = None,
    replacement: str = REDACTED_VALUE,
) -> str:
    """
    Best-effort redaction for JSON text.

    Valid JSON objects are parsed and recursively redacted. Non-JSON text is
    returned unchanged because blind string replacement can corrupt normal
    content or produce misleading redaction.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return text

    redacted = redact(
        parsed,
        sensitive_keys=sensitive_keys,
        replacement=replacement,
    )

    return json.dumps(
        redacted,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def safe_json(
    value: Any,
    *,
    sensitive_keys: Sequence[str] | Set[str] | None = None,
    replacement: str = REDACTED_VALUE,
) -> str:
    """
    Serialize a value to JSON after redacting sensitive fields.
    """
    redacted = redact(
        value,
        sensitive_keys=sensitive_keys,
        replacement=replacement,
    )

    return json.dumps(
        redacted,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


class RedactionFilter(logging.Filter):
    """
    Logging filter that redacts structured mapping arguments and messages.

    The filter mutates the LogRecord arguments only after creating a
    redacted copy, so the original application objects are not modified.
    """

    def __init__(
        self,
        name: str = "",
        *,
        sensitive_keys: Sequence[str] | Set[str] | None = None,
        replacement: str = REDACTED_VALUE,
    ) -> None:
        super().__init__(name)

        self._sensitive_keys = (
            _normalized_sensitive_keys(sensitive_keys)
        )
        self._replacement = replacement

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        if record.args:
            if isinstance(record.args, Mapping):
                record.args = redact(
                    record.args,
                    sensitive_keys=self._sensitive_keys,
                    replacement=self._replacement,
                )
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact(
                        item,
                        sensitive_keys=self._sensitive_keys,
                        replacement=self._replacement,
                    )
                    for item in record.args
                )

        return True


__all__ = [
    "DEFAULT_SENSITIVE_HEADERS",
    "DEFAULT_SENSITIVE_KEYS",
    "REDACTED_VALUE",
    "RedactionFilter",
    "redact",
    "redact_headers",
    "redact_mapping",
    "redact_text",
    "safe_json",
]