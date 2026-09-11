# Path: Version 1_0_0/agent/core/mt5_utils.py

# -*- coding: utf-8 -*-
"""
mt5_utils.py
------------
توابع کمکی مرتبط با MetaTrader5 و پردازش داده‌ها.

قابلیت‌ها:
1) parse_iso_dt
2) to_mt5_const
3) convert_request_fields
4) convert_params
5) safe_serialize

نکات:
- تنظیمات از config_manager خوانده می‌شوند.
- parse_iso_dt همیشه datetime در UTC برمی‌گرداند.
- MetaTrader5 وابستگی اختیاری است تا ماژول در محیط‌هایی که MT5 نصب نیست
  بتواند برای تست/پردازش اولیه import شود.

نکته Migration:
- parse_iso_dt عمداً UTC را برمی‌گرداند.
- این تابع نباید در این مرحله جایگزین _parse_iso_dt موجود در
  meta_trader_manager.py شود؛ زیرا Manager فعلاً رفتار legacy مربوط
  به timezone پیکربندی‌شده را حفظ می‌کند.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict


# ----------------------------------------------------------------------
# Config compatibility import
# ----------------------------------------------------------------------

try:
    from agent.infrastructure.config_manager import cfg
except ImportError:
    # Legacy flat-file execution compatibility.
    from config_manager import cfg


# ----------------------------------------------------------------------
# Optional timezone dependency
# ----------------------------------------------------------------------

try:
    import pytz

    _HAS_PYTZ = True
except Exception:
    _HAS_PYTZ = False
    pytz = None


# ----------------------------------------------------------------------
# Optional MetaTrader5 dependency
# ----------------------------------------------------------------------

try:
    import MetaTrader5 as mt5

    _HAS_MT5 = True
except Exception:
    _HAS_MT5 = False
    mt5 = None


# ----------------------------------------------------------------------
# Timezone helpers
# ----------------------------------------------------------------------

def _get_utc_tz() -> dt.tzinfo:
    """
    Return a UTC tzinfo object.

    pytz is preferred for compatibility with the existing project.
    """
    if _HAS_PYTZ:
        return pytz.timezone("Etc/UTC")

    return dt.timezone.utc


def _get_named_tz(tz_name: str) -> dt.tzinfo:
    """
    Return an IANA timezone.

    If the requested timezone is unavailable or invalid,
    UTC is used as a safe fallback.
    """
    if _HAS_PYTZ:
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return _get_utc_tz()

    return _get_utc_tz()


# ----------------------------------------------------------------------
# 1) ISO datetime parser
# ----------------------------------------------------------------------

def parse_iso_dt(s: str) -> dt.datetime:
    """
    Parse an ISO datetime string and return an aware UTC datetime.

    Supported examples:

        2025-09-04T12:34:56Z
        2025-09-04T12:34:56+03:30
        2025-09-04 12:34:56+03:30
        2025-09-04T12:34:56

    Naive datetimes are interpreted as UTC.

    Returns:
        datetime.datetime with UTC timezone.
    """
    if not isinstance(s, str):
        raise ValueError("datetime must be ISO string")

    value = s.strip()

    if not value:
        raise ValueError("datetime must not be empty")

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        obj = dt.datetime.fromisoformat(value)
    except Exception:
        obj = dt.datetime.fromisoformat(
            value.replace(" ", "T")
        )

    if obj.tzinfo is None:
        if _HAS_PYTZ:
            obj = _get_utc_tz().localize(obj)
        else:
            obj = obj.replace(tzinfo=_get_utc_tz())

    return obj.astimezone(_get_utc_tz())


# ----------------------------------------------------------------------
# 2) MT5 constant resolver
# ----------------------------------------------------------------------

def to_mt5_const(name: str, default: Any) -> Any:
    """
    Safely resolve a string name to an MT5 constant.

    If MT5 is unavailable or the constant does not exist,
    default is returned.
    """
    if not _HAS_MT5:
        return default

    if not isinstance(name, str):
        return default

    return getattr(mt5, name, default)


# ----------------------------------------------------------------------
# 3) Convert request.* fields
# ----------------------------------------------------------------------

def convert_request_fields(req: Dict[str, Any]) -> None:
    """
    Convert string values inside a trading request to MT5 constants.

    Supported fields:
        action
        type
        type_time
        type_filling

    The dictionary is modified in-place.
    """
    if not isinstance(req, dict):
        return

    if "action" in req and isinstance(req["action"], str):
        default = (
            mt5.TRADE_ACTION_DEAL
            if _HAS_MT5
            else "TRADE_ACTION_DEAL"
        )

        req["action"] = to_mt5_const(
            req["action"],
            default,
        )

    if "type" in req and isinstance(req["type"], str):
        default = (
            mt5.ORDER_TYPE_BUY
            if _HAS_MT5
            else "ORDER_TYPE_BUY"
        )

        req["type"] = to_mt5_const(
            req["type"],
            default,
        )

    if "type_time" in req and isinstance(req["type_time"], str):
        default = (
            mt5.ORDER_TIME_GTC
            if _HAS_MT5
            else "ORDER_TIME_GTC"
        )

        req["type_time"] = to_mt5_const(
            req["type_time"],
            default,
        )

    if "type_filling" in req and isinstance(
        req["type_filling"],
        str,
    ):
        default = (
            mt5.ORDER_FILLING_IOC
            if _HAS_MT5
            else "ORDER_FILLING_IOC"
        )

        req["type_filling"] = to_mt5_const(
            req["type_filling"],
            default,
        )


# ----------------------------------------------------------------------
# 4) High-level parameter conversion
# ----------------------------------------------------------------------

def convert_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert high-level command parameters.

    Supported conversions:
        timeframe
        flags
        order_type
        action
        date_from
        date_to
        request.*

    The input dictionary is never modified directly.
    """
    if not isinstance(params, dict):
        raise ValueError("params must be a dictionary")

    out = dict(params)

    if "timeframe" in out and isinstance(
        out["timeframe"],
        str,
    ):
        default = (
            mt5.TIMEFRAME_H4
            if _HAS_MT5
            else "TIMEFRAME_H4"
        )

        out["timeframe"] = to_mt5_const(
            out["timeframe"],
            default,
        )

    if "flags" in out and isinstance(
        out["flags"],
        str,
    ):
        default = (
            mt5.COPY_TICKS_ALL
            if _HAS_MT5
            else "COPY_TICKS_ALL"
        )

        out["flags"] = to_mt5_const(
            out["flags"],
            default,
        )

    if "order_type" in out and isinstance(
        out["order_type"],
        str,
    ):
        default = (
            mt5.ORDER_TYPE_BUY
            if _HAS_MT5
            else "ORDER_TYPE_BUY"
        )

        out["order_type"] = to_mt5_const(
            out["order_type"],
            default,
        )

    if "action" in out and isinstance(
        out["action"],
        str,
    ):
        out["action"] = out["action"].lower()

    if "date_from" in out and isinstance(
        out["date_from"],
        str,
    ):
        out["date_from"] = parse_iso_dt(
            out["date_from"]
        )

    if "date_to" in out and isinstance(
        out["date_to"],
        str,
    ):
        out["date_to"] = parse_iso_dt(
            out["date_to"]
        )

    if isinstance(out.get("request"), dict):
        out["request"] = dict(out["request"])

        convert_request_fields(
            out["request"]
        )

    return out


