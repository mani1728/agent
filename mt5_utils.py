# -*- coding: utf-8 -*-
import time, logging
from typing import Any, Dict, Optional
from config_manager import cfg

_LOG = logging.getLogger("MT5")

try:
    import MetaTrader5 as MT5
    _HAS_MT5 = True
except Exception:
    _HAS_MT5 = False
    MT5 = None

class MT5Session:
    def __init__(self):
        c = cfg()
        self.login = int(c.get("mt5.login", 0))
        self.password = str(c.get("mt5.password", ""))
        self.server = str(c.get("mt5.server", ""))
        self.path = str(c.get("mt5.path", ""))
        self.timeout_sec = int(c.get("mt5.timeout_sec", 10))

        self.connected = False

    def connect(self) -> bool:
        if not _HAS_MT5:
            _LOG.warning("MetaTrader5 package not installed; running in mock mode.")
            self.connected = True
            return True

        kw = {}
        if self.path:
            kw["path"] = self.path
        MT5.initialize(**kw)
        ok = MT5.login(self.login, password=self.password, server=self.server)
        self.connected = bool(ok)
        if not ok:
            _LOG.error("MT5 login failed (login=%s server=%s)", self.login, self.server)
        else:
            _LOG.info("MT5 connected (login=%s server=%s)", self.login, self.server)
        return self.connected

    def shutdown(self):
        if _HAS_MT5:
            MT5.shutdown()
        self.connected = False

    def symbol_info(self, symbol: str) -> Dict[str, Any]:
        if not self.connected:
            raise RuntimeError("MT5 not connected")
        if not _HAS_MT5:
            return {"symbol": symbol, "bid": 1.2345, "ask": 1.2350}
        info = MT5.symbol_info_tick(symbol)
        if info is None:
            raise ValueError(f"Symbol not found: {symbol}")
        return {"symbol": symbol, "bid": info.bid, "ask": info.ask}
