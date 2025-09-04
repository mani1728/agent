# -*- coding: utf-8 -*-
"""
main.py
-------
نقطهٔ شروع برنامه با تکیهٔ کامل بر config.json (هات‌ریلُد).

وظایف:
1) بارگذاری پیکربندی هات‌ریلُد از config.json (بدون ENV)
2) راه‌اندازی لاگ بر اساس بخش "logging" در config.json
3) بررسی فعال/غیر‌فعال بودن Kafka (kafka.enabled)
4) ساخت و اجرای KafkaListener با تزریق cfg (برای استفاده مستقیم از کانفیگِ هات‌ریلُد)
5) خاموش‌سازی تمیز با سیگنال‌ها (Ctrl+C و SIGTERM)

پیش‌نیاز:
- config_manager.py  ← شامل HotReloadConfig و سینگلتون cfg()
- config_logging.py  ← تابع setup_logging(cfg=...) که از بخش "logging" می‌خواند
- kafka_listener.py  ← در گام بعدی بازنویسی‌اش می‌کنیم تا مستقیماً از cfg استفاده کند
"""

from __future__ import annotations  # ✅ سازگاری تایپ‌هینت‌های مدرن (Python 3.8+)
import sys                          # ✅ خروج امن برنامه در صورت نیاز
import time                         # ✅ مکث سبک هنگام حلقه انتظار خاموش‌سازی
import signal                       # ✅ هندل سیگنال‌های سیستم عامل (Ctrl+C/SIGTERM)
import threading                    # ✅ اگر لازم شد منتظر تردها بمانیم

# ✅ ماژولِ پیکربندی با هات‌ریلُد
from config_manager import cfg  # cfg() → شیء HotReloadConfig (سینگلتون)

# ✅ راه‌اندازی لاگ بر اساس قسمت "logging" از config.json
from config_logging import setup_logging

# ✅ شنوندهٔ Kafka (گام بعدی آن را هم با cfg بازنویسی می‌کنیم)
from kafka_listener import KafkaListener


# -----------------------------
# متغیر/پرچم سراسری برای خاموش‌سازی
# -----------------------------
_shutdown_event = threading.Event()  # ✅ وقتی True شود، حلقه‌های بلاکینگ باید متوقف شوند


def _handle_signal(signum, frame):
    """
    هندلر سیگنال‌های سیستم عامل:
    - SIGINT  → Ctrl+C
    - SIGTERM → خاموش‌سازی سرویس در محیط‌های Production
    با دریافت سیگنال، پرچم خاموش‌سازی را ست می‌کنیم تا لوپ اصلی تمیز خارج شود.
    """
    logger = None
    try:
        import logging
        logger = logging.getLogger("App")
    except Exception:
        pass

    if logger:
        logger.info("Shutdown signal received", extra={"signum": signum})
    _shutdown_event.set()


def main() -> None:
    """
    نقطهٔ ورود اصلی برنامه:
    1) گرفتن شیء پیکربندی (هات‌ریلُد)
    2) راه‌اندازی لاگ
    3) بررسی فعال بودن Kafka
    4) ساخت و اجرای KafkaListener
    5) حلقهٔ انتظار برای سیگنال خاموش‌سازی (با خروج تمیز)
    """
    # 1) دسترسی به پیکربندی هات‌ریلُد (سینگلتون)
    #    نکته: cfg() در پس‌زمینه تغییرات فایل را چِک می‌کند و همیشه آخرین مقدارها را برمی‌گرداند.
    config = cfg()

    # 2) راه‌اندازی لاگ:
    #    setup_logging برای هر بار فراخوانی، آخرین تنظیمات logging را می‌گیرد (level/json/file/rotation)
    logger = setup_logging(config)
    logger.info("Application bootstrap started (hot-reload config enabled).")

    # 3) اگر Kafka غیرفعال باشد، خارج می‌شویم (این رفتار برای محیط‌های تست/دیباگ مفید است)
    kafka_enabled = bool(config.get("kafka.enabled", True))
    if not kafka_enabled:
        logger.warning("Kafka is disabled by config (kafka.enabled=false). Exiting main.")
        return

    # 4) ساخت KafkaListener:
    #    ـــ مهم: در بازنویسی kafka_listener.py، سازنده باید شیء cfg را بگیرد
    #    تا در هر لحظه بتواند آخرین مقدارها را (bootstrap_servers/topics/...) بخواند.
    try:
        listener = KafkaListener(config)  # ✅ ترجیح: KafkaListener(cfg: HotReloadConfig)
    except TypeError:
        # اگر نسخهٔ قدیمی KafkaListener هنوز AppSettings می‌خواهد، این خطا می‌خورید.
        # در گام بعدی kafka_listener.py را بازنویسی می‌کنیم تا با cfg کار کند.
        logger.error(
            "KafkaListener constructor signature mismatch. "
            "Expected KafkaListener(cfg: HotReloadConfig). Please use the rewritten kafka_listener.py."
        )
        sys.exit(1)

    # 5) ثبت هندلرهای سیگنال برای خاموش‌سازی تمیز
    signal.signal(signal.SIGINT, _handle_signal)   # Ctrl+C
    try:
        signal.signal(signal.SIGTERM, _handle_signal)  # SIGTERM (روی ویندوز ممکن است دردسترس نباشد)
    except Exception:
        pass

    # 6) استارت شنونده
    try:
        logger.info("KafkaListener starting...")
        # نکتهٔ قراردادی: فرض می‌کنیم KafkaListener.listen() خودش بلاکینگ است و تا زمان stop ادامه می‌دهد.
        # اگر نان-بلاکینگ باشد، می‌توانید آن را در یک ترد جداگانه استارت کنید و جایی که لازم است join کنید.
        t = threading.Thread(target=listener.listen, name="KafkaListener", daemon=True)
        t.start()
        logger.info("KafkaListener started.")

        # 7) حلقهٔ سبک انتظار تا وقتی سیگنال خاموش‌سازی برسد
        while not _shutdown_event.is_set():
            # در این بازه، می‌توانید سلامت سرویس را لاگ کنید یا وضعیت cfg را چک کنید
            # مثال: logger.debug("heartbeat main loop", extra={"env": config.get("app.env")})
            time.sleep(0.5)

    except Exception as e:
        logger.exception("Fatal error in main loop: %s", e)
    finally:
        # 8) تلاش برای خاموش‌سازی تمیز
        logger.info("Shutting down...")
        try:
            # اگر KafkaListener متدی برای توقف دارد، صدا بزنیم (در بازنویسی kafka_listener.py اضافه می‌کنیم)
            if hasattr(listener, "stop"):
                listener.stop()
        except Exception:
            pass
        logger.info("Bye.")


# اجرای مستقیم فایل (python main.py)
if __name__ == "__main__":
    main()
