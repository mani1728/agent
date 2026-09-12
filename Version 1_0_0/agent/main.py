# Path: Version 1_0_0/agent/main.py
# مسیر فایل: نقطه ورود اصلی برنامه (سازگار با مسیر قدیمی و مسیر استاندارد Worker)

# -*- coding: utf-8 -*-
# تعیین کدگذاری UTF-8 برای پشتیبانی کامل از فارسی و کاراکترهای چندزبانه

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
- Transport migration is incremental and backward-compatible.
"""
# این docstring مشخص می‌کند که:
# 1) رفتارهای legacy نگه داشته شده‌اند
# 2) مسیر استاندارد، AgentWorker است
# 3) مهاجرت تدریجی و سازگار با نسخه‌های قبلی انجام می‌شود

from __future__ import annotations
# فعال‌سازی ارزیابی تأخیری type hintها برای سازگاری بهتر importها

# ======================================================================
# Standard library
# ======================================================================
# کتابخانه‌های استاندارد پایتون

import getpass
# برای دریافت نام کاربر سیستم‌عامل

import logging
# برای ثبت لاگ در سطوح مختلف

import platform
# برای خواندن اطلاعات سیستم‌عامل

import signal
# برای مدیریت سیگنال‌های shutdown مثل Ctrl+C

import sys
# برای اطلاعات runtime پایتون

import threading
# برای اجرای worker/listener روی Thread جدا

import time
# برای sleep در حلقه انتظار اصلی

from typing import Any
# برای استفاده از Any در type hintها


# ======================================================================
# Application dependencies
# ======================================================================
# وابستگی‌های داخلی اپلیکیشن با پشتیبانی از دو حالت اجرا

try:  # Package-safe execution: python -m agent
    # حالت اجرای پکیجی (پیشنهادی)
    from .core.command_executor import CommandExecutor
    from .core.worker import AgentWorker
    from .infrastructure.config_logging import setup_logging
    from .infrastructure.config_manager import cfg
    from .security.client_auth import ClientAuth
    from .transport.factory import TransportFactory
    from .reliability.idempotency import SQLiteIdempotencyStore
except ImportError:  # Direct execution compatibility: python agent/main.py
    # حالت اجرای مستقیم فایل برای سازگاری
    from agent.core.command_executor import CommandExecutor
    from agent.core.worker import AgentWorker
    from agent.infrastructure.config_logging import setup_logging
    from agent.infrastructure.config_manager import cfg
    from agent.security.client_auth import ClientAuth
    from agent.transport.factory import TransportFactory
    from agent.reliability.idempotency import SQLiteIdempotencyStore

try:
    # Listener قدیمی اختیاری است (فقط برای compatibility path)
    from .transport.kafka.listener import KafkaListener as _KafkaListener
except Exception:  # pragma: no cover - optional dependency
    # اگر dependency موجود نبود، مسیر legacy listener غیرفعال می‌شود
    _KafkaListener = None


# ======================================================================
# Global shutdown event
# ======================================================================
# رویداد سراسری shutdown برای کنترل خاموش شدن تمیز

_shutdown_event = threading.Event()
# وقتی set شود، حلقه اصلی main وارد مسیر shutdown می‌شود


# ======================================================================
# ClientAuth logging bridge
# ======================================================================
# پل لاگ: خروجی ClientAuth را به logging استاندارد برنامه وصل می‌کند

def _clientauth_logger(level: str, msg: str, **kw: Any) -> None:
    """
    Bridge ClientAuth logging into Python logging.
    """
    # تبدیل سطح لاگ رشته‌ای به مقدار معتبر logging
    lvl = getattr(logging, str(level).upper(), logging.INFO)

    # افزودن kwargs به پیام برای حفظ context
    message = f"{msg} | {kw}" if kw else msg

    # ثبت لاگ در logger اختصاصی ClientAuth
    logging.getLogger("ClientAuth").log(lvl, message)


# ======================================================================
# Signal handling
# ======================================================================
# مدیریت سیگنال‌های سیستم‌عامل

def _handle_signal(signum: int, frame: Any) -> None:
    """
    Request application shutdown.
    """
    # ثبت دریافت سیگنال در لاگ
    logging.getLogger("App").info(
        "Shutdown signal received",
        extra={"signum": signum},
    )

    # فعال‌کردن فلگ shutdown
    _shutdown_event.set()


def _config_bool(config: Any, path: str, default: bool = False) -> bool:
    """
    Read boolean safely from config without 'false' string pitfall.
    """
    # خواندن مقدار خام
    value = config.get(path, default)

    # اگر رشته باشد، به‌صورت صریح parse می‌کنیم
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    # در غیر این صورت cast مستقیم
    return bool(value)


def _safe_config_value(config: Any, path: str, default: Any = None) -> Any:
    """
    Safe config reader (never raises).
    """
    # تلاش برای خواندن مقدار
    try:
        return config.get(path, default)
    except Exception:
        # در هر خطا، مقدار پیش‌فرض بازگردانده می‌شود
        return default


def _normalize_kafka_topics(config: Any, logger: logging.Logger) -> None:
    """
    Normalize topic schema into canonical kafka.topics.commands list.

    Supported inputs:
    - kafka.topics.commands (preferred)
    - topics.command_p0 / topics.command_p1 / topics.command_p2 (legacy/global)
    """
    # ابتدا ساختار canonical را می‌خوانیم
    existing = _safe_config_value(config, "kafka.topics.commands", None)

    # اگر canonical از قبل معتبر باشد، کاری نمی‌کنیم
    if isinstance(existing, (list, tuple)) and any(str(x).strip() for x in existing):
        return

    # fallback از ساختار topics.command_p*
    p0 = _safe_config_value(config, "topics.command_p0", None)
    p1 = _safe_config_value(config, "topics.command_p1", None)
    p2 = _safe_config_value(config, "topics.command_p2", None)

    # لیست‌سازی با حذف مقادیر خالی
    derived = [str(x).strip() for x in (p0, p1, p2) if x is not None and str(x).strip()]

    # اگر چیزی پیدا شد، canonical را پر می‌کنیم
    if derived:
        try:
            config._data.setdefault("kafka", {})
            config._data["kafka"].setdefault("topics", {})
            config._data["kafka"]["topics"]["commands"] = derived
            logger.info(
                "Kafka command topics normalized into kafka.topics.commands",
                extra={"commands": derived},
            )
        except Exception:
            logger.exception("Failed to normalize Kafka command topics")


def _build_idempotency_store(
    config: Any,
    logger: logging.Logger,
) -> SQLiteIdempotencyStore | None:
    """
    Build SQLite idempotency store from persistence/reliability config.
    """
    # خواندن بخش‌های احتمالی تنظیمات
    persistence_config = _safe_config_value(config, "persistence", {})
    reliability_config = _safe_config_value(config, "reliability", {})

    # مسیر DB با چند fallback
    db_path = _safe_config_value(config, "persistence.idempotency_db_path", None)
    if not db_path:
        db_path = _safe_config_value(persistence_config, "idempotency_db_path", None)
    if not db_path:
        db_path = _safe_config_value(config, "persistence.spool_db_path", None)
    if not db_path:
        db_path = _safe_config_value(persistence_config, "spool_db_path", None)

    # اگر DB path نداریم، store ساخته نمی‌شود
    if not db_path:
        return None

    # تبدیل امن float
    def _coerce_float(raw: Any, default: float | None) -> float | None:
        if raw is None:
            return default
        try:
            value = float(raw)
        except Exception:
            return default
        if value < 0:
            return default
        return value

    # TTL اصلی:
    # اولویت با persistence.idempotency_ttl_seconds
    # fallback به reliability.idempotency_ttl_sec
    ttl_seconds = _coerce_float(
        _safe_config_value(config, "persistence.idempotency_ttl_seconds", None),
        None,
    )
    if ttl_seconds is None:
        ttl_seconds = _coerce_float(
            _safe_config_value(reliability_config, "idempotency_ttl_sec", None),
            None,
        )

    # TTL رکوردهای in-progress:
    # اولویت با persistence.idempotency_in_progress_ttl_seconds
    # fallback به reliability.in_progress_ttl_sec
    in_progress_ttl_seconds = _coerce_float(
        _safe_config_value(config, "persistence.idempotency_in_progress_ttl_seconds", None),
        None,
    )
    if in_progress_ttl_seconds is None:
        in_progress_ttl_seconds = _coerce_float(
            _safe_config_value(reliability_config, "in_progress_ttl_sec", None),
            None,
        )
    if in_progress_ttl_seconds is None:
        in_progress_ttl_seconds = 600.0

    # ساخت Store
    try:
        return SQLiteIdempotencyStore(
            db_path,
            ttl_seconds=ttl_seconds,
            in_progress_ttl_seconds=in_progress_ttl_seconds,
        )
    except Exception:
        logger.exception("Failed to initialize SQLite idempotency store.")
        return None


def _validate_canonical_kafka_config(config: Any) -> None:
    """
    Validate minimum operational Kafka settings for worker path.
    """
    # خواندن کلیدهای ضروری
    required = {
        "kafka.bootstrap_servers": config.get("kafka.bootstrap_servers", None),
        "kafka.group_id": config.get("kafka.group_id", None),
        "kafka.topics.commands": config.get("kafka.topics.commands", None),
    }

    missing: list[str] = []

    # اعتبارسنجی خالی نبودن
    for key, value in required.items():
        if isinstance(value, (list, tuple)):
            if not any(str(item).strip() for item in value):
                missing.append(key)
        elif value is None or not str(value).strip():
            missing.append(key)

    # auto-commit باید false باشد
    auto_commit = config.get("kafka.enable_auto_commit", None)
    auto_commit_is_false = (
        auto_commit is False
        or (
            isinstance(auto_commit, str)
            and auto_commit.strip().lower() in {"0", "false", "no", "off"}
        )
    )
    if not auto_commit_is_false:
        missing.append("kafka.enable_auto_commit=false")

    # اگر مورد ناقص وجود داشت، fail-fast
    if missing:
        raise RuntimeError(
            "Canonical Kafka runtime configuration is not operationally configured; "
            "missing required settings: " + ", ".join(missing)
        )


# ======================================================================
# Main application entry point
# ======================================================================
# تابع اصلی راه‌اندازی/توقف برنامه

def main() -> None:
    """
    Legacy-compatible startup/shutdown sequence with canonical worker path.
    """
    # ریست فلگ shutdown
    _shutdown_event.clear()

    # بارگذاری تنظیمات hot-reload
    config = cfg()

    # تنظیم لاگ
    setup_logging(config)
    app_logger = logging.getLogger("App")
    app_logger.info("Application bootstrap started (hot-reload config enabled).")

    # نرمال‌سازی topicها قبل از هر validation
    _normalize_kafka_topics(config, app_logger)

    # ClientAuth (مسیر legacy-preserved)
    ca = None
    try:
        # متادیتای کلاینت
        meta = {
            "os": platform.platform(),
            "username": getpass.getuser(),
            "python": sys.version.split()[0],
            "agent_version": "1.0.0",
            "capabilities": ["mt5", "reports"],
        }

        # ساخت auth client
        ca = ClientAuth(client_meta=meta, logger=_clientauth_logger)

        # register + heartbeat
        ca.register()

        # بعد از register موفق، topicها و group_id با client_id واقعی به‌روز می‌شوند
        try:
            config._data.setdefault("kafka", {})["client_id"] = ca.client_id

            final_cmd_topics = [
                f"cmd.{ca.client_id}.p0",
                f"cmd.{ca.client_id}.p1",
                f"cmd.{ca.client_id}.p2",
            ]

            config._data["kafka"].setdefault("topics", {})
            config._data["kafka"]["topics"]["commands"] = final_cmd_topics
            config._data["kafka"]["group_id"] = f"mt5-service.{ca.client_id}"

            app_logger.info(
                "Client topics updated after registration",
                extra={"client_id": ca.client_id, "topics": final_cmd_topics},
            )
        except Exception:
            app_logger.exception("Failed to update topics after registration")

    except Exception:
        # رفتار legacy: شکست register فقط لاگ می‌شود
        app_logger.exception("Client registration failed")

    # guard: kafka.enabled
    if not bool(config.get("kafka.enabled", True)):
        app_logger.warning("Kafka is disabled by config (kafka.enabled=false). Exiting main.")
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")
        return

    # انتخاب مسیر runtime با feature flag
    use_agent_worker = _config_bool(config, "app.use_agent_worker", True)

    listener = None
    worker = None
    runtime_thread = None

    try:
        if use_agent_worker:
            # مسیر canonical
            _validate_canonical_kafka_config(config)

            transport = TransportFactory.create(config)

            worker = AgentWorker(
                CommandExecutor(),
                transport,
                poll_timeout_sec=float(config.get("app.worker_poll_timeout_sec", 1.0)),
                idempotency_store=_build_idempotency_store(config, app_logger),
                close_idempotency_store=True,
            )

            runtime_thread = threading.Thread(
                target=worker.run,
                name="AgentWorker",
                daemon=True,
            )

            app_logger.info("AgentWorker path selected by feature flag")
        else:
            # مسیر legacy listener
            if _KafkaListener is None:
                raise RuntimeError(
                    "Kafka listener dependency is unavailable (missing runtime dependency)"
                )

            listener = _KafkaListener(config)

            runtime_thread = threading.Thread(
                target=listener.listen,
                name="KafkaListener",
                daemon=True,
            )

            app_logger.info("Legacy KafkaListener path selected")

    except Exception:
        # خطا در bootstrap مسیر اجرایی
        app_logger.exception("Failed to initialize selected runtime path")

        # cleanup ClientAuth در صورت نیاز
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")

        # re-raise برای fail-fast
        raise

    # ثبت handler سیگنال‌ها
    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        # روی برخی runtimeهای ویندوز SIGTERM ممکن است پشتیبانی نشود
        pass

    # شروع Thread مسیر اجرایی
    runtime_thread.start()
    app_logger.info("Runtime path started: worker_enabled=%s", use_agent_worker)

    # حلقه انتظار اصلی
    try:
        while not _shutdown_event.is_set():
            time.sleep(0.5)
    except Exception:
        app_logger.exception("Fatal error in main loop")
    finally:
        # shutdown کنترل‌شده
        app_logger.info("Shutting down...")

        # ابتدا worker/listener
        try:
            if worker is not None:
                worker.stop()
            elif listener is not None:
                listener.stop()

            if runtime_thread is not None:
                runtime_thread.join(
                    timeout=float(config.get("app.shutdown_join_timeout_sec", 10.0))
                )
        except Exception:
            app_logger.exception("Failed to stop command runtime")

        # سپس ClientAuth
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")

        app_logger.info("Bye.")


# اجرای مستقیم فایل
if __name__ == "__main__":
    # entry point
    main()
