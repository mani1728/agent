# کلاس برای کار با MetaTrader 5
import MetaTrader5 as mt5
import pandas as pd

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

    def initialize(self, path=None, login=None, password=None, server=None, timeout=60000, portable=False):
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