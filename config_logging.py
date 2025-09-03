# config_logging.py
# =========================
# ماژول پیکربندی و لاگ‌گذاری پروژه
# - خواندن متغیرهای محیطی (ENV) با مقادیر پیش‌فرض امن
# - ساخت کلاس تنظیمات با dataclass
# - راه‌اندازی لاگ‌گذاری (کنسول Human/JSON + فایل چرخشی Rotation)
# =========================

from __future__ import annotations  # برای سازگاری تایپ‌هینت با نسخه‌های قدیمی‌تر پایتون
import os                          # برای خواندن متغیرهای محیطی
import sys                         # برای کنترل خروجی استاندارد
import logging                     # هستهٔ لاگ‌گذاری
from logging.handlers import RotatingFileHandler  # هندلر فایل با قابلیت Rotation
from dataclasses import dataclass   # برای تعریف کلاس تنظیمات ساده
from typing import Optional         # تایپ‌های اختیاری

# ---------------------------------------------------------
# داده‌ساخت (dataclass) برای نگهداشت تنظیمات برنامه
# ---------------------------------------------------------
@dataclass
class AppSettings:
    """کلاس تنظیمات که یک‌بار از ENV خوانده شده و به بقیهٔ ماژول‌ها تزریق می‌شود."""
    # --- Kafka پایه ---
    kafka_servers: str = "192.168.1.254:9092"        # آدرس/های کافکا (با کاما قابل جداسازی)
    kafka_request_topic: str = "agent-send"          # تاپیک ورودی (دریافت دستورات)
    kafka_response_topic: str = "agent-recive"       # تاپیک خروجی (ارسال پاسخ‌ها)
    kafka_group_id: str = "kafka_listener_group"     # گروه مصرف‌کننده

    # --- تنظیمات Producer برای پاسخ ---
    kafka_compression: str = "zstd"                  # نوع فشرده‌سازی: zstd|lz4|gzip|snappy
    kafka_linger_ms: int = 10                        # تأخیر میکرو-batching
    kafka_batch_num: int = 1000                      # حداکثر پیام در هر بچ
    kafka_max_inflight: int = 5                      # تعداد درخواست‌های همزمان
    kafka_resp_max_part_bytes: int = 900 * 1024      # سایز هر چانک (قبل از فشرده‌سازی)

    # --- Logging ---
    log_level: str = "INFO"                          # سطح لاگ: DEBUG/INFO/WARNING/ERROR/CRITICAL
    log_json: bool = False                           # خروجی JSON به‌جای Human
    log_file: str = "logs/app.log"                   # مسیر فایل لاگ
    log_max_bytes: int = 10 * 1024 * 1024            # حجم هر فایل لاگ (۱۰MB)
    log_backups: int = 10                            # تعداد فایل‌های پشتیبان (Rotation)

    # --- پارامترهای اختیاری MT5 (در صورت نیاز) ---
    mt5_path: Optional[str] = None                   # مسیر ترمینال
    mt5_login: Optional[int] = None                  # لاگین حساب
    mt5_password: Optional[str] = None               # رمز
    mt5_server: Optional[str] = None                 # نام سرور بروکر


def _get_bool_env(name: str, default: bool) -> bool:
    """خواندن امن مقدار بولی از ENV (true/1/yes → True)."""
    val = os.getenv(name, str(default)).strip().lower()  # خواندن و نرمال‌سازی
    return val in ("1", "true", "yes", "y")              # نگاشت به بولی


def _get_int_env(name: str, default: int) -> int:
    """خواندن امن عدد صحیح از ENV، با fallback به مقدار پیش‌فرض."""
    raw = os.getenv(name, None)           # تلاش برای خواندن
    if raw is None:                       # اگر نبود
        return default                    # برگرداندن پیش‌فرض
    try:
        return int(str(raw).strip())      # تبدیل به int
    except ValueError:
        return default                    # در صورت خطا، پیش‌فرض


