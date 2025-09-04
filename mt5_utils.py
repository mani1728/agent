# mt5_utils.py
# =========================
# توابع ابزار برای:
# - نگاشت امن رشته‌ها به کانستنت‌های MT5
# - پارس تاریخ‌های ISO به datetime با UTC
# - تبدیل پارامترهای ورودی (timeframe/flags/order_type/request.*)
# - سریال‌سازی امن برای ارسال به Kafka (JSON-safe)
# =========================

from __future__ import annotations                    # برای تایپ‌هینت‌های مدرن
import json                                          # برای آزمایش سریال‌سازی
import datetime as dt                                # کار با تاریخ/زمان
from typing import Any, Dict                          # تایپ‌ها
import pytz                                          # برای منطقه زمانی
import MetaTrader5 as mt5                            # کتابخانه MT5

UTC_TZ = pytz.timezone("Etc/UTC")                    # منطقه زمانی UTC

def parse_iso_dt(s: str) -> dt.datetime:
    """پارس رشته ISO (با پشتیبانی از Z) و تبدیل به datetime آگاه از UTC."""
    if not isinstance(s, str):                       # اگر رشته نباشد
        raise ValueError("datetime must be ISO string")  # خطا
    if s.endswith("Z"):                              # اگر به Z ختم شود
        s = s[:-1] + "+00:00"                        # تبدیل Z به offset
    try:
        obj = dt.datetime.fromisoformat(s)           # پارس ISO
    except Exception:
        obj = dt.datetime.fromisoformat(s.replace(" ", "T"))  # fallback برای اسپیس
    if obj.tzinfo is None:                           # اگر تایم‌زون نداشت
        return UTC_TZ.localize(obj)                  # افزودن UTC
    return obj.astimezone(UTC_TZ)                    # تبدیل به UTC

def to_mt5_const(name: str, default: Any) -> Any:
    """نگاشت امن رشته به کانستنت mt5؛ در صورت نبودن، default برمی‌گردد."""
    return getattr(mt5, name, default)               # گرفتن خاصیت از ماژول mt5

def convert_request_fields(req: Dict[str, Any]) -> None:
    """تبدیل فیلدهای request به کانستنت‌های mt5 (action/type/time/filling)."""
    if "action" in req and isinstance(req["action"], str):
        req["action"] = to_mt5_const(req["action"], mt5.TRADE_ACTION_DEAL)   # نگاشت action
    if "type" in req and isinstance(req["type"], str):
        req["type"] = to_mt5_const(req["type"], mt5.ORDER_TYPE_BUY)          # نگاشت type
    if "type_time" in req and isinstance(req["type_time"], str):
        req["type_time"] = to_mt5_const(req["type_time"], mt5.ORDER_TIME_GTC)  # نگاشت time
    if "type_filling" in req and isinstance(req["type_filling"], str):
        req["type_filling"] = to_mt5_const(req["type_filling"], mt5.ORDER_FILLING_IOC)  # نگاشت filling

def convert_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """تبدیل امن پارامترها در سطح بالا: timeframe/flags/order_type/date*/request.*"""
    out = dict(params)                               # کپی امن
    if "timeframe" in out and isinstance(out["timeframe"], str):
        out["timeframe"] = to_mt5_const(out["timeframe"], mt5.TIMEFRAME_H4)   # نگاشت timeframe
    if "flags" in out and isinstance(out["flags"], str):
        out["flags"] = to_mt5_const(out["flags"], mt5.COPY_TICKS_ALL)         # نگاشت flags
    if "order_type" in out and isinstance(out["order_type"], str):
        out["order_type"] = to_mt5_const(out["order_type"], mt5.ORDER_TYPE_BUY)  # نگاشت order_type
    if "action" in out and isinstance(out["action"], str):
        out["action"] = out["action"].lower()                                  # نرمال‌سازی action
    if "date_from" in out and isinstance(out["date_from"], str):
        out["date_from"] = parse_iso_dt(out["date_from"])                      # پارس تاریخ
    if "date_to" in out and isinstance(out["date_to"], str):
        out["date_to"] = parse_iso_dt(out["date_to"])                          # پارس تاریخ
    if "request" in out and isinstance(out["request"], dict):
        convert_request_fields(out["request"])                                  # نگاشت داخل request
    return out

def safe_serialize(obj: Any, _depth: int = 0, _limit: int = 3) -> Any:
    """سریال‌سازی امن برای JSON: datetime/np/pd/… → فرم قابل ارسال/ثبت."""
    if _depth > _limit:                                # جلوگیری از بازگشت بی‌نهایت
        return str(obj)                                # تبدیل به رشته
    # datetime → ISO
    if isinstance(obj, (dt.datetime, dt.date, dt.time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    # namedtuple → dict
    if hasattr(obj, "_asdict"):
        try:
            return {k: safe_serialize(v, _depth + 1, _limit) for k, v in obj._asdict().items()}
        except Exception:
            return str(obj)
    # dict → بازگشتی
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, _depth + 1, _limit) for k, v in obj.items()}
    # list/tuple → بازگشتی
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(v, _depth + 1, _limit) for v in obj]
    # numpy → مقدار اسکالر
    try:
        import numpy as np
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    # pandas → پیش‌نمایش + ستون‌ها + تعداد ردیف
    try:
        import pandas as pd
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
    # اگر JSON پذیر است همان را برگردان
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)                                 # آخرین راه: تبدیل به رشته
