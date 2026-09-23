"""Best-effort standard logging at the infrastructure boundary.

Only fixed lifecycle messages are emitted. Arbitrary event metadata, request
payloads, account objects and exception text never enter this adapter.
"""
import logging
import sys

from agent.contracts.configuration import LoggingConfig
from agent.contracts.operational_observability import OperationalEvent, OperationalEventType


def safe_log(logger, level, message, *args):
    try:
        logger.log(level, message, *args)
    except Exception:
        pass  # Telemetry must not change lifecycle outcomes.


class SafeStreamHandler(logging.StreamHandler):
    def handleError(self, record):
        pass  # Do not print exception/record contents on a broken log sink.


class SafeFileHandler(logging.FileHandler):
    def handleError(self, record):
        pass


def configure_logging(config: LoggingConfig, stream=None):
    logger = logging.getLogger("agent")
    for handler in list(logger.handlers):
        if getattr(handler, "_agent_owned", False):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    logger.setLevel(config.level)
    logger.propagate = False
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handlers = [SafeStreamHandler(stream if stream is not None else sys.stderr)]
    file_failed = False
    if config.file:
        try:
            handlers.append(SafeFileHandler(config.file, encoding="utf-8"))
        except (OSError, ValueError):
            file_failed = True
    for handler in handlers:
        handler._agent_owned = True
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if file_failed:
        safe_log(logger, logging.ERROR, "Optional log file unavailable; continuing with console logging")
    safe_log(logger, logging.DEBUG, "Diagnostic logging enabled; sensitive runtime data is omitted")
    return logger


class LoggingOperationalObservability:
    _MESSAGES = {
        OperationalEventType.APPLICATION_STARTING: "Application startup requested",
        OperationalEventType.APPLICATION_STARTED: "Agent started; MT5 connection established",
        OperationalEventType.HOSTING_STARTED: "Application host starting",
        OperationalEventType.APPLICATION_STOPPING: "Application shutdown in progress",
        OperationalEventType.APPLICATION_STOPPED: "Application host stopped",
        OperationalEventType.APPLICATION_START_FAILED: "Application startup failed",
        OperationalEventType.HOSTING_FAILED: "Application hosting failed",
        OperationalEventType.APPLICATION_STOP_FAILED: "Application shutdown failed",
    }

    def __init__(self, logger=None):
        self._logger = logger or logging.getLogger(__name__)

    def record(self, event: OperationalEvent) -> None:
        message = self._MESSAGES.get(event.event_type)
        if message:
            level = logging.ERROR if event.event_type.value.endswith("failed") else logging.INFO
            safe_log(self._logger, level, message)
