# -*- coding: utf-8 -*-
"""
main.py
-------
نقطهٔ شروع برنامه با تکیهٔ کامل بر config.json (هات‌ریلُد).

وظایف:
1) بارگذاری پیکربندی هات‌ریلُد از config.json (بدون ENV)
2) راه‌اندازی لاگ بر اساس بخش "logging" در config.json
3) ثبت‌نام کلاینت (Hello) روی تاپیک clients.register و استارت heartbeat
4) بررسی فعال/غیرفعال بودن Kafka (kafka.enabled)
5) ساخت و اجرای KafkaListener با تزریق cfg (برای استفاده از کانفیگ هات‌ریلُد)
6) خاموش‌سازی تمیز با سیگنال‌ها (Ctrl+C و SIGTERM)

پیش‌نیاز ماژول‌ها:
- config_manager.py  → شامل HotReloadConfig و سینگلتون cfg()
- config_logging.py  → تابع setup_logging(cfg=...) که از بخش "logging" می‌خواند
- client_auth.py     → شامل ClientAuth برای ثبت‌نام و heartbeat
- kafka_listener.py  → شنوندهٔ کافکا که cfg را می‌گیرد و روی cmd.{client_id}.p* گوش می‌دهد
"""

from __future__ import annotations  # ✅ باید بلافاصله بعد از داک‌استرینگ بیاید (PEP 236)

# ==== کتابخانه‌های استاندارد پایتون ====
import sys                  # ✅ برای خروج امن برنامه در صورت خطای بحرانی
import time                 # ✅ مکث سبک در حلقه‌ی اصلی
import signal               # ✅ ثبت هندلر سیگنال‌های سیستم‌عامل (Ctrl+C / SIGTERM)
import threading            # ✅ اجرای لیسنر در ترد جدا و مدیریت رویداد خاموش‌سازی
import platform             # ✅ ساخت meta برای رجیستر (اطلاعات سیستم)
import getpass              # ✅ افزودن نام کاربر به meta
import logging              # ✅ زیرساخت لاگ استاندارد پایتون

# ==== ماژول‌های پروژه (هات‌ریلُد کانفیگ، لاگ، رجیستر، لیسنر) ====
from config_manager import cfg            # ✅ cfg() → شیء HotReloadConfig (سینگلتون با هات‌ریلُد)
from config_logging import setup_logging  # ✅ راه‌اندازی logging بر اساس config.json
from client_auth import ClientAuth        # ✅ مدیریت ثبت‌نام/توکن/heartbeat کلاینت
from kafka_listener import KafkaListener  # ✅ شنونده‌ی دستورات روی cmd.{client_id}.p{0,1,2}

# -----------------------------
# رویداد سراسری برای خاموش‌سازی تمیز
# -----------------------------
_shutdown_event = threading.Event()  # ✅ وقتی set شود، حلقه‌ی اصلی برنامه باید متوقف شود


# -----------------------------
# لاگر سبک برای ClientAuth (bridge به logging استاندارد)
# -----------------------------
def _clientauth_logger(level: str, msg: str, **kw) -> None:
    """
    این تابع را به ClientAuth می‌دهیم تا به‌جای print از logging استاندارد استفاده کند.
    level: "info"|"warning"|"error"|...
    msg: متن پیام
    kw: کلیدواژه‌های اضافه برای لاگ
    """
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger("ClientAuth").log(lvl, f"{msg} | {kw}" if kw else msg)


# -----------------------------
# هندلر سیگنال‌ها برای خاموش‌سازی تمیز
# -----------------------------
def _handle_signal(signum, frame) -> None:
    """
    با دریافت سیگنال‌های SIGINT (Ctrl+C) یا SIGTERM:
    - یک پیام لاگ می‌زنیم
    - رویداد خاموش‌سازی را set می‌کنیم تا حلقه‌ی اصلی خارج شود
    """
    logging.getLogger("App").info("Shutdown signal received", extra={"signum": signum})
    _shutdown_event.set()


