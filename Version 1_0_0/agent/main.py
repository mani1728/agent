# Path: Version 1_0_0/agent/main.py
# مسیر فایل: نقطه ورود اصلی برنامه (سازگار با نسخه قدیمی)

# -*- coding: utf-8 -*-
# تعیین کدگذاری فایل به UTF-8 برای پشتیبانی از کاراکترهای فارسی و غیرا انگلیسی

"""
main.py
-------
Legacy-compatible application entry point.

Migration status:
- Legacy Kafka startup is intentionally preserved.
- Legacy ClientAuth registration/heartbeat is intentionally preserved.
- Legacy hot-reload configuration is intentionally preserved.
- Legacy signal/shutdown behavior is intentionally preserved.
- AgentWorker is the canonical/default runtime; legacy listener remains compatibility-only.
- Transport migration will be introduced incrementally in later phases.

Current responsibility:
1) Load hot-reload configuration from config.json.
2) Configure logging.
3) Register the client through ClientAuth.
4) Start ClientAuth heartbeat.
5) Update runtime Kafka topics after registration.
6) Start KafkaListener.
7) Wait for shutdown.
8) Stop KafkaListener and ClientAuth cleanly.
"""
# این docstring وضعیت مهاجرت و مسئولیت‌های فعلی فایل را توضیح می‌دهد:
# - هنوز رفتارهای قدیمی Kafka و ClientAuth حفظ شده‌اند
# - AgentWorker مسیر اصلی و پیشنهادی اجرا است
# - مسیر قدیمی listener فقط برای سازگاری نگه داشته شده
# وظایف اصلی: بارگذاری تنظیمات، لاگ، ثبت کلاینت، شروع heartbeat، به‌روزرسانی تاپیک‌ها، شروع listener/worker، انتظار برای خاموش شدن و توقف تمیز

from __future__ import annotations
# فعال‌سازی ارزیابی تأخیری تایپ‌هینت‌ها (Type Hints) برای جلوگیری از مشکل تعریف دایره‌ای

# ======================================================================
# Standard library
# ======================================================================
# بخش کتابخانه‌های استاندارد پایتون

import getpass          # برای گرفتن نام کاربری سیستم‌عامل
import logging          # سیستم لاگ استاندارد پایتون
import platform         # اطلاعات سیستم‌عامل و سخت‌افزار
import signal           # مدیریت سیگنال‌های سیستم‌عامل (مثل Ctrl+C)
import sys              # اطلاعات مفسر پایتون و آرگومان‌های خط فرمان
import threading        # کار با نخ‌ها (Thread)
import time             # توابع مربوط به زمان و خواب (sleep)


# ======================================================================
# Application dependencies
# ======================================================================
# بخش وابستگی‌های داخلی برنامه

try:  # Package-safe execution: python -m agent
    # حالت اجرای پکیج (پیشنهادی): python -m agent
    from .core.command_executor import CommandExecutor
    from .core.worker import AgentWorker
    from .infrastructure.config_logging import setup_logging
    from .infrastructure.config_manager import cfg
    from .security.client_auth import ClientAuth
    from .transport.factory import TransportFactory
except ImportError:  # Direct execution compatibility: python agent/main.py
    # حالت سازگاری با اجرای مستقیم فایل: python agent/main.py
    from agent.core.command_executor import CommandExecutor
    from agent.core.worker import AgentWorker
    from agent.infrastructure.config_logging import setup_logging
    from agent.infrastructure.config_manager import cfg
    from agent.security.client_auth import ClientAuth
    from agent.transport.factory import TransportFactory

try:
    from .transport.kafka.listener import KafkaListener as _KafkaListener
except Exception:  # pragma: no cover - optional dependency
    # اگر وابستگی KafkaListener موجود نباشد، آن را None می‌گذاریم
    # (این وابستگی اختیاری است و فقط برای مسیر قدیمی استفاده می‌شود)
    _KafkaListener = None


# ======================================================================
# Global shutdown event
# ======================================================================
# رویداد سراسری برای اعلام خاموش شدن برنامه

