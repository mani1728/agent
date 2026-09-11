# Path: Version 1_0_0/main.py

# -*- coding: utf-8 -*-
"""
main.py
-------
Legacy-compatible application entry point.

Migration status:
- Legacy Kafka startup is intentionally preserved.
- Legacy ClientAuth registration/heartbeat is intentionally preserved.
- Legacy hot-reload configuration is intentionally preserved.
- Legacy signal/shutdown behavior is intentionally preserved.
- AgentWorker is NOT wired here yet.
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

from __future__ import annotations

# ======================================================================
# Standard library
# ======================================================================

import getpass
import logging
import platform
import signal
import sys
import threading
import time


# ======================================================================
# Legacy application dependencies
# ======================================================================

from config_manager import cfg
from config_logging import setup_logging
from client_auth import ClientAuth
from kafka_listener import KafkaListener


# ======================================================================
# Global shutdown event
# ======================================================================

_shutdown_event = threading.Event()


# ======================================================================
# ClientAuth logging bridge
# ======================================================================

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

    lvl = getattr(
        logging,
        str(level).upper(),
        logging.INFO,
    )

    message = f"{msg} | {kw}" if kw else msg

    logging.getLogger("ClientAuth").log(
        lvl,
        message,
    )


# ======================================================================
# Signal handling
# ======================================================================

def _handle_signal(
    signum,
    frame,
) -> None:
    """
    Request application shutdown.

    Actual cleanup remains inside main() so that all resources are
    released from one controlled shutdown path.
    """

    logging.getLogger("App").info(
        "Shutdown signal received",
        extra={"signum": signum},
    )

    _shutdown_event.set()


# ======================================================================
# Main application entry point
# ======================================================================

def main() -> None:
    """
    Legacy application startup/shutdown sequence.

    IMPORTANT:
    This function intentionally remains compatible with the existing
    Kafka-based runtime during the migration.

    The new AgentWorker is not connected here yet.
    """

    # ------------------------------------------------------------------
    # Reset shutdown state
    # ------------------------------------------------------------------

    _shutdown_event.clear()

    # ------------------------------------------------------------------
    # 1) Load hot-reload configuration
    # ------------------------------------------------------------------

    config = cfg()

    # ------------------------------------------------------------------
    # 2) Configure logging
    # ------------------------------------------------------------------

    setup_logging(config)

    app_logger = logging.getLogger("App")

    app_logger.info(
        "Application bootstrap started "
        "(hot-reload config enabled)."
    )

    # ------------------------------------------------------------------
    # 3) Client registration / heartbeat
    # ------------------------------------------------------------------

    ca = None

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

        ca = ClientAuth(
            client_meta=meta,
            logger=_clientauth_logger,
        )

        # Register client and start heartbeat according to legacy
        # ClientAuth behavior.
        ca.register()

        # --------------------------------------------------------------
        # Update runtime Kafka configuration after registration.
        # --------------------------------------------------------------

        try:
            config._data.setdefault(
                "kafka",
                {},
            )["client_id"] = ca.client_id

            final_cmd_topics = [
                f"cmd.{ca.client_id}.p0",
                f"cmd.{ca.client_id}.p1",
                f"cmd.{ca.client_id}.p2",
            ]

            config._data["kafka"].setdefault(
                "topics",
                {},
            )

            config._data["kafka"]["topics"][
                "commands"
            ] = final_cmd_topics

            config._data["kafka"][
                "group_id"
            ] = f"mt5-service.{ca.client_id}"

            app_logger.info(
                "Client topics updated after registration",
                extra={
                    "client_id": ca.client_id,
                    "topics": final_cmd_topics,
                },
            )

        except Exception:
            app_logger.exception(
                "Failed to update topics after registration"
            )

    except Exception:
        # Preserve legacy behavior:
        # registration failure is logged but does not immediately
        # terminate the application.
        app_logger.exception(
            "Client registration failed"
        )

    # ------------------------------------------------------------------
    # 4) Kafka enabled check
    # ------------------------------------------------------------------

    if not bool(
        config.get(
            "kafka.enabled",
            True,
        )
    ):
        app_logger.warning(
            "Kafka is disabled by config "
            "(kafka.enabled=false). Exiting main."
        )

        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception(
                "Failed to stop ClientAuth"
            )

        return

    # ------------------------------------------------------------------
    # 5) Create KafkaListener
    # ------------------------------------------------------------------

    try:
        listener = KafkaListener(config)

    except TypeError:
        app_logger.error(
            "KafkaListener constructor signature mismatch. "
            "Expected KafkaListener(cfg: HotReloadConfig). "
            "Please use the rewritten kafka_listener.py."
        )

        try:
            if ca:
                ca.stop()
        except Exception:
            app_logger.exception(
                "Failed to stop ClientAuth"
            )

        sys.exit(1)

    # ------------------------------------------------------------------
    # 6) Register OS signal handlers
    # ------------------------------------------------------------------

    signal.signal(
        signal.SIGINT,
        _handle_signal,
    )

    try:
        signal.signal(
            signal.SIGTERM,
            _handle_signal,
        )
    except Exception:
        # SIGTERM may not be available/usable on every Windows runtime.
        pass

    # ------------------------------------------------------------------
    # 7) Start KafkaListener
    # ------------------------------------------------------------------

    app_logger.info(
        "KafkaListener starting..."
    )

    listener_thread = threading.Thread(
        target=listener.listen,
        name="KafkaListener",
        daemon=True,
    )

    listener_thread.start()

    app_logger.info(
        "KafkaListener started."
    )

    # ------------------------------------------------------------------
    # 8) Main wait loop
    # ------------------------------------------------------------------

    try:
        while not _shutdown_event.is_set():
            time.sleep(0.5)

    except Exception:
        app_logger.exception(
            "Fatal error in main loop"
        )

    finally:
        # --------------------------------------------------------------
        # 9) Controlled legacy shutdown
        # --------------------------------------------------------------

        app_logger.info(
            "Shutting down..."
        )

        # Stop KafkaListener first.
        try:
            stop_listener = getattr(
                listener,
                "stop",
                None,
            )

            if callable(stop_listener):
                stop_listener()

        except Exception:
            app_logger.exception(
                "Failed to stop KafkaListener"
            )

        # Stop ClientAuth / heartbeat.
        try:
            if ca:
                ca.stop()

        except Exception:
            app_logger.exception(
                "Failed to stop ClientAuth"
            )

        app_logger.info(
            "Bye."
        )


# ======================================================================
# Direct execution compatibility
# ======================================================================

if __name__ == "__main__":
    main()