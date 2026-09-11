# Path: Version 1_0_0/agent/core/meta_trader_manager.py

# -*- coding: utf-8 -*-

"""
MetaTrader 5 Manager
---------------------

مدیریت تعامل Agent با MetaTrader 5.

اصول این نسخه:
- حفظ API و رفتار Legacy تا حد ممکن
- خواندن تنظیمات MT5 از config.json از طریق cfg()
- پشتیبانی از hot-reload
- بدون وابستگی به Kafka / HTTP / Transport
- آماده برای استفاده توسط CommandDispatcher
- عدم تغییر عمدی در قرارداد متدهای MT5

مسئولیت این فایل:
    CommandExecutor / Dispatcher
            |
            v
       Mt5_Manager
            |
            v
       MetaTrader5

این فایل نباید مسئول:
- Kafka
- HTTP
- Retry شبکه
- Persistence
- Transport acknowledgement
- Worker lifecycle
باشد.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

import MetaTrader5 as mt5
import pandas as pd
import pytz


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

try:
    # Target architecture
    from agent.infrastructure.config_manager import cfg
except ImportError:
    # Temporary compatibility with the existing Legacy layout.
    #
    # This fallback can be removed once infrastructure/config_manager.py
    # is migrated and verified.
    from config_manager import cfg


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def _parse_iso_dt(
    value: Union[str, dt.datetime, None],
    timezone: pytz.BaseTzInfo,
) -> Optional[dt.datetime]:
    """
    Parse an ISO datetime and return a timezone-aware datetime.

    Behavior preserved from Legacy implementation:

    - None -> None
    - aware datetime -> converted to requested timezone
    - naive datetime -> localized using requested timezone
    - ISO string with Z -> supported
    - ISO string without timezone -> localized
    """

    if value is None:
        return None

    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return timezone.localize(value)

        return value.astimezone(timezone)

    if not isinstance(value, str):
        raise ValueError(
            "datetime must be ISO string or datetime"
        )

    text = value.strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        parsed = dt.datetime.fromisoformat(
            text.replace(" ", "T")
        )

    if parsed.tzinfo is None:
        return timezone.localize(parsed)

    return parsed.astimezone(timezone)


def _safe_asdict(obj: Any) -> Any:
    """
    Convert common MT5/pandas objects into serializable structures.

    Supported:
    - namedtuple / MT5 structures
    - lists
    - pandas.DataFrame
    - pandas.Series
    """

    if obj is None:
        return None

    if hasattr(obj, "_asdict"):
        try:
            return obj._asdict()
        except Exception:
            return str(obj)

    if isinstance(obj, list):
        return [
            _safe_asdict(item)
            for item in obj
        ]

    try:
        if isinstance(obj, pd.DataFrame):
            return {
                "preview": obj.head(20).to_dict(
                    orient="records"
                ),
                "columns": list(obj.columns),
                "rows": int(obj.shape[0]),
            }

        if isinstance(obj, pd.Series):
            return obj.to_dict()

    except Exception:
        pass

    return obj


def _comma_join(
    servers: Union[List[str], str],
) -> str:
    """
    Convert a list of server strings to comma-separated text.

    Kept for Legacy compatibility.
    """

    if isinstance(servers, list):
        return ",".join(servers)

    return str(servers)


# ---------------------------------------------------------------------
# Main Manager
# ---------------------------------------------------------------------

class Mt5_Manager:
    """
    Main MetaTrader 5 manager.

    Configuration is read from cfg() on every operation so that
    changes to mt5.* can be picked up without restarting the Agent.
    """

    def __init__(self) -> None:
        self.log = logging.getLogger("Mt5_Manager")

    # -----------------------------------------------------------------
    # Configuration helpers
    # -----------------------------------------------------------------

    def _mt5_cfg(self) -> Dict[str, Any]:
        """
        Return the latest MT5 configuration.

        Expected configuration:

        {
            "mt5": {
                "login": 0,
                "password": "",
                "server": "",
                "path": "",
                "timeout_sec": 10,
                "symbols": [],
                "timezone": "UTC"
            }
        }
        """

        try:
            config = cfg().get("mt5", {})
        except Exception:
            self.log.exception(
                "Failed to read MT5 configuration."
            )
            return {}

        return config or {}

    def _tz(self) -> pytz.BaseTzInfo:
        """
        Resolve configured MT5 timezone.

        Invalid timezone falls back to UTC.
        """

        timezone_name = (
            self._mt5_cfg().get("timezone")
            or "UTC"
        )

        timezone_name = str(timezone_name).strip()

        if not timezone_name:
            timezone_name = "UTC"

        try:
            return pytz.timezone(timezone_name)
        except Exception:
            self.log.warning(
                "Invalid MT5 timezone; falling back to UTC."
            )

            return pytz.timezone("UTC")

    def _default_symbol(self) -> Optional[str]:
        """
        Return first configured symbol.
        """

        symbols = (
            self._mt5_cfg().get("symbols")
            or []
        )

        if isinstance(symbols, list) and symbols:
            return str(symbols[0])

        return None

    # -----------------------------------------------------------------
    # Connection helpers
    # -----------------------------------------------------------------

    def _ensure_initialized(self) -> bool:
        """
        Check whether MT5 terminal is currently connected.
        """

        try:
            info = mt5.terminal_info()
        except Exception:
            self.log.exception(
                "Failed to query MT5 terminal_info."
            )
            return False

        if info and getattr(
            info,
            "connected",
            False,
        ):
            return True

        self.log.debug(
            "MT5 not initialized/connected."
        )

        return False

    # -----------------------------------------------------------------
    # Symbol helpers
    # -----------------------------------------------------------------

    def _symbol_sanity(
        self,
        symbol: Optional[str],
    ) -> bool:
        """
        Validate symbol and make it visible if required.
        """

        target = (
            symbol
            or self._default_symbol()
        )

        if not target:
            self.log.error(
                "Symbol is empty and no default symbol exists."
            )
            return False

        try:
            info = mt5.symbol_info(target)
        except Exception:
            self.log.exception(
                "Failed to get symbol information."
            )
            return False

        if info is None:
            self.log.error(
                "Symbol '%s' not found.",
                target,
            )
            return False

        if not getattr(info, "visible", False):
            try:
                selected = mt5.symbol_select(
                    target,
                    True,
                )
            except Exception:
                self.log.exception(
                    "Failed to select symbol."
                )
                return False

            if not selected:
                self.log.error(
                    "Failed to select symbol '%s'.",
                    target,
                )
                return False

        return True

    def _df_preview(
        self,
        dataframe: Optional[pd.DataFrame],
        name: str = "",
    ) -> None:
        """
        Debug-only DataFrame preview.

        No sensitive payload should be passed here.
        """

        if dataframe is None:
            return

        try:
            rows = int(
                dataframe.shape[0]
            )

            self.log.debug(
                "DF preview (%s) rows=%d\n%s",
                name,
                rows,
                dataframe.head(10),
            )

        except Exception:
            pass

    # =================================================================
    # 1. Connection management
    # =================================================================

    def manage_connection(
        self,
        action: str,
        path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: Optional[int] = None,
        portable: bool = False,
    ) -> Optional[
        Union[
            bool,
            Dict[str, Any],
            List[Any],
            str,
        ]
    ]:
        """
        Connection operations:

        initialize
        login
        terminal_info
        version
        account_info
        shutdown
        """

        action = (
            action or ""
        ).lower().strip()

        allowed_actions = {
            "initialize",
            "login",
            "terminal_info",
            "version",
            "account_info",
            "shutdown",
        }

        if action not in allowed_actions:
            self.log.error(
                "Invalid connection action: %s",
                action,
            )
            return None

        config = self._mt5_cfg()

        path = (
            path
            if path is not None
            else config.get("path") or None
        )

        login = (
            login
            if login is not None
            else config.get("login") or None
        )

        password = (
            password
            if password is not None
            else config.get("password") or None
        )

        server = (
            server
            if server is not None
            else config.get("server") or None
        )

        timeout_seconds = (
            timeout
            if timeout is not None
            else int(
                config.get(
                    "timeout_sec",
                    10,
                )
                or 10
            )
        )

        timeout_ms = int(
            timeout_seconds * 1000
        )

        # -------------------------------------------------------------
        # initialize
        # -------------------------------------------------------------

        if action == "initialize":

            try:
                info = mt5.terminal_info()

                if info and getattr(
                    info,
                    "connected",
                    False,
                ):
                    self.log.info(
                        "MT5 already connected; "
                        "skipping initialize."
                    )
                    return True

                self.log.info(
                    "Initializing MT5 terminal "
                    "(path=%s, timeout_ms=%s, portable=%s).",
                    path,
                    timeout_ms,
                    portable,
                )

                initialized = mt5.initialize(
                    path=path,
                    login=login,
                    password=password,
                    server=server,
                    timeout=timeout_ms,
                    portable=portable,
                )

                if not initialized:
                    self.log.error(
                        "Failed to initialize MT5. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return True

            except Exception:
                self.log.exception(
                    "Exception during MT5 initialization."
                )
                return None

        # -------------------------------------------------------------
        # login
        # -------------------------------------------------------------

        if action == "login":

            if not self._ensure_initialized():
                self.log.error(
                    "MT5 not initialized. "
                    "Call initialize first."
                )
                return None

            try:
                success = mt5.login(
                    login=login,
                    password=password,
                    server=server,
                )

                if not success:
                    self.log.error(
                        "Failed to login to configured MT5 account. "
                        "err=%s",
                        mt5.last_error(),
                    )
                    return None

                account = mt5.account_info()

                return (
                    _safe_asdict(account)
                    if account
                    else None
                )

            except Exception:
                self.log.exception(
                    "Exception during MT5 login."
                )
                return None

        # -------------------------------------------------------------
        # terminal_info
        # -------------------------------------------------------------

        if action == "terminal_info":

            try:
                info = mt5.terminal_info()

                if info is None:
                    self.log.error(
                        "Failed to get terminal_info. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return _safe_asdict(info)

            except Exception:
                self.log.exception(
                    "Exception while getting terminal_info."
                )
                return None

        # -------------------------------------------------------------
        # version
        # -------------------------------------------------------------

        if action == "version":

            try:
                return {
                    "version": mt5.version()
                }

            except Exception:
                self.log.exception(
                    "Exception while getting MT5 version."
                )
                return None

        # -------------------------------------------------------------
        # account_info
        # -------------------------------------------------------------

        if action == "account_info":

            try:
                account = mt5.account_info()

                if account is None:
                    self.log.error(
                        "Failed to get account_info. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return _safe_asdict(account)

            except Exception:
                self.log.exception(
                    "Exception while getting account_info."
                )
                return None

        # -------------------------------------------------------------
        # shutdown
        # -------------------------------------------------------------

        if action == "shutdown":

            try:
                mt5.shutdown()

                self.log.info(
                    "MT5 shutdown called."
                )

                return True

            except Exception:
                self.log.exception(
                    "Exception during MT5 shutdown."
                )
                return None

        return None

    # =================================================================
    # 2. Symbol management
    # =================================================================

    def manage_symbols(
        self,
        action: str,
        symbol: Optional[str] = None,
        group: Optional[str] = None,
        enable: bool = True,
    ) -> Optional[
        Union[
            int,
            Dict[str, Any],
            List[Any],
            bool,
        ]
    ]:

        action = (
            action or ""
        ).lower().strip()

        allowed_actions = {
            "total",
            "get",
            "info",
            "tick",
            "select",
        }

        if action not in allowed_actions:
            self.log.error(
                "Invalid action for manage_symbols: %s",
                action,
            )
            return None

        # -------------------------------------------------------------
        # total
        # -------------------------------------------------------------

        if action == "total":

            try:
                total = mt5.symbols_total()

                self.log.debug(
                    "symbols_total=%s",
                    total,
                )

                return total

            except Exception:
                self.log.exception(
                    "Exception in symbols_total."
                )
                return None

        # -------------------------------------------------------------
        # get
        # -------------------------------------------------------------

        if action == "get":

            try:
                symbols = mt5.symbols_get(
                    group or "*"
                )

                if symbols is None:
                    self.log.error(
                        "symbols_get failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return [
                    _safe_asdict(symbol_info)
                    for symbol_info in symbols
                ]

            except Exception:
                self.log.exception(
                    "Exception in symbols_get."
                )
                return None

        # -------------------------------------------------------------
        # info
        # -------------------------------------------------------------

        if action == "info":

            if not self._symbol_sanity(symbol):
                return None

            target = (
                symbol
                or self._default_symbol()
            )

            try:
                info = mt5.symbol_info(target)

                return (
                    _safe_asdict(info)
                    if info
                    else None
                )

            except Exception:
                self.log.exception(
                    "Exception in symbol_info."
                )
                return None

        # -------------------------------------------------------------
        # tick
        # -------------------------------------------------------------

        if action == "tick":

            if not self._symbol_sanity(symbol):
                return None

            target = (
                symbol
                or self._default_symbol()
            )

            try:
                tick = mt5.symbol_info_tick(
                    target
                )

                return (
                    _safe_asdict(tick)
                    if tick
                    else None
                )

            except Exception:
                self.log.exception(
                    "Exception in symbol_info_tick."
                )
                return None

        # -------------------------------------------------------------
        # select
        # -------------------------------------------------------------

        if action == "select":

            target = (
                symbol
                or self._default_symbol()
            )

            if not target:
                self.log.error(
                    "select requires symbol "
                    "and no default exists."
                )
                return None

            try:
                result = mt5.symbol_select(
                    target,
                    enable,
                )

                if not result:
                    self.log.error(
                        "symbol_select failed. err=%s",
                        mt5.last_error(),
                    )

                return bool(result)

            except Exception:
                self.log.exception(
                    "Exception in symbol_select."
                )
                return None

        return None

    # =================================================================
    # 3. Market book
    # =================================================================

    def manage_market_book(
        self,
        action: str,
        symbol: Optional[str] = None,
    ) -> Optional[
        Union[
            List[Dict[str, Any]],
            bool,
        ]
    ]:

        action = (
            action or ""
        ).lower().strip()

        if action not in {
            "add",
            "get",
            "release",
        }:
            self.log.error(
                "Invalid action for market book: %s",
                action,
            )
            return None

        if not self._symbol_sanity(symbol):
            return None

        target = (
            symbol
            or self._default_symbol()
        )

        try:

            if action == "add":

                result = mt5.market_book_add(
                    target
                )

                if not result:
                    self.log.error(
                        "market_book_add failed. err=%s",
                        mt5.last_error(),
                    )

                return bool(result)

            if action == "get":

                book = mt5.market_book_get(
                    target
                )

                if book is None:
                    self.log.error(
                        "market_book_get failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return [
                    _safe_asdict(item)
                    for item in book
                ]

            if action == "release":

                result = mt5.market_book_release(
                    target
                )

                if not result:
                    self.log.error(
                        "market_book_release failed. err=%s",
                        mt5.last_error(),
                    )

                return bool(result)

        except Exception:
            self.log.exception(
                "Exception in market book operation."
            )
            return None

        return None

    # =================================================================
    # 4. Historical data
    # =================================================================

    def fetch_data(
        self,
        symbol: Optional[str] = None,
        data_type: str = "rates",
        method: str = "from",
        timeframe: Any = mt5.TIMEFRAME_M1,
        count: int = 100,
        date_from: Optional[
            Union[str, dt.datetime]
        ] = None,
        date_to: Optional[
            Union[str, dt.datetime]
        ] = None,
        flags: Any = mt5.COPY_TICKS_ALL,
    ) -> Optional[Dict[str, Any]]:

        if not self._ensure_initialized():
            return None

        if not self._symbol_sanity(symbol):
            return None

        target = (
            symbol
            or self._default_symbol()
        )

        data_type = (
            data_type or ""
        ).lower().strip()

        method = (
            method or ""
        ).lower().strip()

        if data_type not in {
            "rates",
            "ticks",
        }:
            self.log.error(
                "Invalid data_type: %s",
                data_type,
            )
            return None

        if method not in {
            "from",
            "from_pos",
            "range",
        }:
            self.log.error(
                "Invalid method: %s",
                method,
            )
            return None

        timezone = self._tz()

        try:
            date_from_parsed = (
                _parse_iso_dt(
                    date_from,
                    timezone,
                )
                if date_from is not None
                else None
            )

            date_to_parsed = (
                _parse_iso_dt(
                    date_to,
                    timezone,
                )
                if date_to is not None
                else None
            )

            dataframe: Optional[
                pd.DataFrame
            ] = None

            rows: List[Dict[str, Any]] = []

            # ---------------------------------------------------------
            # Rates
            # ---------------------------------------------------------

            if data_type == "rates":

                if method == "from":

                    if date_from_parsed is None:
                        self.log.error(
                            "rates/from requires date_from."
                        )
                        return None

                    raw = mt5.copy_rates_from(
                        target,
                        timeframe,
                        date_from_parsed,
                        count,
                    )

                elif method == "from_pos":

                    raw = mt5.copy_rates_from_pos(
                        target,
                        timeframe,
                        0,
                        count,
                    )

                else:

                    if not (
                        date_from_parsed
                        and date_to_parsed
                    ):
                        self.log.error(
                            "rates/range requires "
                            "date_from and date_to."
                        )
                        return None

                    raw = mt5.copy_rates_range(
                        target,
                        timeframe,
                        date_from_parsed,
                        date_to_parsed,
                    )

                if raw is None:
                    self.log.error(
                        "copy_rates_* failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                dataframe = pd.DataFrame(raw)

                if (
                    not dataframe.empty
                    and "time" in dataframe.columns
                ):
                    dataframe["time"] = (
                        pd.to_datetime(
                            dataframe["time"],
                            unit="s",
                        )
                    )

                rows = [
                    {
                        "time": row["time"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "tick_volume": row["tick_volume"],
                        "spread": row["spread"],
                        "real_volume": row["real_volume"],
                    }
                    for _, row
                    in dataframe.iterrows()
                ]

            # ---------------------------------------------------------
            # Ticks
            # ---------------------------------------------------------

            else:

                if method == "from":

                    if date_from_parsed is None:
                        self.log.error(
                            "ticks/from requires date_from."
                        )
                        return None

                    raw = mt5.copy_ticks_from(
                        target,
                        date_from_parsed,
                        count,
                        flags,
                    )

                elif method == "from_pos":

                    # MT5 does not expose copy_ticks_from_pos().
                    # Preserve existing Legacy fallback.
                    if date_from_parsed is None:
                        self.log.error(
                            "ticks/from_pos fallback "
                            "requires date_from."
                        )
                        return None

                    raw = mt5.copy_ticks_from(
                        target,
                        date_from_parsed,
                        count,
                        flags,
                    )

                else:

                    if not (
                        date_from_parsed
                        and date_to_parsed
                    ):
                        self.log.error(
                            "ticks/range requires "
                            "date_from and date_to."
                        )
                        return None

                    raw = mt5.copy_ticks_range(
                        target,
                        date_from_parsed,
                        date_to_parsed,
                        flags,
                    )

                if raw is None:
                    self.log.error(
                        "copy_ticks_* failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                dataframe = pd.DataFrame(raw)

                if (
                    not dataframe.empty
                    and "time" in dataframe.columns
                ):
                    dataframe["time"] = (
                        pd.to_datetime(
                            dataframe["time"],
                            unit="s",
                        )
                    )

                rows = [
                    {
                        "time": row.get("time"),
                        "bid": float(
                            row.get("bid", 0.0)
                        ),
                        "ask": float(
                            row.get("ask", 0.0)
                        ),
                        "last": float(
                            row.get("last", 0.0)
                        ),
                        "volume": float(
                            row.get("volume", 0.0)
                        ),
                        "time_msc": int(
                            row.get("time_msc", 0)
                        ),
                        "flags": int(
                            row.get("flags", 0)
                        ),
                    }
                    for _, row
                    in dataframe.iterrows()
                ]

            self._df_preview(
                dataframe,
                name=f"{data_type}/{method}",
            )

            return {
                "symbol": target,
                "type": data_type,
                "method": method,
                "rows": len(rows),
                "raw": rows,
                "frame": dataframe,
            }

        except Exception:
            self.log.exception(
                "Exception in fetch_data."
            )
            return None

    # =================================================================
    # 5. Trade management
    # =================================================================

    def trade_manager(
        self,
        action: str,
        symbol: Optional[str] = None,
        order_type: Optional[int] = None,
        volume: Optional[float] = None,
        price: Optional[float] = None,
        price_close: Optional[float] = None,
        request: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Optional[Any]:

        action = (
            action or ""
        ).lower().strip()

        if not self._ensure_initialized():
            return None

        # -------------------------------------------------------------
        # orders_total
        # -------------------------------------------------------------

        if action == "total":

            try:
                return mt5.orders_total()

            except Exception:
                self.log.exception(
                    "Exception in orders_total."
                )
                return None

        # -------------------------------------------------------------
        # orders_get
        # -------------------------------------------------------------

        if action == "get":

            try:

                if symbol:
                    orders = mt5.orders_get(
                        symbol=symbol
                    )
                else:
                    orders = mt5.orders_get()

                if orders is None:
                    self.log.error(
                        "orders_get failed. err=%s",
                        mt5.last_error(),
                    )

                    return {
                        "raw_orders": None,
                        "orders_frame": pd.DataFrame(),
                    }

                raw_orders = [
                    order._asdict()
                    for order in orders
                ]

                frame = pd.DataFrame(
                    raw_orders
                )

                return {
                    "raw_orders": raw_orders,
                    "orders_frame": frame,
                }

            except Exception:
                self.log.exception(
                    "Exception in orders_get."
                )
                return None

        # -------------------------------------------------------------
        # order_calc_margin
        # -------------------------------------------------------------

        if action == "calc_margin":

            if not (
                order_type is not None
                and symbol
                and volume is not None
                and price is not None
            ):
                self.log.error(
                    "calc_margin requires "
                    "order_type, symbol, volume and price."
                )
                return None

            try:
                return mt5.order_calc_margin(
                    order_type,
                    symbol,
                    volume,
                    price,
                )

            except Exception:
                self.log.exception(
                    "Exception in order_calc_margin."
                )
                return None

        # -------------------------------------------------------------
        # order_calc_profit
        # -------------------------------------------------------------

        if action == "calc_profit":

            if not (
                order_type is not None
                and symbol
                and volume is not None
                and price is not None
                and price_close is not None
            ):
                self.log.error(
                    "calc_profit requires "
                    "order_type, symbol, volume, "
                    "price and price_close."
                )
                return None

            try:
                return mt5.order_calc_profit(
                    order_type,
                    symbol,
                    volume,
                    price,
                    price_close,
                )

            except Exception:
                self.log.exception(
                    "Exception in order_calc_profit."
                )
                return None

        # -------------------------------------------------------------
        # Internal request preparation
        # -------------------------------------------------------------

        def prepare_request(
            request_data: Dict[str, Any],
        ) -> Dict[str, Any]:

            prepared = dict(
                request_data or {}
            )

            target_symbol = (
                prepared.get("symbol")
                or symbol
                or self._default_symbol()
            )

            if not target_symbol:
                raise ValueError(
                    "request requires symbol."
                )

            if not self._symbol_sanity(
                target_symbol
            ):
                raise ValueError(
                    f"Symbol '{target_symbol}' "
                    "is not ready or visible."
                )

            prepared["symbol"] = target_symbol

            tick = mt5.symbol_info_tick(
                target_symbol
            )

            if tick is None:
                raise RuntimeError(
                    f"Cannot get tick for "
                    f"{target_symbol}."
                )

            request_order_type = (
                prepared.get("type")
                if prepared.get("type")
                is not None
                else order_type
            )

            if (
                prepared.get("action")
                == mt5.TRADE_ACTION_DEAL
            ):

                if not prepared.get("price"):

                    if (
                        request_order_type
                        == mt5.ORDER_TYPE_BUY
                    ):
                        prepared["price"] = float(
                            tick.ask
                        )

                    elif (
                        request_order_type
                        == mt5.ORDER_TYPE_SELL
                    ):
                        prepared["price"] = float(
                            tick.bid
                        )

                    else:
                        prepared["price"] = float(
                            tick.ask
                        )

            prepared.setdefault(
                "deviation",
                10,
            )

            prepared.setdefault(
                "type_filling",
                mt5.ORDER_FILLING_IOC,
            )

            prepared.setdefault(
                "type_time",
                mt5.ORDER_TIME_GTC,
            )

            return prepared

        # -------------------------------------------------------------
        # order_check
        # -------------------------------------------------------------

        if action == "check":

            if not isinstance(
                request,
                dict,
            ):
                self.log.error(
                    "check requires request dict."
                )
                return None

            try:
                prepared = prepare_request(
                    request
                )

                result = mt5.order_check(
                    prepared
                )

                if result is None:
                    self.log.error(
                        "order_check failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                account = mt5.account_info()

                return {
                    "retcode": int(
                        getattr(
                            result,
                            "retcode",
                            0,
                        )
                    ),
                    "balance": (
                        float(
                            getattr(
                                account,
                                "balance",
                                0.0,
                            )
                        )
                        if account
                        else None
                    ),
                    "equity": (
                        float(
                            getattr(
                                account,
                                "equity",
                                0.0,
                            )
                        )
                        if account
                        else None
                    ),
                    "profit": (
                        float(
                            getattr(
                                account,
                                "profit",
                                0.0,
                            )
                        )
                        if account
                        else None
                    ),
                    "margin": float(
                        getattr(
                            result,
                            "margin",
                            0.0,
                        )
                    ),
                    "margin_free": float(
                        getattr(
                            result,
                            "margin_free",
                            0.0,
                        )
                    ),
                    "margin_level": (
                        float(
                            getattr(
                                result,
                                "margin_level",
                                0.0,
                            )
                        )
                        if getattr(
                            result,
                            "margin",
                            0.0,
                        )
                        else None
                    ),
                    "comment": getattr(
                        result,
                        "comment",
                        "",
                    ),
                    "request": prepared,
                }

            except Exception:
                self.log.exception(
                    "Exception in order_check."
                )
                return None

        # -------------------------------------------------------------
        # order_send
        # -------------------------------------------------------------

        if action == "send":

            if not isinstance(
                request,
                dict,
            ):
                self.log.error(
                    "send requires request dict."
                )
                return None

            try:
                prepared = prepare_request(
                    request
                )

            except Exception as exc:
                self.log.error(
                    "prepare_request failed: %s",
                    exc,
                )
                return None

            # ---------------------------------------------------------
            # Legacy behavior preserved:
            # first attempt
            # second attempt after 500ms
            # ---------------------------------------------------------

            self.log.info(
                "order_send attempt #1 for %s",
                prepared.get("symbol"),
            )

            try:
                result = mt5.order_send(
                    prepared
                )
            except Exception:
                self.log.exception(
                    "Exception during first order_send."
                )
                result = None

            if (
                result
                and getattr(
                    result,
                    "retcode",
                    0,
                )
                == mt5.TRADE_RETCODE_DONE
            ):
                return self._trade_result(
                    result,
                    prepared,
                )

            self.log.warning(
                "First order_send attempt "
                "was not successful; retrying."
            )

            time.sleep(0.5)

            try:
                result_retry = mt5.order_send(
                    prepared
                )
            except Exception:
                self.log.exception(
                    "Exception during second order_send."
                )
                result_retry = None

            if (
                result_retry
                and getattr(
                    result_retry,
                    "retcode",
                    0,
                )
                == mt5.TRADE_RETCODE_DONE
            ):
                return self._trade_result(
                    result_retry,
                    prepared,
                )

            self.log.error(
                "order_send failed. retcode=%s err=%s",
                (
                    getattr(
                        result_retry,
                        "retcode",
                        None,
                    )
                    if result_retry
                    else None
                ),
                mt5.last_error(),
            )

            return {
                "retcode": int(
                    getattr(
                        result_retry,
                        "retcode",
                        0,
                    )
                    if result_retry
                    else -1
                ),
                "comment": (
                    getattr(
                        result_retry,
                        "comment",
                        "",
                    )
                    if result_retry
                    else "order_send returned None"
                ),
                "request": prepared,
            }

        self.log.error(
            "Invalid action for trade_manager: %s",
            action,
        )

        return None

    @staticmethod
    def _trade_result(
        result: Any,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert MT5 trade result to a plain dictionary.
        """

        return {
            "retcode": int(
                getattr(
                    result,
                    "retcode",
                    0,
                )
            ),
            "deal": int(
                getattr(
                    result,
                    "deal",
                    0,
                )
            ),
            "order": int(
                getattr(
                    result,
                    "order",
                    0,
                )
            ),
            "volume": float(
                getattr(
                    result,
                    "volume",
                    0.0,
                )
            ),
            "price": float(
                getattr(
                    result,
                    "price",
                    0.0,
                )
            ),
            "bid": float(
                getattr(
                    result,
                    "bid",
                    0.0,
                )
            ),
            "ask": float(
                getattr(
                    result,
                    "ask",
                    0.0,
                )
            ),
            "comment": getattr(
                result,
                "comment",
                "",
            ),
            "request_id": int(
                getattr(
                    result,
                    "request_id",
                    0,
                )
            ),
            "retcode_external": int(
                getattr(
                    result,
                    "retcode_external",
                    0,
                )
            ),
            "request": request,
        }

    # =================================================================
    # 6. Positions and History
    # =================================================================

    def manage_positions_history(
        self,
        action: str,
        symbol: Optional[str] = None,
        ticket: Optional[int] = None,
        group: Optional[str] = None,
        date_from: Optional[
            Union[str, dt.datetime]
        ] = None,
        date_to: Optional[
            Union[str, dt.datetime]
        ] = None,
        position_id: Optional[int] = None,
    ) -> Optional[
        Union[
            int,
            List[Dict[str, Any]],
            Dict[str, Any],
        ]
    ]:

        action = (
            action or ""
        ).lower().strip()

        if not self._ensure_initialized():
            return None

        # -------------------------------------------------------------
        # positions_total
        # -------------------------------------------------------------

        if action == "positions_total":

            try:
                return mt5.positions_total()

            except Exception:
                self.log.exception(
                    "Exception in positions_total."
                )
                return None

        # -------------------------------------------------------------
        # positions_get
        # -------------------------------------------------------------

        if action == "positions_get":

            try:

                if ticket is not None:
                    positions = mt5.positions_get(
                        ticket=ticket
                    )

                elif symbol:
                    positions = mt5.positions_get(
                        symbol=symbol
                    )

                else:
                    positions = mt5.positions_get()

                if positions is None:
                    self.log.error(
                        "positions_get failed. err=%s",
                        mt5.last_error(),
                    )
                    return None

                return [
                    _safe_asdict(position)
                    for position in positions
                ]

            except Exception:
                self.log.exception(
                    "Exception in positions_get."
                )
                return None

        # -------------------------------------------------------------
        # History
        # -------------------------------------------------------------

        history_actions = {
            "history_orders_total",
            "history_orders_get",
            "history_deals_total",
            "history_deals_get",
        }

        if action in history_actions:

            timezone = self._tz()

            try:

                date_from_parsed = (
                    _parse_iso_dt(
                        date_from,
                        timezone,
                    )
                    if date_from is not None
                    else None
                )

                date_to_parsed = (
                    _parse_iso_dt(
                        date_to,
                        timezone,
                    )
                    if date_to is not None
                    else None
                )

            except Exception as exc:

                self.log.error(
                    "Invalid history datetime: %s",
                    exc,
                )

                return None

            # ---------------------------------------------------------
            # history_orders_total
            # ---------------------------------------------------------

            if action == "history_orders_total":

                if (
                    date_from_parsed is None
                    or date_to_parsed is None
                ):
                    self.log.error(
                        "history_orders_total requires "
                        "date_from and date_to."
                    )
                    return None

                try:
                    return mt5.history_orders_total(
                        date_from_parsed,
                        date_to_parsed,
                    )

                except Exception:
                    self.log.exception(
                        "Exception in history_orders_total."
                    )
                    return None

            # ---------------------------------------------------------
            # history_orders_get
            # ---------------------------------------------------------

            if action == "history_orders_get":

                try:

                    if ticket is not None:

                        orders = (
                            mt5.history_orders_get(
                                ticket=ticket
                            )
                        )

                    elif position_id is not None:

                        orders = (
                            mt5.history_orders_get(
                                position=position_id
                            )
                        )

                    else:

                        if (
                            date_from_parsed is None
                            or date_to_parsed is None
                        ):
                            self.log.error(
                                "history_orders_get requires "
                                "date range when ticket/position "
                                "is not supplied."
                            )
                            return None

                        orders = (
                            mt5.history_orders_get(
                                date_from_parsed,
                                date_to_parsed,
                                group=group or "*",
                            )
                        )

                    if orders is None:
                        self.log.error(
                            "history_orders_get failed. err=%s",
                            mt5.last_error(),
                        )
                        return None

                    return [
                        _safe_asdict(order)
                        for order in orders
                    ]

                except Exception:
                    self.log.exception(
                        "Exception in history_orders_get."
                    )
                    return None

            # ---------------------------------------------------------
            # history_deals_total
            # ---------------------------------------------------------

            if action == "history_deals_total":

                if (
                    date_from_parsed is None
                    or date_to_parsed is None
                ):
                    self.log.error(
                        "history_deals_total requires "
                        "date_from and date_to."
                    )
                    return None

                try:
                    return mt5.history_deals_total(
                        date_from_parsed,
                        date_to_parsed,
                    )

                except Exception:
                    self.log.exception(
                        "Exception in history_deals_total."
                    )
                    return None

            # ---------------------------------------------------------
            # history_deals_get
            # ---------------------------------------------------------

            if action == "history_deals_get":

                try:

                    if ticket is not None:

                        deals = (
                            mt5.history_deals_get(
                                ticket=ticket
                            )
                        )

                    elif position_id is not None:

                        deals = (
                            mt5.history_deals_get(
                                position=position_id
                            )
                        )

                    else:

                        if (
                            date_from_parsed is None
                            or date_to_parsed is None
                        ):
                            self.log.error(
                                "history_deals_get requires "
                                "date range when ticket/position "
                                "is not supplied."
                            )
                            return None

                        deals = (
                            mt5.history_deals_get(
                                date_from_parsed,
                                date_to_parsed,
                                group=group or "*",
                            )
                        )

                    if deals is None:
                        self.log.error(
                            "history_deals_get failed. err=%s",
                            mt5.last_error(),
                        )
                        return None

                    return [
                        _safe_asdict(deal)
                        for deal in deals
                    ]

                except Exception:
                    self.log.exception(
                        "Exception in history_deals_get."
                    )
                    return None

        self.log.error(
            "Invalid action for "
            "manage_positions_history: %s",
            action,
        )

        return None


__all__ = [
    "Mt5_Manager",
]