_shutdown_event = threading.Event()
# یک Event از نوع threading که وقتی set شود، حلقه اصلی برنامه متوجه می‌شود باید خاموش شود


# ======================================================================
# ClientAuth logging bridge
# ======================================================================
# پل لاگ برای کلاس ClientAuth

def _clientauth_logger(
    level: str,
    msg: str,
    **kw,
) -> None:
    """
    Bridge ClientAuth logging into Python's standard logging system.

    ClientAuth can continue using its existing logger contract while the
    application keeps one logging infrastructure.
    """
    # این تابع لاگ‌های ClientAuth را به سیستم لاگ استاندارد پایتون وصل می‌کند
    # تا همه لاگ‌ها یکپارچه در یک زیرساخت ثبت شوند

    lvl = getattr(
        logging,
        str(level).upper(),
        logging.INFO,
    )
    # سطح لاگ را از رشته (مثل "info") به مقدار واقعی logging تبدیل می‌کند
    # اگر سطح نامعتبر باشد، به INFO پیش‌فرض می‌رود

    message = f"{msg} | {kw}" if kw else msg
    # اگر پارامترهای اضافی (kw) وجود داشته باشد، آن‌ها را به پیام اضافه می‌کند

    logging.getLogger("ClientAuth").log(
        lvl,
        message,
    )
    # پیام را با سطح مشخص‌شده در لاگر به نام "ClientAuth" ثبت می‌کند


# ======================================================================
# Signal handling
# ======================================================================
# مدیریت سیگنال‌های سیستم‌عامل

def _handle_signal(
    signum,
    frame,
) -> None:
    """
    Request application shutdown.

    Actual cleanup remains inside main() so that all resources are
    released from one controlled shutdown path.
    """
    # این تابع وقتی سیگنال خاموش شدن (مثل Ctrl+C) دریافت شود فراخوانی می‌شود
    # فقط رویداد خاموش شدن را set می‌کند و پاکسازی واقعی داخل تابع main انجام می‌شود

    logging.getLogger("App").info(
        "Shutdown signal received",
        extra={"signum": signum},
    )
    # لاگ می‌کند که سیگنال خاموش شدن دریافت شده و شماره سیگنال را هم ثبت می‌کند

    _shutdown_event.set()
    # رویداد سراسری خاموش شدن را فعال می‌کند تا حلقه اصلی متوجه شود


def _config_bool(config, path: str, default: bool = False) -> bool:
    """Read a JSON-compatible boolean without treating ``\"false\"`` as true."""
    # خواندن مقدار بولین از تنظیمات به شکلی که رشته "false" به اشتباه True نشود
    value = config.get(path, default)
    # مقدار را از مسیر داده‌شده در تنظیمات می‌خواند (اگر نباشد مقدار پیش‌فرض را برمی‌گرداند)
    if isinstance(value, str):
        # اگر مقدار رشته باشد، فقط در صورتی True برمی‌گرداند که یکی از این‌ها باشد
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
    # در غیر این صورت مقدار را به بولین تبدیل می‌کند


def _validate_canonical_kafka_config(config) -> None:
    """Validate minimum operational Kafka settings for the worker path."""
    # اعتبارسنجی حداقل تنظیمات ضروری Kafka برای مسیر Worker

    required = {
        "kafka.bootstrap_servers": config.get("kafka.bootstrap_servers", None),
        "kafka.group_id": config.get("kafka.group_id", None),
        "kafka.topics.commands": config.get("kafka.topics.commands", None),
    }
    # لیست کلیدهای ضروری و مقادیر فعلی آن‌ها

    missing: list[str] = []
    # لیستی برای نگهداری کلیدهای ناقص

    for key, value in required.items():
        if isinstance(value, (list, tuple)):
            # اگر مقدار لیست یا تاپل باشد، بررسی می‌کند که حداقل یک آیتم غیرخالی داشته باشد
            if not any(str(item).strip() for item in value):
                missing.append(key)
        elif value is None or not str(value).strip():
            # اگر مقدار None یا رشته خالی باشد، آن را به لیست ناقص‌ها اضافه می‌کند
            missing.append(key)

    auto_commit = config.get("kafka.enable_auto_commit", None)
    # مقدار enable_auto_commit را می‌خواند

    auto_commit_is_false = (
        auto_commit is False
        or (
            isinstance(auto_commit, str)
            and auto_commit.strip().lower() in {"0", "false", "no", "off"}
        )
    )
    # بررسی می‌کند که auto_commit واقعاً False باشد (نه True و نه مقدار مبهم)

    if not auto_commit_is_false:
        missing.append("kafka.enable_auto_commit=false")
        # اگر auto_commit False نباشد، آن را به لیست خطاها اضافه می‌کند

    if missing:
        raise RuntimeError(
            "Canonical Kafka runtime configuration is not operationally "
            "configured; missing required settings: " + ", ".join(missing)
        )
        # اگر چیزی ناقص باشد، خطای RuntimeError با لیست موارد ناقص پرتاب می‌کند


