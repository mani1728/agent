# Path: Version 1_0_0/agent/main.py
# مسیر فایل: نقطه ورود اصلی برنامه (سازگار با نسخه قدیمی + مسیر canonical worker)

# -*- coding: utf-8 -*-
# تعیین کدگذاری فایل به UTF-8 برای پشتیبانی کامل از کاراکترهای فارسی و سایر زبان‌ها

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
6) Start KafkaListener or AgentWorker (feature-flag driven).
7) Wait for shutdown.
8) Stop command runtime and ClientAuth cleanly.
"""
# این docstring وضعیت مهاجرت و مسئولیت‌های اصلی فایل را توضیح می‌دهد.
# نکته مهم: مسیر Worker مسیر استاندارد است، ولی مسیر Listener قدیمی برای سازگاری هنوز باقی است.

from __future__ import annotations
# فعال‌سازی postponed evaluation برای type hints
# (برای سازگاری بهتر و جلوگیری از برخی مشکلات وابستگی دوری)

# ======================================================================
# Standard library
# ======================================================================
# کتابخانه‌های استاندارد پایتون

import getpass
# برای دریافت نام کاربر سیستم‌عامل

import logging
# زیرساخت لاگ‌گیری استاندارد پایتون

import platform
# برای دریافت اطلاعات سیستم‌عامل

import signal
# برای مدیریت سیگنال‌های OS مثل SIGINT/SIGTERM

import sys
# برای دسترسی به اطلاعات مفسر پایتون و محیط اجرا

import threading
# برای ساخت و مدیریت Thread

import time
# برای sleep و کنترل حلقه انتظار

from typing import Any
# برای تایپ Any (در توابع helper استفاده می‌شود)


# ======================================================================
# Application dependencies
# ======================================================================
# وابستگی‌های داخلی برنامه (با پشتیبانی از دو حالت import)

try:  # Package-safe execution: python -m agent
    # حالت پیشنهادی اجرا: به‌صورت پکیج
    from .core.command_executor import CommandExecutor
    from .core.worker import AgentWorker
    from .infrastructure.config_logging import setup_logging
    from .infrastructure.config_manager import cfg
    from .security.client_auth import ClientAuth
    from .transport.factory import TransportFactory
    from .reliability.idempotency import SQLiteIdempotencyStore
except ImportError:  # Direct execution compatibility: python agent/main.py
    # حالت سازگاری با اجرای مستقیم فایل
    from agent.core.command_executor import CommandExecutor
    from agent.core.worker import AgentWorker
    from agent.infrastructure.config_logging import setup_logging
    from agent.infrastructure.config_manager import cfg
    from agent.security.client_auth import ClientAuth
    from agent.transport.factory import TransportFactory
    from agent.reliability.idempotency import SQLiteIdempotencyStore

try:
    # Listener قدیمی فقط برای compatibility path
    from .transport.kafka.listener import KafkaListener as _KafkaListener
except Exception:  # pragma: no cover - optional dependency
    # اگر dependency موجود نبود، مسیر legacy listener غیرفعال می‌شود
    _KafkaListener = None


# ======================================================================
# Global shutdown event
# ======================================================================
# رویداد سراسری برای مدیریت shutdown هماهنگ کل برنامه

_shutdown_event = threading.Event()
# وقتی set شود، حلقه اصلی main باید فرآیند خاموش شدن را آغاز کند


# ======================================================================
# ClientAuth logging bridge
# ======================================================================
# پل لاگ برای هماهنگ کردن خروجی ClientAuth با logging استاندارد

def _clientauth_logger(
    level: str,
    msg: str,
    **kw: Any,
) -> None:
    """
    Bridge ClientAuth logging into Python's standard logging system.
    """
    # سطح لاگ رشته‌ای را به سطح واقعی logging نگاشت می‌کند.
    lvl = getattr(logging, str(level).upper(), logging.INFO)

    # اگر kwargs داشته باشیم، به پیام اضافه می‌کنیم تا context حفظ شود.
    message = f"{msg} | {kw}" if kw else msg

    # لاگ نهایی داخل logger اختصاصی ClientAuth ثبت می‌شود.
    logging.getLogger("ClientAuth").log(lvl, message)


# ======================================================================
# Signal handling
# ======================================================================
# مدیریت سیگنال‌های سیستم‌عامل (Ctrl+C و SIGTERM)

def _handle_signal(
    signum: int,
    frame: Any,
) -> None:
    """
    Request application shutdown.
    """
    # لاگ دریافت سیگنال برای audit/diagnostics
    logging.getLogger("App").info(
        "Shutdown signal received",
        extra={"signum": signum},
    )

    # فقط shutdown event را set می‌کنیم؛ cleanup کامل در finallyِ main انجام می‌شود.
    _shutdown_event.set()


def _config_bool(config: Any, path: str, default: bool = False) -> bool:
    """
    Read a JSON-compatible boolean without treating "false" as True.
    """
    # مقدار raw را از config می‌خوانیم.
    value = config.get(path, default)

    # اگر رشته بود، تبدیل امن و صریح انجام می‌دهیم.
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    # در غیر این صورت cast استاندارد به bool
    return bool(value)


def _safe_config_value(config: Any, path: str, default: Any = None) -> Any:
    """
    Safely read config value, fallback to default on any access error.
    """
    try:
        return config.get(path, default)
    except Exception:
        return default


def _build_idempotency_store(
    config: Any,
    logger: logging.Logger,
) -> SQLiteIdempotencyStore | None:
    """
    Build SQLite idempotency store if a valid db_path is available.
    """
    # ابتدا بخش persistence را می‌خوانیم (اگر نبود، دیکشنری خالی)
    persistence_config = _safe_config_value(config, "persistence", {})

    # اولویت اول: مسیر صریح idempotency DB
    db_path = _safe_config_value(config, "persistence.idempotency_db_path", None)

    # fallback از زیرشاخه persistence
    if not db_path:
        db_path = _safe_config_value(persistence_config, "idempotency_db_path", None)

    # fallback تاریخی: spool_db_path
    if not db_path:
        db_path = _safe_config_value(config, "persistence.spool_db_path", None)

    # fallback spool داخل persistence
    if not db_path:
        db_path = _safe_config_value(persistence_config, "spool_db_path", None)

    # اگر هیچ path معتبری نبود، store نمی‌سازیم.
    if not db_path:
        return None

    # helper داخلی برای parse امن float
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

    # TTL کلی رکوردها
    ttl_seconds = _coerce_float(
        _safe_config_value(config, "persistence.idempotency_ttl_seconds", None),
        None,
    )

    # TTL رکوردهای in-progress (پیش‌فرض 600 ثانیه)
    in_progress_ttl_seconds = _coerce_float(
        _safe_config_value(
            config,
            "persistence.idempotency_in_progress_ttl_seconds",
            600.0,
        ),
        600.0,
    )

    # ساخت store با handling خطا
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
    Validate minimum operational Kafka settings for the worker path.
    """
    # کلیدهای ضروری برای runtime استاندارد worker + kafka
    required = {
        "kafka.bootstrap_servers": config.get("kafka.bootstrap_servers", None),
        "kafka.group_id": config.get("kafka.group_id", None),
        "kafka.topics.commands": config.get("kafka.topics.commands", None),
    }

    missing: list[str] = []

    # بررسی مقادیر خالی/نامعتبر
    for key, value in required.items():
        if isinstance(value, (list, tuple)):
            if not any(str(item).strip() for item in value):
                missing.append(key)
        elif value is None or not str(value).strip():
            missing.append(key)

    # در مسیر canonical، auto commit باید قطعاً false باشد.
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

    # اگر چیزی missing بود، startup را fail-fast می‌کنیم.
    if missing:
        raise RuntimeError(
            "Canonical Kafka runtime configuration is not operationally "
            "configured; missing required settings: " + ", ".join(missing)
        )


