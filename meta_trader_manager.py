# کلاس برای کار با MetaTrader 5
import MetaTrader5 as mt5
import pandas as pd
import time

class Mt5_Manager:
    def __init__(self):
        # مقادیر پیش‌فرض برای استفاده در صورت عدم ارسال پارامتر
        self.default_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        self.default_login = 96033328
        self.default_password = "D_Hs3tGc"
        self.default_server = "MetaQuotes-Demo"
        self.terminal_info = None  # برای ذخیره اطلاعات ترمینال
        self.version = None  # برای ذخیره نسخه MT5
        self.account_info_dict = None  # برای ذخیره اطلاعات حساب
        self.symbols_count = None  # برای ذخیره تعداد نمادها
        self.all_symbols = None  # برای ذخیره همه نمادها
        self.filtered_symbols = None  # برای ذخیره نمادهای فیلترشده
        self.group_symbols = None  # برای ذخیره نمادهای گروه خاص
        self.symbol_info_dict = None  # برای ذخیره اطلاعات نماد
        self.symbol_tick_dict = None  # برای ذخیره اطلاعات تیک

    def initialize(self, path=None, login=None, password=None, server=None, timeout=60000, portable=False):
        # چک کردن اینکه آیا ترمینال قبلاً متصل است
        if mt5.terminal_info() and mt5.terminal_info().connected:
            print("MT5 already connected, skipping initialize")
            self.terminal_info = mt5.terminal_info()
            self.version = mt5.version()
            return True
        # متد برای اتصال به MetaTrader 5 با پارامترهای داده‌شده
        path = path or self.default_path
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        print(f"mt5_init called: Connecting to MetaTrader 5 with path={path}, login={login}, server={server}")
        if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=timeout, portable=portable):
            print(f"initialize() failed, error code = {mt5.last_error()}")
            print("MT5 initialization failed")
            return False
        print("MT5 initialized successfully")
        # ذخیره اطلاعات ترمینال و نسخه
        self.terminal_info = mt5.terminal_info()
        self.version = mt5.version()
        print(f"Terminal info: {self.terminal_info}")
        print(f"MT5 version: {self.version}")
        return True

    def login(self, login=None, password=None, server=None, timeout=60000):
        # متد برای لاگین به MT5 با استفاده از initialize
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # فراخوانی initialize برای اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        # برگرداندن نتیجه و اطلاعات ترمینال/نسخه
        return success, self.terminal_info, self.version

    def account_info(self, login=None, password=None, server=None, timeout=60000):
        # متد برای گرفتن اطلاعات حساب
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success, terminal_info, version = self.login(login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None
        # گرفتن اطلاعات حساب
        account_info = mt5.account_info()
        if account_info is None:
            print(f"Failed to get account info for login={login}, error code = {mt5.last_error()}")
            return None
        # ذخیره اطلاعات حساب به صورت دیکشنری
        self.account_info_dict = account_info._asdict()
        # چاپ اطلاعات
        print(f"Account info: {account_info}")
        print("Show account_info()._asdict():")
        for prop in self.account_info_dict:
            print(f"  {prop}={self.account_info_dict[prop]}")
        # تبدیل به DataFrame
        df = pd.DataFrame(list(self.account_info_dict.items()), columns=['property', 'value'])
        print("account_info() as dataframe:")
        print(df)
        # برگرداندن اطلاعات حساب
        return self.account_info_dict

    def symbols_total(self, login=None, password=None, server=None, timeout=60000):
        # متد برای گرفتن تعداد نمادهای مالی
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None
        # گرفتن تعداد نمادها
        symbols = mt5.symbols_total()
        self.symbols_count = symbols  # ذخیره تعداد نمادها
        if symbols > 0:
            print(f"Total symbols = {symbols}")
        else:
            print("Symbols not found")
        return self.symbols_count

    def symbols_get(self, group="*", login=None, password=None, server=None, timeout=60000):
        # متد برای گرفتن لیست نمادهای مالی
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None
        # گرفتن همه نمادها
        self.all_symbols = mt5.symbols_get()
        if not self.all_symbols:
            print("No symbols found")
            return None
        print(f"Symbols: {len(self.all_symbols)}")
        # چاپ 5 نماد اول
        count = 0
        for s in self.all_symbols:
            count += 1
            print(f"{count}. {s.name}")
            if count == 5:
                break
        print()
        # گرفتن نمادهای حاوی RU
        self.filtered_symbols = mt5.symbols_get("*RU*")
        print(f"len(*RU*): {len(self.filtered_symbols)}")
        for s in self.filtered_symbols:
            print(s.name)
        print()
        # گرفتن نمادهای گروه خاص
        self.group_symbols = mt5.symbols_get(group=group)
        print(f"len({group}): {len(self.group_symbols)}")
        for s in self.group_symbols:
            print(f"{s.name} : {s}")
        # برگرداندن دیکشنری حاوی همه نتایج
        return {
            "all_symbols": [s.name for s in self.all_symbols],
            "filtered_symbols": [s.name for s in self.filtered_symbols],
            "group_symbols": [s.name for s in self.group_symbols]
        }

    def symbol_info(self, symbol="EURUSD", login=None, password=None, server=None, timeout=60000):
        # متد برای گرفتن اطلاعات یک نماد خاص
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None
        # چک کردن وجود نماد در سرور
        available_symbols = mt5.symbols_get()
        if not any(s.name == symbol for s in available_symbols):
            print(f"Symbol {symbol} not found in server")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            if not any(s.name == symbol for s in available_symbols):
                print(f"Fallback symbol EURUSD not found in server")
                return None
        # محدود کردن تعداد نمادهای فعال در MarketWatch
        current_symbols = mt5.symbols_get()
        if current_symbols and len(current_symbols) > 100:  # محدودیت اختیاری
            print(f"Too many symbols in MarketWatch ({len(current_symbols)}), clearing MarketWatch")
            for s in current_symbols:
                if s.name != symbol:  # نگه داشتن نماد مورد نظر
                    mt5.symbol_select(s.name, False)  # غیرفعال کردن نمادهای دیگر
        # فعال کردن نماد در MarketWatch
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                print(f"Failed to select fallback symbol EURUSD, error code = {mt5.last_error()}")
                return None
        # گرفتن اطلاعات نماد
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"Failed to get symbol info for {symbol}, error code = {mt5.last_error()}")
            return None
        # چک کردن وضعیت بازار
        if symbol_info.bid == 0.0 and symbol_info.ask == 0.0:
            print(f"No price data for {symbol}, market may be closed or data not updated")
            # تلاش دوباره با تاخیر
            time.sleep(1)  # تاخیر 1 ثانیه
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None or (symbol_info.bid == 0.0 and symbol_info.ask == 0.0):
                print(f"Still no price data for {symbol}, skipping")
        # ذخیره اطلاعات نماد به صورت دیکشنری
        self.symbol_info_dict = symbol_info._asdict()
        # چاپ اطلاعات
        print(f"Symbol info for {symbol}: {symbol_info}")
        print(f"{symbol}: spread = {symbol_info.spread}, digits = {symbol_info.digits}")
        print(f"Show symbol_info(\"{symbol}\")._asdict():")
        for prop in self.symbol_info_dict:
            print(f"  {prop}={self.symbol_info_dict[prop]}")
        # برگرداندن اطلاعات نماد
        return self.symbol_info_dict

    def symbol_info_tick(self, symbol="EURUSD", login=None, password=None, server=None, timeout=60000):
        # متد برای گرفتن اطلاعات آخرین تیک یک نماد خاص
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return None
        # چک کردن وجود نماد در سرور
        available_symbols = mt5.symbols_get()
        if not any(s.name == symbol for s in available_symbols):
            print(f"Symbol {symbol} not found in server")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            if not any(s.name == symbol for s in available_symbols):
                print(f"Fallback symbol EURUSD not found in server")
                return None
        # محدود کردن تعداد نمادهای فعال در MarketWatch
        current_symbols = mt5.symbols_get()
        if current_symbols and len(current_symbols) > 100:  # محدودیت اختیاری
            print(f"Too many symbols in MarketWatch ({len(current_symbols)}), clearing MarketWatch")
            for s in current_symbols:
                if s.name != symbol:  # نگه داشتن نماد مورد نظر
                    mt5.symbol_select(s.name, False)  # غیرفعال کردن نمادهای دیگر
        # فعال کردن نماد در MarketWatch
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"Failed to select {symbol}, error code = {mt5.last_error()}")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                print(f"Failed to select fallback symbol EURUSD, error code = {mt5.last_error()}")
                return None
        # گرفتن اطلاعات تیک
        tick_info = mt5.symbol_info_tick(symbol)
        if tick_info is None:
            print(f"Failed to get tick info for {symbol}, error code = {mt5.last_error()}")
            return None
        # چک کردن وضعیت بازار
        if tick_info.bid == 0.0 and tick_info.ask == 0.0:
            print(f"No tick data for {symbol}, market may be closed or data not updated")
            # تلاش دوباره با تاخیر
            time.sleep(1)  # تاخیر 1 ثانیه
            tick_info = mt5.symbol_info_tick(symbol)
            if tick_info is None or (tick_info.bid == 0.0 and tick_info.ask == 0.0):
                print(f"Still no tick data for {symbol}, skipping")
        # ذخیره اطلاعات تیک به صورت دیکشنری
        self.symbol_tick_dict = tick_info._asdict()
        # چاپ اطلاعات
        print(f"Tick info for {symbol}: {tick_info}")
        print(f"Show symbol_info_tick(\"{symbol}\")._asdict():")
        for prop in self.symbol_tick_dict:
            print(f"  {prop}={self.symbol_tick_dict[prop]}")
        # برگرداندن اطلاعات تیک
        return self.symbol_tick_dict

    def symbol_select(self, symbol="EURUSD", enable=True, login=None, password=None, server=None, timeout=60000):
        # متد برای فعال یا غیرفعال کردن یک نماد در MarketWatch
        login = login or self.default_login
        password = password or self.default_password
        server = server or self.default_server
        # اطمینان از اتصال
        success = self.initialize(path=self.default_path, login=login, password=password, server=server, timeout=timeout)
        if not success:
            print(f"Failed to connect to trade account {login} with server={server}, error code = {mt5.last_error()}")
            return False
        # چک کردن وجود نماد در سرور
        available_symbols = mt5.symbols_get()
        if not any(s.name == symbol for s in available_symbols):
            print(f"Symbol {symbol} not found in server")
            print(f"Retrying with fallback symbol EURUSD")
            symbol = "EURUSD"
            if not any(s.name == symbol for s in available_symbols):
                print(f"Fallback symbol EURUSD not found in server")
                return False
        # محدود کردن تعداد نمادهای فعال در MarketWatch
        current_symbols = mt5.symbols_get()
        if current_symbols and len(current_symbols) > 100:  # محدودیت اختیاری
            print(f"Too many symbols in MarketWatch ({len(current_symbols)}), clearing MarketWatch")
            for s in current_symbols:
                if s.name != symbol:  # نگه داشتن نماد مورد نظر
                    mt5.symbol_select(s.name, False)  # غیرفعال کردن نمادهای دیگر
        # فعال یا غیرفعال کردن نماد در MarketWatch
        selected = mt5.symbol_select(symbol, enable)
        if not selected:
            print(f"Failed to select {symbol} with enable={enable}, error code = {mt5.last_error()}")
            return False
        # اگر enable=True، اطلاعات نماد را دریافت و ذخیره کن
        if enable:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"Failed to get symbol info for {symbol}, error code = {mt5.last_error()}")
                return False
            # چک کردن وضعیت بازار
            if symbol_info.bid == 0.0 and symbol_info.ask == 0.0:
                print(f"No price data for {symbol}, market may be closed or data not updated")
                time.sleep(1)  # تاخیر 1 ثانیه
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None or (symbol_info.bid == 0.0 and symbol_info.ask == 0.0):
                    print(f"Still no price data for {symbol}, skipping")
            # ذخیره اطلاعات نماد
            self.symbol_info_dict = symbol_info._asdict()
            # چاپ اطلاعات
            print(f"Symbol info for {symbol}: {symbol_info}")
            print(f"{symbol}: currency_base = {symbol_info.currency_base}, currency_profit = {symbol_info.currency_profit}, currency_margin = {symbol_info.currency_margin}")
            print()
            print(f"Show symbol_info(\"{symbol}\")._asdict():")
            for prop in self.symbol_info_dict:
                print(f"  {prop}={self.symbol_info_dict[prop]}")
            print()
            # تبدیل به DataFrame
            df = pd.DataFrame(list(self.symbol_info_dict.items()), columns=['property', 'value'])
            print("symbol_info_dict() as dataframe:")
            print(df)
            return True, self.symbol_info_dict
        # اگر enable=False، فقط نتیجه را برگردان
        return True

