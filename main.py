# main.py
# شنونده‌ی Kafka با پردازش داینامیک پیام‌ها و فراخوانی Mt5_Manager
# نسخه‌ی بهینه با JSON/Human logging، فایل لاگ چرخشی، تبدیل امن پارامترها،
# مدیریت سیگنال و سازگاری کامل با فرمت پیام‌های فعلی.

from __future__ import annotations

import json
import os
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
import datetime
import ast
from typing import Any, Dict, List, Optional

from confluent_kafka import Consumer, KafkaException, KafkaError
import MetaTrader5 as mt5
import pytz

from meta_trader_manager import Mt5_Manager  # کلاس مدیریتی شما

# =========================
# پیکربندی و لاگ‌گذاری
# =========================

def setup_logging() -> None:
    """
    راه‌اندازی لاگ‌گذاری:
      - خروجی کنسول (خوانا یا JSON)
      - خروجی فایل با Rotation
    ENV:
      LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL
      LOG_JSON=true|false
      LOG_FILE=logs/app.log
      LOG_MAX_BYTES=10485760
      LOG_BACKUPS=10
    """
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    use_json = os.getenv("LOG_JSON", "false").strip().lower() in ("1", "true", "yes")
    log_file = os.getenv("LOG_FILE", "logs/app.log")
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    backups = int(os.getenv("LOG_BACKUPS", "10"))

    root = logging.getLogger()
    root.setLevel(log_level)

    # پاک کردن هندلرهای قبلی برای جلوگیری از تکرار
    for h in list(root.handlers):
        root.removeHandler(h)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import json as _json
            payload = {
                "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                payload["exc"] = self.formatException(record.exc_info)
            # اجازه بده اگر کسی فیلد extra={'foo': 'bar'} ست کرد، اضافه شود
            if hasattr(record, "extra") and isinstance(record.extra, dict):
                payload.update(record.extra)
            return _json.dumps(payload, ensure_ascii=False)

    human_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = JsonFormatter()

    # کنسول
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(json_fmt if use_json else human_fmt)
    root.addHandler(console)

    # فایل با Rotation
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    except Exception:
        pass

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_fmt if use_json else human_fmt)
    root.addHandler(file_handler)

    # کم‌کردن پرگویی برخی کتابخانه‌ها
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    LOGGER.info(
        "Logging initialized (json=%s, file=%s, level=%s, rotation=%s bytes x %s backups)",
        use_json, log_file, log_level, max_bytes, backups
    )


LOGGER = logging.getLogger("KafkaListener")

# =========================
# پیکربندی از محیط با fallback
# =========================

KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "192.168.1.254:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "agent-send")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "kafka_listener_group")

# نگاشت نام کلاس → کلاس. کلید پیام Kafka باید با این نام‌ها بخورد.
CLASS_MAP: Dict[str, Any] = {
    "Mt5_Manager": Mt5_Manager,
}

# =========================
# ابزارهای کمکی تبدیل و سریال‌سازی
# =========================

UTC_TZ = pytz.timezone("Etc/UTC")


