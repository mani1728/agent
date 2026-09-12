# Path: agent/__init__.py
# مسیر فایل: این فایل، فایل اولیه‌ساز (initializer) پکیج agent است

"""MT5 Windows-side Agent package.

The package provides the Agent application and its transport abstraction.

Supported execution modes
--------------------------
Package mode::

    python -m agent

Legacy flat-file mode::

    python main.py

The legacy mode is kept for backward compatibility.
"""
# این docstring توضیح کلی پکیج را می‌دهد:
# این پکیج مربوط به Agent سمت ویندوز برای MetaTrader 5 (MT5) است
# وظیفه آن ارائه اپلیکیشن Agent و لایه انتقال داده (transport) است
# دو روش اجرا پشتیبانی می‌شود:
# ۱. حالت پکیج: python -m agent
# ۲. حالت قدیمی (فایل تخت): python main.py
# حالت قدیمی فقط برای سازگاری با نسخه‌های قبلی نگه داشته شده است

from __future__ import annotations
# این دستور باعث می‌شود تایپ‌هینت‌ها (Type Hints) به صورت رشته‌ای ارزیابی شوند
# تا نیازی به تعریف قبلی کلاس‌ها و تایپ‌ها نباشد

__version__ = "0.2.0"
# نسخه فعلی پکیج را مشخص می‌کند
# این متغیر معمولاً برای نمایش نسخه برنامه یا بررسی سازگاری استفاده می‌شود

__all__: list[str] = []
# لیست نام‌هایی که با دستور from agent import * در دسترس قرار می‌گیرند
# در حال حاضر خالی است، یعنی هیچ چیزی به صورت عمومی از این پکیج export نمی‌شود