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

    @staticmethod
    def _normalise(value):
        """Stable, owned wire representation; no arbitrary object stringification."""
        if value is None or isinstance(value, (str, int, float, bool)): return value
        if hasattr(value, "_asdict"): return {str(k): MT5Adapter._normalise(v) for k, v in value._asdict().items()}
        if isinstance(value, (tuple, list)): return [MT5Adapter._normalise(v) for v in value]
        if isinstance(value, dict): return {str(k): MT5Adapter._normalise(v) for k, v in value.items()}
        raise TypeError("unsupported MT5 response type")
    def _read(self, name, *args):
        if self._module is None: self._module = importlib.import_module("MetaTrader5")
        try:
            value=getattr(self._module, name)(*args)  # name is private allowlisted by methods below
        except Exception as exc: raise MT5ReadError("MT5_CALL_FAILED", {"operation":name}) from exc
        if value is None: raise MT5ReadError("MT5_READ_FAILED", {"operation":name,"last_error":self._normalise(self._module.last_error())})
        return self._normalise(value)
    def terminal_information(self): return self._read("terminal_info")
    def terminal_version(self): return self._read("version")
    def account_information(self): return self._read("account_info")

class MT5ReadError(RuntimeError):
    def __init__(self, code, details): super().__init__(code); self.code=code; self.details=details
