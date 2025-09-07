# -*- coding: utf-8 -*-
"""
kafka_responder.py
------------------
ارسال پاسخ‌ها به Kafka با تکیه‌ی کامل بر config.json و هات‌ریلُد:

ویژگی‌ها:
- خواندن تنظیمات Producer/Topic از config.json (بخش "kafka")
- چانک‌کردن پیام‌های بزرگ بر اساس kafka.response_max_part_bytes
- هدرهای استاندارد: corr_id, schema, seq, total, content_type, encoding
- استفاده از تحویل مطمئن (enable.idempotence=True) و اِعمال acks/retries/linger/...
- بازسازی خودکار Producer وقتی تنظیمات مرتبط تغییر می‌کنند (بدون ری‌استارت برنامه)

کلیدهای مهم در config.json → "kafka":
  - enabled:               bool        فعال/غیرفعال بودن ارسال کافکا
  - bootstrap_servers:     list[str]   لیست host:port (در کد به رشتهٔ comma-separated تبدیل می‌شود)
  - security_protocol:     str         "PLAINTEXT" | "SASL_PLAINTEXT" | "SASL_SSL" | "SSL"
  - sasl_mechanism:        str         "PLAIN" | "SCRAM-SHA-256" | "SCRAM-SHA-512" | "OAUTHBEARER"
  - sasl_username:         str         نام کاربری در صورت نیاز
  - sasl_password:         str         گذرواژه در صورت نیاز
  - acks:                  str         "0" | "1" | "all"  (پیش‌فرض: "all")
  - retries:               int         تعداد تلاش مجدد Producer (پیش‌فرض: 3)
  - linger_ms:             int         تأخیر میکرو-بچینگ (پیش‌فرض: 5)
  - request_timeout_ms:    int         تایم‌اوت درخواست‌ها (پیش‌فرض: 30000)
  - compression            str|null    نوع فشرده‌سازی Producer: "zstd"|"lz4"|"gzip"|"snappy" (اختیاری)
  - response_max_part_bytes int        حداکثر اندازهٔ هر چانک پاسخ (بایت). پیش‌فرض امن: 921,600 ≈ 900KiB
  - topics.replies         str         نام تاپیک خروجی پاسخ‌ها (مثلاً: "server.replies")

نکته:
- اگر "kafka.enabled" = false باشد، پیام‌ها تولید نمی‌شوند (no-op)، اما هیچ خطایی هم پرتاب نمی‌شود.
"""

from __future__ import annotations  # ✅ تایپ‌هینت‌های مدرن (Annotationهای آینده)
from typing import Any, Dict, List, Optional, Tuple  # ✅ تایپ‌ها برای خوانایی بهتر
import json                                         # ✅ سریال‌سازی دیکشنری به JSON
import logging                                      # ✅ لاگ‌گذاری استاندارد پایتون
from confluent_kafka import Producer                # ✅ Producer رسمی Confluent Kafka

# ✅ واردکردن cfg (هات‌ریلُد) برای خواندن تنظیمات زنده از config.json
from config_manager import cfg


# -------------------------------
#  لاگر ماژول
# -------------------------------
LOGGER = logging.getLogger("KafkaResponder")