# ======================================================================
# Main application entry point
# ======================================================================
# نقطه ورود اصلی برنامه

def main() -> None:
    """
    Legacy application startup/shutdown sequence.

    IMPORTANT:
    This function intentionally remains compatible with the existing
    Kafka-based runtime during the migration.

    The AgentWorker is the canonical runtime; the legacy listener remains an explicit compatibility path.
    """
    # تابع اصلی راه‌اندازی و خاموش کردن برنامه
    # هنوز با مسیر قدیمی Kafka سازگار نگه داشته شده
    # AgentWorker مسیر اصلی و پیشنهادی است

    # ------------------------------------------------------------------
    # Reset shutdown state
    # ------------------------------------------------------------------
    # ریست کردن وضعیت خاموش شدن

    _shutdown_event.clear()
    # رویداد خاموش شدن را پاک می‌کند تا برنامه از حالت قبلی خارج شود

    # ------------------------------------------------------------------
    # 1) Load hot-reload configuration
    # ------------------------------------------------------------------
    # ۱) بارگذاری تنظیمات قابل بارگذاری مجدد (hot-reload)

    config = cfg()
    # شیء تنظیمات را از طریق تابع cfg() بارگذاری می‌کند

    # ------------------------------------------------------------------
    # 2) Configure logging
    # ------------------------------------------------------------------
    # ۲) پیکربندی سیستم لاگ

    setup_logging(config)
    # سیستم لاگ را بر اساس تنظیمات پیکربندی می‌کند

    app_logger = logging.getLogger("App")
    # لاگر مخصوص بخش اصلی برنامه را می‌گیرد

    app_logger.info(
        "Application bootstrap started "
        "(hot-reload config enabled)."
    )
    # لاگ شروع راه‌اندازی برنامه را ثبت می‌کند

    # ------------------------------------------------------------------
    # 3) Client registration / heartbeat
    # ------------------------------------------------------------------
    # ۳) ثبت کلاینت و شروع heartbeat

    ca = None
    # متغیر نگهداری شیء ClientAuth (در ابتدا None)

    try:
        meta = {
            "os": platform.platform(),
            "username": getpass.getuser(),
            "python": sys.version.split()[0],
            "agent_version": "0.1.0",
            "capabilities": [
                "mt5",
                "reports",
            ],
        }
        # دیکشنری اطلاعات متا کلاینت:
        # سیستم‌عامل، نام کاربری، نسخه پایتون، نسخه agent و قابلیت‌ها

        ca = ClientAuth(
            client_meta=meta,
            logger=_clientauth_logger,
        )
        # ساخت شیء ClientAuth با اطلاعات متا و تابع لاگ سفارشی

        # Register client and start heartbeat according to legacy
        # ClientAuth behavior.
        ca.register()
        # ثبت کلاینت و شروع heartbeat طبق رفتار قدیمی ClientAuth

        # --------------------------------------------------------------
        # Update runtime Kafka configuration after registration.
        # --------------------------------------------------------------
        # به‌روزرسانی تنظیمات Kafka بعد از ثبت موفق کلاینت

        try:
            config._data.setdefault(
                "kafka",
                {},
            )["client_id"] = ca.client_id
            # شناسه کلاینت را در بخش kafka تنظیمات ذخیره می‌کند

            final_cmd_topics = [
                f"cmd.{ca.client_id}.p0",
                f"cmd.{ca.client_id}.p1",
                f"cmd.{ca.client_id}.p2",
            ]
            # ساخت لیست تاپیک‌های فرمان بر اساس شناسه کلاینت

            config._data["kafka"].setdefault(
                "topics",
                {},
            )
            # اگر بخش topics وجود نداشته باشد، آن را می‌سازد

            config._data["kafka"]["topics"][
                "commands"
            ] = final_cmd_topics
            # تاپیک‌های commands را با لیست جدید جایگزین می‌کند

            config._data["kafka"][
                "group_id"
            ] = f"mt5-service.{ca.client_id}"
            # group_id را بر اساس شناسه کلاینت تنظیم می‌کند

            app_logger.info(
                "Client topics updated after registration",
                extra={
                    "client_id": ca.client_id,
                    "topics": final_cmd_topics,
                },
            )
            # لاگ موفقیت‌آمیز به‌روزرسانی تاپیک‌ها

        except Exception:
            app_logger.exception(
                "Failed to update topics after registration"
            )
            # اگر به‌روزرسانی تاپیک‌ها شکست بخورد، خطا را لاگ می‌کند (برنامه متوقف نمی‌شود)

    except Exception:
        # Preserve legacy behavior:
        # registration failure is logged but does not immediately
        # terminate the application.
        # رفتار قدیمی حفظ شده: شکست ثبت کلاینت فقط لاگ می‌شود و برنامه فوراً متوقف نمی‌شود
        app_logger.exception(
            "Client registration failed"
        )
        # لاگ کامل خطا همراه با traceback

    # ------------------------------------------------------------------
    # 4) Kafka enabled check
    # ------------------------------------------------------------------
    # ۴) بررسی فعال بودن Kafka

    if not bool(
        config.get(
            "kafka.enabled",
            True,
        )
    ):
        # اگر kafka.enabled برابر False باشد
        app_logger.warning(
            "Kafka is disabled by config "
            "(kafka.enabled=false). Exiting main."
        )
        # هشدار می‌دهد که Kafka غیرفعال است و از تابع خارج می‌شود

        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception(
                "Failed to stop ClientAuth"
            )
            # تلاش برای توقف ClientAuth در صورت وجود

        return
        # خروج از تابع main

    # ------------------------------------------------------------------
    # 5) Select the opt-in worker path or preserve the legacy listener.
    # ------------------------------------------------------------------
    # ۵) انتخاب مسیر Worker یا مسیر قدیمی Listener

    use_agent_worker = _config_bool(
        config,
        "app.use_agent_worker",
        True,
    )
    # خواندن فلگ استفاده از AgentWorker (پیش‌فرض True)

    listener = None
    worker = None
    runtime_thread = None
    # متغیرهای نگهداری listener، worker و نخ اجرایی

    try:
        if use_agent_worker:
            # اگر مسیر Worker انتخاب شده باشد
            _validate_canonical_kafka_config(config)
            # اعتبارسنجی تنظیمات ضروری Kafka

            transport = TransportFactory.create(config)
            # ساخت شیء transport از طریق کارخانه (Factory)

            worker = AgentWorker(
                CommandExecutor(),
                transport,
                poll_timeout_sec=float(
                    config.get("app.worker_poll_timeout_sec", 1.0)
                ),
            )
            # ساخت AgentWorker با اجراکننده فرمان، transport و زمان انتظار poll

            runtime_thread = threading.Thread(
                target=worker.run,
                name="AgentWorker",
                daemon=True,
            )
            # ساخت نخ برای اجرای worker (به صورت daemon)

            app_logger.info("AgentWorker path selected by feature flag")
            # لاگ انتخاب مسیر Worker
        else:
            # مسیر قدیمی Listener
            if _KafkaListener is None:
                raise RuntimeError(
                    "Kafka listener dependency is unavailable "
                    "(missing runtime dependency)"
                )
                # اگر KafkaListener در دسترس نباشد، خطا پرتاب می‌کند

            listener = _KafkaListener(config)
            # ساخت شیء KafkaListener با تنظیمات

            runtime_thread = threading.Thread(
                target=listener.listen,
                name="KafkaListener",
                daemon=True,
            )
            # ساخت نخ برای اجرای listener

            app_logger.info("Legacy KafkaListener path selected")
            # لاگ انتخاب مسیر قدیمی

    except Exception:
        app_logger.exception("Failed to initialize selected runtime path")
        # لاگ کامل خطا در صورت شکست راه‌اندازی مسیر انتخاب‌شده

        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")
            # تلاش برای توقف ClientAuth

        raise
        # خطا را دوباره پرتاب می‌کند تا برنامه متوقف شود

    # ------------------------------------------------------------------
    # 6) Register OS signal handlers
    # ------------------------------------------------------------------
    # ۶) ثبت هندلرهای سیگنال سیستم‌عامل

    signal.signal(
        signal.SIGINT,
        _handle_signal,
    )
    # ثبت هندلر برای سیگنال SIGINT (معمولاً Ctrl+C)

    try:
        signal.signal(
            signal.SIGTERM,
            _handle_signal,
        )
        # ثبت هندلر برای سیگنال SIGTERM (خاموش شدن نرم)
    except Exception:
        # SIGTERM may not be available/usable on every Windows runtime.
        # در برخی محیط‌های ویندوز ممکن است SIGTERM در دسترس نباشد
        pass

    # ------------------------------------------------------------------
    # 7) Start selected runtime path
    # ------------------------------------------------------------------
    # ۷) شروع مسیر اجرایی انتخاب‌شده

    runtime_thread.start()
    # شروع نخ اجرایی (worker یا listener)

    app_logger.info("Runtime path started: worker_enabled=%s", use_agent_worker)
    # لاگ شروع مسیر اجرایی همراه با وضعیت فلگ worker

    # ------------------------------------------------------------------
    # 8) Main wait loop
    # ------------------------------------------------------------------
    # ۸) حلقه انتظار اصلی

    try:
        while not _shutdown_event.is_set():
            time.sleep(0.5)
            # تا زمانی که رویداد خاموش شدن set نشده، هر نیم ثانیه یک‌بار چک می‌کند

    except Exception:
        app_logger.exception(
            "Fatal error in main loop"
        )
        # اگر خطای غیرمنتظره در حلقه اصلی رخ دهد، لاگ کامل ثبت می‌کند

    finally:
        # --------------------------------------------------------------
        # 9) Controlled legacy shutdown
        # --------------------------------------------------------------
        # ۹) خاموش شدن کنترل‌شده و تمیز

        app_logger.info(
            "Shutting down..."
        )
        # لاگ شروع فرآیند خاموش شدن

        # Stop the selected command runtime before ClientAuth.
        # ابتدا مسیر اجرایی فرمان را متوقف می‌کنیم
        try:
            if worker is not None:
                worker.stop()
                # توقف AgentWorker
            elif listener is not None:
                listener.stop()
                # توقف KafkaListener

            if runtime_thread is not None:
                runtime_thread.join(
                    timeout=float(
                        config.get("app.shutdown_join_timeout_sec", 10.0)
                    )
                )
                # منتظر می‌ماند تا نخ اجرایی تمام شود (حداکثر زمان مشخص‌شده)
        except Exception:
            app_logger.exception("Failed to stop command runtime")
            # لاگ خطا در صورت شکست توقف مسیر اجرایی

        # Stop ClientAuth / heartbeat.
        # سپس ClientAuth و heartbeat را متوقف می‌کنیم
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception(
                "Failed to stop ClientAuth"
            )
            # لاگ خطا در صورت شکست توقف ClientAuth

        app_logger.info(
            "Bye."
        )
        # لاگ پایان برنامه


# ======================================================================
# Direct execution compatibility
# ======================================================================
# سازگاری با اجرای مستقیم فایل

if __name__ == "__main__":
    main()
    # اگر این فایل مستقیماً اجرا شود، تابع main را صدا می‌زند