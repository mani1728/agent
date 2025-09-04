# -*- coding: utf-8 -*-
"""
mt5_utils.py
------------
توابع کمکی مرتبط با MetaTrader5 و پردازش داده‌ها که تنظیماتشان را
«فقط» از config.json (از طریق config_manager) می‌خوانند و با هات‌ریلُد سازگارند.

قابلیت‌ها:
1) parse_iso_dt: پارس تاریخ‌های ISO (با پشتیبانی از 'Z') و برگرداندن datetime آگاه از UTC
2) to_mt5_const: نگاشت امن نام رشته‌ای به کانستنت‌های mt5 (با پیش‌فرض امن)
3) convert_request_fields: نگاشت فیلدهای درون request.* به کانستنت‌های mt5
4) convert_params: نگاشت سطح-بالا (timeframe/flags/order_type/date*/request.*)
5) safe_serialize: سریال‌سازی امن شیءها برای ارسال به JSON/Kafka/لاگ

نکات پیکربندی (از config.json):
- mt5.timezone : «تایم‌زون منطقی» پروژه (به‌صورت نام IANA؛ مثال "UTC" یا "Asia/Tehran")
  * توجه: خروجی parse_iso_dt طبق قرارداد این فایل **همیشه UTC** است. مقدار mt5.timezone
    صرفاً برای سایر پردازش‌ها/نمایش‌ها می‌تواند موردنیاز باشد.
- سایر کلیدهای mt5 (login/password/server/path/timeout_sec/symbols) در این فایل مصرف نمی‌شوند
  اما برای یکپارچگی پروژه در config.json تعریف شده‌اند.

وابستگی‌ها:
- اگر MetaTrader5 نصب نباشد، ماژول کرش نمی‌کند (پرچم _HAS_MT5=False و fallback).
"""

from __future__ import annotations  # ✅ برای تایپ‌هینت‌های مدرن (Python 3.8+)
import json                        # ✅ برای تست JSON-پذیری و سریال‌سازی
import datetime as dt              # ✅ کار با تاریخ/زمان
from typing import Any, Dict       # ✅ تایپ‌ها برای خوانایی
from config_manager import cfg     # ✅ خواندن تنظیمات از config.json (هات‌ریلُد)

# --- وابستگی‌های اختیاری برای تایم‌زون ---
try:
    import pytz                   # ✅ ترجیحاً pytz برای سازگاری گسترده
    _HAS_PYTZ = True
except Exception:
    _HAS_PYTZ = False
    pytz = None

# --- وابستگی اختیاری MT5 ---
try:
    import MetaTrader5 as mt5     # ✅ کتابخانهٔ رسمی MetaTrader5
    _HAS_MT5 = True
except Exception:
    _HAS_MT5 = False              # ❗ اگر نصب نیست، نگاشت کانستنت‌ها فقط با نام انجام می‌شود
    mt5 = None

# ----------------------------------------------------------------------
# ابزارهای تایم‌زون
# ----------------------------------------------------------------------
def _get_utc_tz() -> dt.tzinfo:
    """برگرداندن آبجکتِ tzinfo برای UTC (با یا بدون pytz)."""
    if _HAS_PYTZ:
        return pytz.timezone("Etc/UTC")
    return dt.timezone.utc

def _get_named_tz(tz_name: str) -> dt.tzinfo:
    """
    تلاش برای برگرداندن tzinfo بر اساس نام IANA (مثلاً "Asia/Tehran").
    اگر در دسترس نباشد، به UTC برمی‌گردد.
    """
    if _HAS_PYTZ:
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return _get_utc_tz()
    # اگر pytz نداریم، از UTC استفاده می‌کنیم (ساده‌سازی)
    return _get_utc_tz()