# ======================================================================
# Main application entry point
# ======================================================================
# نقطه ورود اصلی برنامه

def main() -> None:
    """
    Legacy-compatible startup/shutdown sequence with canonical worker path.
    """
    # ------------------------------------------------------------------
    # 1) Reset shutdown state
    # ------------------------------------------------------------------
    _shutdown_event.clear()

    # ------------------------------------------------------------------
    # 2) Load hot-reload configuration
    # ------------------------------------------------------------------
    config = cfg()

    # ------------------------------------------------------------------
    # 3) Configure logging
    # ------------------------------------------------------------------
    setup_logging(config)
    app_logger = logging.getLogger("App")
    app_logger.info("Application bootstrap started (hot-reload config enabled).")

    # ------------------------------------------------------------------
    # 4) Client registration / heartbeat (legacy-preserved behavior)
    # ------------------------------------------------------------------
    ca = None
    try:
        # متادیتای runtime برای register شدن در gateway/auth
        meta = {
            "os": platform.platform(),
            "username": getpass.getuser(),
            "python": sys.version.split()[0],
            "agent_version": "0.1.0",
            "capabilities": ["mt5", "reports"],
        }

        # ساخت ClientAuth و اتصال لاگ bridge
        ca = ClientAuth(client_meta=meta, logger=_clientauth_logger)

        # ثبت کلاینت + heartbeat
        ca.register()

        # بعد از ثبت موفق، تاپیک‌های kafka با client_id واقعی آپدیت می‌شوند.
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
        # رفتار قدیمی حفظ می‌شود: خطای ثبت فقط لاگ می‌شود، crash فوری نداریم.
        app_logger.exception("Client registration failed")

    # ------------------------------------------------------------------
    # 5) Kafka enabled guard
    # ------------------------------------------------------------------
    if not bool(config.get("kafka.enabled", True)):
        app_logger.warning(
            "Kafka is disabled by config (kafka.enabled=false). Exiting main."
        )
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")
        return

    # ------------------------------------------------------------------
    # 6) Choose runtime path by feature flag
    # ------------------------------------------------------------------
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
            # مسیر compatibility
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
        app_logger.exception("Failed to initialize selected runtime path")
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")
        raise

    # ------------------------------------------------------------------
    # 7) Register OS signal handlers
    # ------------------------------------------------------------------
    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        # روی بعضی runtime های ویندوز ممکن است SIGTERM پشتیبانی نشود.
        pass

    # ------------------------------------------------------------------
    # 8) Start runtime thread
    # ------------------------------------------------------------------
    runtime_thread.start()
    app_logger.info("Runtime path started: worker_enabled=%s", use_agent_worker)

    # ------------------------------------------------------------------
    # 9) Main wait loop
    # ------------------------------------------------------------------
    try:
        while not _shutdown_event.is_set():
            time.sleep(0.5)
    except Exception:
        app_logger.exception("Fatal error in main loop")
    finally:
        # ------------------------------------------------------------------
        # 10) Controlled shutdown
        # ------------------------------------------------------------------
        app_logger.info("Shutting down...")

        # ابتدا runtime فرمان را متوقف می‌کنیم.
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

        # سپس ClientAuth / heartbeat
        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception("Failed to stop ClientAuth")

        app_logger.info("Bye.")


# ======================================================================
# Direct execution compatibility
# ======================================================================
# سازگاری با اجرای مستقیم فایل

if __name__ == "__main__":
    # اگر فایل مستقیم اجرا شود، main اجرا می‌شود.
    main()
