# main.py
# شنونده‌ی Kafka با پردازش داینامیک پیام‌ها و فراخوانی Mt5_Manager
# + ارسال نتیجه‌ی هر دستور به Kafka روی تاپیک agent-recive
# امکانات:
# - JSON/Human logging + فایل لاگ چرخشی
# - تبدیل امن پارامترها و تاریخ‌ها به MT5/UTC
# - correlation_id برای ردگیری end-to-end
# - chunking پیام‌های حجیم (تقسیم به چند پارت)
# - هدرهای Kafka برای سرهم‌سازی (seq/total/schema/...)
# - فشرده‌سازی سطح Producer (compression.type)
# - idempotent producer و acks=all برای تحویل مطمئن

from __future__ import annotations

import json
import os
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
import datetime
import ast
from typing import Any, Dict, List, Optional, Iterable, Tuple
from uuid import uuid4
from time import perf_counter

from confluent_kafka import Consumer, Producer, KafkaException, KafkaError
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
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    use_json = os.getenv("LOG_JSON", "false").strip().lower() in ("1", "true", "yes")
    log_file = os.getenv("LOG_FILE", "logs/app.log")
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    backups = int(os.getenv("LOG_BACKUPS", "10"))

    root = logging.getLogger()
    root.setLevel(log_level)

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
            if hasattr(record, "extra") and isinstance(record.extra, dict):
                payload.update(record.extra)
            return _json.dumps(payload, ensure_ascii=False)

    human_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = JsonFormatter()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(json_fmt if use_json else human_fmt)
    root.addHandler(console)

    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    except Exception:
        pass

    file_handler = RotatingFileHandler(
        filename=log_file, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_fmt if use_json else human_fmt)
    root.addHandler(file_handler)

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
REQUEST_TOPIC = os.getenv("KAFKA_TOPIC", "agent-send")           # تاپیک دریافتی
RESPONSE_TOPIC = os.getenv("KAFKA_RESPONSE_TOPIC", "agent-recive")  # تاپیک پاسخ

GROUP_ID = os.getenv("KAFKA_GROUP_ID", "kafka_listener_group")

# تنظیمات Producer برای تحویل مطمئن و فشرده‌سازی
PRODUCER_CONFIG = {
    "bootstrap.servers": KAFKA_SERVERS,
    "enable.idempotence": True,         # تحویل exactly-once در سطح پارتیشن
    "acks": "all",
    "compression.type": os.getenv("KAFKA_COMPRESSION", "zstd"),  # zstd|lz4|gzip|snappy
    "linger.ms": int(os.getenv("KAFKA_LINGER_MS", "10")),        # میکرو-batching
    "batch.num.messages": int(os.getenv("KAFKA_BATCH_NUM", "1000")),
    "retries": 1000000,
    "max.in.flight.requests.per.connection": int(os.getenv("KAFKA_MAX_INFLIGHT", "5")),
    # می‌توانید message.max.bytes را در Producer و Broker هماهنگ کنید
}