def parse_json_or_literal(text: str) -> Any:
    """ابتدا json.loads، در صورت خطا ast.literal_eval برای انعطاف بیشتر."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except Exception as e:
            LOGGER.error("Unable to parse message payload as JSON or Python literal: %s", e)
            raise


def parse_iso_dt(dt: str) -> datetime.datetime:
    """پارس ISO و تبدیل به datetime آگاه از UTC. از 'Z' نیز پشتیبانی می‌کند."""
    if dt.endswith("Z"):
        dt = dt[:-1] + "+00:00"
    try:
        dt_obj = datetime.datetime.fromisoformat(dt)
    except Exception:
        dt_obj = datetime.datetime.fromisoformat(dt.replace(" ", "T"))
    if dt_obj.tzinfo is None:
        return UTC_TZ.localize(dt_obj)
    return dt_obj.astimezone(UTC_TZ)


def to_mt5_const(name: str, default: Any) -> Any:
    """نگاشت امن رشته به کانستنت MT5 (در صورت نبودن، default)."""
    return getattr(mt5, name, default)


def convert_request_fields(req: Dict[str, Any]) -> None:
    """تبدیل فیلدهای داخل request به کانستنت‌های MT5 در صورت رشته بودن."""
    if "action" in req and isinstance(req["action"], str):
        req["action"] = to_mt5_const(req["action"], mt5.TRADE_ACTION_DEAL)
    if "type" in req and isinstance(req["type"], str):
        req["type"] = to_mt5_const(req["type"], mt5.ORDER_TYPE_BUY)
    if "type_time" in req and isinstance(req["type_time"], str):
        req["type_time"] = to_mt5_const(req["type_time"], mt5.ORDER_TIME_GTC)
    if "type_filling" in req and isinstance(req["type_filling"], str):
        req["type_filling"] = to_mt5_const(req["type_filling"], mt5.ORDER_FILLING_IOC)


def convert_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    تبدیل امن پارامترهای سطح بالا:
      timeframe/flags/order_type → کانستنت
      action → lowercase
      date_from/date_to → datetime (UTC-aware)
      request.* → کانستنت‌سازی
    """
    out = dict(params)

    if "timeframe" in out and isinstance(out["timeframe"], str):
        out["timeframe"] = to_mt5_const(out["timeframe"], mt5.TIMEFRAME_H4)

    if "flags" in out and isinstance(out["flags"], str):
        out["flags"] = to_mt5_const(out["flags"], mt5.COPY_TICKS_ALL)

    if "order_type" in out and isinstance(out["order_type"], str):
        out["order_type"] = to_mt5_const(out["order_type"], mt5.ORDER_TYPE_BUY)

    if "action" in out and isinstance(out["action"], str):
        out["action"] = out["action"].lower()

    if "date_from" in out and isinstance(out["date_from"], str):
        out["date_from"] = parse_iso_dt(out["date_from"])
    if "date_to" in out and isinstance(out["date_to"], str):
        out["date_to"] = parse_iso_dt(out["date_to"])

    if "request" in out and isinstance(out["request"], dict):
        convert_request_fields(out["request"])

    return out


def safe_serialize(obj: Any, _depth: int = 0, _limit: int = 3) -> Any:
    """
    تبدیل نتایج به فرم JSON-safe برای لاگ:
      datetime → ISO
      namedtuple._asdict → dict
      dict/list → بازگشتی
      numpy/pandas → خلاصه
      سایر موارد → str(obj) در صورت نیاز
    """
    if _depth > _limit:
        return str(obj)

    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    if hasattr(obj, "_asdict"):
        try:
            return {k: safe_serialize(v, _depth + 1, _limit) for k, v in obj._asdict().items()}
        except Exception:
            return str(obj)

    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, _depth + 1, _limit) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [safe_serialize(v, _depth + 1, _limit) for v in obj]

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
                "dataframe_preview": obj.head(10).to_dict(orient="records"),
                "columns": list(obj.columns),
                "rows": int(getattr(obj, "shape", [0, 0])[0]),
            }
        if isinstance(obj, pd.Series):
            return obj.to_dict()
    except Exception:
        pass

    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

# =========================
# شنونده کافکا
# =========================

