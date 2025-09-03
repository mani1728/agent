# meta_trader_manager.py
# کلاس Mt5_Manager برای مدیریت تعامل با MetaTrader 5
# این نسخه بهینه‌سازی شده با مدیریت خطا، تبدیل خروجی‌ها به قالب‌های خوانا،
# سازگاری با پیام‌های Kafka و پشتیبانی کامل از متدها/اکشن‌های مورد نیاز است.

# -----------------------------
# وارد کردن کتابخانه‌های لازم
# -----------------------------
import MetaTrader5 as mt5  # کتابخانه رسمی MT5 برای پایتون
import pandas as pd        # برای DataFrame و کار با داده‌ها
import datetime            # کار با تاریخ/زمان
import pytz                # مدیریت timezone (UTC و ...)
import time                # تاخیرهای کوتاه بین درخواست‌ها (مثلاً ارسال سفارش)
from typing import Any, Dict, List, Optional, Union  # تایپ‌ هینت‌ها برای خوانایی بهتر


# ---------------------------------------
# تعریف کلاس اصلی مدیریت MetaTrader 5
# ---------------------------------------
class Mt5_Manager:
    # سازنده کلاس: آماده‌سازی مقادیر پیش‌فرض و وضعیت اتصال
    def __init__(self):
        self.default_path: Optional[str] = None          # مسیر ترمینال در صورت نیاز (اختیاری)
        self.default_login: Optional[int] = None         # لاگین پیش‌فرض (اختیاری)
        self.default_password: Optional[str] = None      # پسورد پیش‌فرض (اختیاری)
        self.default_server: Optional[str] = None        # نام سرور پیش‌فرض (اختیاری)
        self.terminal_info = None                        # کش اطلاعات ترمینال
        self.version = None                              # کش نسخه MT5
        self.account_info_dict: Dict[str, Any] = {}      # کش اطلاعات حساب به‌صورت dict
        self.utc_tz = pytz.timezone("Etc/UTC")           # منطقه زمانی UTC برای تاریخ‌های history
        # نکته: اتصال واقعی در متد manage_connection انجام می‌شود، اینجا فقط آماده‌سازی است.

    # -----------------------------
    # ابزارهای کمکی داخلی
    # -----------------------------
    def _ensure_initialized(self) -> bool:
        """بررسی می‌کند که ترمینال MT5 وصل است؛ در غیراینصورت تلاش می‌کند از وضعیت فعلی info بگیرد."""
        info = mt5.terminal_info()  # گرفتن اطلاعات فعلی ترمینال
        if info and getattr(info, "connected", False):   # اگر متصل است
            return True                                  # اوکی
        print("MT5 not initialized/connected.")          # اطلاع برای دیباگ
        return False                                     # عدم اتصال

    def _symbol_sanity(self, symbol: str) -> bool:
        """اطمینان از اینکه نماد انتخاب و فعال است؛ در صورت لزوم فعال‌سازی می‌کند."""
        if not symbol:                                   # اگر نماد خالی بود
            print("Symbol is empty.")                    # چاپ هشدار
            return False                                 # خروج
        info = mt5.symbol_info(symbol)                   # اطلاعات نماد
        if info is None:                                 # اگر نماد نامعتبر بود
            print(f"Symbol '{symbol}' not found.")       # هشدار
            return False
        if not info.visible:                             # اگر نماد در MarketWatch غیرفعال است
            if not mt5.symbol_select(symbol, True):      # تلاش برای فعال‌سازی
                print(f"Failed to select symbol '{symbol}', err={mt5.last_error()}")  # خطا
                return False
        return True                                      # نماد آماده است

    def _dt(self, dt: Union[str, datetime.datetime, None]) -> Optional[datetime.datetime]:
        """تبدیل ورودی به datetime آگاه از UTC (اگر رشته باشد)."""
        if dt is None:                                   # اگر چیزی ندادند
            return None                                  # None برگردان
        if isinstance(dt, datetime.datetime):            # اگر خودش datetime است
            return dt if dt.tzinfo else self.utc_tz.localize(dt)  # timezone دارش کن
        # اگر رشته ISO باشد (main.py از قبل به datetime تبدیل می‌کند، اما برای ایمنی اینجا هم پشتیبانی می‌کنیم)
        try:
            if dt.endswith("Z"):                         # پشتیبانی از Z انتهای ISO
                dt = dt[:-1] + "+00:00"                  # تبدیل Z به +00:00
            obj = datetime.datetime.fromisoformat(dt)    # تبدیل به datetime
            return obj if obj.tzinfo else self.utc_tz.localize(obj)  # timezone
        except Exception:
            print(f"Invalid datetime format: {dt}")      # هشدار فرمت اشتباه
            return None

    def _df_preview(self, df: pd.DataFrame, name: str = "") -> None:
        """برای دیباگ: نمایش چند ردیف اول DataFrame."""
        rows = df.shape[0] if isinstance(df, pd.DataFrame) else 0  # تعداد ردیف
        print(f"\nDisplay dataframe preview ({name}) - rows={rows}")  # چاپ وضعیت
        try:
            print(df.head(10))                            # چاپ 10 ردیف اول
        except Exception:
            pass                                          # اهمیتی ندارد اگر df خیلی بزرگ است

    # ---------------------------------------------------
    # 1) مدیریت اتصال به ترمینال (initialize/login/...)
    # ---------------------------------------------------
    def manage_connection(
        self,
        action: str,                         # اکشن درخواستی: initialize/login/terminal_info/version/account_info/shutdown
        path: Optional[str] = None,          # مسیر ترمینال (اختیاری)
        login: Optional[int] = None,         # لاگین (اختیاری)
        password: Optional[str] = None,      # پسورد (اختیاری)
        server: Optional[str] = None,        # نام سرور (اختیاری)
        timeout: int = 60000,                # تایم‌اوت اتصال
        portable: bool = False               # حالت پرتابل (در صورت نیاز)
    ) -> Optional[Union[bool, Dict[str, Any], List[Any], str]]:
        """مدیریت اتصال به MT5 (initialize/login/info/version/account/shutdown)."""

        # یکسان‌سازی حروف اکشن برای اطمینان
        action = (action or "").lower()      # اکشن را به حروف کوچک تبدیل کن

        # بررسی اکشن مجاز
        allowed = {"initialize", "login", "terminal_info", "version", "account_info", "shutdown"}  # لیست مجاز
        if action not in allowed:            # اگر اکشن نامعتبر بود
            print(f"Invalid action: {action}. Allowed: {sorted(allowed)}")  # چاپ خطا
            return None                      # خروج

        # جایگزینی با مقادیر پیش‌فرض اگر پارامترها خالی باشند
        path = path or self.default_path
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server

        # اکشن initialize: تلاش برای اتصال کامل با پارامترها
        if action == "initialize":
            # اگر از قبل متصل است، فقط کش را به‌روزرسانی کن
            info = mt5.terminal_info()                               # اطلاعات ترمینال
            if info and getattr(info, "connected", False):           # اگر وصل است
                print("MT5 already connected, skipping initialize")  # پیام
                self.terminal_info = info                            # کش اطلاعات ترمینال
                self.version = mt5.version()                         # کش نسخه
                return True                                          # موفقیت

            print(f"mt5_init called: path={path}, login={login}, server={server}")  # چاپ جزئیات اتصال
            ok = mt5.initialize(                                     # فراخوانی initialize اصلی کتابخانه
                path=path, login=login, password=password, server=server,
                timeout=timeout, portable=portable
            )
            if not ok:                                               # اگر اتصال موفق نبود
                print(f"Failed to initialize MT5. err={mt5.last_error()}")  # چاپ خطا
                return None                                          # خروج
            self.terminal_info = mt5.terminal_info()                 # کش ترمینال
            self.version = mt5.version()                             # کش نسخه
            return True                                              # موفقیت

        # اکشن login: اگر initialize شده، لاگین مجدد به حساب
        if action == "login":
            if not self._ensure_initialized():                       # باید ابتدا initialize انجام شده باشد
                print("MT5 not initialized. Call initialize first.") # پیام راهنما
                return None
            # تابع login در MT5 برای سوئیچ حساب/ورود مجدد
            success = mt5.login(login=login, password=password, server=server)  # تلاش لاگین
            if not success:                                          # اگر لاگین موفق نبود
                print(f"Failed to login to {login}@{server}. err={mt5.last_error()}")  # چاپ خطا
                return None
            acc = mt5.account_info()                                  # اطلاعات حساب بعد از لاگین
            if acc is None:                                          # اگر نگرفت
                print(f"Failed to read account_info after login. err={mt5.last_error()}")  # خطا
                return None
            self.account_info_dict = acc._asdict()                    # ذخیره دیکشنری
            return self.account_info_dict                             # برگرداندن خروجی

        # اکشن terminal_info: برگرداندن اطلاعات ترمینال
        if action == "terminal_info":
            info = mt5.terminal_info()                                # اطلاعات ترمینال
            if info is None:
                print(f"Failed to get terminal_info. err={mt5.last_error()}")  # چاپ خطا
                return None
            self.terminal_info = info                                 # کش
            return info._asdict()                                     # دیکشنری قابل سریال

        # اکشن version: برگرداندن نسخه MT5
        if action == "version":
            self.version = mt5.version()                              # گرفتن نسخه
            return {"version": self.version}                          # برگرداندن در قالب dict

        # اکشن account_info: برگرداندن اطلاعات حساب
        if action == "account_info":
            acc = mt5.account_info()                                  # خواندن اطلاعات حساب
            if acc is None:
                print(f"Failed to get account_info. err={mt5.last_error()}")  # خطا
                return None
            self.account_info_dict = acc._asdict()                    # کش
            return self.account_info_dict                             # خروجی

        # اکشن shutdown: بستن اتصال
        if action == "shutdown":
            mt5.shutdown()                                            # قطع اتصال
            print("MT5 shutdown called.")                             # پیام
            return True                                               # اتمام موفق

        return None                                                   # حالت غیرمنتظره

    # -------------------------------------
    # 2) مدیریت نمادها (total/get/info/...)
    # -------------------------------------
    def manage_symbols(
        self,
        action: str,                          # اکشن: total/get/info/tick/select
        symbol: Optional[str] = None,         # نماد هدف
        group: Optional[str] = None,          # گروه فیلتر (برای get)
        enable: bool = True                   # فعال/غیرفعال کردن در select
    ) -> Optional[Union[int, Dict[str, Any], List[Any], bool]]:
        """عملیات مربوط به نمادها مثل total/get/info/tick/select."""

        action = (action or "").lower()       # یکسان‌سازی اکشن
        if action not in {"total", "get", "info", "tick", "select"}:  # اعتبارسنجی اکشن
            print(f"Invalid action for manage_symbols: {action}")     # خطا
            return None

        if action == "total":                 # تعداد کل نمادهای موجود
            total = mt5.symbols_total()       # فراخوانی API
            print(f"Symbols total: {total}")  # چاپ
            return total                      # خروجی عددی

        if action == "get":                   # لیست نمادها با فیلتر group
            syms = mt5.symbols_get(group or "*")  # فراخوانی API با گروه
            if syms is None:                      # اگر نتیجه None شد
                print(f"Failed to get symbols. err={mt5.last_error()}")  # خطا
                return None
            print(f"Fetched {len(syms)} symbols for group='{group or '*'}'")  # چاپ
            return [s._asdict() for s in syms]                                # تبدیل به dict

        if action == "info":                 # اطلاعات یک نماد
            if not self._symbol_sanity(symbol):  # اطمینان از آماده بودن نماد
                return None
            info = mt5.symbol_info(symbol)       # گرفتن اطلاعات
            if info is None:                     # اگر پیدا نشد
                print(f"Failed to get symbol_info({symbol}). err={mt5.last_error()}")  # خطا
                return None
            return info._asdict()                # خروجی dict

        if action == "tick":                 # آخرین تیک قیمت نماد
            if not self._symbol_sanity(symbol):  # آماده‌سازی نماد
                return None
            tick = mt5.symbol_info_tick(symbol)  # دریافت آخرین تیک
            if tick is None:                     # خطا
                print(f"Failed to get tick for {symbol}. err={mt5.last_error()}")  # چاپ خطا
                return None
            return tick._asdict()                # خروجی dict

        if action == "select":              # فعال/غیرفعال کردن نماد
            if not symbol:
                print("select action requires 'symbol'.")  # نیاز به نماد
                return None
            ok = mt5.symbol_select(symbol, enable)         # تغییر وضعیت
            if not ok:
                print(f"Failed to symbol_select({symbol}, {enable}). err={mt5.last_error()}")  # خطا
            return bool(ok)                                 # خروجی بولی

        return None

    # -----------------------------------------
    # 3) عمق بازار (market_book add/get/release)
    # -----------------------------------------
    def manage_market_book(
        self,
        action: str,                        # اکشن: add/get/release
        symbol: Optional[str] = None        # نماد هدف
    ) -> Optional[Union[List[Dict[str, Any]], bool]]:
        """مدیریت عمق بازار نماد (market_book) شامل add/get/release."""

        action = (action or "").lower()     # یکسان‌سازی اکشن
        if action not in {"add", "get", "release"}:  # اعتبارسنجی
            print(f"Invalid action for manage_market_book: {action}")  # خطا
            return None

        if not self._symbol_sanity(symbol):  # آماده‌سازی نماد
            return None

        if action == "add":                 # افزودن اشتراک عمق بازار
            ok = mt5.market_book_add(symbol)  # فراخوانی API
            if not ok:
                print(f"Failed to market_book_add({symbol}). err={mt5.last_error()}")  # خطا
            return bool(ok)                  # خروجی بولی

        if action == "get":                 # گرفتن اسنپ‌شات عمق بازار
            book = mt5.market_book_get(symbol)  # فراخوانی API
            if book is None:
                print(f"Failed to market_book_get({symbol}). err={mt5.last_error()}")  # خطا
                return None
            return [b._asdict() for b in book]  # خروجی لیست dict

        if action == "release":            # لغو اشتراک عمق بازار
            ok = mt5.market_book_release(symbol)  # فراخوانی API
            if not ok:
                print(f"Failed to market_book_release({symbol}). err={mt5.last_error()}")  # خطا
            return bool(ok)                 # خروجی بولی

        return None

    # -----------------------------------------
    # 4) داده‌های تاریخی (rates / ticks)
    # -----------------------------------------
    def fetch_data(
        self,
        symbol: str,                          # نماد هدف
        data_type: str = "rates",             # نوع داده: "rates" یا "ticks"
        method: str = "from",                 # روش: "from" | "from_pos" | "range"
        timeframe: Any = mt5.TIMEFRAME_M1,    # تایم‌فریم برای rates (main.py رشته‌ها را به کانستنت تبدیل می‌کند)
        count: int = 100,                     # تعداد داده برای "from" یا "from_pos"
        date_from: Optional[datetime.datetime] = None,  # شروع بازه
        date_to: Optional[datetime.datetime] = None,    # پایان بازه
        flags: Any = mt5.COPY_TICKS_ALL       # فلگ‌های ticks (COPY_TICKS_* )
    ) -> Optional[Dict[str, Any]]:
        """دریافت داده‌های تاریخی rates/ticks با روش‌های متنوع."""

        # بررسی اتصال
        if not self._ensure_initialized():       # باید متصل باشیم
            return None

        # آماده‌سازی نماد
        if not self._symbol_sanity(symbol):      # نماد باید فعال باشد
            return None

        data_type = (data_type or "").lower()    # نوع داده
        method = (method or "").lower()          # روش دریافت

        # اعتبارسنجی پارامترها
        if data_type not in {"rates", "ticks"}:
            print(f"Invalid data_type: {data_type}. Must be 'rates' or 'ticks'.")  # خطا
            return None
        if method not in {"from", "from_pos", "range"}:
            print(f"Invalid method: {method}. Must be 'from', 'from_pos', or 'range'.")  # خطا
            return None

        # --- دریافت داده‌ها بر اساس نوع و روش ---
        raw_data = []                             # ظرف خروجی خام
        df: Optional[pd.DataFrame] = None         # DataFrame برای پیش‌نمایش

        try:
            if data_type == "rates":              # اگر نرخ‌ها (OHLCV)
                if method == "from":              # از یک تاریخ مشخص با count
                    if not date_from:             # اگر تاریخ شروع نداریم
                        print("fetch_data(rates/from) requires 'date_from'.")  # راهنما
                        return None
                    df_arr = mt5.copy_rates_from(symbol, timeframe, date_from, count)  # فراخوانی API
                elif method == "from_pos":        # از یک ایندکس شروع با count
                    df_arr = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)      # فراخوانی
                else:                              # "range" → بازه‌ی زمانی
                    if not date_from or not date_to:                                   # نیاز به بازه
                        print("fetch_data(rates/range) requires 'date_from' and 'date_to'.")  # راهنما
                        return None
                    df_arr = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)      # فراخوانی

                if df_arr is None:                 # اگر داده‌ای نیامد
                    print(f"Failed to copy rates. err={mt5.last_error()}")  # خطا
                    return None

                df = pd.DataFrame(df_arr)          # ساخت DataFrame
                if df.shape[0] > 0:                # اگر ردیف داریم
                    df["time"] = pd.to_datetime(df["time"], unit="s")  # تبدیل timestamp به datetime

                # تبدیل هر ردیف به dict استاندارد
                raw_data = [
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
                    for _, row in df.iterrows()
                ]

            else:  # data_type == "ticks"
                if method == "from":               # از یک تاریخ مشخص با count
                    if not date_from:
                        print("fetch_data(ticks/from) requires 'date_from'.")  # راهنما
                        return None
                    df_arr = mt5.copy_ticks_from(symbol, date_from, count, flags)  # فراخوانی
                elif method == "from_pos":         # از یک ایندکس شروع با count (ticks اپی رسمی ندارد؛ نگه‌داشتیم برای سازگاری)
                    print("ticks/from_pos is not supported by MT5. Using ticks/from with 'date_from' now.")  # اطلاع
                    if not date_from:
                        print("fetch_data(ticks/from_pos) fallback requires 'date_from'.")  # راهنما
                        return None
                    df_arr = mt5.copy_ticks_from(symbol, date_from, count, flags)         # fallback
                else:                               # "range" → با بازه زمانی
                    if not date_from or not date_to:
                        print("fetch_data(ticks/range) requires 'date_from' and 'date_to'.")  # راهنما
                        return None
                    df_arr = mt5.copy_ticks_range(symbol, date_from, date_to, flags)          # فراخوانی

                if df_arr is None:                 # اگر داده‌ای نیامد
                    print(f"Failed to copy ticks. err={mt5.last_error()}")  # خطا
                    return None

                # ساخت DataFrame ticks با ستون‌های متعارف
                df = pd.DataFrame(df_arr)
                if df.shape[0] > 0:
                    # MT5 برای ticks ستون های: time, bid, ask, last, flags, volume, time_msc دارد
                    df["time"] = pd.to_datetime(df["time"], unit="s")       # تبدیل time
                    # سایر ستون‌ها را دست‌نخورده می‌گذاریم

                # تبدیل به لیست dict
                raw_data = [
                    {
                        "time": row.get("time"),
                        "bid": float(row.get("bid", 0.0)),
                        "ask": float(row.get("ask", 0.0)),
                        "last": float(row.get("last", 0.0)),
                        "volume": float(row.get("volume", 0.0)) if "volume" in row else 0.0,
                        "time_msc": int(row.get("time_msc", 0)) if "time_msc" in row else 0,
                        "flags": int(row.get("flags", 0)) if "flags" in row else 0,
                    }
                    for _, row in df.iterrows()
                ]

            # نمایش پیش‌نمایش DataFrame برای دیباگ
            self._df_preview(df, name=f"{data_type}/{method}")

            # خروجی نهایی
            return {
                "symbol": symbol,
                "type": data_type,
                "method": method,
                "rows": len(raw_data),
                "raw": raw_data,
                "frame": df,  # DataFrame برای تحلیل داخلی؛ در main.py برای لاگ خلاصه می‌شود
            }

        except Exception as e:
            print(f"Exception in fetch_data: {e}")  # چاپ خطای غیرمنتظره
            return None

    # -----------------------------------------
    # 5) مدیریت معاملات (total/get/calc*/check/send)
    # -----------------------------------------
    def trade_manager(
        self,
        action: str,                            # اکشن: total/get/calc_margin/calc_profit/check/send
        symbol: Optional[str] = None,           # نماد (برای get/calc*/check/send)
        order_type: Optional[int] = None,       # نوع سفارش (mt5.ORDER_TYPE_*)
        volume: Optional[float] = None,         # حجم
        price: Optional[float] = None,          # قیمت (در مارکت لازم نیست و اتوماتیک ست می‌شود)
        price_close: Optional[float] = None,    # قیمت بستن برای calc_profit
        request: Optional[Dict[str, Any]] = None,  # دیکشنری کامل درخواست برای check/send
    ) -> Optional[Any]:
        """عملیات مدیریتی معاملات شامل total/get/calc_margin/calc_profit/check/send."""

        action = (action or "").lower()         # یکسان‌سازی اکشن

        # اتصال باید برقرار باشد
        if not self._ensure_initialized():
            return None

        # اکشن: تعداد سفارش‌های در صف
        if action == "total":
            total = mt5.orders_total()          # تعداد سفارش‌ها
            print(f"Total open orders: {total}")  # چاپ وضعیت
            return total

        # اکشن: دریافت سفارش‌ها (فیلتر ساده با symbol)
        if action == "get":
            if symbol:
                orders = mt5.orders_get(symbol=symbol)  # با فیلتر نماد
            else:
                orders = mt5.orders_get()               # همه سفارش‌ها
            if orders is None:
                print(f"Failed to get orders. err={mt5.last_error()}")  # خطا
                return {"raw_orders": None, "orders_frame": pd.DataFrame()}  # خروجی امن
            # تبدیل به DataFrame و dict
            frame = pd.DataFrame([o._asdict() for o in orders]) if orders else pd.DataFrame()
            print(f"Found {len(frame)} orders.")       # چاپ تعداد
            return {"raw_orders": [o._asdict() for o in (orders or [])], "orders_frame": frame}

        # اکشن: محاسبه مارجین
        if action == "calc_margin":
            if not (order_type is not None and symbol and volume is not None and price is not None):
                print("calc_margin requires 'order_type', 'symbol', 'volume', 'price'.")  # راهنما
                return None
            margin = mt5.order_calc_margin(order_type, symbol, volume, price)  # فراخوانی API
            print(f"Calculated margin: {margin}")        # چاپ نتیجه
            return margin

        # اکشن: محاسبه سود/زیان
        if action == "calc_profit":
            if not (order_type is not None and symbol and volume is not None and price is not None and price_close is not None):
                print("calc_profit requires 'order_type', 'symbol', 'volume', 'price', 'price_close'.")  # راهنما
                return None
            profit = mt5.order_calc_profit(order_type, symbol, volume, price, price_close)  # API
            print(f"Calculated profit: {profit}")        # چاپ
            return profit

        # تابع کمکی برای تکمیل فیلدهای request قبل از check/send
        def _prepare_request(req: Dict[str, Any]) -> Dict[str, Any]:
            """تکمیل request: قیمت مارکت، پر کردن فیلدهای ضروری و سازگارسازی Filling/Time."""
            req = dict(req or {})                        # کپی امن
            sy = req.get("symbol") or symbol             # نماد از request یا آرگومان تابع
            if not sy:
                raise ValueError("request requires 'symbol'.")  # باید نماد داشته باشیم

            # اطمینان از آماده بودن نماد
            if not self._symbol_sanity(sy):
                raise ValueError(f"Symbol '{sy}' is not ready/visible.")

            # گرفتن تیک برای قیمت‌های مارکت
            tick = mt5.symbol_info_tick(sy)              # آخرین تیک
            if tick is None:
                raise RuntimeError(f"Cannot get tick for {sy}. err={mt5.last_error()}")  # خطا

            # نوع سفارش (BUY/SELL) برای تصمیم bid/ask
            otype = req.get("type", order_type)          # نوع سفارش از request یا آرگومان
            # اگر قیمت خالی باشد و سفارش از نوع مارکت باشد → به طور خودکار تنظیم کن
            # TRADE_ACTION_DEAL یعنی مارکت؛ TRADE_ACTION_PENDING یعنی اردر معلق
            if req.get("action") == mt5.TRADE_ACTION_DEAL:
                # اگر قیمت صفر/خالی است → ست کن
                if not req.get("price"):
                    if otype == mt5.ORDER_TYPE_BUY:      # برای BUY از ask استفاده کن
                        req["price"] = float(tick.ask)
                    elif otype == mt5.ORDER_TYPE_SELL:   # برای SELL از bid استفاده کن
                        req["price"] = float(tick.bid)
                    else:
                        # اگر نوع نامشخص بود، پیش‌فرض ask را می‌گذاریم
                        req["price"] = float(tick.ask)
                    print(f"Price for Market Execution set to {req['price']}")  # پیام مشابه لاگ شما

            # deviation پیش‌فرض
            req.setdefault("deviation", 10)              # انحراف مجاز
            # type_filling پیش‌فرض
            req.setdefault("type_filling", mt5.ORDER_FILLING_IOC)   # حالت IOC
            # type_time پیش‌فرض
            req.setdefault("type_time", mt5.ORDER_TIME_GTC)         # تا لغو (Good-Till-Cancel)

            # در صورت نیاز می‌توانید با symbol_info.filling_mode سازگار کنید (بروکرها متفاوت‌اند)
            # توصیه: اگر order_check خطای Filling داد، این فیلد را تغییر دهید.

            return req

        # اکشن: check (اعتبارسنجی درخواست قبل از ارسال)
        if action == "check":
            if not isinstance(request, dict):
                print("check requires 'request' dict.")  # راهنما
                return None
            req = _prepare_request(request)              # تکمیل request
            result = mt5.order_check(req)                # فراخوانی API
            if result is None:
                print(f"order_check failed. err={mt5.last_error()}")  # خطا
                return None
            # ساخت پاسخ خوانا
            account = mt5.account_info()                 # اطلاعات حساب لحظه‌ای
            return {
                "retcode": int(getattr(result, "retcode", 0)),
                "balance": float(getattr(account, "balance", 0.0)) if account else None,
                "equity": float(getattr(account, "equity", 0.0)) if account else None,
                "profit": float(getattr(account, "profit", 0.0)) if account else None,
                "margin": float(getattr(result, "margin", 0.0)),
                "margin_free": float(getattr(result, "margin_free", 0.0)),
                "margin_level": float(getattr(result, "margin_level", 0.0)) if getattr(result, "margin", 0.0) else None,
                "comment": getattr(result, "comment", ""),
                "request": req,
            }

        # اکشن: send (ارسال سفارش)
        if action == "send":
            if not isinstance(request, dict):
                print("send requires 'request' dict.")  # راهنما
                return None
            req = _prepare_request(request)             # تکمیل request

            # تلاش شماره 1: ارسال مستقیم
            print(f"Attempting to send order for {req.get('symbol')}...")  # لاگ اقدام
            res = mt5.order_send(req)                   # ارسال سفارش
            if res and getattr(res, "retcode", 0) == mt5.TRADE_RETCODE_DONE:
                # اگر در همان تلاش اول Done شد
                print(f"Order sent successfully on first attempt! Deal: {getattr(res,'deal',0)}, Order: {getattr(res,'order',0)}")
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

            # اگر ارسال اول موفق نبود → کمی صبر و یک تلاش دیگر
            print(f"First order_send attempt not 'DONE'. retcode={getattr(res,'retcode',None)} - retrying...")  # اطلاع
            time.sleep(0.5)                              # تاخیر کوتاه
            res2 = mt5.order_send(req)                   # تلاش دوم
            if res2 and getattr(res2, "retcode", 0) == mt5.TRADE_RETCODE_DONE:
                print(f"Order sent successfully on second attempt! Deal: {getattr(res2,'deal',0)}, Order: {getattr(res2,'order',0)}")
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

            # اگر هنوز Done نشد، نتیجه آخرین تلاش را برگردان
            print(f"Order send failed or not done. retcode={getattr(res2,'retcode',None)}, err={mt5.last_error()}")
            # نکته: در کد شما لاجیک بررسی با magic/position هم بود؛ می‌توان اضافه کرد در صورت نیاز (وضعیت محیطی متفاوته)
            return {
                "retcode": int(getattr(res2, "retcode", 0) if res2 else -1),
                "comment": getattr(res2, "comment", "") if res2 else "order_send returned None",
                "request": req,
            }

        # اگر اکشن ناشناخته بود
        print(f"Invalid action for trade_manager: {action}")  # اطلاع
        return None

    # -----------------------------------------------------
    # 6) پوزیشن‌ها و تاریخچه (positions_* ، history_*)
    # -----------------------------------------------------
    def manage_positions_history(
        self,
        action: str,                                      # اکشن های مجاز: positions_total/positions_get/history_orders_*/history_deals_*
        symbol: Optional[str] = None,                     # فیلتر اختیار‌ی نماد
        ticket: Optional[int] = None,                     # فیلتر تیکت مشخص
        group: Optional[str] = None,                      # فیلتر گروه/نماد برای history_*_get (در orders_get به صورت پایتونی هم فیلتر می‌شود)
        date_from: Optional[datetime.datetime] = None,    # شروع بازه تاریخی
        date_to: Optional[datetime.datetime] = None,      # پایان بازه تاریخی
        position_id: Optional[int] = None                 # فیلتر position_id در history_get
    ) -> Optional[Union[int, List[Dict[str, Any]], Dict[str, Any]]]:
        """مدیریت پوزیشن‌های باز و تاریخچه سفارش‌ها/دیل‌ها."""

        action = (action or "").lower()                  # یکسان‌سازی اکشن

        # اتصال باید برقرار باشد
        if not self._ensure_initialized():
            return None

        # ---- بخش پوزیشن‌های باز ----
        if action == "positions_total":                   # تعداد پوزیشن‌های باز
            total = mt5.positions_total()                 # فراخوانی API
            print(f"Total open positions: {total}")       # چاپ
            return total                                  # خروجی

        if action == "positions_get":                     # لیست پوزیشن‌ها با فیلتر
            if ticket is not None:                        # اگر تیکت مشخص داده‌اند
                pos = mt5.positions_get(ticket=ticket)    # گرفتن همان پوزیشن
            elif symbol:                                  # در غیر اینصورت با نماد فیلتر کن
                pos = mt5.positions_get(symbol=symbol)
            else:
                pos = mt5.positions_get()                 # همه پوزیشن‌ها

            if pos is None:                               # اگر None شد
                print(f"Failed to get positions. err={mt5.last_error()}")  # خطا
                return None

            print(f"Found {len(pos)} open positions.")    # چاپ تعداد
            return [p._asdict() for p in pos]             # تبدیل به dict

        # ---- بخش تاریخچه سفارش‌ها ----
        if action in {"history_orders_total", "history_orders_get",
                      "history_deals_total", "history_deals_get"}:
            # برای total لازم است بازه زمانی داشته باشیم (غیر از حالت position/ticket)
            if action.endswith("_total") and (date_from is None or date_to is None):
                print(f"{action} requires 'date_from' and 'date_to'.")       # راهنما
                return None

            # نرمال‌سازی تاریخ‌ها به UTC
            if date_from:
                date_from = date_from if date_from.tzinfo else self.utc_tz.localize(date_from)
            if date_to:
                date_to = date_to if date_to.tzinfo else self.utc_tz.localize(date_to)

            # ----- ORDERS -----
            if action == "history_orders_total":
                total = mt5.history_orders_total(date_from, date_to)         # تعداد
                print(f"Total history orders from {date_from} to {date_to}: {total}")  # چاپ
                return total

            if action == "history_orders_get":
                # اولویت فیلتر بر اساس ticket یا position_id
                if ticket is not None:
                    orders = mt5.history_orders_get(ticket=ticket)           # فیلتر با تیکت
                elif position_id is not None:
                    orders = mt5.history_orders_get(position=position_id)    # فیلتر با پوزیشن
                else:
                    # گرفتن همه سفارش‌ها در بازه (سرور فیلتر group را پشتیبانی می‌کند)
                    orders = mt5.history_orders_get(date_from, date_to, group=group or "*")

                if orders is None:
                    print(f"Failed to get history orders. err={mt5.last_error()}")  # خطا
                    return None

                # اگر کاربر group را نماد گذاشته، و خواستیم در پایتون هم مضاعف فیلتر کنیم:
                orders_list = [o._asdict() for o in orders]                 # به dict
                print(f"Found {len(orders_list)} matching history orders.") # چاپ
                return orders_list

            # ----- DEALS -----
            if action == "history_deals_total":
                total = mt5.history_deals_total(date_from, date_to)         # تعداد
                print(f"Total history deals from {date_from} to {date_to}: {total}")  # چاپ
                return total

            if action == "history_deals_get":
                if ticket is not None:
                    deals = mt5.history_deals_get(ticket=ticket)            # با تیکت
                elif position_id is not None:
                    deals = mt5.history_deals_get(position=position_id)     # با position_id
                else:
                    deals = mt5.history_deals_get(date_from, date_to, group=group or "*")  # بازه + گروه

                if deals is None:
                    print(f"Failed to get history deals. err={mt5.last_error()}")  # خطا
                    return None
                deals_list = [d._asdict() for d in deals]                  # تبدیل به dict
                print(f"Found {len(deals_list)} history deals.")           # چاپ
                return deals_list

        # اگر اکشن ناشناخته بود
        print(f"Invalid action for manage_positions_history: {action}")     # اطلاع
        return None