# ----------------------------------------------------------------------
# 5) Safe serialization
# ----------------------------------------------------------------------

def safe_serialize(
    obj: Any,
    _depth: int = 0,
    _limit: int = 3,
) -> Any:
    """
    Safely convert an object into JSON-compatible data.

    Supported:
        datetime
        date
        time
        namedtuple
        dict
        list
        tuple
        numpy scalar
        pandas.DataFrame
        pandas.Series

    A maximum recursion depth is used to prevent problematic
    deeply nested structures.
    """

    if _depth > _limit:
        return str(obj)

    if isinstance(
        obj,
        (
            dt.datetime,
            dt.date,
            dt.time,
        ),
    ):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    if hasattr(obj, "_asdict"):
        try:
            return {
                str(key): safe_serialize(
                    value,
                    _depth + 1,
                    _limit,
                )
                for key, value in obj._asdict().items()
            }
        except Exception:
            return str(obj)

    if isinstance(obj, dict):
        return {
            str(key): safe_serialize(
                value,
                _depth + 1,
                _limit,
            )
            for key, value in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [
            safe_serialize(
                value,
                _depth + 1,
                _limit,
            )
            for value in obj
        ]

    try:
        import numpy as np  # type: ignore

        if isinstance(obj, np.generic):
            return obj.item()

    except Exception:
        pass

    try:
        import pandas as pd  # type: ignore

        if isinstance(obj, pd.DataFrame):
            return {
                "dataframe_preview": obj.head(50).to_dict(
                    orient="records"
                ),
                "columns": list(obj.columns),
                "rows": int(
                    getattr(
                        obj,
                        "shape",
                        [0, 0],
                    )[0]
                ),
            }

        if isinstance(obj, pd.Series):
            return {
                str(key): safe_serialize(
                    value,
                    _depth + 1,
                    _limit,
                )
                for key, value in obj.to_dict().items()
            }

    except Exception:
        pass

    try:
        json.dumps(obj)
        return obj

    except Exception:
        return str(obj)


__all__ = [
    "parse_iso_dt",
    "to_mt5_const",
    "convert_request_fields",
    "convert_params",
    "safe_serialize",
]