# -*- coding: utf-8 -*-
"""
config_manager.py
-----------------
ماژول مدیریت تنظیمات با قابلیت «هات-پلاگ/هات-ریلُد» از فایل config.json.

ویژگی‌ها:
- پشتیبانی از کامنت داخل JSON (سبک JSONC: // و /* */ و #)
- ست کردن مقادیر پیش‌فرض اگر در فایل نبود
- ریلود خودکار وقتی فایل تغییر کند (بدون نیاز به ری‌استارت برنامه)
- دسترسی ساده با مسیر نقطه‌ای مثل: cfg().get("kafka.bootstrap_servers")
- پشتیبانی از قالب رشته‌ای {client_id} در مقادیر متنی (مثلاً نام تاپیک‌ها)

نکته: اگر فایل پیکربندی موجود نباشد، با مقادیر پیش‌فرض ساخته می‌شود.
"""

from __future__ import annotations          # ✅ اجازهٔ استفاده از تایپ‌هینت‌های مدرن
import json, os, re, threading, time        # ✅ کتابخانه‌های استاندارد موردنیاز
from typing import Any, Dict                # ✅ تایپ‌های کمکی برای خوانایی بهتر

# ------------------------------
# جدول «پیش‌فرض‌ها» برای کلیدهایی که در config.json وجود ندارند
# هر بخش با کامنت توضیح داده شده تا بدانید چه مقادیری می‌پذیرد و چرا
# ------------------------------
_DEFAULTS: Dict[str, Any] = {
    "app": {
        "env": "dev",                       # محیط اجرا: dev | prod | test
        "hot_reload_check_sec": 2           # هر چند ثانیه یکبار فایل config.json را برای تغییرات بررسی کند
    },
    "logging": {
        "level": "INFO",                    # سطح لاگ: DEBUG | INFO | WARNING | ERROR | CRITICAL
        "json": False,                      # اگر True باشد، خروجی لاگ در قالب JSON چاپ می‌شود
        "file_enabled": True,               # اگر True باشد، لاگ علاوه بر کنسول در فایل هم ذخیره می‌شود
        "file_path": "logs/app.log",        # مسیر فایل لاگ
        "max_bytes": 5_000_000,             # حداکثر حجم فایل لاگ قبل از گردش (حدود 5MB)
        "backup_count": 3                   # تعداد فایل‌های پشتیبان لاگ
    },
    "kafka": {
        "enabled": True,                    # اگر False باشد، تمام قسمت‌های مرتبط با Kafka غیرفعال می‌شود
        "bootstrap_servers": ["localhost:9092"],  # لیست بروکرها (host:port)
        "client_id": "client-001",          # شناسهٔ کلاینت؛ برای قالب {client_id} نیز استفاده می‌شود
        "group_id": "mt5-service",          # گروه مصرف‌کننده برای Listener
        "security_protocol": "PLAINTEXT",   # PLAINTEXT | SASL_PLAINTEXT | SASL_SSL | SSL
        "sasl_mechanism": "PLAIN",          # PLAIN | SCRAM-SHA-256 | SCRAM-SHA-512 | OAUTHBEARER
        "sasl_username": "",                # نام کاربری SASL (در صورت نیاز)
        "sasl_password": "",                # گذرواژهٔ SASL (در صورت نیاز)
        "acks": "all",                      # acks برای Producer: 0 | 1 | all
        "retries": 3,                       # تعداد تلاش مجدد در ارسال پیام
        "linger_ms": 5,                     # تأخیر قبل از ارسال برای batching
        "request_timeout_ms": 30_000,       # تایم‌اوت درخواست‌ها
        "consumer_auto_offset_reset": "latest",  # رفتار شروع مصرف: earliest | latest
        "enable_auto_commit": True,         # کمیت خودکار آفست‌ها توسط مصرف‌کننده
        "session_timeout_ms": 45_000,       # تایم‌اوت جلسهٔ مصرف‌کننده
        "topics": {
            # لیست تاپیک‌های دستورات با اولویت: انتهای نام ".p0" یا ".p1" یا ".p2"
            # از قالب {client_id} پشتیبانی می‌شود: پس از بارگذاری، به مقدار واقعی جایگزین می‌گردد
            "commands": ["cmd.{client_id}.p0","cmd.{client_id}.p1","cmd.{client_id}.p2"],
            "replies": "server.replies",        # تاپیک ارسال پاسخ‌ها
            "status": "clients.status",         # تاپیک وضعیت کلاینت‌ها (compacted پیشنهاد می‌شود)
            "register": "clients.register",     # تاپیک ثبت‌نام کلاینت‌ها
            "register_responses": "clients.register.responses"  # تاپیک پاسخ ثبت‌نام
        }
    },
    "auth": {
        "token_required": False,            # اگر True، پیام‌ها باید توکن معتبر داشته باشند
        "tokens": {"client-001": "changeme-token"},  # دیکشنری client_id -> token
        "header_key": "auth_token"          # کلیدِ فیلدی که توکن در payload/headers می‌آید
    },
    "mt5": {
        "login": 0,                         # شماره لاگین MT5
        "password": "",                     # گذرواژهٔ MT5
        "server": "",                       # نام/آدرس سرور بروکر
        "path": "",                         # مسیر اجرایی ترمینال MT5 (در برخی سیستم‌ها لازم است)
        "timeout_sec": 10,                  # تایم‌اوت عملیات
        "symbols": ["EURUSD","XAUUSD"],     # سیمبل‌های رایج
        "timezone": "UTC"                   # تایم‌زون منطقی برای پردازش
    },
    "executor": {
        "max_workers": 4,                   # تعداد تردهای اجرا
        "priority_levels": [0,1,2],         # سطوح اولویت (0=بالاترین). برای قرارداد 1..10، همین را عوض کنید.
        "queue_maxsize": 100,               # حداکثر اندازهٔ صف
        # ===== کلیدهای اختیاری کنترل رفتار (اگر در config.json نبودند، این‌ها اعمال می‌شود) =====
        "reserved_low_slots": 1,            # تعداد ورکرهای رزرو برای Low
        "aging_step_seconds": 5,            # بازهٔ اجرای Aging (ثانیه)
        "aging_step_amount": 1,             # اندازهٔ پلهٔ Aging
        "idle_sleep": 0.05,                 # خواب کوتاه ورکر هنگام بی‌کاری (ثانیه)
        "max_exec_ms_default": 3000         # حداکثر زمان اجرای تسک اگر در هدر نبود (میلی‌ثانیه)
    },
    "client_auth": {
        "heartbeat_interval_sec": 15,       # فاصلهٔ heartbeat (ثانیه)
        "register_timeout_sec": 20,         # مهلت انتظار پاسخ ثبت‌نام (ثانیه)
        "token_refresh_margin_sec": 120,    # حاشیهٔ امن برای رفرش توکن (ثانیه)
        "sig_alg": "HMAC-SHA256",           # نام الگوریتم امضا (اطلاعاتی)
        "hmac_secret": "changeme",          # کلید سری HMAC (در محیط واقعی امن بگذارید)
        "kid": "k-2025-09",                 # شناسهٔ کلید (rotation)
        "consumer_group_prefix": "client-register-waiter-"  # پیشوند گروه مصرف‌کنندهٔ موقت
    }
}