class KafkaResponder:
    """
    کلاس مسئول ارسال پاسخ‌ها به تاپیک خروجی کافکا طبق config.json.

    نکتهٔ مهم «هات‌ریلُد»:
    - شیء Producer بر اساس snapshot فعلی تنظیمات ساخته می‌شود.
    - در هر بار ارسال، اگر هرکدام از تنظیمات مهم Producer/Topic تغییر کرده باشند،
      Producer به صورت خودکار بازسازی می‌شود (بدون نیاز به ری‌استارت برنامه).
    """

    # ---------------------------------------------
    #  سازنده
    # ---------------------------------------------
    def __init__(self, cfg_provider=cfg) -> None:
        """
        پارامترها:
          cfg_provider: تابع یا آبجکت قابل‌فراخوانی که نمونهٔ HotReloadConfig را برمی‌گرداند.
                        به طور پیش‌فرض از config_manager.cfg استفاده می‌شود.

        الگو:
          responder = KafkaResponder(cfg)  ← همانطور که در مصرف‌کننده اشاره کرده‌اید.
        """
        self._cfg_provider = cfg_provider              # ✅ مرجع خواندن پیکربندی (هات‌ریلُد)
        self._producer: Optional[Producer] = None      # ✅ Producer فعلی
        self._last_signature: Optional[Tuple] = None   # ✅ امضای تنظیمات آخرین Producer ساخته‌شده

    # ---------------------------------------------
    #  متد کمکی: تبدیل لیست bootstrap_servers به رشته
    # ---------------------------------------------
    @staticmethod
    def _servers_to_string(servers: List[str]) -> str:
        """
        confluent_kafka انتظار یک رشتهٔ comma-separated دارد.
        این متد لیست ["host1:9092","host2:9092"] را به "host1:9092,host2:9092" تبدیل می‌کند.
        """
        return ",".join(servers or [])
    def _get_cfg(self):
        return self._cfg_provider() if callable(self._cfg_provider) else self._cfg_provider
    # ---------------------------------------------
    #  متد کمکی: خواندن تنظیمات مرتبط با Producer از cfg
    #  و ساخت دیکشنری قابل‌استفاده برای Producer(...)
    # ---------------------------------------------
    def _current_producer_config(self) -> Tuple[Dict[str, Any], str, int, bool]:
        """
        خروجی:
          - conf: دیکشنری پیکربندی Producer برای confluent_kafka.Producer
          - replies_topic: نام تاپیک خروجی برای ارسال پاسخ
          - resp_max_part_bytes: حداکثر اندازهٔ هر چانک پاسخ
          - kafka_enabled: آیا ارسال کافکا فعال است یا نه (kafka.enabled)

        نکتهٔ هات‌ریلُد:
          این متد در هر بار فراخوانی مقادیر را «زنده» از config.json می‌خواند.
        """
        c = self._get_cfg()  # ✅ گرفتن سینگلتون پیکربندی با هات‌ریلُد

        # ---- خواندن ریشهٔ kafka ----
        kafka_enabled = bool(c.get("kafka.enabled", True))  # دیفالت: True
        servers_list = c.get("kafka.bootstrap_servers", ["localhost:9092"])  # لیست
        bootstrap_servers = self._servers_to_string(servers_list)            # رشته

        # ---- امنیت/احراز هویت ----
        security_protocol = c.get("kafka.security_protocol", "PLAINTEXT")  # "PLAINTEXT"|...
        sasl_mechanism = c.get("kafka.sasl_mechanism", "PLAIN")
        sasl_username = c.get("kafka.sasl_username", "")
        sasl_password = c.get("kafka.sasl_password", "")

        # ---- Producer tuning ----
        acks = str(c.get("kafka.acks", "all"))                    # "0"|"1"|"all"
        retries = int(c.get("kafka.retries", 3))                  # تعداد تلاش مجدد
        linger_ms = int(c.get("kafka.linger_ms", 5))              # batching delay
        request_timeout_ms = int(c.get("kafka.request_timeout_ms", 30000))
        compression = c.get("kafka.compression", None)            # "zstd"|"lz4"|... یا None

        # ---- چانکینگ پاسخ ----
        # اگر در config.json کلید نبود، پیش‌فرض امن (900KiB) را اعمال می‌کنیم:
        resp_max_part_bytes = int(c.get("kafka.response_max_part_bytes", 900 * 1024))

        # ---- تاپیک خروجی ----
        replies_topic = c.get("kafka.topics.replies", "server.replies")

        # ---- ساخت دیکشنری Producer.conf ----
        conf: Dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,     # آدرس/های بروکر
            "enable.idempotence": True,                 # تحویل مطمئن (تک‌نسخه‌ای)
            "acks": acks,                               # سطح تأیید
            "linger.ms": linger_ms,                     # batching
            "retries": retries,                         # تلاش مجدد
            "request.timeout.ms": request_timeout_ms,   # تایم‌اوت
            "security.protocol": security_protocol,     # پروتکل امنیتی
        }

        # اگر SASL لازم است، فیلدهای مربوطه را ست می‌کنیم:
        # - وقتی security_protocol یکی از حالت‌های SASL_* باشد، این‌ها معنی‌دارند.
        if security_protocol.upper().startswith("SASL"):
            conf["sasl.mechanism"] = sasl_mechanism
            if sasl_username:
                conf["sasl.username"] = sasl_username
            if sasl_password:
                conf["sasl.password"] = sasl_password

        # فشرده‌سازی اختیاری (اگر در کانفیگ مشخص شده باشد)
        if compression:
            conf["compression.type"] = str(compression)

        return conf, replies_topic, resp_max_part_bytes, kafka_enabled

    # ---------------------------------------------
    #  متد کمکی: ساخت «امضای تنظیمات» برای تشخیص تغییر
    # ---------------------------------------------
    @staticmethod
    def _make_signature(conf: Dict[str, Any], replies_topic: str, resp_sz: int, enabled: bool) -> Tuple:
        """
        از فیلدهای مهم Producer و تاپیک خروجی یک امضا (tuple) می‌سازد.
        اگر این امضا نسبت به امضای قبلی فرق کند، Producer باید بازسازی شود.
        """
        # توجه: dict مرتب نیست؛ کلیدهای مهم را صراحتاً انتخاب/مرتب می‌کنیم:
        keys = [
            "bootstrap.servers",
            "security.protocol",
            "sasl.mechanism",
            "sasl.username",
            "acks",
            "linger.ms",
            "retries",
            "request.timeout.ms",
            "compression.type",
            "enable.idempotence",
        ]
        base = tuple((k,conf.get(k)) for k in keys)
        extra = (("replies_topic", replies_topic), ("resp_max_part_bytes", resp_sz), ("enabled", enabled))
        return base + extra
        # ساخت tuple منظم
        # sig = tuple((k, conf.get(k)) for k in keys) + ("replies_topic", replies_topic), ("resp_max_part_bytes", resp_sz), ("enabled", enabled)
        # return sig

    # ---------------------------------------------
    #  متد کمکی: ساخت یا بازسازی Producer در صورت نیاز
    # ---------------------------------------------
    def _ensure_producer(self) -> Tuple[Optional[Producer], str, int, bool]:
        """
        Producer را بر اساس تنظیمات فعلی آماده می‌کند.
        اگر تنظیمات مهم تغییر کرده باشد → Producer جدید ساخته می‌شود.

        خروجی:
          - Producer یا None (اگر kafka.enabled=False)
          - replies_topic: نام تاپیک پاسخ
          - resp_max_part_bytes: اندازهٔ چانک
          - kafka_enabled: فعال/غیرفعال بودن ارسال
        """
        conf, replies_topic, resp_max_part_bytes, kafka_enabled = self._current_producer_config()

        # اگر کلاً Kafka غیرفعال است → Producer نخواهیم ساخت
        if not kafka_enabled:
            if self._producer is not None:
                try:
                    self._producer.flush(1)   # تلاش برای تخلیهٔ سریع
                except Exception:
                    pass
            self._producer = None
            self._last_signature = None
            return None, replies_topic, resp_max_part_bytes, False

        # امضا از تنظیمات فعلی
        sig = self._make_signature(conf, replies_topic, resp_max_part_bytes, kafka_enabled)

        # اگر Producer نداریم یا امضا تغییر کرده → بازسازی
        if (self._producer is None) or (sig != self._last_signature):
            # اگر Producer قبلی هست، قبل از جایگزینی flush کوتاه انجام دهیم
            if self._producer is not None:
                try:
                    self._producer.flush(2)
                except Exception:
                    pass

            # تلاش برای ساخت Producer جدید
            self._producer = Producer(conf)
            self._last_signature = sig
            LOGGER.info("KafkaResponder: Producer (re)built with config=%s, replies_topic=%s, part_max=%s",
                        conf, replies_topic, resp_max_part_bytes)

        return self._producer, replies_topic, resp_max_part_bytes, True

    # ---------------------------------------------
    #  متد کمکی: تقسیم بایت‌ها به چانک
    # ---------------------------------------------
    @staticmethod
    def _chunk_bytes(data: bytes, max_part: int) -> List[bytes]:
        """
        تقسیم محتوای باینری به چند چانک با اندازهٔ حداکثر max_part.
        اگر data خالی باشد، حداقل یک چانک خالی برمی‌گردانیم تا سمت مقابل بداند پاسخی آمد.
        """
        return [data[i:i + max_part] for i in range(0, len(data), max_part)] or [b""]

    # ---------------------------------------------
    #  کالبک تحویل پیام (Delivery Report)
    # ---------------------------------------------
    @staticmethod
    def _delivery_cb(err, msg) -> None:
        """
        اگر خطا رخ دهد، در همین‌جا قابل‌لاگ‌کردن است.
        (ترجیحاً از LOGGER استفاده می‌کنیم؛ چاپ مستقیم نمی‌کنیم.)
        """
        if err is not None:
            LOGGER.warning("KafkaResponder delivery error: %s | topic=%s partition=%s offset=%s",
                           err, msg.topic(), msg.partition(), msg.offset())

    # ---------------------------------------------
    #  API اصلی: ارسال یک پاسخ (با چانکینگ و هدرهای استاندارد)
    # ---------------------------------------------
    def send_result(
        self,
        corr_id: str,                                # شناسه هم‌بستگی (corr_id)
        payload_obj: Dict[str, Any],                 # بدنهٔ پاسخ به صورت dict
        schema: str = "Mt5ResultV1",                 # نام/نسخهٔ اسکیمای پاسخ
        key: str = "Mt5_Manager",                    # کلید پیام (برای پارتیشنینگ/مسیر)
        headers_extra: Optional[List[Tuple[str, bytes]]] = None,  # هدرهای اضافه (اختیاری)
        auto_flush: bool = True,                     # پس از enqueue همهٔ چانک‌ها، flush انجام شود؟
    ) -> None:
        """
        ارسال پاسخ به Kafka:
        - بدنه به JSON UTF-8 تبدیل می‌شود.
        - در صورت بزرگ‌بودن، به چند «چانک» تقسیم می‌شود.
        - برای هر چانک هدرهای (corr_id, schema, seq, total, content_type, encoding) ست می‌گردد.
        - اگر kafka.enabled=False باشد، این تابع no-op است.

        پارامترها:
          corr_id:       شناسهٔ هم‌بستگی درخواست/پاسخ (برای ردگیری end-to-end)
          payload_obj:   دیکشنری نتیجه (ترجیحاً قبلاً JSON-safe شده باشد)
          schema:        نام اسکیمای پاسخ برای سمت مقابل
          key:           کلید پیام (مثلاً نام کلاس یا روتیگ)
          headers_extra: لیست اختیاری از هدرهای اضافه به‌صورت [(str, bytes), ...]
          auto_flush:    اگر True، پس از تولید تمام چانک‌ها، producer.flush() می‌زند
        """
        # 1) Producer/Topic/Size را مطابق config.json آماده کن (با هات‌ریلُد)
        producer, replies_topic, max_part, enabled = self._ensure_producer()

        # اگر Kafka غیرفعال است → هیچ کاری نکن (no-op)
        if not enabled or producer is None:
            LOGGER.debug("KafkaResponder is disabled by config. Dropping reply (corr_id=%s).", corr_id)
            return

        # 2) تبدیل payload به JSON فشرده و امن برای ارسال
        #    separators=(",", ":") → خروجی جمع‌وجورتر
        data = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        # 3) چانک‌کردن داده
        parts = self._chunk_bytes(data, max_part)
        total = len(parts)

        # 4) ارسال همهٔ چانک‌ها
        for i, part in enumerate(parts, start=1):
            # هدرهای استاندارد
            headers: List[Tuple[str, bytes]] = [
                ("corr_id", corr_id.encode("utf-8")),
                ("schema", schema.encode("utf-8")),
                ("seq", str(i).encode("utf-8")),
                ("total", str(total).encode("utf-8")),
                ("content_type", b"application/json"),
                ("encoding", b"utf-8"),
            ]
            # الحاق هدرهای اضافه اگر داده شده باشد
            if headers_extra:
                headers.extend(headers_extra)

            # enqueue پیام در Producer (ارسال غیرهمزمان)
            producer.produce(
                topic=replies_topic,               # تاپیک خروجی از کانفیگ
                key=key.encode("utf-8"),          # کلید پیام (برای پارتیشنینگ/مسیر)
                value=part,                        # بدنهٔ چانک
                headers=headers,                   # هدرها
                on_delivery=self._delivery_cb,     # کالبک تحویل
            )

        # 5) برای اطمینان از ارسال، flush اختیاری
        if auto_flush:
            try:
                producer.flush()  # توجه: در مسیرهای پرترافیک می‌توانید این را False کنید و به batching تکیه کنید.
            except Exception as e:
                LOGGER.warning("KafkaResponder flush error: %s", e)