# حداکثر اندازه هر پارت (قبل از فشرده‌سازی Producer) — 900KB امن برای حد پیش‌فرض 1MB
MAX_PART_BYTES = int(os.getenv("KAFKA_RESPONSE_MAX_PART_BYTES", str(900 * 1024)))

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
    تبدیل نتایج به فرم JSON-safe برای لاگ/ارسال:
      datetime → ISO
      namedtuple._asdict → dict
      dict/list → بازگشتی
      numpy/pandas → خلاصه
      سایر موارد → str(obj) در صورت نیاز
    """
    if _depth > _limit:
        return str(obj)

    import datetime as _dt
    if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
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
        import numpy as np
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass

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

    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

# =========================
# تولیدکننده‌ی پاسخ به Kafka
# =========================

class KafkaResponder:
    """
    Producer امن برای ارسال پاسخ‌ها به Kafka با:
    - chunking پیام‌های حجیم (part/total)
    - هدرهای seq/total/schema/corr_id
    - فشرده‌سازی سطح Producer
    """

    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.producer = Producer(PRODUCER_CONFIG)
        LOGGER.info("KafkaResponder initialized for topic=%s", topic)

    @staticmethod
    def _chunk_bytes(data: bytes, max_part: int) -> List[bytes]:
        """تقسیم آرایه بایت به پارت‌های حداکثر max_part بایتی."""
        return [data[i:i + max_part] for i in range(0, len(data), max_part)] or [b""]

    def _delivery_cb(self, err, msg) -> None:
        """کالبک تحویل هر پارت؛ لاگ خطا در صورت نیاز."""
        if err is not None:
            LOGGER.error("Delivery failed: %s", err)
        else:
            LOGGER.debug("Delivered to %s [%d] @%d", msg.topic(), msg.partition(), msg.offset())

    def send_result(
        self,
        key: str,
        corr_id: str,
        payload_obj: Dict[str, Any],
        schema: str = "Mt5ResultV1",
        headers_extra: Optional[List[Tuple[str, bytes]]] = None,
    ) -> None:
        """
        ارسال نتیجه به Kafka:
        - payload_obj → JSON → بایت
        - chunking → multi-part
        - هدرها: corr_id/seq/total/schema/content_type
        """
        # تبدیل به JSON بایت با UTF-8
        data = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        parts = self._chunk_bytes(data, MAX_PART_BYTES)
        total = len(parts)

        for i, part in enumerate(parts, start=1):
            # هدرهای استاندارد برای سرهم‌سازی سمت گیرنده
            headers = [
                ("corr_id", corr_id.encode("utf-8")),
                ("schema", schema.encode("utf-8")),
                ("seq", str(i).encode("utf-8")),
                ("total", str(total).encode("utf-8")),
                ("content_type", b"application/json"),
                ("encoding", b"utf-8"),
            ]
            if headers_extra:
                headers.extend(headers_extra)

            # تولید پیام
            self.producer.produce(
                topic=self.topic,
                key=key.encode("utf-8"),
                value=part,
                headers=headers,
                on_delivery=self._delivery_cb,
            )

        # flush برای اطمینان از ارسال
        self.producer.flush()

# =========================
# شنونده کافکا
# =========================

CLASS_MAP: Dict[str, Any] = {
    "Mt5_Manager": Mt5_Manager,
}

class KafkaListener:
    def __init__(self) -> None:
        self.consumer: Optional[Consumer] = None
        self.producer: Optional[KafkaResponder] = None
        self.running: bool = False
        self.manager_instances: Dict[str, Any] = {}
        self._init_managers()
        self._init_consumer()
        self._init_producer()

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
                # اگر نیاز به هدرهای ورودی داری، confluent_kafka به صورت پیش‌فرض پشتیبانی می‌کند
            }
            self.consumer = Consumer(conf)
            self.consumer.subscribe([REQUEST_TOPIC])
            LOGGER.info("Connected to Kafka. servers=%s topic=%s group=%s",
                        KAFKA_SERVERS, REQUEST_TOPIC, GROUP_ID)
        except KafkaException as e:
            LOGGER.error("Failed to connect to Kafka: %s", e)
            self.consumer = None

    def _init_producer(self) -> None:
        try:
            self.producer = KafkaResponder(RESPONSE_TOPIC)
        except Exception as e:
            LOGGER.exception("Failed to init KafkaResponder: %s", e)
            self.producer = None

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

        if not self.producer:
            LOGGER.error("Producer not initialized, cannot send responses.")
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

                # خواندن key/value
                raw_value = msg.value().decode("utf-8") if msg.value() else ""
                raw_key = msg.key().decode("utf-8") if msg.key() else ""
                cleaned_key = raw_key.strip().strip('"').strip("'")

                # استخراج هدرهای ورودی (اگر فرستاده شده بود)
                in_headers = dict((k, (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v))
                                  for k, v in (msg.headers() or []))

                # correlation_id ورودی اگر هست، نگه داریم؛ وگرنه جدید بسازیم
                corr_id = in_headers.get("corr_id") or in_headers.get("correlation_id") or str(uuid4())

                LOGGER.info("Received message | key=%r value_len=%d corr_id=%s",
                            cleaned_key, len(raw_value), corr_id)

                # پردازش پیام
                self.process_message(cleaned_key, raw_value, corr_id, in_headers,
                                     src_meta={"partition": msg.partition(), "offset": msg.offset()})

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

    def _send_response(
        self,
        class_name: str,
        corr_id: str,
        request_index: int,
        method_name: str,
        status: str,
        result_obj: Any,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """پکیج کردن پاسخ و ارسال به تاپیک agent-recive با chunking."""
        if not self.producer:
            LOGGER.error("Producer not initialized, cannot send responses.")
            return

        # بدنه‌ی پاسخ: ساخت یک envelope استاندارد
        payload = {
            "schema": "Mt5ResultV1",
            "corr_id": corr_id,
            "class": class_name,
            "method": method_name,
            "request_index": request_index,
            "status": status,  # ok | error
            "result": safe_serialize(result_obj),
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
        }
        if extra_meta:
            payload["meta"] = safe_serialize(extra_meta)

        # کلید پاسخ را هم‌نام با کلاس نگه می‌داریم تا مصرف‌کننده بتواند فیلتر کند
        key = class_name

        # ارسال با Producer (تقسیم به پارت‌ها در صورت بزرگی)
        self.producer.send_result(
            key=key,
            corr_id=corr_id,
            payload_obj=payload,
            schema="Mt5ResultV1",
            headers_extra=None,  # اگر هدر اضافه‌ای لازم بود، اینجا بده
        )

    def process_message(
        self,
        class_name: str,
        raw_value: str,
        corr_id: str,
        in_headers: Dict[str, Any],
        src_meta: Dict[str, Any],
    ) -> None:
        # 1) یافتن نمونه کلاس از روی key
        if class_name not in self.manager_instances:
            err = f"Class instance for key '{class_name}' not found. Available: {list(self.manager_instances.keys())}"
            LOGGER.error(err)
            self._send_response(class_name or "UNKNOWN", corr_id, -1, "N/A", "error", {"error": err})
            return
        instance = self.manager_instances[class_name]

        # 2) پارس پیام
        try:
            obj = parse_json_or_literal(raw_value)
        except Exception as e:
            err = f"Parse error: {e}"
            LOGGER.error(err)
            self._send_response(class_name, corr_id, -1, "N/A", "error", {"error": err})
            return

        if not isinstance(obj, list):
            obj = [obj]

        # 3) حلقه روی دستورات
        for idx, command in enumerate(obj, start=1):
            start = perf_counter()

            if not isinstance(command, dict):
                warn = f"Command #{idx} is not a dict. Skipping."
                LOGGER.warning(warn)
                self._send_response(class_name, corr_id, idx, "N/A", "error", {"error": warn})
                continue

            method_name = command.get("method")
            params = command.get("params", {}) or {}

            if not method_name or not hasattr(instance, method_name):
                err = f"Method '{method_name}' not found in class '{class_name}'."
                LOGGER.error(err)
                self._send_response(class_name, corr_id, idx, method_name or "N/A", "error", {"error": err})
                continue

            # 4) تبدیل امن پارامترها
            try:
                conv_params = convert_params(params)
            except Exception as e:
                err = f"Parameter conversion failed for command #{idx}: {e}"
                LOGGER.exception(err)
                self._send_response(class_name, corr_id, idx, method_name, "error", {"error": err})
                continue

            # 5) فراخوانی متد
            method = getattr(instance, method_name)
            try:
                LOGGER.info("Calling %s.%s | params=%s", class_name, method_name, safe_serialize(conv_params))
                result = method(**conv_params)
                LOGGER.info("Result of %s: %s", method_name, safe_serialize(result))

                elapsed_ms = int((perf_counter() - start) * 1000)
                # 6) ارسال پاسخ "ok"
                self._send_response(
                    class_name, corr_id, idx, method_name, "ok", result,
                    extra_meta={"elapsed_ms": elapsed_ms, "src": src_meta, "in_headers": in_headers},
                )

            except TypeError as te:
                err = f"Invalid parameters for {class_name}.{method_name}: {te}"
                LOGGER.error(err)
                self._send_response(class_name, corr_id, idx, method_name, "error", {"error": err})
            except Exception as e:
                LOGGER.exception("Unhandled error calling %s.%s", class_name, method_name)
                self._send_response(class_name, corr_id, idx, method_name, "error", {"error": str(e)})

# =========================
# نقطه شروع
# =========================

def main() -> None:
    setup_logging()
    listener = KafkaListener()
    listener.listen()

if __name__ == "__main__":
    main()
