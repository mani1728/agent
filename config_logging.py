# -*- coding: utf-8 -*-
"""
config_logging.py
-----------------
ماژول پیکربندی لاگ که تنظیمات را مستقیماً از config.json می‌خواند
(با استفاده از config_manager و قابلیت هات‌ریلُد).

کلیدهای مربوط در فایل config.json:
-----------------------------------
logging.level        : سطح لاگ (DEBUG | INFO | WARNING | ERROR | CRITICAL)
logging.json         : اگر True باشد، خروجی به صورت JSON چاپ می‌شود
logging.file_enabled : اگر True باشد، علاوه بر کنسول در فایل هم ذخیره می‌شود
logging.file_path    : مسیر فایل لاگ (مثلاً logs/app.log)
logging.max_bytes    : حداکثر حجم هر فایل لاگ قبل از Rotation (مثلاً 5000000)
logging.backup_count : تعداد فایل‌های پشتیبان (Rotation)

رفتارها:
- اگر هندلرهایی از قبل روی روت لاگر وجود داشته باشد، قبل از راه‌اندازی جدید پاک می‌شوند
  (برای سازگاری با هات‌ریلُد/اجرای مجدد setup_logging)
- اگر پوشهٔ مقصد فایل لاگ وجود نداشت، تلاش می‌شود ساخته شود
- برای سازگاری با کلکسیونرهای لاگ (ELK/Graylog)، فرمت JSON ساده و تمیز فراهم شده است
"""

from __future__ import annotations                 # ✔ اجازهٔ سازگاری تایپ‌هینت با نسخه‌های مختلف پایتون
import os                                         # ✔ ساخت پوشهٔ لاگ در صورت نیاز
import sys                                        # ✔ ارسال خروجی لاگ به stdout
import time                                       # ✔ مهر زمانی ساده در فرمتر JSON
import json as _json                              # ✔ برای سریال‌سازی JSON در فرمتر
import logging                                    # ✔ هستهٔ لاگ‌گذاری پایتون
import logging.handlers                           # ✔ شامل RotatingFileHandler
from typing import Any, Dict                      # ✔ تایپ‌ها برای خوانایی
from config_manager import cfg                    # ✔ خواندن تنظیمات از config.json با هات‌ریلُد

# -------------------------------------------------------------------
# فرمتر JSON ساده: خروجی‌ای تمیز و قابل‌مصرف برای سامانه‌های جمع‌آوری لاگ
# -------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """فرمت JSON برای لاگ‌ها (کم‌حرف، خوانا، و مناسب لاگ‌کالکتورها)."""
    def format(self, record: logging.LogRecord) -> str:
        # ✅ ساخت یک دیکشنری مینیمال از فیلدهای مهم لاگ
        payload: Dict[str, Any] = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),  # زمان به فرم ISO-like
            "level": record.levelname,                                                   # سطح لاگ (INFO/ERROR/...)
            "name": record.name,                                                         # نام لاگر
            "message": record.getMessage(),                                              # متن پیام
        }
        # ✅ اگر استک‌تریس داریم (مثلاً با logger.exception)، آن را هم اضافه کن
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # ✅ امکان افزودن فیلدهای اضافه (extra=...) در صورت نیاز
        #   توجه: logging خودکار فیلد extra را به پراپرتی‌های رکورد تبدیل می‌کند؛
        #   اینجا برای سادگی تنها اگر صراحتاً 'extra' دیکت بود، الحاق می‌کنیم.
        if hasattr(record, "extra") and isinstance(getattr(record, "extra"), dict):
            payload.update(record.extra)
        # ✅ تبدیل به رشتهٔ JSON با پشتیبانی از یونیکد
        return _json.dumps(payload, ensure_ascii=False)

