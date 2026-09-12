# Path: agent/__main__.py
# مسیر فایل: این فایل نقطه ورود پکیج agent است

"""Package entry point for ``python -m agent``.

Delegates execution to the same ``main()`` function used by the
legacy flat entry point so both execution modes remain consistent.
"""
# این docstring توضیح می‌دهد که این فایل نقطه ورود پکیج است
# وقتی کاربر دستور python -m agent را اجرا می‌کند، این فایل اجرا می‌شود
# کار اصلی آن این است که اجرای برنامه را به تابع main() که در فایل main.py وجود دارد، واگذار کند
# تا هم اجرای ماژولار (python -m agent) و هم اجرای قدیمی (مستقیم) یکسان باشند

from __future__ import annotations
# این دستور باعث می‌شود که نوع‌های داده (Type Hints) به صورت رشته‌ای (string) ارزیابی شوند
# یعنی نیازی نیست کلاس‌ها و تایپ‌ها قبل از استفاده تعریف شده باشند (ویژگی پایتون ۳.۷ به بالا)

from .main import main
# از فایل main.py که در همین پکیج (پوشه فعلی) قرار دارد، تابع main را وارد (import) می‌کند
# نقطه (.) یعنی «از همین پکیج فعلی»


if __name__ == "__main__":
    # این شرط بررسی می‌کند که آیا این فایل مستقیماً اجرا شده یا نه
    # اگر فایل به صورت مستقیم اجرا شود (مثلاً با python -m agent)، مقدار __name__ برابر "__main__" می‌شود
    # اگر فایل فقط import شده باشد، این شرط برقرار نمی‌شود
    main()
    # تابع main را صدا می‌زند تا برنامه اصلی شروع به کار کند