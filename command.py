"""Unified CommandEnvelope dataclass (single source of truth)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.contracts.models import (
    JsonDict, Params, parse_json_or_literal, safe_int, utc_now_iso,
)
from agent.contracts.schemas import (
    KNOWN_COMMAND_SCHEMAS, SCHEMA_VERSION_COMMAND, assert_known_schema,
)

_METHOD_KEYS = ("method", "target_method", "func", "name")

@dataclass
class CommandEnvelope:
    target_class: str
    target_method: str
    params: Params = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 1
    request_index: int = 0
    auth_token: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: str = SCHEMA_VERSION_COMMAND
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target_class, str) or not self.target_class.strip():
            raise ValueError("target_class is required")
        if not isinstance(self.target_method, str) or not self.target_method.strip():
            raise ValueError("target_method is required")
        if not isinstance(self.params, dict):
            raise ValueError("params must be a dict")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority < 0:
            raise ValueError("priority must be a non-negative integer")
        assert_known_schema(self.schema_version, KNOWN_COMMAND_SCHEMAS, "command")

    def to_dict(self) -> JsonDict:
        return {
            "target_class": self.target_class,
            "target_method": self.target_method,
            "params": self.params,
            "command_id": self.command_id,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "request_index": self.request_index,
            "auth_token": self.auth_token,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: JsonDict) -> "CommandEnvelope":
        known = {
            "target_class", "target_method", "params", "command_id",
            "correlation_id", "priority", "request_index", "auth_token",
            "created_at", "schema_version", "metadata",
        }
        data = dict(d)
        extra = {k: v for k, v in data.items() if k not in known}
        for k in extra:
            data.pop(k)
        if extra:
            meta = data.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["_extra"] = {**(meta.get("_extra") or {}), **extra}
            data["metadata"] = meta
        return cls(**data)

    @classmethod
    def from_legacy_item(
        cls,
        item: JsonDict,
        *,
        target_class: str,
        correlation_id: str,
        priority: int = 1,
        request_index: int = 0,
        auth_token: Optional[str] = None,
        metadata: Optional[JsonDict] = None,
    ) -> "CommandEnvelope":
        if not isinstance(item, dict):
            raise ValueError("legacy item must be a dict")
        method = None
        for key in _METHOD_KEYS:
            if isinstance(item.get(key), str) and item.get(key):
                method = item[key]
                break
        if not method:
            raise ValueError("legacy item is missing a method key (method/target_method/func/name)")
        params = item.get("params", {})
        if isinstance(params, str):
            params = parse_json_or_literal(params, {})
        if not isinstance(params, dict):
            params = {}
        return cls(
            target_class=target_class,
            target_method=method,
            params=params,
            correlation_id=correlation_id,
            priority=priority,
            request_index=request_index,
            auth_token=auth_token,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_legacy_message(
        cls,
        key: str,
        value: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> List["CommandEnvelope"]:
        headers = headers or {}
        target_class = (key or "").strip() or "Mt5_Manager"
        corr_id = headers.get("corr_id") or headers.get("correlation_id") or str(uuid.uuid4())
        auth_token = headers.get("auth_token")
        priority = safe_int(headers.get("priority"), 1)
        meta_keys = ("partition", "offset", "topic")
        metadata = {k: headers[k] for k in meta_keys if k in headers}

        payload = value if isinstance(value, dict) else parse_json_or_literal(value, {})
        if not isinstance(payload, dict):
            payload = {}

        if "items" in payload and isinstance(payload["items"], list):
            items = payload["items"]
        elif any(k in payload for k in _METHOD_KEYS):
            items = [payload]
        elif isinstance(value, list):
            items = value
        else:
            items = []

        envelopes: List[CommandEnvelope] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                item = {"method": str(item)}
            envelopes.append(
                cls.from_legacy_item(
                    item,
                    target_class=target_class,
                    correlation_id=corr_id,
                    priority=priority,
                    request_index=idx,
                    auth_token=auth_token,
                    metadata=metadata,
                )
            )
        return envelopes
