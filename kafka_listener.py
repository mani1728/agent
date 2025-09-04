# -*- coding: utf-8 -*-
"""
kafka_listener.py
-----------------
شنوندهٔ Kafka با تکیه بر config.json (هات‌ریلُد) برای:
- دریافت دستورات (value به‌صورت JSON یا literal)
- تطبیق کلاس/متد و تبدیل امن پارامترها
- فراخوانی Mt5_Manager و ...
- ارسال نتیجه توسط KafkaResponder

ویژگی‌ها:
- بدون وابستگی به ENV؛ همه‌چیز از cfg() ← config.json
- هات‌ریلُد تاپیک‌ها: اگر "kafka.topics.commands" در حین اجرا تغییر کند،
  بدون ری‌استارت برنامه resubscribe انجام می‌شود.
- احراز هویت اختیاری: اگر auth.token_required=true، توکن از هدر یا payload برداشته و
  با auth.tokens اعتبارسنجی می‌شود.
"""

from __future__ import annotations  # ✅ تایپ‌هینت‌های مدرن (Python 3.8+)

# ---- ایمپورت‌های استاندارد
import json                       # ✅ پارس JSON
import ast                        # ✅ fallback پارس literal (مثل دیکشنری پایتونی)
import logging                    # ✅ لاگ‌گذاری
import signal                     # ✅ مدیریت سیگنال‌ها برای خاموش‌سازی تمیز
import threading                  # ✅ اجرای لیسن و توقف تمیز
from time import perf_counter, sleep  # ✅ زمان‌سنج و مکث‌های سبک
from typing import Any, Dict, List, Optional  # ✅ تایپ‌ها
from uuid import uuid4           # ✅ ساخت corr_id در صورت نبود

# ---- کافکا
from confluent_kafka import Consumer, KafkaException, KafkaError  # ✅ Consumer رسمی Confluent

# ---- ماژول‌های پروژه
from config_manager import HotReloadConfig, cfg   # ✅ cfg(): سینگلتون هات‌ریلُد پیکربندی
from kafka_responder import KafkaResponder        # ✅ پاسخ‌دهنده (بازنویسی‌شده بر پایه cfg)
from meta_trader_manager import Mt5_Manager       # ✅ کلاس اصلی MT5
from mt5_utils import convert_params, safe_serialize  # ✅ تبدیل امن پارامترها / سریال‌سازی پاسخ

# ---- لاگر ماژول
LOGGER = logging.getLogger("KafkaListener")  # ✅ لاگر اختصاصی این فایل

# ---- نگاشت نام کلاس به کلاس واقعی (قابل توسعه)
CLASS_MAP: Dict[str, Any] = {
    "Mt5_Manager": Mt5_Manager,  # ✅ در صورت نیاز کلاس‌های دیگر اضافه شوند
}


