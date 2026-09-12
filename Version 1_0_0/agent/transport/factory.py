# Path: Version 1_0_0/agent/transport/factory.py
# مسیر فایل: کارخانه ساخت Transport برای Agent

# -*- coding: utf-8 -*-
# تعیین کدگذاری فایل

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
# این ماژول فقط مسئول ساخت شیء Transport مناسب بر اساس تنظیمات است.
# منطق انتخاب نوع Transport را در یک نقطه متمرکز می‌کند
# و اجازه نمی‌دهد لایه Core به پیاده‌سازی‌های واقعی وابسته شود.
# هیچ منطق کسب‌وکار، کار با MetaTrader، Retry یا ذخیره‌سازی انجام نمی‌دهد.

from __future__ import annotations
# فعال‌سازی ارزیابی تأخیری تایپ‌هینت‌ها

from typing import Any, Mapping, Optional
# تایپ‌های مورد نیاز برای تنظیمات و مقادیر اختیاری

from .base import ITransportClient
# رابط اصلی Transport که همه پیاده‌سازی‌ها باید از آن پیروی کنند

from .errors import TransportConfigurationError
# خطای مخصوص تنظیمات نادرست Transport


# ============================================================================
# Transport names
# ============================================================================
# نام‌های استاندارد انواع Transport

TRANSPORT_KAFKA = "kafka"
# نوع Kafka

TRANSPORT_HTTP = "http"
# نوع HTTP (هنوز پیاده‌سازی نشده)

TRANSPORT_WEBSOCKET = "websocket"
# نوع WebSocket (برای آینده رزرو شده)


# ============================================================================
# Helpers
# ============================================================================
# توابع کمکی داخلی


def _normalize_transport_name(value: Any) -> str:
    """Normalize a configured transport name."""
    # نرمال‌سازی نام Transport (حذف فاصله و تبدیل به حروف کوچک)

    if not isinstance(value, str):
        raise TransportConfigurationError(
            "transport type must be a string",
            details={
                "value_type": type(value).__name__,
            },
        )
        # اگر مقدار رشته نباشد، خطا پرتاب می‌کند

    normalized = value.strip().lower()
    # حذف فاصله‌های اضافی و تبدیل به حروف کوچک

    if not normalized:
        raise TransportConfigurationError(
            "transport type cannot be empty"
        )
        # اگر بعد از نرمال‌سازی خالی شد، خطا می‌دهد

    return normalized
    # نام نرمال‌شده را برمی‌گرداند


def _config_value(
    config: Optional[Mapping[str, Any]],
    key: str,
    default: Any = None,
) -> Any:
    """Read a top-level configuration value."""
    # خواندن یک مقدار سطح بالا از تنظیمات

    if config is None:
        return default
        # اگر تنظیمات وجود نداشته باشد، مقدار پیش‌فرض را برمی‌گرداند

    return config.get(key, default)
    # مقدار کلید را می‌خواند یا در صورت نبود، پیش‌فرض را برمی‌گرداند


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
    # استخراج نام نوع Transport از تنظیمات
    # دو شکل پشتیبانی می‌شود: مقدار ساده یا دیکشنری دارای کلید type

    if config is None:
        return TRANSPORT_KAFKA
        # اگر تنظیمات نباشد، پیش‌فرض Kafka در نظر گرفته می‌شود

    raw_transport = config.get(
        "transport",
        TRANSPORT_KAFKA,
    )
    # مقدار خام transport را می‌خواند

    if isinstance(raw_transport, Mapping):
        # اگر مقدار خودش دیکشنری باشد
        raw_name = raw_transport.get(
            "type",
            TRANSPORT_KAFKA,
        )
        # نام را از کلید type می‌خواند
    else:
        raw_name = raw_transport
        # در غیر این صورت همان مقدار خام را به‌عنوان نام در نظر می‌گیرد

    return _normalize_transport_name(raw_name)
    # نام را نرمال‌سازی کرده و برمی‌گرداند


# ============================================================================
# Factory
# ============================================================================
# کلاس اصلی کارخانه


class TransportFactory:
    """
    Creates transport implementations from configuration.

    The factory does not start the transport.

    Example
    -------
        transport = TransportFactory.create(config)

        transport.start()
    """
    # این کلاس بر اساس تنظیمات، پیاده‌سازی مناسب Transport را می‌سازد
    # توجه: خودش Transport را start نمی‌کند

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
        # ساخت یک نمونه از Transport بر اساس تنظیمات یا نام صریح

        if transport_type is not None:
            # اگر نام به‌صورت صریح داده شده باشد، اولویت دارد
            name = _normalize_transport_name(
                transport_type
            )
        else:
            # در غیر این صورت از تنظیمات استخراج می‌شود
            name = _transport_name_from_config(
                config
            )

        # --------------------------------------------------------------
        # Kafka
        # --------------------------------------------------------------
        # مسیر Kafka

        if name == TRANSPORT_KAFKA:
            from .kafka.kafka_transport import KafkaTransport
            # بارگذاری تنبل کلاس KafkaTransport

            return KafkaTransport(
                config=config
            )
            # ساخت و بازگرداندن نمونه Kafka

        # --------------------------------------------------------------
        # HTTP
        #
        # Not implemented yet. The architecture reserves this transport
        # without pretending that an implementation exists.
        # --------------------------------------------------------------
        # مسیر HTTP (هنوز پیاده‌سازی نشده)

        if name == TRANSPORT_HTTP:
            raise TransportConfigurationError(
                "HTTP transport is not implemented",
                details={
                    "transport": TRANSPORT_HTTP,
                },
            )
            # خطای مشخص برای اعلام عدم پیاده‌سازی

        # --------------------------------------------------------------
        # WebSocket
        #
        # Reserved for a future transport implementation.
        # --------------------------------------------------------------
        # مسیر WebSocket (برای آینده رزرو شده)

        if name == TRANSPORT_WEBSOCKET:
            raise TransportConfigurationError(
                "WebSocket transport is not implemented",
                details={
                    "transport": TRANSPORT_WEBSOCKET,
                },
            )
            # خطای مشخص برای اعلام عدم پیاده‌سازی

        # --------------------------------------------------------------
        # Unknown transport
        # --------------------------------------------------------------
        # نوع ناشناخته

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
        # خطای نوع پشتیبانی‌نشده همراه با لیست انواع مجاز


# ============================================================================
# Module-level compatibility helper
# ============================================================================
# تابع کمکی در سطح ماژول برای سازگاری


def create_transport(
    config: Optional[Mapping[str, Any]] = None,
    *,
    transport_type: Optional[str] = None,
) -> ITransportClient:
    """
    Compatibility helper for callers that prefer a function API.
    """
    # تابع ساده برای کسانی که ترجیح می‌دهند به‌جای کلاس از تابع استفاده کنند

    return TransportFactory.create(
        config=config,
        transport_type=transport_type,
    )
    # فقط کار را به کلاس Factory واگذار می‌کند


# ============================================================================
# Public API
# ============================================================================
# رابط عمومی ماژول


__all__ = [
    "TRANSPORT_KAFKA",
    "TRANSPORT_HTTP",
    "TRANSPORT_WEBSOCKET",
    "TransportFactory",
    "create_transport",
]
# لیست نمادهایی که با import * در دسترس قرار می‌گیرند