# ----------------------------------------------------------------------
# 1) پارس ISO → datetime آگاه از UTC
# ----------------------------------------------------------------------
def parse_iso_dt(s: str) -> dt.datetime:
    """
    پارس رشتهٔ ISO (با پشتیبانی از انتهای 'Z') و تبدیل به datetime آگاه از UTC.

    ورودی:
      - s: رشتهٔ ISO مانند "2025-09-04T12:34:56Z" یا "2025-09-04 12:34:56+03:30"

    خروجی:
      - datetime آگاه از ناحیهٔ زمانی (tz-aware) در UTC.

    نکتهٔ پیکربندی:
      - مقدار mt5.timezone در config.json به عنوان «تایم‌زون منطقی» پروژه تعریف می‌شود،
        اما این تابع مطابق قرارداد «همواره UTC» برمی‌گرداند تا رفتار یکدست بماند.
    """
    if not isinstance(s, str):
        raise ValueError("datetime must be ISO string")

    # ✅ پشتیبانی از انتهای 'Z' → تبدیل به offset صریح +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # ✅ تلاش برای پارس استاندارد ISO؛ اگر بین تاریخ/زمان اسپیس بود، آن را به 'T' تبدیل می‌کنیم
    try:
        obj = dt.datetime.fromisoformat(s)
    except Exception:
        obj = dt.datetime.fromisoformat(s.replace(" ", "T"))

    # ✅ اگر tz نداشت، آن را «UTC» فرض می‌کنیم
    if obj.tzinfo is None:
        if _HAS_PYTZ:
            obj = _get_utc_tz().localize(obj)  # نوع-aware با pytz
        else:
            obj = obj.replace(tzinfo=_get_utc_tz())  # جای‌گذاری tzinfo ساده

    # ✅ تبدیل نهایی به UTC (ممکن است ورودی offset متفاوت داشته باشد)
    return obj.astimezone(_get_utc_tz())

# ----------------------------------------------------------------------
# 2) نگاشت امن رشته → کانستنت‌های mt5
# ----------------------------------------------------------------------
def to_mt5_const(name: str, default: Any) -> Any:
    """
    نگاشت امن نام رشته‌ای به کانستنت‌های mt5؛ در صورت نبودن/نصب نبودن MT5، default برمی‌گردد.

    مثال‌ها:
      to_mt5_const("TIMEFRAME_H4", mt5.TIMEFRAME_H1)
      to_mt5_const("ORDER_TYPE_BUY", mt5.ORDER_TYPE_SELL)
    """
    # ❗ اگر MT5 نصب نیست، امکان getattr روی mt5 نداریم → مستقیم default
    if not _HAS_MT5:
        return default
    # ✅ تلاش برای گرفتن خاصیت از ماژول mt5
    return getattr(mt5, str(name), default)

# ----------------------------------------------------------------------
# 3) نگاشت فیلدهای درون request.* به کانستنت‌های mt5
# ----------------------------------------------------------------------
def convert_request_fields(req: Dict[str, Any]) -> None:
    """
    تبدیل فیلدهای request به کانستنت‌های mt5 (درجا/همان شیء):

    فیلدهای پشتیبانی‌شده (در صورت رشته بودن):
      - action      → mt5.TRADE_ACTION_*
      - type        → mt5.ORDER_TYPE_*
      - type_time   → mt5.ORDER_TIME_*
      - type_filling→ mt5.ORDER_FILLING_*

    نکته:
      - اگر مقدار رشته‌ای نامعتبر باشد، پیش‌فرض امن استفاده می‌شود.
      - این تابع «in-place» عمل می‌کند و چیزی برنمی‌گرداند.
    """
    if "action" in req and isinstance(req["action"], str):
        # پیش‌فرض امن: DEAL (شایع‌ترین حالت برای ارسال فوری)
        default = mt5.TRADE_ACTION_DEAL if _HAS_MT5 else "TRADE_ACTION_DEAL"
        req["action"] = to_mt5_const(req["action"], default)

    if "type" in req and isinstance(req["type"], str):
        # پیش‌فرض امن: BUY
        default = mt5.ORDER_TYPE_BUY if _HAS_MT5 else "ORDER_TYPE_BUY"
        req["type"] = to_mt5_const(req["type"], default)

    if "type_time" in req and isinstance(req["type_time"], str):
        # پیش‌فرض امن: GTC (Good Till Cancelled)
        default = mt5.ORDER_TIME_GTC if _HAS_MT5 else "ORDER_TIME_GTC"
        req["type_time"] = to_mt5_const(req["type_time"], default)

    if "type_filling" in req and isinstance(req["type_filling"], str):
        # پیش‌فرض امن: IOC (Immediate-Or-Cancel)
        default = mt5.ORDER_FILLING_IOC if _HAS_MT5 else "ORDER_FILLING_IOC"
        req["type_filling"] = to_mt5_const(req["type_filling"], default)

