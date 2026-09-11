# Path: Version 1_0_0/agent/transport/factory.py

# -*- coding: utf-8 -*-
"""
factory.py
----------
Transport factory for Agent.

مسئولیت:
- ساخت Transport مناسب بر اساس configuration
- نگه‌داشتن منطق انتخاب Transport در یک نقطه
- جلوگیری از وابستگی Core به implementationهای concrete

این فایل:
- Business Logic را نمی‌شناسد
- MetaTrader5 را نمی‌شناسد
- Retry انجام نمی‌دهد
- Persistence انجام نمی‌دهد
- Command را اجرا نمی‌کند
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .base import ITransportClient
from .errors import TransportConfigurationError


# ============================================================================
# Transport names
# ============================================================================

TRANSPORT_KAFKA = "kafka"
TRANSPORT_HTTP = "http"
TRANSPORT_WEBSOCKET = "websocket"


# ============================================================================
# Helpers
# ============================================================================


def _normalize_transport_name(value: Any) -> str:
    """Normalize a configured transport name."""

    if not isinstance(value, str):
        raise TransportConfigurationError(
            "transport type must be a string",
            details={
                "value_type": type(value).__name__,
            },
        )

    normalized = value.strip().lower()

    if not normalized:
        raise TransportConfigurationError(
            "transport type cannot be empty"
        )

    return normalized


def _config_value(
    config: Optional[Mapping[str, Any]],
    key: str,
    default: Any = None,
) -> Any:
    """Read a top-level configuration value."""

    if config is None:
        return default

    return config.get(key, default)


def _transport_name_from_config(
    config: Optional[Mapping[str, Any]],
) -> str:
    """
    Resolve transport type from configuration.

    Supported forms:

        {
            "transport": "kafka"
        }

    or:

        {
            "transport": {
                "type": "kafka"
            }
        }
    """

    if config is None:
        return TRANSPORT_KAFKA

    raw_transport = config.get(
        "transport",
        TRANSPORT_KAFKA,
    )

    if isinstance(raw_transport, Mapping):
        raw_name = raw_transport.get(
            "type",
            TRANSPORT_KAFKA,
        )
    else:
        raw_name = raw_transport

    return _normalize_transport_name(raw_name)


# ============================================================================
# Factory
# ============================================================================


class TransportFactory:
    """
    Creates transport implementations from configuration.

    The factory does not start the transport.

    Example
    -------
        transport = TransportFactory.create(config)

        transport.start()
    """

    @staticmethod
    def create(
        config: Optional[Mapping[str, Any]] = None,
        *,
        transport_type: Optional[str] = None,
    ) -> ITransportClient:
        """
        Create a configured transport instance.

        Parameters
        ----------
        config:
            Agent configuration mapping.

        transport_type:
            Optional explicit transport name.

            If supplied, it takes precedence over configuration.

        Returns
        -------
        ITransportClient

        Raises
        ------
        TransportConfigurationError
            If the requested transport is unsupported or incorrectly
            configured.
        """

        if transport_type is not None:
            name = _normalize_transport_name(
                transport_type
            )
        else:
            name = _transport_name_from_config(
                config
            )

        # --------------------------------------------------------------
        # Kafka
        # --------------------------------------------------------------

        if name == TRANSPORT_KAFKA:
            from .kafka.kafka_transport import KafkaTransport

            return KafkaTransport(
                config=config
            )

        # --------------------------------------------------------------
        # HTTP
        #
        # Not implemented yet. The architecture reserves this transport
        # without pretending that an implementation exists.
        # --------------------------------------------------------------

        if name == TRANSPORT_HTTP:
            raise TransportConfigurationError(
                "HTTP transport is not implemented",
                details={
                    "transport": TRANSPORT_HTTP,
                },
            )

        # --------------------------------------------------------------
        # WebSocket
        #
        # Reserved for a future transport implementation.
        # --------------------------------------------------------------

        if name == TRANSPORT_WEBSOCKET:
            raise TransportConfigurationError(
                "WebSocket transport is not implemented",
                details={
                    "transport": TRANSPORT_WEBSOCKET,
                },
            )

        # --------------------------------------------------------------
        # Unknown transport
        # --------------------------------------------------------------

        raise TransportConfigurationError(
            f"unsupported transport type: {name!r}",
            details={
                "transport": name,
                "supported": [
                    TRANSPORT_KAFKA,
                    TRANSPORT_HTTP,
                    TRANSPORT_WEBSOCKET,
                ],
            },
        )


# ============================================================================
# Module-level compatibility helper
# ============================================================================


def create_transport(
    config: Optional[Mapping[str, Any]] = None,
    *,
    transport_type: Optional[str] = None,
) -> ITransportClient:
    """
    Compatibility helper for callers that prefer a function API.
    """

    return TransportFactory.create(
        config=config,
        transport_type=transport_type,
    )


# ============================================================================
# Public API
# ============================================================================


__all__ = [
    "TRANSPORT_KAFKA",
    "TRANSPORT_HTTP",
    "TRANSPORT_WEBSOCKET",
    "TransportFactory",
    "create_transport",
]