# -----------------------------
# تابع اصلی برنامه
# -----------------------------
def main() -> None:
    """
    مراحل اصلی اجرای برنامه:
      - گرفتن cfg (هات‌ریلُد)
      - راه‌اندازی logging
      - ثبت‌نام کلاینت و آغاز heartbeat
      - استارت KafkaListener در ترد جدا
      - انتظار تا زمان دریافت سیگنال خاموش‌سازی و سپس خروج تمیز
    """
    # 1) گرفتن شیء پیکربندی با هات‌ریلُد (از config.json)
    config = cfg()  # ✅ از این به بعد هر بار config.get(...) صدا بزنیم آخرین مقادیر را می‌خواند

    # 2) راه‌اندازی logging با تنظیمات فایل config.json (level/json/file/rotation/...)
    setup_logging(config)
    app_logger = logging.getLogger("App")
    app_logger.info("Application bootstrap started (hot-reload config enabled).")

    # 3) ثبت‌نام کلاینت روی تاپیک clients.register + استارت heartbeat
    #    - اگر خطایی رخ دهد، لاگ می‌زنیم ولی برنامه را متوقف نمی‌کنیم
    #      (می‌توانید بسته به سیاست‌تان این‌جا return یا sys.exit(1) هم بکنید)
    ca = None  # نگه‌داشتن مرجع تا گاربیج‌کالکت نشود (heartbeat زنده بماند)
    try:
        # متادیتای دلخواه که همراه درخواست ثبت‌نام ارسال می‌شود
        meta = {
            "os": platform.platform(),          # مثال: 'Windows-10-10.0.19045-SP0'
            "username": getpass.getuser(),      # مثال: 'Administrator'
            "python": sys.version.split()[0],   # مثال: '3.13.0'
            "agent_version": "0.1.0",           # نسخه‌ی ایجنت شما
            "capabilities": ["mt5", "reports"], # قابلیت‌های این کلاینت
        }
        # ساخت ClientAuth با لاگر بریج‌شده
        ca = ClientAuth(client_meta=meta, logger=_clientauth_logger)
        # ارسال پیام Hello (ClientRegisterV1) به clients.register و انتظار پاسخ
        ca.register()
        # نکته: پس از موفقیت، heartbeat به‌صورت خودکار در یک ترد daemon شروع می‌شود.
    except Exception as e:
        app_logger.exception("Client registration failed: %s", e)
        # اگر می‌خواهید بدون رجیستر ادامه ندهید، این خط را uncomment کنید:
        # return

    # 4) اگر Kafka غیرفعال باشد، خروج (برای حالت‌های تست/دیباگ)
    if not bool(config.get("kafka.enabled", True)):
        app_logger.warning("Kafka is disabled by config (kafka.enabled=false). Exiting main.")
        # تلاش برای توقف heartbeat و تمیزکاری
        try:
            if ca:
                ca.stop()
        except Exception:
            pass
        return

    # 5) ساخت شنونده‌ی کافکا و سابسکرایب به cmd.{client_id}.p{0,1,2}
    try:
        listener = KafkaListener(config)  # سازنده نسخه‌ی بازنویسی‌شده که HotReloadConfig می‌گیرد
    except TypeError:
        # اگر هنوز نسخه‌ی قدیمی KafkaListener نصب است که به AppSettings نیاز داشت:
        app_logger.error(
            "KafkaListener constructor signature mismatch. "
            "Expected KafkaListener(cfg: HotReloadConfig). Please use the rewritten kafka_listener.py."
        )
        # توقف heartbeat در صورت وجود
        try:
            if ca:
                ca.stop()
        except Exception:
            pass
        sys.exit(1)

    # 6) ثبت هندلر سیگنال‌ها برای خاموش‌سازی تمیز
    signal.signal(signal.SIGINT, _handle_signal)   # Ctrl+C
    try:
        signal.signal(signal.SIGTERM, _handle_signal)  # ممکن است روی ویندوز در دسترس نباشد
    except Exception:
        pass

    # 7) استارت KafkaListener در یک ترد daemon تا حلقه‌ی اصلی بلاکه نشود
    app_logger.info("KafkaListener starting...")
    t = threading.Thread(target=listener.listen, name="KafkaListener", daemon=True)
    t.start()
    app_logger.info("KafkaListener started.")

    # 8) حلقه‌ی سبک انتظار تا زمان دریافت سیگنال خاموش‌سازی
    try:
        while not _shutdown_event.is_set():
            # اگر خواستید health-check یا متریک چاپ کنید، این‌جا مناسب است
            time.sleep(0.5)
    except Exception as e:
        app_logger.exception("Fatal error in main loop: %s", e)
    finally:
        # 9) خاموش‌سازی تمیز: توقف listener و heartbeat
        app_logger.info("Shutting down...")

        # توقف KafkaListener اگر متد stop دارد
        try:
            if hasattr(listener, "stop"):
                listener.stop()
        except Exception:
            pass

        # توقف heartbeat/Producer/Consumer مربوط به ClientAuth
        try:
            if ca:
                ca.stop()
        except Exception:
            pass

        app_logger.info("Bye.")


# -----------------------------
# اجرای مستقیم فایل (python main.py)
# -----------------------------
if __name__ == "__main__":
    main()
