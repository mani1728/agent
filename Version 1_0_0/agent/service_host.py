# Path: Version 1_0_0/agent/service_host.py
# مسیر فایل: میزبان سرویس ویندوز برای Agent

from __future__ import annotations
# فعال‌سازی ارزیابی تأخیری تایپ‌هینت‌ها

import importlib          # برای بارگذاری پویای ماژول‌ها
import logging            # سیستم لاگ
import sys                # دسترسی به آرگومان‌های خط فرمان و اطلاعات مفسر
import threading          # کار با نخ‌ها
import time               # توابع زمانی
from typing import Optional  # تایپ اختیاری

try:
    import win32event
    import win32service
    import win32serviceutil
except ImportError:  # pragma: no cover - non-Windows environments
    # اگر کتابخانه pywin32 نصب نباشد (مثلاً در محیط غیر ویندوز)
    # متغیرها را None می‌گذاریم تا ایمپورت فایل خطا ندهد
    win32event = None
    win32service = None
    win32serviceutil = None


logger = logging.getLogger(__name__)
# لاگر مخصوص این ماژول


SERVICE_NAME = "MT5Agent"
# نام داخلی سرویس ویندوز

SERVICE_DISPLAY_NAME = "MT5 Agent"
# نام نمایشی سرویس در لیست سرویس‌های ویندوز

SERVICE_DESCRIPTION = (
    "MetaTrader 5 Agent service."
)
# توضیح کوتاه سرویس

SERVICE_STOP_TIMEOUT_SEC = 30.0
# حداکثر زمان انتظار برای توقف تمیز Agent (بر حسب ثانیه)


def _load_legacy_main():
    """
    Load the application's legacy bootstrap module.

    Kept as a lazily-imported helper so service-host import does not
    create circular module initialization issues.
    """
    # بارگذاری تنبل (lazy) ماژول اصلی قدیمی برنامه
    # این کار برای جلوگیری از ایجاد وابستگی دایره‌ای هنگام ایمپورت انجام می‌شود
    return importlib.import_module("agent.main")


class ServiceHostError(RuntimeError):
    """Base error for Windows service host failures."""
    # خطای پایه برای مشکلات مربوط به میزبان سرویس ویندوز


