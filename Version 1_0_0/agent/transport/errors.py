# Path: Version 1_0_0/agent/transport/errors.py

# -*- coding: utf-8 -*-
"""
errors.py
---------
Transport-layer exceptions for Agent.

مسئولیت:
- تعریف خطاهای مربوط به Transport
- فراهم کردن یک hierarchy مشترک برای Kafka / HTTP / سایر Transportها

این فایل:
- Business Logic را نمی‌شناسد
- MetaTrader5 را نمی‌شناسد
- Retry انجام نمی‌دهد
- Persistence انجام نمی‌دهد
- Exception را swallow نمی‌کند
"""

from __future__ import annotations

from typing import Any, Optional


# ============================================================================
# Base Transport Error
# ============================================================================


class TransportError(Exception):
    """Base exception for all transport-layer failures."""

    def __init__(
        self,
        message: str = "transport error",
        *,
        code: Optional[str] = None,
        cause: Optional[BaseException] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        if not isinstance(message, str):
            message = str(message)

        self.message = message
        self.code = code
        self.cause = cause
        self.details = dict(details or {})

        super().__init__(message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"

        return self.message


# ============================================================================
# Configuration
# ============================================================================


class TransportConfigurationError(TransportError):
    """Invalid or incomplete transport configuration."""

    def __init__(
        self,
        message: str = "invalid transport configuration",
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_CONFIGURATION_ERROR",
            details=details,
        )


# ============================================================================
# Lifecycle
# ============================================================================


class TransportLifecycleError(TransportError):
    """Transport could not start, stop, or transition lifecycle state."""

    def __init__(
        self,
        message: str = "transport lifecycle error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_LIFECYCLE_ERROR",
            cause=cause,
            details=details,
        )


class TransportNotStartedError(TransportLifecycleError):
    """Operation requires a started transport."""

    def __init__(
        self,
        message: str = "transport is not started",
    ) -> None:
        super().__init__(
            message,
            details={"state": "not_started"},
        )


class TransportAlreadyStartedError(TransportLifecycleError):
    """Transport was started when the operation expected it to be stopped."""

    def __init__(
        self,
        message: str = "transport is already started",
    ) -> None:
        super().__init__(
            message,
            details={"state": "started"},
        )


# ============================================================================
# Connection
# ============================================================================


class TransportConnectionError(TransportError):
    """Transport connection or connection-state failure."""

    def __init__(
        self,
        message: str = "transport connection error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_CONNECTION_ERROR",
            cause=cause,
            details=details,
        )


class TransportConnectionTimeoutError(
    TransportConnectionError
):
    """Transport connection attempt timed out."""

    def __init__(
        self,
        message: str = "transport connection timed out",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            cause=cause,
        )

        self.code = "TRANSPORT_CONNECTION_TIMEOUT"


# ============================================================================
# Receive / Poll
# ============================================================================


class TransportReceiveError(TransportError):
    """Failure while receiving or polling inbound messages."""

    def __init__(
        self,
        message: str = "transport receive error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_RECEIVE_ERROR",
            cause=cause,
            details=details,
        )


class TransportPollError(TransportReceiveError):
    """Failure while polling for inbound commands."""

    def __init__(
        self,
        message: str = "transport poll error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            cause=cause,
        )

        self.code = "TRANSPORT_POLL_ERROR"


# ============================================================================
# Send
# ============================================================================


class TransportSendError(TransportError):
    """Failure while sending an outbound message."""

    def __init__(
        self,
        message: str = "transport send error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_SEND_ERROR",
            cause=cause,
            details=details,
        )


class TransportFlushError(TransportSendError):
    """Failure while flushing outbound transport messages."""

    def __init__(
        self,
        message: str = "transport flush error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            cause=cause,
        )

        self.code = "TRANSPORT_FLUSH_ERROR"


# ============================================================================
# Serialization
# ============================================================================


class TransportSerializationError(TransportError):
    """Failure while serializing or deserializing transport data."""

    def __init__(
        self,
        message: str = "transport serialization error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_SERIALIZATION_ERROR",
            cause=cause,
            details=details,
        )


class TransportDeserializationError(
    TransportSerializationError
):
    """Failure while decoding an inbound transport message."""

    def __init__(
        self,
        message: str = "transport deserialization error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            cause=cause,
        )

        self.code = "TRANSPORT_DESERIALIZATION_ERROR"


# ============================================================================
# Protocol
# ============================================================================


class TransportProtocolError(TransportError):
    """Message does not satisfy the expected transport protocol."""

    def __init__(
        self,
        message: str = "transport protocol error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_PROTOCOL_ERROR",
            cause=cause,
            details=details,
        )


# ============================================================================
# Authentication / Authorization
# ============================================================================


class TransportAuthenticationError(TransportError):
    """Transport-level authentication failure."""

    def __init__(
        self,
        message: str = "transport authentication failed",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_AUTHENTICATION_ERROR",
            cause=cause,
            details=details,
        )


class TransportAuthorizationError(TransportError):
    """Transport-level authorization failure."""

    def __init__(
        self,
        message: str = "transport authorization failed",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_AUTHORIZATION_ERROR",
            cause=cause,
            details=details,
        )


# ============================================================================
# Acknowledgement
# ============================================================================


class TransportAckError(TransportError):
    """Failure while acknowledging an inbound transport message."""

    def __init__(
        self,
        message: str = "transport acknowledgement error",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_ACK_ERROR",
            cause=cause,
            details=details,
        )


# ============================================================================
# Availability
# ============================================================================


class TransportUnavailableError(TransportError):
    """Transport is currently unavailable."""

    def __init__(
        self,
        message: str = "transport is unavailable",
        *,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="TRANSPORT_UNAVAILABLE",
            cause=cause,
            details=details,
        )


# ============================================================================
# Public API
# ============================================================================


__all__ = [
    "TransportError",
    "TransportConfigurationError",
    "TransportLifecycleError",
    "TransportNotStartedError",
    "TransportAlreadyStartedError",
    "TransportConnectionError",
    "TransportConnectionTimeoutError",
    "TransportReceiveError",
    "TransportPollError",
    "TransportSendError",
    "TransportFlushError",
    "TransportSerializationError",
    "TransportDeserializationError",
    "TransportProtocolError",
    "TransportAuthenticationError",
    "TransportAuthorizationError",
    "TransportAckError",
    "TransportUnavailableError",
]