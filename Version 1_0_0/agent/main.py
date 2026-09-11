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
- AgentWorker is opt-in through app.use_agent_worker.
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
# Application dependencies
# ======================================================================

try:  # Package-safe execution: python -m agent
    from .core.command_executor import CommandExecutor
    from .core.worker import AgentWorker
    from .infrastructure.config_logging import setup_logging
    from .infrastructure.config_manager import cfg
    from .security.client_auth import ClientAuth
    from .transport.factory import TransportFactory
except ImportError:  # Direct execution compatibility: python agent/main.py
    from agent.core.command_executor import CommandExecutor
    from agent.core.worker import AgentWorker
    from agent.infrastructure.config_logging import setup_logging
    from agent.infrastructure.config_manager import cfg
    from agent.security.client_auth import ClientAuth
    from agent.transport.factory import TransportFactory

try:
    from .transport.kafka.listener import KafkaListener as _KafkaListener
except Exception:  # pragma: no cover - optional dependency
    _KafkaListener = None


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


def _config_bool(config, path: str, default: bool = False) -> bool:
    """Read a JSON-compatible boolean without treating ``\"false\"`` as true."""
    value = config.get(path, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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
    # 5) Select the opt-in worker path or preserve the legacy listener.
    # ------------------------------------------------------------------

    use_agent_worker = _config_bool(
        config,
        "app.use_agent_worker",
        False,
    )
    listener = None
    worker = None
    runtime_thread = None

    try:
        if use_agent_worker:
            transport = TransportFactory.create(config)
            worker = AgentWorker(
                CommandExecutor(),
                transport,
                poll_timeout_sec=float(
                    config.get("app.worker_poll_timeout_sec", 1.0)
                ),
            )
            runtime_thread = threading.Thread(
                target=worker.run,
                name="AgentWorker",
                daemon=True,
            )
            app_logger.info("AgentWorker path selected by feature flag")
        else:
            if _KafkaListener is None:
                raise RuntimeError(
                    "Kafka listener dependency is unavailable "
                    "(missing runtime dependency)"
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
    # 7) Start selected runtime path
    # ------------------------------------------------------------------

    runtime_thread.start()
    app_logger.info("Runtime path started: worker_enabled=%s", use_agent_worker)

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

        # Stop the selected command runtime before ClientAuth.
        try:
            if worker is not None:
                worker.stop()
            elif listener is not None:
                listener.stop()

            if runtime_thread is not None:
                runtime_thread.join(
                    timeout=float(
                        config.get("app.shutdown_join_timeout_sec", 10.0)
                    )
                )
        except Exception:
            app_logger.exception("Failed to stop command runtime")

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
