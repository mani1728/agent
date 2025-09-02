# C:\Users\Administrator\Desktop\agent_low\agent\meta_trader_manager.py
# این فایل شامل کلاسی برای مدیریت تمام تعاملات با پلتفرم MetaTrader 5 است.

# --- وارد کردن کتابخانه‌های مورد نیاز ---
import MetaTrader5 as mt5  # کتابخانه اصلی برای اتصال و کار با متاتریدر 5
import pandas as pd  # برای کار با داده‌ها در قالب DataFrame که خوانایی و تحلیل را ساده‌تر می‌کند
import time  # برای ایجاد تاخیر در برنامه (مثلاً هنگام انتظار برای به‌روزرسانی قیمت)
import pytz  # برای کار با مناطق زمانی (Timezones)، که برای درخواست داده‌های تاریخی ضروری است
import datetime  # برای کار با آبجکت‌های تاریخ و زمان


# تعریف کلاس اصلی برای مدیریت متاتریدر 5
class Mt5_Manager:
    # متد سازنده (Constructor) که هنگام ایجاد یک نمونه جدید از این کلاس، به صورت خودکار اجرا می‌شود
    def __init__(self):
        # --- مقادیر پیش‌فرض ---
        # این مقادیر در صورتی استفاده می‌شوند که کاربر هنگام فراخوانی متدها، مقادیر دلخواه خود را ارسال نکند.
        self.default_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"  # مسیر پیش‌فرض فایل اجرایی ترمینال متاتریدر 5
        self.default_login = 96033328  # شماره حساب پیش‌فرض
        self.default_password = "D_Hs3tGc"  # رمز عبور پیش‌فرض
        self.default_server = "MetaQuotes-Demo"  # نام سرور پیش‌فرض

        # --- متغیرهای وضعیت (State) ---
        # این متغیرها برای ذخیره اطلاعاتی که از متاتریدر دریافت می‌شود، استفاده می‌شوند تا نیازی به درخواست مجدد آنها نباشد.
        self.terminal_info = None  # برای ذخیره اطلاعات کلی ترمینال
        self.version = None  # برای ذخیره نسخه متاتریدر 5
        self.account_info_dict = None  # برای ذخیره اطلاعات حساب معاملاتی
        self.symbols_count = None  # برای ذخیره تعداد کل نمادهای موجود در سرور
        self.all_symbols = None  # برای ذخیره لیست تمام نمادها
        self.filtered_symbols = None  # برای ذخیره لیست نمادهای فیلتر شده
        self.group_symbols = None  # برای ذخیره لیست نمادهای یک گروه خاص
        self.symbol_info_dict = None  # برای ذخیره اطلاعات یک نماد خاص
        self.symbol_tick_dict = None  # برای ذخیره آخرین تیک قیمت یک نماد
        self.market_book_data = None  # برای ذخیره داده‌های عمق بازار (Market Depth)

    # متد یکپارچه برای مدیریت تمام عملیات مربوط به اتصال
    def manage_connection(self, action, path=None, login=None, password=None, server=None, timeout=60000,
                          portable=False):
        """
        متد برای مدیریت اتصال به MetaTrader 5 (اتصال، لاگین، اطلاعات ترمینال، نسخه، اطلاعات حساب و قطع اتصال)
        :param action: نوع عملیات ("initialize", "login", "terminal_info", "version", "account_info", "shutdown")
        """
        # بررسی اینکه آیا مقدار 'action' ارسال شده، یکی از مقادیر مجاز است یا خیر
        if action not in ["initialize", "login", "terminal_info", "version", "account_info", "shutdown"]:
            print(
                f"Invalid action: {action}. Must be one of 'initialize', 'login', 'terminal_info', 'version', 'account_info', 'shutdown'.")
            return None

        # اگر پارامترهای ورودی (مانند path, login و ...) ارسال نشده باشند، از مقادیر پیش‌فرض استفاده کن
        path = path or self.default_path
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server

        # --- بخش پردازش دستورات بر اساس پارامتر 'action' ---

        if action == "initialize":
            # بررسی اینکه آیا از قبل به ترمینال متصل هستیم یا نه
            if mt5.terminal_info() and mt5.terminal_info().connected:
                print("MT5 already connected, skipping initialize")
                # اگر متصل بودیم، اطلاعات ترمینال و نسخه را در متغیرهای کلاس ذخیره می‌کنیم
                self.terminal_info = mt5.terminal_info()
                self.version = mt5.version()
                return True  # بازگرداندن مقدار True به نشانه موفقیت

            # اگر متصل نبودیم، اقدام به برقراری اتصال می‌کنیم
            print(f"mt5_init called: Connecting to MetaTrader 5 with path={path}, login={login}, server={server}")
            # فراخوانی تابع اصلی اتصال در کتابخانه متاتریدر 5
            if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=timeout,
                                  portable=portable):
                # اگر اتصال ناموفق بود، کد خطا را چاپ کن
                print(f"initialize() failed, error code = {mt5.last_error()}")
                print("MT5 initialization failed")
                return False  # بازگرداندن مقدار False به نشانه شکست

            print("MT5 initialized successfully")
            # پس از اتصال موفق، اطلاعات ترمینال و نسخه را دریافت و ذخیره کن
            self.terminal_info = mt5.terminal_info()
            self.version = mt5.version()
            print(f"Terminal info: {self.terminal_info}")
            print(f"MT5 version: {self.version}")
            return True

        elif action == "login":
            # برای لاگین کردن، کافی است همان عملیات 'initialize' را با اطلاعات جدید فراخوانی کنیم
            success = self.manage_connection(action="initialize", path=path, login=login, password=password,
                                             server=server, timeout=timeout, portable=portable)
            # خروجی شامل وضعیت موفقیت، اطلاعات ترمینال و نسخه است
            return success, self.terminal_info, self.version

        elif action == "terminal_info":
            # دریافت اطلاعات ترمینال
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                print(f"Failed to get terminal info, error code = {mt5.last_error()}")
                return None
            self.terminal_info = terminal_info
            print(f"Terminal info: {self.terminal_info}")
            # اطلاعات را به صورت دیکشنری برمی‌گردانیم تا کار با آن راحت‌تر باشد
            return self.terminal_info._asdict() if self.terminal_info else None

        elif action == "version":
            # دریافت نسخه متاتریدر
            version = mt5.version()
            if version is None:
                print(f"Failed to get version, error code = {mt5.last_error()}")
                return None
            self.version = version
            print(f"MT5 version: {self.version}")
            return self.version

        elif action == "account_info":
            # ابتدا از برقراری اتصال اطمینان حاصل می‌کنیم
            success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                             timeout=timeout)
            if not success:
                print(
                    f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
                return None
            # دریافت اطلاعات حساب معاملاتی
            account_info = mt5.account_info()
            if account_info is None:
                print(f"Failed to get account info for login={login}, error code = {mt5.last_error()}")
                return None
            # ذخیره اطلاعات حساب به صورت دیکشنری
            self.account_info_dict = account_info._asdict()
            # چاپ اطلاعات به صورت‌های مختلف برای نمایش
            print(f"Account info: {account_info}")
            print("Show account_info()._asdict():")
            for prop in self.account_info_dict:
                print(f"  {prop}={self.account_info_dict[prop]}")
            # تبدیل به DataFrame برای نمایش جدولی و زیبا
            df = pd.DataFrame(list(self.account_info_dict.items()), columns=['property', 'value'])
            print("account_info() as dataframe:")
            print(df)
            # برگرداندن اطلاعات حساب به صورت دیکشنری
            return self.account_info_dict

        elif action == "shutdown":
            # قطع اتصال از ترمینال متاتریدر
            mt5.shutdown()
            print("MT5 connection shut down")
            # پس از قطع اتصال، متغیرهای وضعیت را پاک می‌کنیم
            self.terminal_info = None
            self.version = None
            self.account_info_dict = None
            return True

    # متد یکپارچه برای مدیریت تمام عملیات مربوط به نمادهای معاملاتی
    def manage_symbols(self, action, symbol=None, group="*", enable=True, login=None, password=None, server=None,
                       timeout=60000):
        """
        متد برای مدیریت عملیات نمادها (تعداد، لیست، اطلاعات نماد، اطلاعات تیک، فعال/غیرفعال کردن)
        """
        # بررسی اعتبار مقدار 'action'
        if action not in ["total", "get", "info", "tick", "select"]:
            print(f"Invalid action: {action}. Must be 'total', 'get', 'info', 'tick', or 'select'.")
            return None

        # استفاده از مقادیر پیش‌فرض در صورت نیاز
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اگر عملیات نیاز به نماد داشت و کاربر نمادی ارسال نکرده بود، از EURUSD استفاده کن
        symbol = symbol or "EURUSD" if action in ["info", "tick", "select"] else None

        # اطمینان از برقراری اتصال
        success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                         timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None

        if action == "total":
            # گرفتن تعداد کل نمادهای موجود در سرور
            symbols = mt5.symbols_total()
            self.symbols_count = symbols  # ذخیره تعداد نمادها
            if symbols > 0:
                print(f"Total symbols = {symbols}")
            else:
                print("Symbols not found")
            return self.symbols_count

        elif action == "get":
            # گرفتن لیست تمام نمادها
            self.all_symbols = mt5.symbols_get()
            if not self.all_symbols:
                print("No symbols found")
                return None
            print(f"Symbols: {len(self.all_symbols)}")
            # چاپ 5 نماد اول برای نمونه
            count = 0
            for s in self.all_symbols:
                count += 1
                print(f"{count}. {s.name}")
                if count == 5:
                    break
            print()
            # گرفتن نمادهایی که در نامشان 'RU' وجود دارد (مثال فیلتر با وایلدکارد)
            self.filtered_symbols = mt5.symbols_get("*RU*")
            print(f"len(*RU*): {len(self.filtered_symbols)}")
            for s in self.filtered_symbols:
                print(s.name)
            print()
            # گرفتن نمادهای یک گروه خاص (مثلاً group="Forex")
            self.group_symbols = mt5.symbols_get(group=group)
            print(f"len({group}): {len(self.group_symbols)}")
            for s in self.group_symbols:
                print(f"{s.name} : {s}")
            # برگرداندن دیکشنری حاوی نام تمام نمادهای دریافت شده
            return {
                "all_symbols": [s.name for s in self.all_symbols],
                "filtered_symbols": [s.name for s in self.filtered_symbols],
                "group_symbols": [s.name for s in self.group_symbols]
            }

        # اگر عملیات مربوط به یک نماد خاص بود
        elif action in ["info", "tick", "select"]:
            # بررسی اینکه آیا نماد درخواستی در سرور وجود دارد یا نه
            available_symbols = mt5.symbols_get()
            if not any(s.name == symbol for s in available_symbols):
                print(f"Symbol {symbol} not found in server")
                print(f"Retrying with fallback symbol EURUSD")
                # اگر وجود نداشت، از نماد پیش‌فرض EURUSD استفاده کن
                symbol = "EURUSD"
                if not any(s.name == symbol for s in available_symbols):
                    print(f"Fallback symbol EURUSD not found in server")
                    return None if action in ["info", "tick"] else False

            # یک منطق اختیاری برای مدیریت پنجره MarketWatch: اگر تعداد نمادهای فعال زیاد بود، آنها را پاک کن
            current_symbols = mt5.symbols_get()
            if current_symbols and len(current_symbols) > 100:
                print(f"Too many symbols in MarketWatch ({len(current_symbols)}), clearing MarketWatch")
                for s in current_symbols:
                    # نمادهایی غیر از نماد فعلی مورد نیاز را غیرفعال کن
                    if s.name != symbol:
                        mt5.symbol_select(s.name, False)

            # فعال کردن نماد مورد نظر در MarketWatch تا بتوان اطلاعات قیمتی آن را دریافت کرد
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                # اگر فعال‌سازی ناموفق بود، یک بار دیگر با EURUSD تلاش کن
                print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
                print(f"Retrying with fallback symbol EURUSD")
                symbol = "EURUSD"
                selected = mt5.symbol_select(symbol, True)
                if not selected:
                    print(f"Failed to select fallback symbol EURUSD, error code = {mt5.last_error()}")
                    return None if action in ["info", "tick"] else False

            if action == "info":
                # گرفتن اطلاعات کامل و استاتیک نماد
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    print(f"Failed to get symbol info for {symbol}, error code = {mt5.last_error()}")
                    return None
                # بررسی اینکه آیا قیمت وجود دارد (ممکن است بازار بسته باشد)
                if symbol_info.bid == 0.0 and symbol_info.ask == 0.0:
                    print(f"No price data for {symbol}, market may be closed or data not updated")
                    time.sleep(1)  # 1 ثانیه صبر می‌کنیم و دوباره تلاش می‌کنیم
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info is None or (symbol_info.bid == 0.0 and symbol_info.ask == 0.0):
                        print(f"Still no price data for {symbol}, skipping")
                # ذخیره و چاپ اطلاعات نماد
                self.symbol_info_dict = symbol_info._asdict()
                print(f"Symbol info for {symbol}: {symbol_info}")
                print(f"{symbol}: spread = {symbol_info.spread}, digits = {symbol_info.digits}")
                print(f"Show symbol_info(\"{symbol}\")._asdict():")
                for prop in self.symbol_info_dict:
                    print(f"  {prop}={self.symbol_info_dict[prop]}")
                return self.symbol_info_dict

            elif action == "tick":
                # گرفتن آخرین تیک قیمت (bid/ask)
                tick_info = mt5.symbol_info_tick(symbol)
                if tick_info is None:
                    print(f"Failed to get tick info for {symbol}, error code = {mt5.last_error()}")
                    return None
                # بررسی وضعیت بازار
                if tick_info.bid == 0.0 and tick_info.ask == 0.0:
                    print(f"No tick data for {symbol}, market may be closed or data not updated")
                    time.sleep(1)
                    tick_info = mt5.symbol_info_tick(symbol)
                    if tick_info is None or (tick_info.bid == 0.0 and tick_info.ask == 0.0):
                        print(f"Still no tick data for {symbol}, skipping")
                # ذخیره و چاپ اطلاعات تیک
                self.symbol_tick_dict = tick_info._asdict()
                print(f"Tick info for {symbol}: {tick_info}")
                print(f"Show symbol_info_tick(\"{symbol}\")._asdict():")
                for prop in self.symbol_tick_dict:
                    print(f"  {prop}={self.symbol_tick_dict[prop]}")
                return self.symbol_tick_dict

            elif action == "select":
                # فعال (enable=True) یا غیرفعال (enable=False) کردن یک نماد در MarketWatch
                selected = mt5.symbol_select(symbol, enable)
                if not selected:
                    print(f"Failed to select {symbol} with enable={enable}, error code = {mt5.last_error()}")
                    return False
                # اگر عملیات فعال‌سازی بود، اطلاعات نماد را هم دریافت و برگردان
                if enable:
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info is None:
                        return False
                    # بررسی وضعیت بازار
                    if symbol_info.bid == 0.0 and symbol_info.ask == 0.0:
                        print(f"No price data for {symbol}, market may be closed or data not updated")
                        time.sleep(1)
                        symbol_info = mt5.symbol_info(symbol)
                        if symbol_info is None or (symbol_info.bid == 0.0 and symbol_info.ask == 0.0):
                            print(f"Still no price data for {symbol}, skipping")
                    # ذخیره و چاپ اطلاعات
                    self.symbol_info_dict = symbol_info._asdict()
                    print(f"Symbol info for {symbol}: {symbol_info}")
                    print(
                        f"{symbol}: currency_base = {symbol_info.currency_base}, currency_profit = {symbol_info.currency_profit}, currency_margin = {symbol_info.currency_margin}")
                    print()
                    print(f"Show symbol_info(\"{symbol}\")._asdict():")
                    for prop in self.symbol_info_dict:
                        print(f"  {prop}={self.symbol_info_dict[prop]}")
                    print()
                    # تبدیل اطلاعات به DataFrame برای نمایش
                    df = pd.DataFrame(list(self.symbol_info_dict.items()), columns=['property', 'value'])
                    print("symbol_info_dict() as dataframe:")
                    print(df)
                    return True, self.symbol_info_dict
                return True

    # متد یکپارچه برای مدیریت عمق بازار (Depth of Market)
    def manage_market_book(self, action, symbol="EURUSD", login=None, password=None, server=None, timeout=60000):
        """
        متد برای مدیریت عملیات عمق بازار (اشتراک، دریافت داده، لغو اشتراک)
        """
        # بررسی اعتبار 'action'
        if action not in ["add", "get", "release"]:
            print(f"Invalid action: {action}. Must be 'add', 'get', or 'release'.")
            return None

        # استفاده از مقادیر پیش‌فرض
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server

        # اطمینان از اتصال
        success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                         timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None if action == "get" else False

        # اعتبارسنجی و انتخاب نماد (این الگو در بسیاری از متدها تکرار می‌شود)
        available_symbols = mt5.symbols_get()
        if not any(s.name == symbol for s in available_symbols):
            print(f"Symbol {symbol} not found in server")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            if not any(s.name == symbol for s in available_symbols):
                print(f"Fallback symbol EURUSD not found in server")
                return None if action == "get" else False

        # ... (تکرار منطق پاکسازی MarketWatch و انتخاب نماد)
        current_symbols = mt5.symbols_get()
        if current_symbols and len(current_symbols) > 100:
            print(f"Too many symbols in MarketWatch ({len(current_symbols)}), clearing MarketWatch")
            for s in current_symbols:
                if s.name != symbol:
                    mt5.symbol_select(s.name, False)

        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                print(f"Failed to select fallback symbol EURUSD, error code = {mt5.last_error()}")
                return None if action == "get" else False

        # بررسی اینکه آیا سرور بروکر برای این نماد، داده‌های عمق بازار را ارائه می‌دهد یا نه
        if action in ["add", "get"]:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return None if action == "get" else False
            if symbol_info.ticks_bookdepth == 0:
                print(f"Market depth not supported for {symbol} on this server")
                return None if action == "get" else False

        # انجام عملیات بر اساس 'action'
        if action == "add":
            # اشتراک (subscribe) برای دریافت رویدادهای مربوط به تغییرات عمق بازار
            success = mt5.market_book_add(symbol)
            if not success:
                print(f"Failed to subscribe to market book for {symbol}, error code = {mt5.last_error()}")
                return False
            print(f"Successfully subscribed to market book for {symbol}")
            return True

        elif action == "get":
            # ابتدا اشتراک را انجام می‌دهیم تا مطمئن شویم داده‌ها به‌روز هستند
            if not mt5.market_book_add(symbol):
                return None
            # دریافت یک تصویر لحظه‌ای (snapshot) از وضعیت فعلی عمق بازار
            book_data = mt5.market_book_get(symbol)
            if book_data is None:
                print(f"Failed to get market book data for {symbol}, error code = {mt5.last_error()}")
                return None
            # ذخیره و چاپ داده‌ها
            self.market_book_data = [item._asdict() for item in book_data]
            print(f"Market book data for {symbol}: {book_data}")
            if book_data:
                print(f"Show market_book_get(\"{symbol}\")._asdict():")
                for item in self.market_book_data:
                    print(f"  Order: {item}")
            else:
                print(f"No market book data available for {symbol}")
            return self.market_book_data

        elif action == "release":
            # لغو اشتراک (unsubscribe) از رویدادهای عمق بازار برای یک نماد
            success = mt5.market_book_release(symbol)
            if not success:
                print(f"Failed to release market book for {symbol}, error code = {mt5.last_error()}")
                return False
            print(f"Successfully released market book for {symbol}")
            return True
        else:
            pass

    # متد یکپارچه برای دریافت داده‌های تاریخی (نرخ‌ها و تیک‌ها)
    def fetch_data(self, symbol="EURUSD", data_type="rates", method="from", timeframe=mt5.TIMEFRAME_H4, date_from=None,
                   date_to=None, start_pos=0, count=None, flags=mt5.COPY_TICKS_ALL, login=None, password=None,
                   server=None, timeout=60000):
        """
        متد یکپارچه برای دریافت نرخ‌ها یا تیک‌ها از MetaTrader 5
        """
        # تنظیمات نمایش DataFrame
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.width', 1500)

        # استفاده از مقادیر پیش‌فرض
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اگر تعداد مشخص نشده بود، برای تیک‌ها ۱۰۰،۰۰۰ و برای نرخ‌ها ۱۰ در نظر بگیر
        count = count or (100000 if data_type == "ticks" else 10)

        # تنظیم تاریخ‌های پیش‌فرض در صورت عدم ارسال توسط کاربر
        timezone = pytz.timezone("Etc/UTC")
        if date_from is None:
            date_from = datetime.datetime(2020, 1, 10, tzinfo=timezone)
        if method == "range" and date_to is None:
            date_to = datetime.datetime(2020, 1, 11, hour=13 if data_type == "rates" else 0, tzinfo=timezone)

        # اطمینان از اتصال
        success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                         timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None

        # اعتبارسنجی و انتخاب نماد
        available_symbols = mt5.symbols_get()
        if not any(s.name == symbol for s in available_symbols):
            print(f"Symbol {symbol} not found in server")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            if not any(s.name == symbol for s in available_symbols):
                print(f"Fallback symbol EURUSD not found in server")
                return None

        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
            return None

        # دریافت داده‌ها بر اساس نوع داده و روش درخواست شده
        data = None
        if data_type == "rates":  # اگر درخواست برای نرخ‌ها (کندل‌ها) بود
            if method == "from":  # از یک تاریخ مشخص به تعداد count
                data = mt5.copy_rates_from(symbol, timeframe, date_from, count)
            elif method == "from_pos":  # از یک موقعیت (ایندکس) مشخص به تعداد count
                data = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
            elif method == "range":  # در یک بازه زمانی مشخص
                data = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
        elif data_type == "ticks":  # اگر درخواست برای تیک‌ها بود
            if method == "from":  # از یک تاریخ مشخص به تعداد count
                data = mt5.copy_ticks_from(symbol, date_from, count, flags)
            elif method == "range":  # در یک بازه زمانی مشخص
                data = mt5.copy_ticks_range(symbol, date_from, date_to, flags)
        else:
            print(f"Invalid data_type: {data_type}. Must be 'rates' or 'ticks'.")
            return None

        # بررسی اعتبار روش دریافت داده
        if method not in ["from", "from_pos", "range"]:
            print(f"Invalid method: {method}. Must be 'from', 'from_pos', or 'range'.")
            return None

        if data is None:
            print(f"Failed to get {data_type} for {symbol}, error code = {mt5.last_error()}")
            return None

        # چاپ تعداد داده‌های دریافت شده برای اطلاع
        if data_type == "ticks":
            print(f"Ticks received: {len(data)}")

        # چاپ ۱۰ ردیف اول از داده‌های خام برای نمونه
        print(f"Display obtained {data_type} 'as is'")
        counter = 0
        for item in data:
            counter += 1
            if counter <= 10:
                print(item)

        # ایجاد DataFrame از داده‌های دریافت شده
        data_frame = pd.DataFrame(data)
        # تبدیل ستون زمان از فرمت timestamp (ثانیه) به فرمت datetime قابل خواندن
        if data_frame.shape[0] > 0:
            data_frame['time'] = pd.to_datetime(data_frame['time'], unit='s')

        # نمایش ۱۰ ردیف اول DataFrame
        print(f"\nDisplay dataframe with {data_type}")
        print(data_frame.head(10))

        # تبدیل داده‌های خام به فرمت لیست دیکشنری‌ها (مناسب برای ارسال در API)
        if data_type == "rates":
            raw_data = [
                {
                    'time': item['time'], 'open': item['open'], 'high': item['high'], 'low': item['low'],
                    'close': item['close'], 'tick_volume': item['tick_volume'], 'spread': item['spread'],
                    'real_volume': item['real_volume']
                } for item in data
            ]
        else:  # ticks
            raw_data = [
                {
                    'time': item['time'], 'bid': item['bid'], 'ask': item['ask'],
                    'last': item['last'], 'flags': item['flags']
                } for item in data
            ]

        # برگرداندن خروجی نهایی شامل داده‌های خام و DataFrame
        return {
            "raw_data": raw_data,
            "data_frame": data_frame
        }

    # متد یکپارچه برای مدیریت تمام عملیات مربوط به معاملات و سفارشات
    def trade_manager(self, action="total", symbol="EURUSD", group=None, ticket=None, request=None, order_type=None,
                      volume=0.1, price=None, price_close=None, login=None, password=None, server=None, timeout=60000):
        """
        متد یکپارچه، مقاوم و قابل اعتماد برای مدیریت سفارش‌ها و ارسال درخواست‌های معاملاتی در MetaTrader 5
        """
        # --- بخش ۱: آماده‌سازی اولیه ---

        # تنظیمات نمایش DataFrame در کنسول برای خوانایی بهتر
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.width', 1500)

        # اگر کاربر لاگین، پسورد یا سرور را مشخص نکرده باشد، از مقادیر پیش‌فرض استفاده کن
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server

        # اطمینان از برقراری ارتباط با سرور متاتریدر 5
        success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                         timeout=timeout)
        # اگر اتصال ناموفق بود، از تابع خارج شو
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None

        # --- بخش ۲: آماده‌سازی نماد (برای اکشن‌های نیازمند نماد) ---

        # برای عملیات‌هایی که نیاز به کار با یک نماد خاص دارند، آن را بررسی و آماده کن
        if action in ["get", "calc_margin", "calc_profit", "check", "send"]:
            # نماد را از داخل ساختار request بخوان؛ در غیر این صورت از پارامتر symbol استفاده کن
            symbol = request.get("symbol", symbol) if action in ["send", "check"] and request else symbol

            # بررسی وجود نماد در سرور و استفاده از EURUSD به عنوان جایگزین
            available_symbols = mt5.symbols_get()
            if not any(s.name == symbol for s in available_symbols):
                print(f"Symbol {symbol} not found in server. Retrying with EURUSD.")
                symbol = "EURUSD"
                if action in ["send", "check"] and request:
                    request["symbol"] = symbol  # نماد داخل درخواست را هم به‌روز کن
                if not any(s.name == symbol for s in available_symbols):
                    print(f"Fallback symbol EURUSD not found in server.")
                    return None

            # نماد مورد نظر را در MarketWatch فعال کن تا بتوان اطلاعات قیمت آن را دریافت کرد
            if not mt5.symbol_select(symbol, True):
                print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
                return None

            # --- بخش ۳: آماده‌سازی درخواست معامله (برای اکشن‌های send و check) ---

            # برای عملیات 'send' و 'check'، درخواست را بر اساس مشخصات نماد تنظیم می‌کنیم
            if action in ["send", "check"] and request:
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    print(f"Failed to get symbol info for {symbol}, error code = {mt5.last_error()}")
                    return None

                # بررسی و تنظیم نوع پر کردن سفارش (Filling Mode) با مقدار پیش‌فرض صحیح
                filling_mode = symbol_info.filling_mode
                requested_filling = request.get("type_filling", mt5.ORDER_FILLING_IOC)
                if not (filling_mode & requested_filling):
                    # اگر حالت درخواستی پشتیبانی نمی‌شد، آن را به حالت مورد پشتیبانی بروکر تغییر بده
                    if filling_mode & mt5.ORDER_FILLING_IOC:
                        request["type_filling"] = mt5.ORDER_FILLING_IOC
                        print(f"Filling mode changed to IOC for {symbol}")
                    elif filling_mode & mt5.ORDER_FILLING_FOK:
                        request["type_filling"] = mt5.ORDER_FILLING_FOK
                        print(f"Filling mode changed to FOK for {symbol}")
                    else:
                        print(f"No supported filling mode for {symbol}.")
                        return None

                # بررسی نوع اجرای معامله (Execution Mode)
                try:
                    trade_exemode = symbol_info.trade_exemode
                except AttributeError:
                    trade_exemode = mt5.SYMBOL_TRADE_EXECUTION_MARKET  # مقدار پیش‌فرض

                # اگر نوع اجرا 'Market Execution' بود، قیمت را به صورت خودکار از سرور بگیر
                if trade_exemode == mt5.SYMBOL_TRADE_EXECUTION_MARKET and request.get(
                        "action") == mt5.TRADE_ACTION_DEAL:
                    if "price" in request: del request["price"]  # حذف قیمت ارسال شده توسط کاربر
                    symbol_tick = mt5.symbol_info_tick(symbol)
                    if symbol_tick is None:
                        print(f"Failed to get tick data for {symbol}, error code = {mt5.last_error()}")
                        return None
                    # تنظیم قیمت خرید (ask) یا فروش (bid) بر اساس نوع سفارش
                    request["price"] = symbol_tick.ask if request.get("type") == mt5.ORDER_TYPE_BUY else symbol_tick.bid
                    print(f"Price for Market Execution set to {request['price']}")

        # --- بخش ۴: اجرای اکشن‌ها ---

        # اگر دستور 'send' بود، از منطق جدید و امن استفاده کن
        if action == "send":
            # بررسی وجود داشتن درخواست
            if request is None:
                print("Request is required for order_send")
                return None

            # --- مرحله ۱: تلاش اول برای ارسال سفارش ---
            print(f"Attempting to send order for {symbol}...")
            result = mt5.order_send(request)

            # --- مرحله ۲: بررسی نتیجه تلاش اول ---
            # اگر ارسال موفق بود (happy path)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Order sent successfully on first attempt! Deal: {result.deal}, Order: {result.order}")
                return result._asdict()  # نتیجه را به صورت دیکشنری برگردان

            # --- مرحله ۳: اگر تلاش اول شکست خورد، وارد منطق "بررسی و تایید" شو ---
            print(
                f"Initial send failed. Retcode: {result.retcode if result else 'None'}. Starting verification process...")

            # شماره مجیک را برای پیگیری سفارش از درخواست استخراج کن
            magic_number = request.get('magic')

            # اگر شماره مجیک وجود نداشت، پیگیری غیرممکن است، پس از ارسال مجدد صرف نظر می‌کنیم
            if not magic_number:
                print("No magic number in request. Cannot verify order status. Aborting.")
                return None

            # به سرور ۱ ثانیه فرصت می‌دهیم تا وضعیت را نهایی کند
            time.sleep(1)

            # --- مرحله ۳.۱: جستجو در پوزیشن‌های باز ---
            # بررسی می‌کنیم آیا پوزیشنی با این شماره مجیک باز شده است یا نه
            positions = mt5.positions_get(symbol=symbol, magic=magic_number)
            if positions and len(positions) > 0:
                print(
                    f"VERIFICATION SUCCESS: Position {positions[0].ticket} found with magic number {magic_number}. No retry needed.")
                # چون پوزیشن باز شده، یعنی سفارش اولیه در واقع موفق بوده است
                # می‌توانیم اطلاعات پوزیشن را برگردانیم یا یک پیام موفقیت سفارشی
                return {"status": "Verified", "message": "Position already exists",
                        "position_info": positions[0]._asdict()}

            # --- مرحله ۳.۲: جستجو در سفارشات در حال انتظار (برای Pending Orders) ---
            orders = mt5.orders_get(symbol=symbol, magic=magic_number)
            if orders and len(orders) > 0:
                print(
                    f"VERIFICATION SUCCESS: Order {orders[0].ticket} found with magic number {magic_number}. No retry needed.")
                return {"status": "Verified", "message": "Order already exists", "order_info": orders[0]._asdict()}

            # --- مرحله ۴: اگر سفارشی پیدا نشد، حالا ارسال مجدد امن است ---
            print("VERIFICATION FAILED: No existing order or position found. Retrying the send command...")

            # تلاش دوم برای ارسال سفارش
            new_result = mt5.order_send(request)

            # بررسی نتیجه تلاش دوم
            if new_result and new_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Order sent successfully on second attempt! Deal: {new_result.deal}, Order: {new_result.order}")
                return new_result._asdict()  # نتیجه را به صورت دیکشنری برگردان
            else:
                print(f"Second attempt also failed. Retcode: {new_result.retcode if new_result else 'None'}. Aborting.")
                # اگر تلاش دوم هم ناموفق بود، عملیات شکست خورده است
                if new_result:
                    return new_result._asdict()  # برگرداندن نتیجه شکست خورده
                return None

        # سایر اکشن‌ها مانند قبل باقی می‌مانند
        elif action == "total":
            orders = mt5.orders_total()
            return orders

        elif action == "get":
            if ticket:
                orders = mt5.orders_get(ticket=ticket)
            elif group:
                orders = mt5.orders_get(group=group)
            elif symbol:
                orders = mt5.orders_get(symbol=symbol)
            else:
                orders = mt5.orders_get()
            if orders is None or len(orders) == 0: return {"raw_orders": [], "orders_frame": pd.DataFrame()}
            df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())
            return {"raw_orders": [order._asdict() for order in orders], "orders_frame": df}

        elif action == "calc_margin":
            if order_type is None or price is None: return None
            return mt5.order_calc_margin(order_type, symbol, volume, price)

        elif action == "calc_profit":
            if order_type is None or price is None or price_close is None: return None
            return mt5.order_calc_profit(order_type, symbol, volume, price, price_close)

        elif action == "check":
            if request is None: return None
            result = mt5.order_check(request)
            return result._asdict() if result else None

        # اگر اکشن ارسال شده معتبر نبود
        else:
            print(
                f"Invalid action: {action}. Must be one of 'total', 'get', 'calc_margin', 'calc_profit', 'check', or 'send'.")
            return None

    # این متود را به کلاس Mt5_Manager خود اضافه کنید

    def manage_positions_history(self, action, symbol=None, group=None, ticket=None, position_id=None, date_from=None,
                                 date_to=None, login=None, password=None, server=None, timeout=60000):
        """
        متد یکپارچه برای مدیریت پوزیشن‌های باز و تاریخچه معاملات (سفارشات و دیل‌ها).
        :param action: نوع عملیات:
                       - برای پوزیشن‌های باز: 'positions_total', 'positions_get'
                       - برای تاریخچه سفارشات: 'history_orders_total', 'history_orders_get'
                       - برای تاریخچه دیل‌ها: 'history_deals_total', 'history_deals_get'
        :param symbol: نام نماد برای فیلتر کردن پوزیشن‌های باز (فقط برای 'positions_get').
        :param group: فیلتر گروهی برای نمادها (برای 'positions_get', 'history_orders_get', 'history_deals_get').
        :param ticket: تیکت یک پوزیشن یا سفارش خاص.
        :param position_id: تیکت یک پوزیشن برای فیلتر کردن سفارشات یا دیل‌های مرتبط با آن.
        :param date_from: تاریخ شروع برای دریافت تاریخچه (datetime object).
        :param date_to: تاریخ پایان برای دریافت تاریخچه (datetime object).
        :return: نتیجه عملیات (عدد، لیست دیکشنری‌ها، یا None).
        """
        # --- بخش ۱: آماده‌سازی و اعتبارسنجی ---

        # لیست تمام اکشن‌های مجاز برای این متود
        allowed_actions = [
            'positions_total', 'positions_get',
            'history_orders_total', 'history_orders_get',
            'history_deals_total', 'history_deals_get'
        ]
        # بررسی اینکه آیا 'action' ارسال شده معتبر است یا خیر
        if action not in allowed_actions:
            print(f"Invalid action: {action}. Please use one of {allowed_actions}")
            return None

        # استفاده از مقادیر پیش‌فرض برای اتصال
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server

        # اطمینان از برقراری ارتباط با سرور متاتریدر 5
        success = self.manage_connection(action="initialize", login=login, password=password, server=server,
                                         timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login}, error code = {mt5.last_error()}")
            return None

        # تنظیم تاریخ‌های پیش‌فرض برای درخواست‌های تاریخچه در صورت عدم ارسال
        if action.startswith('history'):
            # --- این بخش را اصلاح کنید ---
            timezone = pytz.timezone("Etc/UTC")  # منطقه زمانی را تعریف کن
            if date_from is None:
                # اگر تاریخ شروع مشخص نشده بود، ۳۰ روز قبل را در نظر بگیر (آگاه از منطقه زمانی)
                date_from = datetime.datetime.now(timezone) - datetime.timedelta(days=30)
            if date_to is None:
                # اگر تاریخ پایان مشخص نشده بود، زمان حال را در نظر بگیر (آگاه از منطقه زمانی)
                date_to = datetime.datetime.now(timezone)
            # -------------------------

        # --- بخش ۲: اجرای اکشن‌ها ---

        # --- پوزیشن‌های باز ---
        if action == 'positions_total':
            # دریافت تعداد کل پوزیشن‌های باز
            total = mt5.positions_total()
            print(f"Total open positions: {total}")
            return total

        elif action == 'positions_get':
            # دریافت لیست پوزیشن‌های باز با قابلیت فیلتر
            positions = None
            if ticket:
                # فیلتر بر اساس تیکت پوزیشن
                positions = mt5.positions_get(ticket=ticket)
            elif symbol:
                # فیلتر بر اساس نام نماد
                positions = mt5.positions_get(symbol=symbol)
            elif group:
                # فیلتر بر اساس گروه نمادها
                positions = mt5.positions_get(group=group)
            else:
                # دریافت تمام پوزیشن‌های باز
                positions = mt5.positions_get()

            # بررسی نتیجه و برگرداندن آن
            if positions is None:
                print(f"Failed to get positions, error code = {mt5.last_error()}")
                return None
            print(f"Found {len(positions)} open positions.")
            # تبدیل namedtuple به لیست دیکشنری‌ها برای کاربری آسان‌تر
            return [p._asdict() for p in positions]

        # --- تاریخچه سفارشات ---
        elif action == 'history_orders_total':
            # دریافت تعداد کل سفارشات در بازه زمانی مشخص
            total = mt5.history_orders_total(date_from, date_to)
            print(f"Total history orders from {date_from} to {date_to}: {total}")
            return total

            # این بخش را در متد manage_positions_history جایگزین کنید
        elif action == 'history_orders_get':
            # دریافت لیست سفارشات در تاریخچه با قابلیت فیلتر
            orders = None
            if ticket:
                # فیلتر بر اساس تیکت سفارش همچنان باید سمت سرور انجام شود چون بهینه است
                orders = mt5.history_orders_get(ticket=ticket)
            elif position_id:
                # فیلتر بر اساس تیکت پوزیشن نیز باید سمت سرور باشد
                orders = mt5.history_orders_get(position=position_id)
            else:
                # --- منطق جدید برای دور زدن مشکل پارامتر group ---

                # مرحله ۱: دریافت تمام سفارشات تاریخچه در بازه زمانی (بدون فیلتر گروه)
                print("Fetching ALL history orders from server...")
                all_orders = mt5.history_orders_get(date_from, date_to)

                # بررسی اینکه آیا سفارشی دریافت شده است یا نه
                if all_orders is None:
                    print(f"Failed to get any history orders, error code = {mt5.last_error()}")
                    return None

                # مرحله ۲: فیلتر کردن نتایج در پایتون (اگر پارامتر group ارسال شده بود)
                if group and group != "*":
                    print(f"Filtering {len(all_orders)} orders by group '{group}' in Python...")
                    # یک لیست خالی برای نتایج فیلتر شده ایجاد می‌کنیم
                    filtered_orders = []
                    # الگوی ساده wildcard را به یک جستجوی ساده "contains" تبدیل می‌کنیم
                    search_term = group.replace("*", "")
                    for order in all_orders:
                        # بررسی می‌کنیم که آیا نام نماد سفارش، شامل عبارت مورد نظر ما هست یا نه
                        if search_term in order.symbol:
                            filtered_orders.append(order)
                    orders = filtered_orders  # لیست نهایی را برابر با لیست فیلتر شده قرار می‌دهیم
                else:
                    # اگر پارامتر group ارسال نشده بود، همان لیست کامل را استفاده می‌کنیم
                    orders = all_orders

            # بررسی نتیجه نهایی و برگرداندن آن
            if orders is None:
                # این حالت معمولاً رخ نمی‌دهد مگر اینکه در فیلتر با تیکت/پوزیشن خطایی باشد
                print(f"Failed to get history orders, error code = {mt5.last_error()}")
                return None

            print(f"Found {len(orders)} matching history orders.")
            # تبدیل namedtuple به لیست دیکشنری‌ها برای کاربری آسان‌تر
            return [o._asdict() for o in orders]

        # --- تاریخچه دیل‌ها (معاملات) ---
        elif action == 'history_deals_total':
            # دریافت تعداد کل دیل‌ها در بازه زمانی مشخص
            total = mt5.history_deals_total(date_from, date_to)
            print(f"Total history deals from {date_from} to {date_to}: {total}")
            return total

        elif action == 'history_deals_get':
            # دریافت لیست دیل‌ها در تاریخچه با قابلیت فیلتر
            deals = None
            if ticket:
                # فیلتر بر اساس تیکت سفارش مرتبط
                deals = mt5.history_deals_get(ticket=ticket)
            elif position_id:
                # فیلتر بر اساس تیکت پوزیشن مرتبط
                deals = mt5.history_deals_get(position=position_id)
            else:
                # دریافت تمام دیل‌ها در بازه زمانی و گروه مشخص
                deals = mt5.history_deals_get(date_from, date_to, group=group or "*")

            # بررسی نتیجه و برگرداندن آن
            if deals is None:
                print(f"Failed to get history deals, error code = {mt5.last_error()}")
                return None
            print(f"Found {len(deals)} history deals.")
            return [d._asdict() for d in deals]

        # اگر به هر دلیلی هیچ اکشنی اجرا نشد، None برگردان
        return None
