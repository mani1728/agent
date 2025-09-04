# -*- coding: utf-8 -*-
"""
meta_trader_manager.py
----------------------
کلاس Mt5_Manager برای مدیریت تعامل با MetaTrader 5 با خواندن «تمام تنظیمات» از config.json
و پشتیبانی کامل از «هات‌ریلُد» (بدون نیاز به ری‌استارت سرویس).

ویژگی‌ها:
- عدم استفاده از ENV؛ همه‌چیز از config.json خوانده می‌شود (از طریق config_manager.cfg()).
- پیش‌فرض‌ها: از بخش "mt5" در config.json (login/password/server/path/timeout_sec/symbols/timezone).
- هر متد، در زمان اجرا، آخرین مقادیر کانفیگ را می‌خواند (هات‌ریلُد واقعی).
- مدیریت اتصال (initialize/login/info/version/account/shutdown)
- مدیریت نمادها (total/get/info/tick/select)
- عمق بازار (market_book add/get/release)
- داده‌های تاریخی (rates/ticks با روش‌های from/from_pos/range)
- مدیریت معاملات (total/get/calc_margin/calc_profit/check/send)
- پوزیشن‌ها و تاریخچه (positions_*/history_*)

پیش‌نیاز:
- MetaTrader5 (کتابخانه رسمی mt5)
- pandas (برای DataFrame)
- pytz (برای timezone)
- config_manager.py (نسخهٔ هات‌ریلُد که قبلاً نوشتیم)

نکته امنیتی:
- رمزها و اطلاعات اتصال را در config.json مدیریت کنید؛ این فایل ENV نمی‌خواهد.
"""

from __future__ import annotations               # ✅ تایپ‌هینت‌های مدرن (سازگاری پایتون 3.8+)
import logging                                   # ✅ لاگ‌گیری یکپارچه (سازگار با config_logging.py)
import datetime as dt                            # ✅ کار با تاریخ/زمان
import time                                      # ✅ تأخیرهای کوتاه در ارسال سفارش/ریترای
from typing import Any, Dict, List, Optional, Union  # ✅ تایپ‌ها برای خوانایی

import pytz                                      # ✅ مدیریت timezone
import pandas as pd                              # ✅ کار با DataFrame
import MetaTrader5 as mt5                        # ✅ کتابخانه رسمی MetaTrader5

from config_manager import cfg                   # ✅ دسترسی به پیکربندی هات‌ریلُد

# -----------------------------
# ابزارهای کمکی داخلی (بدون وابستگی به فایل دیگر)
# -----------------------------

def _parse_iso_dt(s: Union[str, dt.datetime, None], tz: pytz.BaseTzInfo) -> Optional[dt.datetime]:
    """
    ✅ پارس تاریخ/زمان ورودی به datetime آگاه از timezone:
    - اگر None باشد → None
    - اگر datetime باشد → در صورت naive، timezone را اعمال می‌کنیم؛ وگرنه به tz تبدیل می‌کنیم.
    - اگر str باشد (ISO با یا بدون 'Z') → تبدیل به datetime آگاه از tz.
    """
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s if s.tzinfo else tz.localize(s)
    if not isinstance(s, str):
        raise ValueError("datetime must be ISO string or datetime")

    # پشتیبانی از 'Z' در انتها
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        obj = dt.datetime.fromisoformat(s)
    except Exception:
        # fallback: تبدیل فاصله به T
        obj = dt.datetime.fromisoformat(s.replace(" ", "T"))
    if obj.tzinfo is None:
        return tz.localize(obj)
    return obj.astimezone(tz)

