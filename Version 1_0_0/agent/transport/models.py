# Path: agent/transport/models.py
# مسیر فایل: مدل‌های لایه انتقال (برای سازگاری با نسخه‌های قدیمی)

"""Backward-compatible transport model imports.

Canonical domain contracts live in :mod:`agent.contracts`.

This module intentionally contains no model definitions. It only
re-exports the canonical contracts so older transport-layer imports
remain compatible.

Transport implementations should prefer importing these contracts
directly from ``agent.contracts`` when possible.
"""
# این ماژول فقط برای سازگاری با کدهای قدیمی نوشته شده است.
# مدل‌های اصلی و رسمی در پکیج agent.contracts قرار دارند.
# اینجا هیچ تعریف جدیدی وجود ندارد و فقط مدل‌های اصلی دوباره export می‌شوند
# تا importهای قدیمی لایه transport همچنان کار کنند.
# پیشنهاد می‌شود در کدهای جدید مستقیماً از agent.contracts استفاده شود.

from __future__ import annotations
# فعال‌سازی ارزیابی تأخیری تایپ‌هینت‌ها

from ..contracts.command import CommandEnvelope
# وارد کردن مدل پاکت فرمان از لایه قراردادها

from ..contracts.response import ResponseEnvelope, ResponseStatus
# وارد کردن مدل پاکت پاسخ و وضعیت پاسخ از لایه قراردادها


__all__ = [
    "CommandEnvelope",
    "ResponseEnvelope",
    "ResponseStatus",
]
# لیست نمادهایی که با دستور from ... import * در دسترس قرار می‌گیرند