def load_settings_from_env() -> AppSettings:
    """ساخت AppSettings با خواندن ENV و اعمال پیش‌فرض‌های امن."""
    return AppSettings(
        kafka_servers=os.getenv("KAFKA_SERVERS", "192.168.1.254:9092"),
        kafka_request_topic=os.getenv("KAFKA_TOPIC", "agent-send"),
        kafka_response_topic=os.getenv("KAFKA_RESPONSE_TOPIC", "agent-recive"),
        kafka_group_id=os.getenv("KAFKA_GROUP_ID", "kafka_listener_group"),

        kafka_compression=os.getenv("KAFKA_COMPRESSION", "zstd"),
        kafka_linger_ms=_get_int_env("KAFKA_LINGER_MS", 10),
        kafka_batch_num=_get_int_env("KAFKA_BATCH_NUM", 1000),
        kafka_max_inflight=_get_int_env("KAFKA_MAX_INFLIGHT", 5),
        kafka_resp_max_part_bytes=_get_int_env("KAFKA_RESPONSE_MAX_PART_BYTES", 900 * 1024),

        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_json=_get_bool_env("LOG_JSON", False),
        log_file=os.getenv("LOG_FILE", "logs/app.log"),
        log_max_bytes=_get_int_env("LOG_MAX_BYTES", 10 * 1024 * 1024),
        log_backups=_get_int_env("LOG_BACKUPS", 10),

        mt5_path=os.getenv("MT5_PATH") or None,
        mt5_login=_get_int_env("MT5_LOGIN", 0) or None,
        mt5_password=os.getenv("MT5_PASSWORD") or None,
        mt5_server=os.getenv("MT5_SERVER") or None,
    )


class _JsonFormatter(logging.Formatter):
    """فرمتر JSON برای سازگاری با ELK/Graylog و…"""
    def format(self, record: logging.LogRecord) -> str:
        import json as _json                          # ایمپورت محلی برای سبک نگه داشتن namespace
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),  # زمان استاندارد
            "level": record.levelname,                           # سطح لاگ
            "logger": record.name,                               # نام لاگر
            "msg": record.getMessage(),                          # پیام
        }
        if record.exc_info:                                      # اگر استک تریس داریم
            payload["exc"] = self.formatException(record.exc_info)  # اضافه‌کردن آن
        if hasattr(record, "extra") and isinstance(record.extra, dict):  # الحاق extra در صورت وجود
            payload.update(record.extra)
        return _json.dumps(payload, ensure_ascii=False)          # تبدیل به JSON


def setup_logging(settings: AppSettings) -> logging.Logger:
    """راه‌اندازی کامل لاگ‌گذاری پروژه بر اساس AppSettings."""
    root = logging.getLogger()                                   # گرفتن لاگر روت
    root.setLevel(settings.log_level)                            # اعمال سطح لاگ

    for h in list(root.handlers):                                # پاک‌سازی هندلرهای قبلی
        root.removeHandler(h)

    human_fmt = logging.Formatter(                               # فرمت Human
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = _JsonFormatter()                                  # فرمت JSON

    console = logging.StreamHandler(sys.stdout)                  # هندلر کنسول
    console.setLevel(settings.log_level)                         # سطح هندلر
    console.setFormatter(json_fmt if settings.log_json else human_fmt)  # انتخاب فرمت
    root.addHandler(console)                                     # افزودن هندلر

    try:
        log_dir = os.path.dirname(settings.log_file)             # مسیر پوشه لاگ
        if log_dir:                                              # اگر تعریف شده
            os.makedirs(log_dir, exist_ok=True)                  # ساخت پوشه در صورت نبود
    except Exception:
        pass                                                     # در صورت شکست ساخت، فقط کنسول داریم

    file_handler = RotatingFileHandler(                          # هندلر فایل با Rotation
        filename=settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backups,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.log_level)                    # سطح هندلر فایل
    file_handler.setFormatter(json_fmt if settings.log_json else human_fmt)  # فرمت فایل
    root.addHandler(file_handler)                                # افزودن هندلر فایل

    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)  # کاهش پرحرفی کتابخانه‌ها
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("App")                            # ساخت یک لاگر سطح-اپ
    logger.info(
        "Logging initialized (json=%s, file=%s, level=%s, rotation=%s bytes x %s backups)",
        settings.log_json, settings.log_file, settings.log_level,
        settings.log_max_bytes, settings.log_backups
    )
    return logger                                                # برگرداندن لاگر اپ (اختیاری)