# -------------------------------------------------------
# ابزار: پارس value به JSON؛ در صورت خطا از literal_eval استفاده می‌کنیم
# -------------------------------------------------------
def parse_json_or_literal(text: str):
    """تبدیل رشته ورودی به آبجکت پایتونی:
    - تلاش اول: json.loads
    - تلاش دوم: ast.literal_eval (برای سازگاری با ورودی‌های غیر JSON سفت‌وسخت)
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return ast.literal_eval(text)


# =======================================================
#                     KafkaListener
# =======================================================
class KafkaListener:
    """
    شنوندهٔ کافکا که تنظیماتش را مستقیماً از cfg (هات‌ریلُد) می‌خواند.

    ورودی سازنده:
    - config: شیء HotReloadConfig (معمولاً cfg()) برای دسترسی لحظه‌ای به config.json

    رفتار:
    - _build_consumer() را با توجه به config.json صدا می‌زند.
    - به تاپیک‌های "kafka.topics.commands" سابسکرایب می‌کند (لیست).
    - اگر در حین اجرا لیست تاپیک‌ها تغییر کند، re-subscribe انجام می‌شود.
    - پیاده‌سازی stop() برای خاموشی تمیز حلقهٔ listen().
    """

    def __init__(self, config: HotReloadConfig) -> None:
        # ✅ نگهداشت مرجع به پیکربندی هات‌ریلُد (cfg)
        self.config = config

        # ✅ وضعیت حلقهٔ شنود
        self._running = False
        self._stop_event = threading.Event()

        # ✅ Consumer و Responder
        self.consumer: Optional[Consumer] = None
        self.responder = KafkaResponder(self.config)  # فرض: kafka_responder.py نیز cfg-محور بازنویسی شده

        # ✅ کش آخرین لیست تاپیک‌ها (برای تشخیص تغییر و resubscribe)
        self._subscribed_topics: List[str] = []

        # ✅ نمونه‌های کلاس‌های قابل فراخوانی (Mt5_Manager و ...)
        self.manager_instances: Dict[str, Any] = {}
        self._init_managers()

        # ✅ ساخت اولیه Consumer (بر اساس config فعلی)
        self._build_consumer_and_subscribe()

    # ---------------------------------------------------
    #     ساخت نمونه از کلاس‌های ثبت‌شده در CLASS_MAP
    # ---------------------------------------------------
    def _init_managers(self) -> None:
        for name, cls in CLASS_MAP.items():
            try:
                self.manager_instances[name] = cls()  # ✅ سازندهٔ پیش‌فرض
                LOGGER.info("Manager instance created: %s", name)
            except Exception as e:
                LOGGER.exception("Failed to instantiate manager '%s': %s", name, e)

    # ---------------------------------------------------
    #   خواندن/ساخت تنظیمات Consumer از روی config.json
    #   و subscribe کردن به تاپیک‌ها
    # ---------------------------------------------------
    def _build_consumer_and_subscribe(self) -> None:
        # ✅ اگر قبلاً Consumer داشتیم، ابتدا ببندیم
        if self.consumer is not None:
            try:
                self.consumer.close()
            except Exception:
                pass
            self.consumer = None

        # ---- خواندن پارامترهای اتصال از cfg() ----
        # bootstrap_servers: در json لیست است → به رشتهٔ comma-separated تبدیل می‌کنیم.
        bs_list = self.config.get("kafka.bootstrap_servers", ["localhost:9092"]) or ["localhost:9092"]
        bootstrap_servers = ",".join(bs_list)

        group_id = self.config.get("kafka.group_id", "mt5-service")
        auto_reset = self.config.get("kafka.consumer_auto_offset_reset", "latest")
        enable_auto_commit = bool(self.config.get("kafka.enable_auto_commit", True))
        session_timeout_ms = int(self.config.get("kafka.session_timeout_ms", 45_000))

        # امنیت (اختیاری)
        security_protocol = self.config.get("kafka.security_protocol", "PLAINTEXT")
        sasl_mechanism = self.config.get("kafka.sasl_mechanism", "PLAIN")
        sasl_username = self.config.get("kafka.sasl_username", "")
        sasl_password = self.config.get("kafka.sasl_password", "")

        # ---- ساخت دیکشنری پیکربندی Consumer ----
        conf = {
            "bootstrap.servers": bootstrap_servers,     # ✅ آدرس‌های کافکا
            "group.id": group_id,                       # ✅ گروه مصرف‌کننده
            "auto.offset.reset": auto_reset,            # ✅ "latest" یا "earliest"
            "enable.auto.commit": enable_auto_commit,   # ✅ کمیت خودکار آفست
            "session.timeout.ms": session_timeout_ms,   # ✅ تایم‌اوت جلسه
        }

        # اگر امنیت غیر از PLAINTEXT بود یا SASL مشخص شده بود، پارامترها را اضافه کن
        if security_protocol and security_protocol != "PLAINTEXT":
            conf["security.protocol"] = security_protocol
        if security_protocol.startswith("SASL"):
            conf["sasl.mechanism"] = sasl_mechanism
            if sasl_username:
                conf["sasl.username"] = sasl_username
            if sasl_password:
                conf["sasl.password"] = sasl_password

        # ---- ساخت Consumer ----
        try:
            self.consumer = Consumer(conf)
        except KafkaException as e:
            LOGGER.error("Failed to create Kafka Consumer: %s", e)
            self.consumer = None
            return

        # ---- محاسبه لیست فعلی تاپیک‌ها از config ----
        topics = self._current_command_topics()

        # ---- subscribe به تاپیک‌ها ----
        try:
            if topics:
                self.consumer.subscribe(topics)
                self._subscribed_topics = topics
                LOGGER.info("Kafka Consumer created and subscribed | servers=%s | group=%s | topics=%s",
                            bootstrap_servers, group_id, topics)
            else:
                LOGGER.warning("No command topics found in config; listener will idle until topics appear.")
                self._subscribed_topics = []
        except KafkaException as e:
            LOGGER.error("Failed to subscribe to topics: %s", e)
            self._subscribed_topics = []

    # ---------------------------------------------------
    #   خواندن لیست تاپیک‌های دستورات از cfg (با جایگزینی {client_id})
    # ---------------------------------------------------
    def _current_command_topics(self) -> List[str]:
        topics = self.config.get("kafka.topics.commands", []) or []
        # نکته: config_manager قبلاً {client_id} را در رشته‌ها resolve می‌کند
        # بنابراین همین مقدارها نهایی هستند.
        # اطمینان از لیست بودن خروجی:
        if isinstance(topics, str):
            topics = [topics]
        # پاکسازی آیتم‌های خالی:
        return [t for t in topics if isinstance(t, str) and t.strip()]

    # ---------------------------------------------------
    #   بررسی تغییر تاپیک‌ها (برای هات‌ریلُد) و resubscribe در صورت لزوم
    # ---------------------------------------------------
    def _ensure_topics_up_to_date(self) -> None:
        new_topics = self._current_command_topics()
        if new_topics != self._subscribed_topics:
            try:
                if self.consumer:
                    self.consumer.subscribe(new_topics or [])
                self._subscribed_topics = new_topics
                LOGGER.info("Re-subscribed due to config change | topics=%s", new_topics)
            except Exception as e:
                LOGGER.warning("Failed to re-subscribe after config change: %s", e)

    # ---------------------------------------------------
    #   ثبت هندلرهای سیگنال برای خاموشی تمیز
    # ---------------------------------------------------
    def _register_signal_handlers(self) -> None:
        def _handle(_signum, _frame):
            LOGGER.info("Signal received. Stopping KafkaListener gracefully...")
            self.stop()

        try:
            signal.signal(signal.SIGINT, _handle)   # Ctrl+C
            signal.signal(signal.SIGTERM, _handle)  # kill
        except Exception:
            # در برخی پلتفرم‌ها (مثلاً داخل بعضی رانتایم‌ها) ممکن است پشتیبانی نشود
            LOGGER.debug("Signal handlers not supported on this platform.")

    # ---------------------------------------------------
    #   شروع حلقهٔ شنود
    # ---------------------------------------------------
    def listen(self) -> None:
        """
        حلقهٔ اصلی شنود:
        - poll پیام‌ها با تایم‌اوت کوتاه
        - قبل از هر پردازش، به‌روزرسانی موضوعات (هات‌ریلُد)
        - پارس و اجرای فرمان‌ها + ارسال پاسخ
        """
        if self.consumer is None:
            LOGGER.error("Consumer not initialized; cannot listen.")
            return

        self._register_signal_handlers()
        self._running = True
        self._stop_event.clear()

        LOGGER.info("Listening for messages... (hot-reload enabled)")

        try:
            while self._running and not self._stop_event.is_set():
                # ✅ تاپیک‌ها را با config لحظه‌ای تطبیق بده (هات‌ریلُد)
                self._ensure_topics_up_to_date()

                # ✅ poll یک پیام با تایم‌اوت 1 ثانیه
                msg = self.consumer.poll(1.0)

                # ✅ اگر پیامی نیست، یک دور دیگر
                if msg is None:
                    continue

                # ✅ رسیدگی به خطای کافکا
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        LOGGER.warning("Kafka error: %s", msg.error())
                    continue

                # ✅ استخراج key/value/headers
                raw_key = (msg.key().decode("utf-8") if msg.key() else "").strip().strip('"').strip("'")
                raw_value = msg.value().decode("utf-8") if msg.value() else ""
                headers_in = dict(
                    (k, (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v))
                    for k, v in (msg.headers() or [])
                )
                corr_id = headers_in.get("corr_id") or headers_in.get("correlation_id") or str(uuid4())

                LOGGER.info("Received message | key=%r len=%d corr_id=%s part=%s off=%s",
                            raw_key, len(raw_value), corr_id, msg.partition(), msg.offset())

                # ✅ پردازش پیام واحد
                self._process_one(
                    class_name=raw_key,
                    raw_value=raw_value,
                    corr_id=corr_id,
                    in_headers=headers_in,
                    meta={"partition": msg.partition(), "offset": msg.offset()}
                )

        except KeyboardInterrupt:
            LOGGER.info("KeyboardInterrupt → stopping KafkaListener...")
        except Exception:
            LOGGER.exception("Unexpected error in listen loop")
        finally:
            try:
                if self.consumer:
                    self.consumer.close()
            except Exception:
                pass
            LOGGER.info("KafkaListener stopped.")

    # ---------------------------------------------------
    #   توقف تمیز Listener (برای main.py یا سیگنال‌ها)
    # ---------------------------------------------------
    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    # ---------------------------------------------------
    #   احراز هویت اختیاری بر اساس config.json
    # ---------------------------------------------------
    def _check_auth(self, payload_obj: Any, headers: Dict[str, Any]) -> Optional[str]:
        """
        اگر auth.token_required=true:
          - اولویت با برداشتن توکن از هدرهاست.
          - اگر هدر نبود، از داخل payload با کلید auth.header_key برداشته می‌شود.
        مقدار برگشتی:
          - None  → تایید شد یا auth لازم نیست
          - str   → پیام خطای توضیحی در صورت رد اعتبار
        """
        token_required = bool(self.config.get("auth.token_required", False))
        if not token_required:
            return None

        header_key = self.config.get("auth.header_key", "auth_token") or "auth_token"
        tokens_map = self.config.get("auth.tokens", {}) or {}
        allowed_tokens = set(tokens_map.values())  # فقط مقدار توکن‌ها مهم است

        # تلاش 1: از هدر
        token = headers.get(header_key)
        # تلاش 2: از payload (اگر dict باشد)
        if token in (None, "") and isinstance(payload_obj, dict):
            token = payload_obj.get(header_key)

        if not token:
            return f"Missing auth token (header/payload '{header_key}')."

        if token not in allowed_tokens:
            return "Invalid auth token."

        return None  # تایید شد

    # ---------------------------------------------------
    #   ارسال پاسخ در قالب Envelope استاندارد
    # ---------------------------------------------------
    def _send_enveloped(
        self,
        class_name: str,
        corr_id: str,
        idx: int,
        method_name: str,
        status: str,
        result_obj: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "schema": "Mt5ResultV1",                 # ✅ نسخه اسکیمای پاسخ
            "corr_id": corr_id,                      # ✅ شناسه هم‌بستگی
            "class": class_name or "UNKNOWN",        # ✅ نام کلاس هدف
            "method": method_name or "N/A",          # ✅ نام متد
            "request_index": idx,                    # ✅ شمارهٔ آیتم در آرایهٔ درخواست
            "status": status,                        # ✅ "ok" | "error"
            "result": safe_serialize(result_obj),    # ✅ سریال‌سازی امن نتیجه
        }
        if meta:
            payload["meta"] = safe_serialize(meta)

        # ✅ ارسال پاسخ با KafkaResponder (تاپیک پاسخ‌ها داخل KafkaResponder از cfg خوانده می‌شود)
        try:
            self.responder.send_result(corr_id=corr_id, payload_obj=payload, key=(class_name or "UNKNOWN"))
        except Exception as e:
            LOGGER.warning("Failed to send response: %s", e)

    # ---------------------------------------------------
    #   پردازش یک پیام دریافتی (یک key/value)
    # ---------------------------------------------------
    def _process_one(
        self,
        class_name: str,
        raw_value: str,
        corr_id: str,
        in_headers: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> None:
        # ✅ کلاس مقصد باید در CLASS_MAP موجود باشد
        if class_name not in self.manager_instances:
            err = f"Class '{class_name}' not found. Available: {list(self.manager_instances.keys())}"
            LOGGER.error(err)
            self._send_enveloped(class_name or "UNKNOWN", corr_id, -1, "N/A", "error", {"error": err})
            return

        # ✅ پارس value به آبجکت پایتونی
        try:
            obj = parse_json_or_literal(raw_value)
        except Exception as e:
            err = f"Parse error: {e}"
            LOGGER.error(err)
            self._send_enveloped(class_name, corr_id, -1, "N/A", "error", {"error": err})
            return

        # ✅ احراز هویت اختیاری
        auth_err = self._check_auth(payload_obj=obj, headers=in_headers)
        if auth_err:
            LOGGER.warning("Auth rejected: %s", auth_err)
            self._send_enveloped(class_name, corr_id, -1, "N/A", "error", {"error": auth_err})
            return

        # ✅ به یک لیست از کامندها تبدیل کنیم
        commands: List[Dict[str, Any]] = obj if isinstance(obj, list) else [obj]

        # ✅ نمونهٔ کلاس موردنظر
        manager = self.manager_instances[class_name]

        # ✅ حلقهٔ اجرای هر آیتم
        for idx, command in enumerate(commands, start=1):
            t0 = perf_counter()

            if not isinstance(command, dict):
                warn = f"Command #{idx} is not a dict"
                LOGGER.warning(warn)
                self._send_enveloped(class_name, corr_id, idx, "N/A", "error", {"error": warn})
                continue

            method_name = command.get("method")
            params = command.get("params", {}) or {}

            if not method_name or not hasattr(manager, method_name):
                err = f"Method '{method_name}' not found in '{class_name}'"
                LOGGER.error(err)
                self._send_enveloped(class_name, corr_id, idx, method_name or "N/A", "error", {"error": err})
                continue

            # ✅ تبدیل امن پارامترها (نگاشت رشته‌ها به کانستنت‌های MT5، پارس تاریخ‌ها و ...)
            try:
                conv_params = convert_params(params)
            except Exception as e:
                err = f"Parameter conversion failed: {e}"
                LOGGER.exception(err)
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": err})
                continue

            # ✅ فراخوانی متد و ارسال پاسخ
            try:
                LOGGER.info("Calling %s.%s | params=%s", class_name, method_name, safe_serialize(conv_params))
                result = getattr(manager, method_name)(**conv_params)
                LOGGER.info("Result of %s: %s", method_name, safe_serialize(result))
                elapsed = int((perf_counter() - t0) * 1000)

                self._send_enveloped(
                    class_name,
                    corr_id,
                    idx,
                    method_name,
                    "ok",
                    result,
                    meta={"elapsed_ms": elapsed, "in_headers": in_headers, "src": meta},
                )

            except TypeError as te:
                err = f"Invalid parameters for {class_name}.{method_name}: {te}"
                LOGGER.error(err)
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": err})

            except Exception as e:
                LOGGER.exception("Unhandled error calling %s.%s", class_name, method_name)
                self._send_enveloped(class_name, corr_id, idx, method_name, "error", {"error": str(e)})
