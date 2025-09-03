# kafka_listener.py
# =========================
# مصرف‌کنندهٔ Kafka برای دریافت دستورات،
# تبدیل امن پارامترها، فراخوانی متدهای Mt5_Manager،
# و ارسال نتایج از طریق KafkaResponder.
# =========================

from __future__ import annotations                                    # تایپ‌هینت‌های مدرن
from typing import Any, Dict, List, Optional                          # تایپ‌ها
import json                                                           # پارس/سریال‌سازی
import ast                                                            # fallback پارس
import logging                                                        # لاگ‌گذاری
import signal                                                         # مدیریت سیگنال‌ها
from uuid import uuid4                                                # ساخت corr_id در صورت نبود
from time import perf_counter                                          # اندازه‌گیری زمان اجرا

from confluent_kafka import Consumer, KafkaError, KafkaException       # Kafka Consumer
from meta_trader_manager import Mt5_Manager                            # کلاس اصلی MT5
from config_logging import AppSettings                                 # تنظیمات
from kafka_responder import KafkaResponder                             # پاسخ‌دهنده
from mt5_utils import convert_params, safe_serialize                   # ابزارهای تبدیل/سریال‌سازی

LOGGER = logging.getLogger("KafkaListener")                            # لاگر ماژول

# نگاشت key پیام به کلاس مربوطه
CLASS_MAP: Dict[str, Any] = {
    "Mt5_Manager": Mt5_Manager,                                        # می‌توانید بعداً کلاس‌های دیگری اضافه کنید
}

def parse_json_or_literal(text: str):
    """پارس ورودی به JSON؛ در صورت خطا، literal_eval برای انعطاف بیشتر."""
    try:
        return json.loads(text)                                        # تلاش اول: JSON
    except json.JSONDecodeError:
        return ast.literal_eval(text)                                  # تلاش دوم: literal_eval (کنترل‌شده)