def _safe_asdict(obj: Any) -> Any:
    """
    ✅ تبدیل امن آبجکت‌های برگشتی MT5 به dict برای سریال‌سازی/لاگ:
    - اگر _asdict داشت → dict
    - اگر لیست از namedtupleها بود → لیست dict
    - اگر pandas بود → به شکل مناسب
    - در غیراینصورت همان را برمی‌گردانیم
    """
    # namedtuple/structs
    if hasattr(obj, "_asdict"):
        try:
            return obj._asdict()
        except Exception:
            return str(obj)
    if isinstance(obj, list):
        out = []
        for x in obj:
            out.append(_safe_asdict(x))
        return out
    # pandas
    try:
        if isinstance(obj, pd.DataFrame):
            return {
                "preview": obj.head(20).to_dict(orient="records"),
                "columns": list(obj.columns),
                "rows": int(getattr(obj, "shape", [0, 0])[0]),
            }
        if isinstance(obj, pd.Series):
            return obj.to_dict()
    except Exception:
        pass
    return obj

def _comma_join(servers: Union[List[str], str]) -> str:
    """
    ✅ کافکا/شبکه بعضاً رشتهٔ comma-separated می‌خواهد؛
    این تابع لیستِ ['host:port', ...] را به 'a,b,c' تبدیل می‌کند.
    برای MT5 لازم نیست، ولی نگه‌داشتیم اگر لازم شد.
    """
    if isinstance(servers, list):
        return ",".join(servers)
    return str(servers)

