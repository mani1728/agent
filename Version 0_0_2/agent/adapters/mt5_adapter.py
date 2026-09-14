import logging

import MetaTrader5 as mt5


class MT5Adapter:
    """Concrete adapter implementing the MT5Port contract."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def connect(self) -> bool:
        try:
            connected = bool(mt5.initialize())
        except Exception:
            self._logger.exception("MT5 initialization failed")
            return False
        if not connected:
            self._logger.error("MT5 initialization returned false")
        return connected

    def disconnect(self) -> None:
        try:
            mt5.shutdown()
        except Exception:
            self._logger.exception("MT5 shutdown failed")

    def is_connected(self) -> bool:
        try:
            return mt5.terminal_info() is not None
        except Exception:
            self._logger.exception("MT5 health probe failed")
            return False