if win32serviceutil is not None:
    # فقط وقتی pywin32 در دسترس باشد، کلاس واقعی سرویس تعریف می‌شود

    class MT5AgentService(win32serviceutil.ServiceFramework):
        """
        Windows Service wrapper around the existing agent entry point.

        The service host owns only the Windows Service lifecycle. Agent
        business logic remains in the existing main/worker layers.
        """
        # این کلاس فقط چرخه حیات سرویس ویندوز را مدیریت می‌کند
        # منطق اصلی Agent همچنان در لایه‌های main و worker باقی می‌ماند

        _svc_name_ = SERVICE_NAME
        # نام سرویس

        _svc_display_name_ = SERVICE_DISPLAY_NAME
        # نام نمایشی سرویس

        _svc_description_ = SERVICE_DESCRIPTION
        # توضیح سرویس

        def __init__(
            self,
            args: list[str],
        ) -> None:
            super().__init__(args)
            # فراخوانی سازنده کلاس پایه

            self._stop_event = threading.Event()
            # رویداد داخلی برای اعلام درخواست توقف

            self._main_thread: Optional[threading.Thread] = None
            # نخی که تابع main مربوط به Agent روی آن اجرا می‌شود

            self._legacy_main_module = None
            # نگهداری ماژول main بعد از بارگذاری

            self._service_stop_handle = win32event.CreateEvent(
                None,
                True,
                False,
                None,
            )
            # ساخت یک Event ویندوزی برای سیگنال توقف سرویس

        # --------------------------------------------------------------
        # Service lifecycle
        # --------------------------------------------------------------
        # بخش چرخه حیات سرویس

        def SvcStop(self) -> None:
            # متدی که ویندوز هنگام درخواست توقف سرویس صدا می‌زند
            logger.info("Windows service stop requested")
            # ثبت درخواست توقف

            self.ReportServiceStatus(
                win32service.SERVICE_STOP_PENDING
            )
            # اعلام وضعیت «در حال توقف» به ویندوز

            self._stop_event.set()
            # فعال کردن رویداد توقف داخلی

            try:
                win32event.SetEvent(
                    self._service_stop_handle
                )
                # سیگنال دادن به Event ویندوزی
            except Exception:
                logger.debug(
                    "Unable to signal service stop event",
                    exc_info=True,
                )
                # در صورت شکست، فقط لاگ دیباگ ثبت می‌شود

            self._request_agent_shutdown()
            # درخواست خاموش شدن نرم از سمت Agent

        def SvcDoRun(self) -> None:
            # متد اصلی اجرای سرویس (وقتی سرویس استارت می‌شود)
            logger.info(
                "Starting Windows service: %s",
                SERVICE_NAME,
            )
            # لاگ شروع سرویس

            self.ReportServiceStatus(
                win32service.SERVICE_START_PENDING
            )
            # اعلام وضعیت «در حال شروع» به ویندوز

            self._main_thread = threading.Thread(
                target=self._run_agent,
                name="mt5-agent-main",
                daemon=False,
            )
            # ساخت نخ برای اجرای Agent (غیر daemon تا سرویس زود بسته نشود)

            self._main_thread.start()
            # شروع نخ Agent

            self.ReportServiceStatus(
                win32service.SERVICE_RUNNING
            )
            # اعلام وضعیت «در حال اجرا» به ویندوز

            self._wait_for_agent()
            # منتظر ماندن تا Agent تمام شود یا درخواست توقف بیاید

            self.ReportServiceStatus(
                win32service.SERVICE_STOP_PENDING
            )
            # اعلام وضعیت «در حال توقف»

            self._wait_for_main_thread()
            # منتظر ماندن محدود برای تمام شدن نخ اصلی

            logger.info(
                "Windows service stopped: %s",
                SERVICE_NAME,
            )
            # لاگ توقف کامل سرویس

        # --------------------------------------------------------------
        # Agent execution
        # --------------------------------------------------------------
        # بخش اجرای Agent

        def _run_agent(self) -> None:
            # تابعی که روی نخ جداگانه اجرا می‌شود و Agent را راه می‌اندازد
            try:
                self._legacy_main_module = (
                    _load_legacy_main()
                )
                # بارگذاری ماژول main قدیمی

                main_func = getattr(
                    self._legacy_main_module,
                    "main",
                    None,
                )
                # گرفتن تابع main از ماژول

                if not callable(main_func):
                    raise ServiceHostError(
                        "Legacy main module does not expose main()"
                    )
                    # اگر تابع main وجود نداشته باشد، خطا پرتاب می‌شود

                main_func()
                # اجرای تابع main مربوط به Agent

            except Exception:
                logger.exception(
                    "Agent main loop terminated with an exception"
                )
                # ثبت کامل خطا در صورت بروز مشکل

            finally:
                self._stop_event.set()
                # در هر صورت رویداد توقف را فعال می‌کند

        def _request_agent_shutdown(self) -> None:
            """
            Request graceful shutdown from the existing legacy main.

            The legacy main owns the actual shutdown event. Reusing it avoids
            introducing a second lifecycle mechanism during migration.
            """
            # درخواست خاموش شدن نرم از main قدیمی
            # با استفاده از همان رویداد خاموش شدن موجود، از ایجاد مکانیزم دوم جلوگیری می‌شود

            module = self._legacy_main_module

            if module is None:
                return
                # اگر هنوز ماژول بارگذاری نشده، کاری انجام نمی‌دهد

            shutdown_event = getattr(
                module,
                "_shutdown_event",
                None,
            )
            # گرفتن رویداد خاموش شدن از ماژول main

            if shutdown_event is None:
                logger.warning(
                    "Legacy main shutdown event is unavailable"
                )
                return
                # اگر رویداد پیدا نشود، هشدار می‌دهد و خارج می‌شود

            try:
                shutdown_event.set()
                # فعال کردن رویداد خاموش شدن Agent
            except Exception:
                logger.exception(
                    "Unable to request legacy agent shutdown"
                )
                # ثبت خطا در صورت شکست

        # --------------------------------------------------------------
        # Waiting / bounded shutdown
        # --------------------------------------------------------------
        # بخش انتظار و توقف محدودشده

        def _wait_for_agent(self) -> None:
            """
            Wait until either the service is stopped or the agent exits.
            """
            # منتظر می‌ماند تا یا سرویس متوقف شود یا Agent خودش تمام شود

            while not self._stop_event.is_set():
                # تا زمانی که رویداد توقف فعال نشده

                if (
                    self._main_thread is not None
                    and not self._main_thread.is_alive()
                ):
                    return
                    # اگر نخ Agent مرده باشد، از حلقه خارج می‌شود

                try:
                    result = win32event.WaitForSingleObject(
                        self._service_stop_handle,
                        1000,
                    )
                    # منتظر سیگنال توقف ویندوز (حداکثر ۱ ثانیه)

                    if result == win32event.WAIT_OBJECT_0:
                        return
                        # اگر سیگنال توقف آمد، خارج می‌شود

                except Exception:
                    logger.debug(
                        "Service wait failed; "
                        "falling back to event wait",
                        exc_info=True,
                    )
                    # در صورت خطا، به روش ساده‌تر (Event پایتون) برمی‌گردد

                    self._stop_event.wait(1.0)
                    # یک ثانیه منتظر رویداد داخلی می‌ماند

        def _wait_for_main_thread(self) -> None:
            # منتظر تمام شدن نخ اصلی با محدودیت زمانی
            thread = self._main_thread

            if thread is None:
                return
                # اگر نخی وجود نداشته باشد، کاری نمی‌کند

            deadline = (
                time.monotonic()
                + SERVICE_STOP_TIMEOUT_SEC
            )
            # محاسبه زمان نهایی مجاز برای توقف

            while thread.is_alive():
                # تا زمانی که نخ زنده است

                remaining = (
                    deadline - time.monotonic()
                )
                # محاسبه زمان باقی‌مانده

                if remaining <= 0:
                    logger.error(
                        "Agent did not stop within "
                        "%s seconds",
                        SERVICE_STOP_TIMEOUT_SEC,
                    )
                    return
                    # اگر زمان تمام شد، خطا لاگ می‌کند و خارج می‌شود

                thread.join(
                    timeout=min(0.5, remaining)
                )
                # حداکثر نیم ثانیه (یا زمان باقی‌مانده) منتظر می‌ماند


