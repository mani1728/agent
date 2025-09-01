# کلاس برای کار با MetaTrader 5
import MetaTrader5 as mt5

class Mt5_Manager:
    def __init__(self):
        # مقادیر پیش‌فرض برای استفاده در صورت عدم ارسال پارامتر
        self.default_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        self.default_login = 96033328
        self.default_password = "D_Hs3tGc"
        self.default_server = "MetaQuotes-Demo"
        self.terminal_info = None  # برای ذخیره اطلاعات ترمینال
        self.version = None  # برای ذخیره نسخه MT5

    def initialize(self, path=None, login=None, password=None, server=None, timeout=60000, portable=False):
        # متد برای اتصال به MetaTrader 5 با پارامترهای داده‌شده
        # استفاده از مقادیر پیش‌فرض اگر پارامترها None باشن
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
        self.last_error = mt5.last_error()
        print(f"Terminal info: {self.terminal_info}")
        print(f"MT5 version: {self.version}")
        print(f"MT5 last error: {self.last_error}")
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