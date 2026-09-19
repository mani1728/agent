import importlib
import logging

from agent.infrastructure.logging_observability import safe_log
from agent.infrastructure.terminal_inspection import inspect_terminal


class MT5Adapter:
    def __init__(self, logger: logging.Logger | None = None, *, module=None, inspector=inspect_terminal) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._module = module
        self._inspector = inspector

    def connect(self) -> bool:
        try:
            inspection = self._inspector()
            safe_log(self._logger, logging.INFO,
                     "MT5 discovery: %d terminal candidate(s); process running=%s",
                     len(inspection.paths), inspection.process_running)
            if inspection.errors:
                safe_log(self._logger, logging.WARNING,
                         "MT5 inspection incomplete; retaining vendor automatic discovery")
        except Exception:
            safe_log(self._logger, logging.WARNING,
                     "MT5 inspection unavailable; retaining vendor automatic discovery")
        safe_log(self._logger, logging.INFO,
                 "Initializing MT5 connection; vendor integration may launch the terminal")
        try:
            if self._module is None:
                self._module = importlib.import_module("MetaTrader5")
            connected = bool(self._module.initialize())
        except Exception:
            safe_log(self._logger, logging.ERROR, "MT5 initialization failed; check dependency and terminal installation")
            return False
        if connected:
            safe_log(self._logger, logging.INFO, "MT5 initialized and connected successfully")
        else:
            safe_log(self._logger, logging.ERROR, "MT5 initialization returned false")
        return connected

    def disconnect(self) -> bool:
        try:
            if self._module is not None:
                self._module.shutdown()
            return True
        except Exception:
            safe_log(self._logger, logging.ERROR, "MT5 shutdown failed")
            return False

    def is_connected(self) -> bool:
        try:
            return self._module is not None and self._module.terminal_info() is not None
        except Exception:
            safe_log(self._logger, logging.ERROR, "MT5 health probe failed")
            return False