# ---------------------------------------------------
# تابع کمکی: حذف کامنت‌ها از متن JSON (سبک JSONC)
# پشتیبانی از سه نوع کامنت:  /* ... */  ،  // ...  ،  # ...
# ---------------------------------------------------
def _strip_json_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)   # ✅ حذف بلاک‌کامنت‌های /* ... */ به‌صورت چندخطی
    text = re.sub(r"//.*?$", "", text, flags=re.M)      # ✅ حذف کامنت تک‌خطی // تا انتهای همان خط
    text = re.sub(r"#.*?$", "", text, flags=re.M)       # ✅ حذف کامنت تک‌خطی # تا انتهای همان خط
    return text                                         # ✅ برگرداندن متن پاک‌سازی‌شده

# ---------------------------------------------------
# کلاس هسته: پیکربندی با هات‌ریلُد
# ---------------------------------------------------
class HotReloadConfig:
    def __init__(self, path: str = "config.json"):
        self.path = path                                 # ✅ مسیر فایل پیکربندی
        self._lock = threading.RLock()                   # ✅ قفل بازگشتی برای ایمنی در برابر هم‌زمانی
        self._data: Dict[str, Any] = {}                  # ✅ ساختارِ پیکربندیِ در حافظه
        self._mtime: float = 0.0                         # ✅ آخرین زمان تغییر فایل (mtime)
        self._stop = False                               # ✅ پرچم توقف واچ‌لوپ

        self._load(first_time=True)                      # ✅ بارگذاری اولیهٔ پیکربندی (با اعمال پیش‌فرض‌ها و قالب‌ها)

        # ✅ آغاز ترد سبکِ ناظر بر تغییرات فایل؛ اگر فایل تغییر کند، مجدد بارگذاری می‌شود
        t = threading.Thread(target=self._watch_loop, name="ConfigWatchdog", daemon=True)
        t.start()

    def _watch_loop(self):
        """حلقهٔ ناظر: در بازه‌های زمانی مشخص، اگر فایل تغییر کرده باشد، ریلود می‌کند."""
        while not self._stop:                                                     # ✅ تا وقتی دستور توقف نگرفته‌ایم
            # ✅ فاصلهٔ بررسی از config (اگر هنوز داده‌ای نبود، 2 ثانیه)
            time.sleep(max(1, int(self._data.get("app", {}).get("hot_reload_check_sec", 2))))
            try:
                self._reload_if_modified()                                        # ✅ تلاش برای ریلود در صورت تغییر mtime
            except Exception:
                # ✅ از کرش جلوگیری می‌کنیم؛ خطای لحظه‌ای IO یا JSON نباید سرویس را بخواباند
                pass

    def stop(self):
        """توقف حلقهٔ ناظر (برای خروج تمیز از برنامه)."""
        self._stop = True                                                         # ✅ ست‌کردن پرچم توقف

    def __call__(self, path: str, default=None):
        return self.get(path, default)

    # ---------------------------------------------------
    # خواندن فایل پیکربندی از دیسک + حذف کامنت‌ها + parse JSON
    # اگر فایل نبود، با پیش‌فرض‌ها ساخته می‌شود
    # ---------------------------------------------------
    def _read_file(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):                                         # ✅ اگر فایل اصلاً وجود ندارد
            with open(self.path, "w", encoding="utf-8") as f:                     # ✅ ایجاد فایل جدید
                json.dump(_DEFAULTS, f, ensure_ascii=False, indent=2)             # ✅ نوشتن پیش‌فرض‌ها برای راه‌اندازی سریع
            return dict(_DEFAULTS)                                                # ✅ بازگرداندن کپیِ پیش‌فرض‌ها به حافظه

        with open(self.path, "r", encoding="utf-8") as f:                         # ✅ باز کردن فایل موجود
            raw = f.read()                                                        # ✅ خواندن کل محتوا به‌صورت متن

        clean = _strip_json_comments(raw)                                         # ✅ حذف کامنت‌ها از متن
        data = json.loads(clean or "{}")                                          # ✅ parse به دیکشنری (اگر خالی بود، شیء تهی)
        return data                                                               # ✅ برگرداندن دیکشنری خام (قبل از مرج با پیش‌فرض‌ها)

    # ---------------------------------------------------
    # مرج بازگشتیِ دادهٔ خوانده‌شده با پیش‌فرض‌ها
    # هر کلید جاافتاده با مقدار پیش‌فرض پر می‌شود
    # ---------------------------------------------------
    def _merge_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def merge(a, b):
            # a = دادهٔ خوانده‌شده، b = پیش‌فرض‌ها
            if not isinstance(a, dict) or not isinstance(b, dict):               # ✅ اگر هردو dict نبودند
                return a if a is not None else b                                  # ✅ اولویت با a؛ در غیر این صورت b (پیش‌فرض)
            out = dict(b)                                                         # ✅ شروع از کپیِ پیش‌فرض‌ها
            for k, v in a.items():                                                # ✅ پیمایش کلیدهای خوانده‌شده
                if isinstance(v, dict) and k in b and isinstance(b[k], dict):     # ✅ اگر مقدار هر دو dict بود، ادغام عمیق
                    out[k] = merge(v, b[k])
                else:
                    out[k] = v                                                    # ✅ در غیر این صورت، مقدار خوانده‌شده را جایگزین کن
            return out
        return merge(data or {}, _DEFAULTS)                                       # ✅ اجرای ادغام با هندلِ a=None

    # ---------------------------------------------------
    # جایگزینی قالب‌ها (Template Resolution)
    # فعلاً فقط {client_id} را در رشته‌ها پشتیبانی می‌کند
    # روی لیست‌ها و دیکشنری‌ها بازگشتی اعمال می‌شود
    # ---------------------------------------------------
    def _resolve_templates(self, data: Any) -> Any:
        # ✅ client_id را از داده‌های فعلیِ ساخته‌شده (یا app) برمی‌داریم؛ اگر نبود، پیش‌فرض
        client_id = (
            self._data.get("kafka", {}).get("client_id")
            or self._data.get("app", {}).get("client_id")
            or "client-001"
        )

        def resolve(value):
            if isinstance(value, str):                                            # ✅ اگر رشته است، قالب را جایگزین کن
                # توجه: format() با کلیدهای ناشناخته خطا می‌دهد؛
                # در این نسخه فقط {client_id} پشتیبانی می‌شود:
                return value.format(client_id=client_id)
            if isinstance(value, list):                                           # ✅ اگر لیست است، بازگشتی روی آیتم‌ها
                return [resolve(x) for x in value]
            if isinstance(value, dict):                                           # ✅ اگر دیکشنری است، بازگشتی روی مقادیر
                return {k: resolve(v) for k, v in value.items()}
            return value                                                          # ✅ سایر انواع (int/float/bool/None) دست‌نخورده

        return resolve(data)                                                      # ✅ خروجیِ دادهٔ جایگزین‌شده

    # ---------------------------------------------------
    # بارگذاری/ریلود اصلی:
    # 1) خواندن فایل
    # 2) مرج با پیش‌فرض‌ها
    # 3) جایگذاری قالب‌ها
    # 4) به‌روزرسانی mtime
    # ---------------------------------------------------
    def _load(self, first_time: bool=False):
        with self._lock:                                                          # ✅ قفل برای ایمنیِ هم‌زمانی
            data = self._read_file()                                              # ✅ خواندن خام
            data = self._merge_defaults(data)                                     # ✅ اعمال پیش‌فرض‌ها
            self._data = data                                                     # ✅ ست‌کردن دادهٔ پایه (برای دسترسی به client_id)
            self._data = self._resolve_templates(self._data)                      # ✅ اعمال قالب‌ها روی رشته‌ها/لیست‌ها/دیکشنری‌ها
            try:
                self._mtime = os.path.getmtime(self.path)                         # ✅ ذخیرهٔ mtime فعلی فایل
            except FileNotFoundError:
                self._mtime = 0.0                                                 # ✅ اگر فایل ناگهان حذف شد

    # ---------------------------------------------------
    # اگر mtime فایل نسبت به آخرین بارگذاری تغییر کرده باشد، مجدد لود کن
    # ---------------------------------------------------
    def _reload_if_modified(self):
        try:
            mtime = os.path.getmtime(self.path)                                   # ✅ خواندن mtime فعلی فایل
        except FileNotFoundError:
            mtime = 0.0                                                           # ✅ اگر فایل حذف شده بود
        if mtime != self._mtime:                                                  # ✅ تشخیص تغییر
            self._load(first_time=False)                                          # ✅ بارگذاری مجدد

    # ---------------------------------------------------
    # ریلود اجباری (مثلاً برای تست یا زمانی‌که می‌خواهید دستی تازه‌سازی کنید)
    # ---------------------------------------------------
    def reload(self):
        self._load(first_time=False)                                              # ✅ بارگذاری مجددِ بدون درنظرگرفتن first_time

    # ---------------------------------------------------
    # دریافت کپی کامل از پیکربندی فعلی
    # json round-trip برای ایجاد «کپی دفاعی» (جلوگیری از تغییر مستقیم بیرونی)
    # ---------------------------------------------------
    def get_all(self) -> Dict[str, Any]:
        with self._lock:                                                          # ✅ قفل هم‌زمانی
            self._reload_if_modified()                                            # ✅ قبل از برگرداندن، تغییرات را چک کن
            return json.loads(json.dumps(self._data))                             # ✅ کپی امن (deep copy سبک)

    # ---------------------------------------------------
    # دسترسی مسیرنقطه‌ای (dot-path) به کلیدها
    # مثال: cfg().get("kafka.bootstrap_servers")
    # اگر مسیر معتبر نبود، default برمی‌گرداند
    # ---------------------------------------------------
    def get(self, path: str, default: Any=None) -> Any:
        with self._lock:                                                          # ✅ قفل هم‌زمانی
            self._reload_if_modified()                                            # ✅ هات‌ریلُد در لحظهٔ درخواست
            d = self._data                                                        # ✅ شروع از ریشهٔ داده
            for part in path.split("."):                                          # ✅ هر بخش مسیر را جداگانه طی کن
                if isinstance(d, dict) and part in d:                             # ✅ اگر دیکشنری و کلید موجود است
                    d = d[part]                                                   # ✅ یک سطح عمیق‌تر برو
                else:
                    return default                                                # ✅ اگر نبود، مقدار پیش‌فرض را برگردان
            return d                                                              # ✅ مقدار نهایی مسیر

# ---------------------------------------------------
# سینگلتون سراسری برای دسترسی راحت به پیکربندی
# استفاده: from config_manager import cfg ; cfg().get(...)
# ---------------------------------------------------
_cfg_singleton: HotReloadConfig | None = None

def cfg() -> HotReloadConfig:
    """دسترسی به نمونهٔ سراسری پیکربندی (lazy-init)."""
    global _cfg_singleton
    if _cfg_singleton is None:                                                    # ✅ اگر هنوز ساخته نشده
        _cfg_singleton = HotReloadConfig("config.json")                           # ✅ بساز با مسیر پیش‌فرض
    return _cfg_singleton                                                         # ✅ همان نمونهٔ مشترک را برگردان