class KafkaListener:
    def __init__(self) -> None:
        self.consumer: Optional[Consumer] = None
        self.running: bool = False
        self.manager_instances: Dict[str, Any] = {}
        self._init_managers()
        self._init_consumer()

    def _init_managers(self) -> None:
        for name, cls in CLASS_MAP.items():
            try:
                self.manager_instances[name] = cls()
                LOGGER.info("Manager instance created: %s", name)
            except Exception as e:
                LOGGER.exception("Failed to instantiate manager '%s': %s", name, e)

    def _init_consumer(self) -> None:
        try:
            conf = {
                "bootstrap.servers": KAFKA_SERVERS,
                "group.id": GROUP_ID,
                "auto.offset.reset": "earliest",
            }
            self.consumer = Consumer(conf)
            self.consumer.subscribe([TOPIC])
            LOGGER.info("Connected to Kafka. servers=%s topic=%s group=%s", KAFKA_SERVERS, TOPIC, GROUP_ID)
        except KafkaException as e:
            LOGGER.error("Failed to connect to Kafka: %s", e)
            self.consumer = None

    def _shutdown(self) -> None:
        if self.consumer:
            try:
                self.consumer.close()
                LOGGER.info("Kafka consumer closed.")
            except Exception:
                LOGGER.exception("Error while closing consumer.")
        self.consumer = None

    def listen(self) -> None:
        if not self.consumer:
            LOGGER.error("Consumer not initialized, cannot listen.")
            return

        self.running = True
        self._register_signal_handlers()
        LOGGER.info("Starting to listen for messages...")

        try:
            while self.running:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        LOGGER.warning("Kafka error: %s", msg.error())
                    continue

                raw_value = msg.value().decode("utf-8") if msg.value() else ""
                raw_key = msg.key().decode("utf-8") if msg.key() else ""
                cleaned_key = raw_key.strip().strip('"').strip("'")

                LOGGER.info("Received message | key=%r value_len=%d", cleaned_key, len(raw_value))
                self.process_message(cleaned_key, raw_value)

        except KeyboardInterrupt:
            LOGGER.info("KeyboardInterrupt received. Stopping...")
        except Exception:
            LOGGER.exception("Unexpected error in listen loop.")
        finally:
            self._shutdown()

    def _register_signal_handlers(self) -> None:
        def handle_sigterm(signum, frame):
            LOGGER.info("Signal %s received. Shutting down gracefully...", signum)
            self.running = False

        try:
            signal.signal(signal.SIGINT, handle_sigterm)
            signal.signal(signal.SIGTERM, handle_sigterm)
        except Exception:
            LOGGER.debug("Signal handlers not fully supported on this platform.")

    def process_message(self, class_name: str, raw_value: str) -> None:
        # 1) یافتن نمونه کلاس از روی key
        if class_name not in self.manager_instances:
            LOGGER.error("Class instance for key '%s' not found. Available: %s",
                         class_name, list(self.manager_instances.keys()))
            return
        instance = self.manager_instances[class_name]

        # 2) پارس پیام
        try:
            obj = parse_json_or_literal(raw_value)
        except Exception:
            LOGGER.error("Skipping message due to parse error.")
            return

        # پیام تکی را هم به لیست تبدیل می‌کنیم
        if not isinstance(obj, list):
            obj = [obj]

        # 3) حلقه روی دستورات
        for idx, command in enumerate(obj, start=1):
            if not isinstance(command, dict):
                LOGGER.warning("Command #%d is not a dict. Skipping: %r", idx, command)
                continue

            method_name = command.get("method")
            params = command.get("params", {}) or {}

            if not method_name or not hasattr(instance, method_name):
                LOGGER.error("Method '%s' not found in class '%s'.", method_name, class_name)
                continue

            # 4) تبدیل امن پارامترها
            try:
                conv_params = convert_params(params)
            except Exception:
                LOGGER.exception("Parameter conversion failed for command #%d: %r", idx, params)
                continue

            # 5) فراخوانی متد
            method = getattr(instance, method_name)
            try:
                LOGGER.info("Calling %s.%s | params=%s", class_name, method_name, safe_serialize(conv_params))
                result = method(**conv_params)
                LOGGER.info("Result of %s: %s", method_name, safe_serialize(result))
            except TypeError as te:
                LOGGER.error("Invalid parameters for %s.%s: %s | params=%s",
                             class_name, method_name, te, safe_serialize(conv_params))
            except Exception:
                LOGGER.exception("Unhandled error calling %s.%s", class_name, method_name)

# =========================
# نقطه شروع
# =========================

def main() -> None:
    setup_logging()
    listener = KafkaListener()
    listener.listen()

if __name__ == "__main__":
    main()