# -----------------------------
# کلاس اصلی مدیریت MT5
# -----------------------------
class Mt5_Manager:
    """
    ✅ تمام رفتارهای مرتبط با MetaTrader 5 با تکیه بر config.json
    - مقادیر پیش‌فرض را «هر بار» از cfg().get("mt5.*") می‌خوانیم (هات‌ریلُد)
    - اگر ورودی‌های متد را ارسال کنید، همان‌ها بر کانفیگ مقدم‌اند.
    """

    def __init__(self):
        # ✅ logger ماژول؛ سطح/فرمت توسط setup_logging() خارج از این فایل تعیین می‌شود.
        self.log = logging.getLogger("Mt5_Manager")

    # ------------- ابزار داخلی خواندن کانفیگ MT5 -------------

    def _mt5_cfg(self) -> Dict[str, Any]:
        """
        ✅ خواندن آخرین بخش mt5 از config.json (هات‌ریلُد)
        ساختار مورد انتظار در config.json:
        "mt5": {
          "login": 0, "password": "", "server": "", "path": "",
          "timeout_sec": 10, "symbols": ["EURUSD","XAUUSD"], "timezone": "UTC"
        }
        """
        return cfg().get("mt5", {}) or {}

    def _tz(self) -> pytz.BaseTzInfo:
        """
        ✅ استخراج timezone از کانفیگ (mt5.timezone). اگر اشتباه بود → UTC.
        """
        tz_name = (self._mt5_cfg().get("timezone") or "UTC").strip() or "UTC"
        try:
            return pytz.timezone(tz_name)
        except Exception:
            self.log.warning("Invalid timezone in config: %s (fallback to UTC)", tz_name)
            return pytz.timezone("UTC")

    def _default_symbol(self) -> Optional[str]:
        """
        ✅ انتخاب یک نماد پیش‌فرض از mt5.symbols در config.json (اگر موجود باشد).
        """
        syms = self._mt5_cfg().get("symbols") or []
        if isinstance(syms, list) and syms:
            return str(syms[0])
        return None

    # ------------- ابزارهای داخلی وضعیت/نماد/پیش‌نمایش -------------

    def _ensure_initialized(self) -> bool:
        """
        ✅ بررسی اتصال فعلی به ترمینال MT5.
        اگر connected=False باشد، False برمی‌گرداند.
        """
        info = mt5.terminal_info()
        if info and getattr(info, "connected", False):
            return True
        self.log.debug("MT5 not initialized/connected.")
        return False

    def _symbol_sanity(self, symbol: Optional[str]) -> bool:
        """
        ✅ اطمینان از اینکه نماد معتبر و visible است؛ در صورت لزوم فعال‌سازی (symbol_select).
        اگر symbol خالی بود سعی می‌کنیم از پیش‌فرض کانفیگ برداریم.
        """
        sym = symbol or self._default_symbol()
        if not sym:
            self.log.error("Symbol is empty and no default symbol found in config.")
            return False

        info = mt5.symbol_info(sym)
        if info is None:
            self.log.error("Symbol '%s' not found.", sym)
            return False
        if not info.visible:
            if not mt5.symbol_select(sym, True):
                self.log.error("Failed to select symbol '%s', err=%s", sym, mt5.last_error())
                return False
        return True

    def _df_preview(self, df: Optional[pd.DataFrame], name: str = "") -> None:
        """
        ✅ برای دیباگ: چند ردیف اول DataFrame را لاگ می‌کنیم (نه print).
        """
        if df is None:
            return
        try:
            rows = int(getattr(df, "shape", [0, 0])[0])
            self.log.debug("DF preview (%s) rows=%d\n%s", name, rows, df.head(10))
        except Exception:
            pass

    # ---------------------------------------------------
    # 1) مدیریت اتصال (initialize/login/info/version/account/shutdown)
    # ---------------------------------------------------
    def manage_connection(
        self,
        action: str,                         # "initialize" | "login" | "terminal_info" | "version" | "account_info" | "shutdown"
        path: Optional[str] = None,          # مسیر ترمینال (بر کانفیگ مقدم است)
        login: Optional[int] = None,         # لاگین (بر کانفیگ مقدم است)
        password: Optional[str] = None,      # پسورد (بر کانفیگ مقدم است)
        server: Optional[str] = None,        # نام سرور (بر کانفیگ مقدم است)
        timeout: Optional[int] = None,       # تایم‌اوت اتصال (ms) (اگر None → از کانفیگ)
        portable: bool = False               # حالت پرتابل
    ) -> Optional[Union[bool, Dict[str, Any], List[Any], str]]:
        """
        ✅ اتصال به MT5 و دریافت اطلاعات مرتبط با ترمینال/اکانت.
        - تمام پارامترهای خالی از کانفیگ mt5 پر می‌شوند (هات‌ریلُد).
        """
        action = (action or "").lower().strip()
        allowed = {"initialize", "login", "terminal_info", "version", "account_info", "shutdown"}
        if action not in allowed:
            self.log.error("Invalid action: %s - allowed=%s", action, sorted(allowed))
            return None

        # 📥 خواندن مقادیر از کانفیگ (در لحظه)
        m = self._mt5_cfg()
        path = path if path is not None else (m.get("path") or None)
        login = login if login is not None else (m.get("login") or None)
        password = password if password is not None else (m.get("password") or None)
        server = server if server is not None else (m.get("server") or None)
        # timeout در کانفیگ برحسب «ثانیه» آمده؛ mt5.initialize انتظار ms دارد
        timeout_ms = int((timeout if timeout is not None else int(m.get("timeout_sec") or 10)) * 1000)

        # --- initialize ---
        if action == "initialize":
            info = mt5.terminal_info()
            if info and getattr(info, "connected", False):
                self.log.info("MT5 already connected; skipping initialize.")
                return True

            self.log.info("mt5.initialize(path=%s, login=%s, server=%s, timeout_ms=%s, portable=%s)",
                          path, login, server, timeout_ms, portable)
            ok = mt5.initialize(path=path, login=login, password=password, server=server,
                                timeout=timeout_ms, portable=portable)
            if not ok:
                self.log.error("Failed to initialize MT5. err=%s", mt5.last_error())
                return None
            return True

        # --- login ---
        if action == "login":
            if not self._ensure_initialized():
                self.log.error("MT5 not initialized. Call initialize first.")
                return None
            ok = mt5.login(login=login, password=password, server=server)
            if not ok:
                self.log.error("Failed to login to %s@%s. err=%s", login, server, mt5.last_error())
                return None
            acc = mt5.account_info()
            return _safe_asdict(acc) if acc else None

        # --- terminal_info ---
        if action == "terminal_info":
            info = mt5.terminal_info()
            if info is None:
                self.log.error("Failed to get terminal_info. err=%s", mt5.last_error())
                return None
            return _safe_asdict(info)

        # --- version ---
        if action == "version":
            ver = mt5.version()
            return {"version": ver}

        # --- account_info ---
        if action == "account_info":
            acc = mt5.account_info()
            if acc is None:
                self.log.error("Failed to get account_info. err=%s", mt5.last_error())
                return None
            return _safe_asdict(acc)

        # --- shutdown ---
        if action == "shutdown":
            mt5.shutdown()
            self.log.info("MT5 shutdown called.")
            return True

        return None

    # -------------------------------------
    # 2) مدیریت نمادها (total/get/info/tick/select)
    # -------------------------------------
    def manage_symbols(
        self,
        action: str,                          # "total" | "get" | "info" | "tick" | "select"
        symbol: Optional[str] = None,         # نماد هدف
        group: Optional[str] = None,          # فیلتر group برای get
        enable: bool = True                   # وضعیت در select
    ) -> Optional[Union[int, Dict[str, Any], List[Any], bool]]:
        """
        ✅ عملیات مرتبط با نمادها؛ اگر symbol خالی باشد از پیش‌فرض کانفیگ استفاده می‌شود.
        """
        action = (action or "").lower().strip()
        if action not in {"total", "get", "info", "tick", "select"}:
            self.log.error("Invalid action for manage_symbols: %s", action)
            return None

        if action == "total":
            total = mt5.symbols_total()
            self.log.debug("symbols_total=%s", total)
            return total

        if action == "get":
            syms = mt5.symbols_get(group or "*")
            if syms is None:
                self.log.error("symbols_get failed. err=%s", mt5.last_error())
                return None
            return [_safe_asdict(s) for s in syms]

        if action == "info":
            if not self._symbol_sanity(symbol):
                return None
            info = mt5.symbol_info(symbol or self._default_symbol())
            return _safe_asdict(info) if info else None

        if action == "tick":
            if not self._symbol_sanity(symbol):
                return None
            tick = mt5.symbol_info_tick(symbol or self._default_symbol())
            return _safe_asdict(tick) if tick else None

        if action == "select":
            target = symbol or self._default_symbol()
            if not target:
                self.log.error("select requires symbol (no default found).")
                return None
            ok = mt5.symbol_select(target, enable)
            if not ok:
                self.log.error("symbol_select(%s,%s) failed. err=%s", target, enable, mt5.last_error())
            return bool(ok)

        return None

    # -----------------------------------------
    # 3) عمق بازار (market_book add/get/release)
    # -----------------------------------------
    def manage_market_book(
        self,
        action: str,                        # "add" | "get" | "release"
        symbol: Optional[str] = None        # نماد هدف
    ) -> Optional[Union[List[Dict[str, Any]], bool]]:
        """
        ✅ مدیریت عمق بازار برای نماد؛ add/get/release
        """
        action = (action or "").lower().strip()
        if action not in {"add", "get", "release"}:
            self.log.error("Invalid action for manage_market_book: %s", action)
            return None

        if not self._symbol_sanity(symbol):
            return None
        target = symbol or self._default_symbol()

        if action == "add":
            ok = mt5.market_book_add(target)
            if not ok:
                self.log.error("market_book_add(%s) failed. err=%s", target, mt5.last_error())
            return bool(ok)

        if action == "get":
            book = mt5.market_book_get(target)
            if book is None:
                self.log.error("market_book_get(%s) failed. err=%s", target, mt5.last_error())
                return None
            return [_safe_asdict(b) for b in book]

        if action == "release":
            ok = mt5.market_book_release(target)
            if not ok:
                self.log.error("market_book_release(%s) failed. err=%s", target, mt5.last_error())
            return bool(ok)

        return None

    # -----------------------------------------
    # 4) داده‌های تاریخی (rates / ticks)
    # -----------------------------------------
    def fetch_data(
        self,
        symbol: Optional[str] = None,           # نماد هدف؛ اگر None → از کانفیگ
        data_type: str = "rates",               # "rates" | "ticks"
        method: str = "from",                   # "from" | "from_pos" | "range"
        timeframe: Any = mt5.TIMEFRAME_M1,      # کانستنت mt5 (در صورت رشته، خودتان نگاشت کنید قبل از فراخوانی)
        count: int = 100,                       # تعداد برای from/from_pos
        date_from: Optional[Union[str, dt.datetime]] = None,  # شروع بازه
        date_to: Optional[Union[str, dt.datetime]] = None,    # پایان بازه
        flags: Any = mt5.COPY_TICKS_ALL         # برای ticks: COPY_TICKS_*
    ) -> Optional[Dict[str, Any]]:
        """
        ✅ دریافت داده‌های تاریخی rates/ticks.
        - تاریخ‌ها (str یا datetime) با timezone کانفیگ تبدیل می‌شوند (هات‌ریلُد).
        - symbol اگر None باشد، از mt5.symbols[0] کانفیگ برداشته می‌شود.
        """
        # اتصال
        if not self._ensure_initialized():
            return None

        # symbol آماده
        if not self._symbol_sanity(symbol):
            return None
        target = symbol or self._default_symbol()

        # تنظیم نوع و روش
        data_type = (data_type or "").lower().strip()
        method = (method or "").lower().strip()
        if data_type not in {"rates", "ticks"}:
            self.log.error("Invalid data_type: %s", data_type)
            return None
        if method not in {"from", "from_pos", "range"}:
            self.log.error("Invalid method: %s", method)
            return None

        # منطقه زمانی از کانفیگ
        tz = self._tz()
        # پارس تاریخ‌ها
        dfrom = _parse_iso_dt(date_from, tz) if date_from is not None else None
        dto = _parse_iso_dt(date_to, tz) if date_to is not None else None

        df: Optional[pd.DataFrame] = None
        rows = []

        try:
            if data_type == "rates":
                if method == "from":
                    if not dfrom:
                        self.log.error("fetch_data(rates/from) requires 'date_from'.")
                        return None
                    arr = mt5.copy_rates_from(target, timeframe, dfrom, count)
                elif method == "from_pos":
                    arr = mt5.copy_rates_from_pos(target, timeframe, 0, count)
                else:  # range
                    if not (dfrom and dto):
                        self.log.error("fetch_data(rates/range) requires 'date_from' and 'date_to'.")
                        return None
                    arr = mt5.copy_rates_range(target, timeframe, dfrom, dto)

                if arr is None:
                    self.log.error("copy_rates_* failed. err=%s", mt5.last_error())
                    return None

                df = pd.DataFrame(arr)
                if df.shape[0] > 0 and "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], unit="s")

                rows = [
                    {
                        "time": r["time"],
                        "open": r["open"],
                        "high": r["high"],
                        "low": r["low"],
                        "close": r["close"],
                        "tick_volume": r["tick_volume"],
                        "spread": r["spread"],
                        "real_volume": r["real_volume"],
                    }
                    for _, r in df.iterrows()
                ]

            else:  # ticks
                if method == "from":
                    if not dfrom:
                        self.log.error("fetch_data(ticks/from) requires 'date_from'.")
                        return None
                    arr = mt5.copy_ticks_from(target, dfrom, count, flags)
                elif method == "from_pos":
                    # MT5 تابع from_pos برای ticks ندارد؛ fallback روی from
                    if not dfrom:
                        self.log.error("fetch_data(ticks/from_pos) fallback requires 'date_from'.")
                        return None
                    arr = mt5.copy_ticks_from(target, dfrom, count, flags)
                else:  # range
                    if not (dfrom and dto):
                        self.log.error("fetch_data(ticks/range) requires 'date_from' and 'date_to'.")
                        return None
                    arr = mt5.copy_ticks_range(target, dfrom, dto, flags)

                if arr is None:
                    self.log.error("copy_ticks_* failed. err=%s", mt5.last_error())
                    return None

                df = pd.DataFrame(arr)
                if df.shape[0] > 0 and "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], unit="s")

                rows = [
                    {
                        "time": r.get("time"),
                        "bid": float(r.get("bid", 0.0)),
                        "ask": float(r.get("ask", 0.0)),
                        "last": float(r.get("last", 0.0)),
                        "volume": float(r.get("volume", 0.0)) if "volume" in r else 0.0,
                        "time_msc": int(r.get("time_msc", 0)) if "time_msc" in r else 0,
                        "flags": int(r.get("flags", 0)) if "flags" in r else 0,
                    }
                    for _, r in df.iterrows()
                ]

            # پیش‌نمایش برای دیباگ
            self._df_preview(df, name=f"{data_type}/{method}")

            # خروجی نهایی (frame برای مصرف داخلی/لاگ؛ بیرون اگر لازم بود سریال‌سازی امن انجام دهید)
            return {
                "symbol": target,
                "type": data_type,
                "method": method,
                "rows": len(rows),
                "raw": rows,
                "frame": df,
            }

        except Exception as e:
            self.log.exception("Exception in fetch_data: %s", e)
            return None

    # -----------------------------------------
    # 5) مدیریت معاملات (total/get/calc*/check/send)
    # -----------------------------------------
    def trade_manager(
        self,
        action: str,                            # "total" | "get" | "calc_margin" | "calc_profit" | "check" | "send"
        symbol: Optional[str] = None,           # نماد
        order_type: Optional[int] = None,       # mt5.ORDER_TYPE_*
        volume: Optional[float] = None,         # حجم
        price: Optional[float] = None,          # قیمت
        price_close: Optional[float] = None,    # برای calc_profit
        request: Optional[Dict[str, Any]] = None,  # درخواست کامل برای check/send
    ) -> Optional[Any]:
        """
        ✅ عملیات معاملات شامل:
        - total/get
        - calc_margin / calc_profit
        - check / send
        نکته: symbol خالی باشد → از کانفیگ انتخاب می‌شود.
        """
        action = (action or "").lower().strip()
        if not self._ensure_initialized():
            return None

        # ---- total ----
        if action == "total":
            total = mt5.orders_total()
            self.log.debug("orders_total=%s", total)
            return total

        # ---- get ----
        if action == "get":
            if symbol:
                orders = mt5.orders_get(symbol=symbol)
            else:
                orders = mt5.orders_get()
            if orders is None:
                self.log.error("orders_get failed. err=%s", mt5.last_error())
                return {"raw_orders": None, "orders_frame": pd.DataFrame()}
            frame = pd.DataFrame([o._asdict() for o in orders]) if orders else pd.DataFrame()
            return {"raw_orders": [o._asdict() for o in (orders or [])], "orders_frame": frame}

        # ---- calc_margin ----
        if action == "calc_margin":
            if not (order_type is not None and symbol and volume is not None and price is not None):
                self.log.error("calc_margin requires 'order_type','symbol','volume','price'.")
                return None
            margin = mt5.order_calc_margin(order_type, symbol, volume, price)
            self.log.debug("calc_margin=%s", margin)
            return margin

        # ---- calc_profit ----
        if action == "calc_profit":
            if not (order_type is not None and symbol and volume is not None and price is not None and price_close is not None):
                self.log.error("calc_profit requires 'order_type','symbol','volume','price','price_close'.")
                return None
            profit = mt5.order_calc_profit(order_type, symbol, volume, price, price_close)
            self.log.debug("calc_profit=%s", profit)
            return profit

        # ---- check / send ----
        def _prepare_request(req: Dict[str, Any]) -> Dict[str, Any]:
            """
            ✅ تکمیل request قبل از check/send:
            - اگر action=TRADE_ACTION_DEAL و price خالی است، قیمت مارکت را بر اساس BUY/SELL ست می‌کنیم.
            - deviation/type_filling/type_time پیش‌فرض می‌گذاریم.
            - نماد را sanity-check می‌کنیم.
            """
            out = dict(req or {})
            sy = out.get("symbol") or symbol or self._default_symbol()
            if not sy:
                raise ValueError("request requires 'symbol'.")

            if not self._symbol_sanity(sy):
                raise ValueError(f"Symbol '{sy}' not ready/visible.")
            out["symbol"] = sy

            tick = mt5.symbol_info_tick(sy)
            if tick is None:
                raise RuntimeError(f"Cannot get tick for {sy}. err={mt5.last_error()}")

            otype = out.get("type", order_type)

            # اگر مارکت اکشن است و قیمت نداریم → بر اساس BUY/SELL ست کن
            if out.get("action") == mt5.TRADE_ACTION_DEAL:
                if not out.get("price"):
                    if otype == mt5.ORDER_TYPE_BUY:
                        out["price"] = float(tick.ask)
                    elif otype == mt5.ORDER_TYPE_SELL:
                        out["price"] = float(tick.bid)
                    else:
                        out["price"] = float(tick.ask)
                    self.log.debug("Price set to market (%s)", out["price"])

            # پیش‌فرض‌ها
            out.setdefault("deviation", 10)
            out.setdefault("type_filling", mt5.ORDER_FILLING_IOC)
            out.setdefault("type_time", mt5.ORDER_TIME_GTC)
            return out

        if action == "check":
            if not isinstance(request, dict):
                self.log.error("check requires 'request' dict.")
                return None
            try:
                req = _prepare_request(request)
            except Exception as e:
                self.log.error("prepare_request failed: %s", e)
                return None

            res = mt5.order_check(req)
            if res is None:
                self.log.error("order_check failed. err=%s", mt5.last_error())
                return None

            acc = mt5.account_info()
            return {
                "retcode": int(getattr(res, "retcode", 0)),
                "balance": float(getattr(acc, "balance", 0.0)) if acc else None,
                "equity": float(getattr(acc, "equity", 0.0)) if acc else None,
                "profit": float(getattr(acc, "profit", 0.0)) if acc else None,
                "margin": float(getattr(res, "margin", 0.0)),
                "margin_free": float(getattr(res, "margin_free", 0.0)),
                "margin_level": float(getattr(res, "margin_level", 0.0)) if getattr(res, "margin", 0.0) else None,
                "comment": getattr(res, "comment", ""),
                "request": req,
            }

        if action == "send":
            if not isinstance(request, dict):
                self.log.error("send requires 'request' dict.")
                return None

            try:
                req = _prepare_request(request)
            except Exception as e:
                self.log.error("prepare_request failed: %s", e)
                return None

            self.log.info("order_send attempt #1 for %s", req.get("symbol"))
            res = mt5.order_send(req)
            if res and getattr(res, "retcode", 0) == mt5.TRADE_RETCODE_DONE:
                self.log.info("order_send DONE on first attempt. deal=%s order=%s",
                              getattr(res, "deal", 0), getattr(res, "order", 0))
                return {
                    "retcode": int(getattr(res, "retcode", 0)),
                    "deal": int(getattr(res, "deal", 0)),
                    "order": int(getattr(res, "order", 0)),
                    "volume": float(getattr(res, "volume", 0.0)),
                    "price": float(getattr(res, "price", 0.0)),
                    "bid": float(getattr(res, "bid", 0.0)),
                    "ask": float(getattr(res, "ask", 0.0)),
                    "comment": getattr(res, "comment", ""),
                    "request_id": int(getattr(res, "request_id", 0)),
                    "retcode_external": int(getattr(res, "retcode_external", 0)),
                    "request": req,
                }

            self.log.warning("First attempt not DONE (retcode=%s). Retrying...", getattr(res, "retcode", None))
            time.sleep(0.5)
            res2 = mt5.order_send(req)
            if res2 and getattr(res2, "retcode", 0) == mt5.TRADE_RETCODE_DONE:
                self.log.info("order_send DONE on second attempt. deal=%s order=%s",
                              getattr(res2, "deal", 0), getattr(res2, "order", 0))
                return {
                    "retcode": int(getattr(res2, "retcode", 0)),
                    "deal": int(getattr(res2, "deal", 0)),
                    "order": int(getattr(res2, "order", 0)),
                    "volume": float(getattr(res2, "volume", 0.0)),
                    "price": float(getattr(res2, "price", 0.0)),
                    "bid": float(getattr(res2, "bid", 0.0)),
                    "ask": float(getattr(res2, "ask", 0.0)),
                    "comment": getattr(res2, "comment", ""),
                    "request_id": int(getattr(res2, "request_id", 0)),
                    "retcode_external": int(getattr(res2, "retcode_external", 0)),
                    "request": req,
                }

            self.log.error("order_send failed or not DONE. retcode=%s err=%s",
                           getattr(res2, "retcode", None) if res2 else None, mt5.last_error())
            return {
                "retcode": int(getattr(res2, "retcode", 0) if res2 else -1),
                "comment": getattr(res2, "comment", "") if res2 else "order_send returned None",
                "request": req,
            }

        self.log.error("Invalid action for trade_manager: %s", action)
        return None

    # -----------------------------------------------------
    # 6) پوزیشن‌ها و تاریخچه (positions_* ، history_*)
    # -----------------------------------------------------
    def manage_positions_history(
        self,
        action: str,                                      # "positions_total" | "positions_get" | "history_orders_total" | "history_orders_get" | "history_deals_total" | "history_deals_get"
        symbol: Optional[str] = None,                     # فیلتر نماد
        ticket: Optional[int] = None,                     # فیلتر تیکت
        group: Optional[str] = None,                      # فیلتر group برای history_*_get
        date_from: Optional[Union[str, dt.datetime]] = None,  # شروع بازه
        date_to: Optional[Union[str, dt.datetime]] = None,    # پایان بازه
        position_id: Optional[int] = None                 # فیلتر position_id
    ) -> Optional[Union[int, List[Dict[str, Any]], Dict[str, Any]]]:
        """
        ✅ مدیریت پوزیشن‌های باز و تاریخچه سفارش‌ها/دیل‌ها با پشتیبانی timezone از کانفیگ.
        """
        action = (action or "").lower().strip()
        if not self._ensure_initialized():
            return None

        # ---- پوزیشن‌های باز ----
        if action == "positions_total":
            total = mt5.positions_total()
            self.log.debug("positions_total=%s", total)
            return total

        if action == "positions_get":
            if ticket is not None:
                pos = mt5.positions_get(ticket=ticket)
            elif symbol:
                pos = mt5.positions_get(symbol=symbol)
            else:
                pos = mt5.positions_get()

            if pos is None:
                self.log.error("positions_get failed. err=%s", mt5.last_error())
                return None
            return [_safe_asdict(p) for p in pos]

        # ---- تاریخچه orders/deals ----
        if action in {"history_orders_total", "history_orders_get", "history_deals_total", "history_deals_get"}:
            tz = self._tz()
            dfrom = _parse_iso_dt(date_from, tz) if date_from is not None else None
            dto = _parse_iso_dt(date_to, tz) if date_to is not None else None

            if action.endswith("_total") and (dfrom is None or dto is None):
                self.log.error("%s requires 'date_from' and 'date_to'.", action)
                return None

            # ----- ORDERS -----
            if action == "history_orders_total":
                total = mt5.history_orders_total(dfrom, dto)
                self.log.debug("history_orders_total %s→%s = %s", dfrom, dto, total)
                return total

            if action == "history_orders_get":
                if ticket is not None:
                    orders = mt5.history_orders_get(ticket=ticket)
                elif position_id is not None:
                    orders = mt5.history_orders_get(position=position_id)
                else:
                    orders = mt5.history_orders_get(dfrom, dto, group=group or "*")

                if orders is None:
                    self.log.error("history_orders_get failed. err=%s", mt5.last_error())
                    return None

                out = [_safe_asdict(o) for o in orders]
                self.log.debug("history_orders_get found=%d", len(out))
                return out

            # ----- DEALS -----
            if action == "history_deals_total":
                total = mt5.history_deals_total(dfrom, dto)
                self.log.debug("history_deals_total %s→%s = %s", dfrom, dto, total)
                return total

            if action == "history_deals_get":
                if ticket is not None:
                    deals = mt5.history_deals_get(ticket=ticket)
                elif position_id is not None:
                    deals = mt5.history_deals_get(position=position_id)
                else:
                    deals = mt5.history_deals_get(dfrom, dto, group=group or "*")

                if deals is None:
                    self.log.error("history_deals_get failed. err=%s", mt5.last_error())
                    return None

                out = [_safe_asdict(d) for d in deals]
                self.log.debug("history_deals_get found=%d", len(out))
                return out

        self.log.error("Invalid action for manage_positions_history: %s", action)
        return None
