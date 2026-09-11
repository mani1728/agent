# Path: Version 1_0_0/agent/service_host.py

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Optional

try:
    import win32event
    import win32service
    import win32serviceutil
except ImportError:  # pragma: no cover - non-Windows environments
    win32event = None
    win32service = None
    win32serviceutil = None

from .main import _load_legacy_main


logger = logging.getLogger(__name__)


SERVICE_NAME = "MT5Agent"
SERVICE_DISPLAY_NAME = "MT5 Agent"
SERVICE_DESCRIPTION = (
    "MetaTrader 5 Agent service."
)

SERVICE_STOP_TIMEOUT_SEC = 30.0


class ServiceHostError(RuntimeError):
    """Base error for Windows service host failures."""


if win32serviceutil is not None:

    class MT5AgentService(win32serviceutil.ServiceFramework):
        """
        Windows Service wrapper around the existing agent entry point.

        The service host owns only the Windows Service lifecycle. Agent
        business logic remains in the existing main/worker layers.
        """

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(
            self,
            args: list[str],
        ) -> None:
            super().__init__(args)

            self._stop_event = threading.Event()
            self._main_thread: Optional[threading.Thread] = None

            self._legacy_main_module = None

            self._service_stop_handle = win32event.CreateEvent(
                None,
                True,
                False,
                None,
            )

        # --------------------------------------------------------------
        # Service lifecycle
        # --------------------------------------------------------------

        def SvcStop(self) -> None:
            logger.info("Windows service stop requested")

            self.ReportServiceStatus(
                win32service.SERVICE_STOP_PENDING
            )

            self._stop_event.set()

            try:
                win32event.SetEvent(
                    self._service_stop_handle
                )
            except Exception:
                logger.debug(
                    "Unable to signal service stop event",
                    exc_info=True,
                )

            self._request_agent_shutdown()

        def SvcDoRun(self) -> None:
            logger.info(
                "Starting Windows service: %s",
                SERVICE_NAME,
            )

            self.ReportServiceStatus(
                win32service.SERVICE_START_PENDING
            )

            self._main_thread = threading.Thread(
                target=self._run_agent,
                name="mt5-agent-main",
                daemon=False,
            )

            self._main_thread.start()

            self.ReportServiceStatus(
                win32service.SERVICE_RUNNING
            )

            self._wait_for_agent()

            self.ReportServiceStatus(
                win32service.SERVICE_STOP_PENDING
            )

            self._wait_for_main_thread()

            logger.info(
                "Windows service stopped: %s",
                SERVICE_NAME,
            )

        # --------------------------------------------------------------
        # Agent execution
        # --------------------------------------------------------------

        def _run_agent(self) -> None:
            try:
                self._legacy_main_module = (
                    _load_legacy_main()
                )

                main_func = getattr(
                    self._legacy_main_module,
                    "main",
                    None,
                )

                if not callable(main_func):
                    raise ServiceHostError(
                        "Legacy main module does not expose main()"
                    )

                main_func()

            except Exception:
                logger.exception(
                    "Agent main loop terminated with an exception"
                )

            finally:
                self._stop_event.set()

        def _request_agent_shutdown(self) -> None:
            """
            Request graceful shutdown from the existing legacy main.

            The legacy main owns the actual shutdown event. Reusing it avoids
            introducing a second lifecycle mechanism during migration.
            """
            module = self._legacy_main_module

            if module is None:
                return

            shutdown_event = getattr(
                module,
                "_shutdown_event",
                None,
            )

            if shutdown_event is None:
                logger.warning(
                    "Legacy main shutdown event is unavailable"
                )
                return

            try:
                shutdown_event.set()
            except Exception:
                logger.exception(
                    "Unable to request legacy agent shutdown"
                )

        # --------------------------------------------------------------
        # Waiting / bounded shutdown
        # --------------------------------------------------------------

        def _wait_for_agent(self) -> None:
            """
            Wait until either the service is stopped or the agent exits.
            """
            while not self._stop_event.is_set():
                if (
                    self._main_thread is not None
                    and not self._main_thread.is_alive()
                ):
                    return

                try:
                    result = win32event.WaitForSingleObject(
                        self._service_stop_handle,
                        1000,
                    )

                    if result == win32event.WAIT_OBJECT_0:
                        return

                except Exception:
                    logger.debug(
                        "Service wait failed; "
                        "falling back to event wait",
                        exc_info=True,
                    )

                    self._stop_event.wait(1.0)

        def _wait_for_main_thread(self) -> None:
            thread = self._main_thread

            if thread is None:
                return

            deadline = (
                time.monotonic()
                + SERVICE_STOP_TIMEOUT_SEC
            )

            while thread.is_alive():
                remaining = (
                    deadline - time.monotonic()
                )

                if remaining <= 0:
                    logger.error(
                        "Agent did not stop within "
                        "%s seconds",
                        SERVICE_STOP_TIMEOUT_SEC,
                    )
                    return

                thread.join(
                    timeout=min(0.5, remaining)
                )


else:

    class MT5AgentService:
        """
        Placeholder used when pywin32 is unavailable.

        This keeps importing the package possible on non-Windows systems
        while making actual Windows Service execution fail explicitly.
        """

        def __init__(
            self,
            *args: object,
            **kwargs: object,
        ) -> None:
            raise ServiceHostError(
                "pywin32 is required to run MT5Agent as a Windows service"
            )


# ----------------------------------------------------------------------
# Service management
# ----------------------------------------------------------------------


def install_service() -> None:
    """
    Install the Windows service.
    """
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to install the Windows service"
        )

    win32serviceutil.InstallService(
        MT5AgentService,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        startType=win32service.SERVICE_AUTO_START,
        description=SERVICE_DESCRIPTION,
    )


def remove_service() -> None:
    """
    Remove the Windows service.
    """
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required to remove the Windows service"
        )

    win32serviceutil.RemoveService(
        SERVICE_NAME
    )


def start_service() -> None:
    """
    Start the installed Windows service.
    """
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
    if win32serviceutil is None:
        raise ServiceHostError(
            "pywin32 is required for Windows Service commands"
        )

    win32serviceutil.HandleCommandLine(
        MT5AgentService,
        argv=args,
    )


def main() -> None:
    """
    Service-host entry point.

    With no arguments, this behaves like the normal pywin32 service
    command-line handler.
    """
    if win32serviceutil is None:
        raise ServiceHostError(
            "Windows Service host requires pywin32"
        )

    run_service_command(sys.argv)


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


if __name__ == "__main__":
    main()