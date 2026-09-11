# Path: Version 1_0_0/agent/core/result_builder.py

# -*- coding: utf-8 -*-
"""
result_builder.py
-----------------
Centralized response/result construction for Agent Core.

مسئولیت:
- ساخت ResponseEnvelope موفق
- ساخت ResponseEnvelope خطا
- نگه‌داشتن metadata استاندارد execution

این فایل:
- Kafka/HTTP را نمی‌شناسد
- Transport را نمی‌شناسد
- Retry را انجام نمی‌دهد
- Persistence را انجام نمی‌دهد
- Exception را به شکل خودکار swallow نمی‌کند
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope


SCHEMA_VERSION = "Mt5ResultV1"


class ResultBuilder:
    """
    سازنده‌ی transport-independent برای ResponseEnvelope.
    """

    def __init__(
        self,
        schema_version: str = SCHEMA_VERSION,
    ) -> None:
        if not isinstance(schema_version, str) or not schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")

        self._schema_version = schema_version.strip()

    # ------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------

    def success(
        self,
        command: CommandEnvelope,
        data: Any = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ResponseEnvelope:
        """
        Build a successful response for a command.
        """

        response_metadata = self._build_metadata(
            command=command,
            metadata=metadata,
        )

        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data=data,
            schema_version=self._schema_version,
            metadata=response_metadata,
        )

    # ------------------------------------------------------------------
    # Error
    # ------------------------------------------------------------------

    def error(
        self,
        command: CommandEnvelope,
        error_code: str,
        error_message: str,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ResponseEnvelope:
        """
        Build an error response for a command.
        """

        if not isinstance(error_code, str) or not error_code.strip():
            raise ValueError("error_code must be a non-empty string")

        if not isinstance(error_message, str):
            error_message = str(error_message)

        response_metadata = self._build_metadata(
            command=command,
            metadata=metadata,
        )

        return ResponseEnvelope.error(
            correlation_id=command.correlation_id,
            error_code=error_code.strip(),
            error_message=error_message,
            schema_version=self._schema_version,
            metadata=response_metadata,
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metadata(
        *,
        command: CommandEnvelope,
        metadata: Optional[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """
        Build response metadata without copying sensitive command data.

        فقط اطلاعات routing غیرحساس وارد metadata می‌شود.
        """

        result: dict[str, Any] = {
            "target_class": command.target_class,
            "target_method": command.target_method,
        }

        if metadata:
            result.update(dict(metadata))

        return result


# ----------------------------------------------------------------------
# Module-level compatibility helpers
# ----------------------------------------------------------------------

_default_builder = ResultBuilder()


def build_success(
    command: CommandEnvelope,
    data: Any = None,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> ResponseEnvelope:
    """
    Compatibility helper for callers that prefer a function API.
    """

    return _default_builder.success(
        command,
        data,
        metadata=metadata,
    )


def build_error(
    command: CommandEnvelope,
    error_code: str,
    error_message: str,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> ResponseEnvelope:
    """
    Compatibility helper for callers that prefer a function API.
    """

    return _default_builder.error(
        command,
        error_code,
        error_message,
        metadata=metadata,
    )


__all__ = [
    "SCHEMA_VERSION",
    "ResultBuilder",
    "build_success",
    "build_error",
]