# -------------------------------------------------------------------
# تابع راه‌اندازی لاگ بر اساس config.json
# -------------------------------------------------------------------
def setup_logging() -> None:
    """
    راه‌اندازی کامل لاگ‌گذاری پروژه بر اساس کلیدهای logging.* در config.json.

    این تابع:
    1) تنظیمات را از cfg().get_all() می‌خواند (هات‌ریلُد-فرندلی)
    2) لاگر روت را پاک‌سازی و دوباره با هندلرهای کنسول/فایل می‌سازد
    3) فرمت خروجی را بر اساس logging.json انتخاب می‌کند (Human یا JSON)
    """
    # ✅ خواندن snapshot فعلیِ کانفیگ (cfg() خودش تغییرات را در پس‌زمینه رصد می‌کند)
    c = cfg().get_all()                                # دیکشنری کاملِ تنظیمات فعلی
    log_cfg: Dict[str, Any] = c.get("logging", {})     # زیرشاخهٔ logging

    # ✅ تعیین سطح لاگ از روی رشتهٔ پیکربندی (با fallback امن به INFO)
    level_name = str(log_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    # ✅ آیا خروجی JSON است یا Human-readable؟
    as_json = bool(log_cfg.get("json", False))

    # ✅ آیا نوشتن در فایل فعال است؟
    file_enabled = bool(log_cfg.get("file_enabled", True))

    # ✅ مسیر فایل لاگ و مشخصات Rotation
    file_path = str(log_cfg.get("file_path", "logs/app.log"))
    max_bytes = int(log_cfg.get("max_bytes", 5_000_000))
    backup_count = int(log_cfg.get("backup_count", 3))

    # ✅ گرفتن لاگر روت و ست‌کردن سطح
    root = logging.getLogger()
    root.setLevel(level)

    # ✅ پاک‌سازی هندلرهای قبلی (اهمیت دارد؛ مخصوصاً وقتی setup_logging چندبار صدا زده شود)
    for h in list(root.handlers):
        root.removeHandler(h)

    # ✅ ساخت فرمترهای Human و JSON
    human_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",  # الگوی متن لاگ
        datefmt="%Y-%m-%d %H:%M:%S",                             # فرمت زمان برای حالت Human
    )
    json_formatter = JsonFormatter()                             # فرمتر JSON

    # ✅ هندلر کنسول (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(json_formatter if as_json else human_formatter)
    root.addHandler(console_handler)

    # ✅ اگر لاگ فایل فعال است، هندلر فایل چرخشی را اضافه کن
    if file_enabled:
        # تلاش برای ساخت پوشهٔ مقصد فایل لاگ (در صورت وجود مسیر دایرکتوری)
        try:
            log_dir = os.path.dirname(file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
        except Exception:
            # اگر ساخت پوشه شکست خورد، تنها کنسول را داریم؛ از کرش جلوگیری می‌کنیم
            pass

        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,               # مسیر فایل لاگ
            maxBytes=max_bytes,               # حد حجم فایل قبل از Rotation
            backupCount=backup_count,         # تعداد فایل‌های پشتیبان
            encoding="utf-8",                 # رمزنگاری فایل
        )
        file_handler.setLevel(level)          # سطح هندلر فایل
        file_handler.setFormatter(json_formatter if as_json else human_formatter)
        root.addHandler(file_handler)

    # ✅ کاهش پرحرفی برخی کتابخانه‌ها (اختیاری اما مفید)
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # ✅ یک لاگر سطح اپ برای پیام آغازین
    app_logger = logging.getLogger("App")
    app_logger.info(
        "Logging initialized (json=%s, file=%s, level=%s, rotation=%s bytes x %s backups)",
        as_json, file_path if file_enabled else "DISABLED", level_name, max_bytes, backup_count
    )

# -------------------------------------------------------------------
# نکتهٔ مهم دربارهٔ هات‌ریلُد:
# -------------------------------------------------------------------
# این ماژول، تنظیمات لاگ را «هنگام فراخوانی setup_logging» از config.json می‌خواند.
# اگر می‌خواهید هنگام تغییر config.json، فرمت/سطح/فایل لاگ نیز بلافاصله به‌روز شود،
# کافیست در نقطهٔ مناسب برنامه (مثلاً تایمر مدیریتی یا سیگنال کنترل) دوباره setup_logging() را صدا بزنید.
# چون قبل از افزودن هندلرها، تمام هندلرهای قبلی پاک می‌شوند، «ری‌کانفیگ» تمیز انجام می‌شود.