class KafkaListener:
    """شنوندهٔ کافکا که دستورات را می‌گیرد و نتایج را برمی‌گرداند."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings                                       # نگهداشت تنظیمات
        self.consumer: Optional[Consumer] = None                       # مصرف‌کننده کافکا
        self.responder = KafkaResponder(settings)                      # تولیدکنندهٔ پاسخ
        self.running: bool = False                                     # وضعیت حلقهٔ اصلی
        self.manager_instances: Dict[str, Any] = {}                    # نمونه‌های کلاس‌ها
        self._init_managers()                                          # آماده‌سازی نمونه‌ها
        self._init_consumer()                                          # راه‌اندازی کافکا

    def _init_managers(self) -> None:
        """ساخت نمونه از کلاس‌های تعریف‌شده در CLASS_MAP."""
        for name, cls in CLASS_MAP.items():                            # عبور از روی همه کلاس‌ها
            try:
                self.manager_instances[name] = cls()                   # ساخت نمونه
                LOGGER.info("Manager instance created: %s", name)      # لاگ موفقیت
            except Exception as e:
                LOGGER.exception("Failed to instantiate manager '%s': %s", name, e)  # لاگ خطا

    def _init_consumer(self) -> None:
        """ایجاد Consumer و اتصال به تاپیک ورودی."""
        try:
            conf = {
                "bootstrap.servers": self.settings.kafka_servers,      # آدرس کافکا
                "group.id": self.settings.kafka_group_id,              # گروه مصرف‌کننده
                "auto.offset.reset": "earliest",                       # از ابتدا اگر offset نبود
            }
            self.consumer = Consumer(conf)                             # ساخت Consumer
            self.consumer.subscribe([self.settings.kafka_request_topic])  # عضویت در تاپیک
            LOGGER.info("Connected to Kafka. servers=%s topic=%s group=%s",
                        self.settings.kafka_servers,
                        self.settings.kafka_request_topic,
                        self.settings.kafka_group_id)
        except KafkaException as e:
            LOGGER.error("Failed to connect to Kafka: %s", e)          # در صورت خطا لاگ
            self.consumer = None                                       # Consumer نامعتبر

    def _register_signal_handlers(self) -> None:
        """ثبت هندلرهای SIGINT و SIGTERM برای خاموشی ایمن."""
        def handle_sig(_signum, _frame):
            LOGGER.info("Signal received. Stopping gracefully...")     # لاگ دریافت سیگنال
            self.running = False                                       # خروج از حلقه

        try:
            signal.signal(signal.SIGINT, handle_sig)                   # Ctrl+C
            signal.signal(signal.SIGTERM, handle_sig)                  # kill
        except Exception:
            LOGGER.debug("Signal handlers not supported on this platform.")  # برخی سیستم‌ها

    def _send_enveloped(
        self,
        class_name: str, corr_id: str, idx: int, method_name: str,
        status: str, result_obj: Any, meta: Optional[Dict[str, Any]] = None
    ) -> None:
        """بسته‌بندی پاسخ در یک Envelope استاندارد و ارسال با KafkaResponder."""
        payload = {                                                    # ساخت بدنهٔ استاندارد
            "schema": "Mt5ResultV1",                                   # نسخه اسکیمای پاسخ
            "corr_id": corr_id,                                        # شناسه هم‌بستگی
            "class": class_name,                                       # نام کلاس مقصد
            "method": method_name,                                     # نام متد فراخوانی‌شده
            "request_index": idx,                                      # شماره دستور داخل آرایه
            "status": status,                                          # ok | error
            "result": safe_serialize(result_obj),                      # سریال‌سازی امن نتیجه
        }
        if meta:                                                       # افزودن متاداده اختیاری
            payload["meta"] = safe_serialize(meta)
        self.responder.send_result(                                    # ارسال پاسخ
            corr_id=corr_id, payload_obj=payload, key=class_name
        )

    def listen(self) -> None:
        """حلقهٔ اصلی شنود و پردازش پیام‌ها."""
        if not self.consumer:                                          # ارزیابی صحت Consumer
            LOGGER.error("Consumer not initialized")
            return

        self.running = True                                            # شروع حلقه
        self._register_signal_handlers()                               # ثبت سیگنال‌ها
        LOGGER.info("Listening for messages...")                       # لاگ شروع

        try:
            while self.running:                                        # حلقه تا زمان توقف
                msg = self.consumer.poll(1.0)                          # پول با تایم‌اوت ۱ ثانیه
                if msg is None:                                        # اگر پیامی نیست
                    continue                                           # تکرار
                if msg.error():                                        # اگر خطای کافکا
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        LOGGER.warning("Kafka error: %s", msg.error()) # هشدار
                    continue

                raw_key = (msg.key().decode("utf-8") if msg.key() else "").strip().strip('"').strip("'")  # کلید
                raw_value = msg.value().decode("utf-8") if msg.value() else ""                              # مقدار
                headers_in = dict((k, (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v))
                                  for k, v in (msg.headers() or []))                                        # هدرهای ورودی
                corr_id = headers_in.get("corr_id") or headers_in.get("correlation_id") or str(uuid4())     # corr_id

                LOGGER.info("Received message | key=%r len=%d corr_id=%s",
                            raw_key, len(raw_value), corr_id)                                               # لاگ دریافت

                self._process_one(raw_key, raw_value, corr_id, headers_in,                                  # پردازش
                                   meta={"partition": msg.partition(), "offset": msg.offset()})

        except KeyboardInterrupt:
            LOGGER.info("KeyboardInterrupt, stopping...")                                                   # توقف با Ctrl+C
        except Exception:
            LOGGER.exception("Unexpected error in listen loop")                                             # خطای غیرمنتظره
        finally:
            try:
                self.consumer.close()                                                                       # بستن امن Consumer
            except Exception:
                pass

    def _process_one(
        self, class_name: str, raw_value: str, corr_id: str,
        in_headers: Dict[str, Any], meta: Dict[str, Any]
    ) -> None:
        """پردازش یک پیام: پارس، تطبیق کلاس/متد، تبدیل پارامترها، اجرا و پاسخ."""
        if class_name not in self.manager_instances:                                                        # وجود کلاس؟
            err = f"Class '{class_name}' not found. Available: {list(self.manager_instances.keys())}"       # پیام خطا
            LOGGER.error(err)
            self._send_enveloped(class_name or "UNKNOWN", corr_id, -1, "N/A", "error", {"error": err})      # پاسخ خطا
            return

        manager = self.manager_instances[class_name]                                                        # نمونه کلاس

        try:
            obj = parse_json_or_literal(raw_value)                                                          # پارس value
        except Exception as e:
            err = f"Parse error: {e}"                                                                       # خطای پارس
            LOGGER.error(err)
            self._send_enveloped(class_name, corr_id, -1, "N/A", "error", {"error": err})                   # پاسخ خطا
            return

        commands: List[Dict[str, Any]] = obj if isinstance(obj, list) else [obj]                           # لیست‌سازی

        for idx, command in enumerate(commands, start=1):                                                   # روی دستورات
            t0 = perf_counter()                                                                             # شروع زمان‌سنج
            if not isinstance(command, dict):                                                               # اعتبارسنجی
                warn = f"Command #{idx} is not a dict"
                LOGGER.warning(warn)
                self._send_enveloped(class_name, corr_id, idx, "N/A", "error", {"error": warn})             # پاسخ خطا
                continue

            method_name = command.get("method")                                                             # نام متد
            params = command.get("params", {}) or {}                                                        # پارامترها
            if not method_name or not hasattr(manager, method_name):                                        # وجود متد؟
                err = f"Method '{method_name}' not found in '{class_name}'"
                LOGGER.error(err)
                self._send_enveloped(class_name, corr_id, idx, method_name or "N/A", "error", {"error": err})
                continue

            try:
                conv_params = convert_params(params)                                                         # تبدیل امن
            except Exception as e:
                err = f"Parameter conversion failed: {e}"                                                    # خطای تبدیل
                LOGGER.exception(err)
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": err})
                continue

            try:
                LOGGER.info("Calling %s.%s | params=%s", class_name, method_name, safe_serialize(conv_params))  # لاگ فراخوانی
                result = getattr(manager, method_name)(**conv_params)                                        # اجرای متد
                LOGGER.info("Result of %s: %s", method_name, safe_serialize(result))                         # لاگ نتیجه
                elapsed = int((perf_counter() - t0) * 1000)                                                  # محاسبه زمان

                self._send_enveloped(                                                                        # ارسال پاسخ ok
                    class_name, corr_id, idx, method_name, "ok", result,
                    meta={"elapsed_ms": elapsed, "in_headers": in_headers, "src": meta}
                )
            except TypeError as te:
                err = f"Invalid parameters for {class_name}.{method_name}: {te}"                             # خطای تایپی پارامتر
                LOGGER.error(err)
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": err})
            except Exception as e:
                LOGGER.exception("Unhandled error calling %s.%s", class_name, method_name)                   # خطای غیرمنتظره
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": str(e)})