# ----------------------------------------------------------------------
# 4) تبدیل سطح-بالا: timeframe/flags/order_type/date*/request.*
# ----------------------------------------------------------------------
def convert_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    تبدیل امن پارامترها در سطح بالا. این تابع روی یک کپی از ورودی کار می‌کند
    و دیکشنریِ تبدیل‌شده را برمی‌گرداند.

    نگاشت‌ها:
      - timeframe (str) → mt5.TIMEFRAME_*
      - flags     (str) → mt5.COPY_TICKS_*
      - order_type(str) → mt5.ORDER_TYPE_*
      - action    (str) → lowercase (برای قراردادهای سطح اپ)
      - date_from/date_to (str ISO) → datetime آگاه از UTC
      - request   (dict) → convert_request_fields(req)

    پیش‌فرض‌های امن (وقتی نام رشته‌ای نامعتبر باشد یا MT5 نصب نباشد):
      - timeframe: TIMEFRAME_H4
      - flags    : COPY_TICKS_ALL
      - order_type: ORDER_TYPE_BUY
    """
    out = dict(params)  # ✅ کپی امن (تا ورودی کاربر دست‌نخورده بماند)

    if "timeframe" in out and isinstance(out["timeframe"], str):
        default = mt5.TIMEFRAME_H4 if _HAS_MT5 else "TIMEFRAME_H4"
        out["timeframe"] = to_mt5_const(out["timeframe"], default)

    if "flags" in out and isinstance(out["flags"], str):
        default = mt5.COPY_TICKS_ALL if _HAS_MT5 else "COPY_TICKS_ALL"
        out["flags"] = to_mt5_const(out["flags"], default)

    if "order_type" in out and isinstance(out["order_type"], str):
        default = mt5.ORDER_TYPE_BUY if _HAS_MT5 else "ORDER_TYPE_BUY"
        out["order_type"] = to_mt5_const(out["order_type"], default)

    if "action" in out and isinstance(out["action"], str):
        # ✅ نرمال‌سازی قرارداد سطح اپ (مثلاً "Place" → "place")
        out["action"] = out["action"].lower()

    if "date_from" in out and isinstance(out["date_from"], str):
        out["date_from"] = parse_iso_dt(out["date_from"])

    if "date_to" in out and isinstance(out["date_to"], str):
        out["date_to"] = parse_iso_dt(out["date_to"])

    if "request" in out and isinstance(out["request"], dict):
        convert_request_fields(out["request"])  # ✅ in-place

    return out

# ----------------------------------------------------------------------
# 5) سریال‌سازی امن برای JSON (برای لاگ/کافکا/ذخیره)
# ----------------------------------------------------------------------
def safe_serialize(obj: Any, _depth: int = 0, _limit: int = 3) -> Any:
    """
    سریال‌سازی امن برای JSON:
    - datetime/date/time → ISO8601
    - namedtuple → dict
    - dict/list/tuple → بازگشتی
    - numpy scalar → مقدار اسکالر
    - pandas.DataFrame → پیش‌نمایش + لیست ستون‌ها + تعداد ردیف
    - pandas.Series → dict
    - سایر انواع → اگر JSON‌پذیر، همان؛ وگرنه str(obj)

    پارامترها:
      - _depth: عمق فعلیِ بازگشت (برای جلوگیری از حلقه‌های تودرتو/بی‌نهایت)
      - _limit: حداکثر عمق مجاز بازگشت
    """
    # ✅ جلوگیری از بازگشت بی‌نهایت در ساختارهای عمیق/دایره‌ای
    if _depth > _limit:
        return str(obj)

    # ✅ datetime/date/time → ISO
    if isinstance(obj, (dt.datetime, dt.date, dt.time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    # ✅ namedtuple → dict
    if hasattr(obj, "_asdict"):
        try:
            return {k: safe_serialize(v, _depth + 1, _limit) for k, v in obj._asdict().items()}
        except Exception:
            return str(obj)

    # ✅ dict → serialize بازگشتی
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, _depth + 1, _limit) for k, v in obj.items()}

    # ✅ list/tuple → serialize بازگشتی
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(v, _depth + 1, _limit) for v in obj]

    # ✅ numpy scalar → مقدار اسکالر پایتونی
    try:
        import numpy as np  # type: ignore
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass

    # ✅ pandas ساختارهای رایج → خلاصهٔ قابل‌مصرف
    try:
        import pandas as pd  # type: ignore
        if isinstance(obj, pd.DataFrame):
            return {
                "dataframe_preview": obj.head(50).to_dict(orient="records"),
                "columns": list(obj.columns),
                "rows": int(getattr(obj, "shape", [0, 0])[0]),
            }
        if isinstance(obj, pd.Series):
            return obj.to_dict()
    except Exception:
        pass

    # ✅ اگر JSON‌پذیر است، همان را برگردان
    try:
        json.dumps(obj)
        return obj
    except Exception:
        # ✅ آخرین راه: رشته‌ای‌سازی
        return str(obj)