else:
    # اگر pywin32 در دسترس نباشد

    class MT5AgentService:
        """
        Placeholder used when pywin32 is unavailable.

        This keeps importing the package possible on non-Windows systems
        while making actual Windows Service execution fail explicitly.
        """
        # کلاس جایگزین برای محیط‌های غیر ویندوز
        # اجازه می‌دهد پکیج ایمپورت شود، اما اجرای واقعی سرویس با خطا مواجه شود

        def __init__(
            self,
            *args: object,
            **kwargs: object,
        ) -> None:
            raise ServiceHostError(
                "pywin32 is required to run MT5Agent as a Windows service"
            )
            # همیشه خطا پرتاب می‌کند تا مشخص شود pywin32 لازم است


# ----------------------------------------------------------------------
# Service management
# ----------------------------------------------------------------------
# توابع مدیریت سرویس (نصب، حذف، شروع، توقف)


def install_service() -> None:
    """
    Install the Windows service.
    """
    # نصب سرویس ویندوز
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to install the Windows service"
        )
        # اگر pywin32 نباشد، خطا می‌دهد

    win32serviceutil.InstallService(
        MT5AgentService,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        startType=win32service.SERVICE_AUTO_START,
        description=SERVICE_DESCRIPTION,
    )
    # نصب سرویس با شروع خودکار


def remove_service() -> None:
    """
    Remove the Windows service.
    """
    # حذف سرویس ویندوز
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to remove the Windows service"
        )

    win32serviceutil.RemoveService(
        SERVICE_NAME
    )
    # حذف سرویس با نام مشخص‌شده


def start_service() -> None:
    """
    Start the installed Windows service.
    """
    # شروع سرویس نصب‌شده
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to start the Windows service"
        )

    win32serviceutil.StartService(
        SERVICE_NAME
    )


def stop_service() -> None:
    """
    Stop the installed Windows service.
    """
    # توقف سرویس نصب‌شده
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to stop the Windows service"
        )

    win32serviceutil.StopService(
        SERVICE_NAME
    )


def run_service_command(args: Optional[list[str]] = None) -> None:
    """
    Delegate standard Windows Service commands to pywin32.

    Supported commands include:
        install
        remove
        start
        stop
        restart
        debug
    """
    # واگذاری دستورات استاندارد مدیریت سرویس به pywin32
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required for Windows Service commands"
        )

    win32serviceutil.HandleCommandLine(
        MT5AgentService,
        argv=args,
    )
    # اجرای دستور خط فرمان مربوط به سرویس


def main() -> None:
    """
    Service-host entry point.

    With no arguments, this behaves like the normal pywin32 service
    command-line handler.
    """
    # نقطه ورود میزبان سرویس
    if win32serviceutil is None:
        raise ServiceHostError(
            "Windows Service host requires pywin32"
        )

    run_service_command(sys.argv)
    # اجرای دستورات با آرگومان‌های خط فرمان


__all__ = [
    "MT5AgentService",
    "SERVICE_DESCRIPTION",
    "SERVICE_DISPLAY_NAME",
    "SERVICE_NAME",
    "SERVICE_STOP_TIMEOUT_SEC",
    "ServiceHostError",
    "install_service",
    "remove_service",
    "start_service",
    "stop_service",
    "run_service_command",
    "main",
]
# لیست نمادهایی که با import * در دسترس قرار می‌گیرند


if __name__ == "__main__":
    main()
    # اگر فایل مستقیماً اجرا شود، تابع main صدا زده می‌شود