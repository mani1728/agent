# kafka_responder.py
# =========================
# تولیدکنندهٔ پاسخ به Kafka با:
# - چانک‌کردن پیام‌های بزرگ (seq/total)
# - هدرهای استاندارد: corr_id/schema/seq/total/content_type/encoding
# - فشرده‌سازی Producer و تحویل مطمئن (idempotence, acks=all)
# =========================

from __future__ import annotations                    # تایپ‌هینت‌های مدرن
from typing import Any, Dict, List, Optional, Tuple   # تایپ‌ها
import json                                          # سریال‌سازی به JSON
from confluent_kafka import Producer                  # Producer کافکا
from config_logging import AppSettings                # تنظیمات برنامه

class KafkaResponder:
    """کلاس مسئول ارسال پاسخ‌ها به تاپیک خروجی (agent-recive)."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings                                               # نگهداری تنظیمات
        # پیکربندی Producer با تحویل مطمئن و فشرده‌سازی
        self._producer = Producer({
            "bootstrap.servers": settings.kafka_servers,                       # آدرس کافکا
            "enable.idempotence": True,                                        # تحویل دقیق‌تر
            "acks": "all",                                                     # تأیید از همه رپلیکاها
            "compression.type": settings.kafka_compression,                    # نوع فشرده‌سازی
            "linger.ms": settings.kafka_linger_ms,                             # میکرو-بچینگ
            "batch.num.messages": settings.kafka_batch_num,                    # اندازه بچ
            "retries": 1000000,                                                # تعداد تلاش مجدد
            "max.in.flight.requests.per.connection": settings.kafka_max_inflight,  # کنترل ترتیب
        })

    @staticmethod
    def _chunk_bytes(data: bytes, max_part: int) -> List[bytes]:
        """تقسیم بایت‌ها به چانک‌های با حداکثر طول مشخص."""
        return [data[i:i + max_part] for i in range(0, len(data), max_part)] or [b""]  # حداقل یک چانک

    def _delivery_cb(self, err, msg) -> None:
        """کالبک تحویل هر پیام؛ اگر خطا رخ دهد، در همین‌جا گرفته می‌شود."""
        if err is not None:
            # توجه: اینجا عمداً print نمی‌کنیم تا لاگ‌گذاری مرکزی هندل کند؛ caller می‌تواند لاگ بگیرد.
            pass

    def send_result(
        self,
        corr_id: str,                                 # شناسه هم‌بستگی
        payload_obj: Dict[str, Any],                  # بدنهٔ پاسخ (دیکشنری)
        schema: str = "Mt5ResultV1",                  # اسکیمای پاسخ
        key: str = "Mt5_Manager",                     # کلید پیام (برای پارتیشنینگ/مسیر)
        headers_extra: Optional[List[Tuple[str, bytes]]] = None,  # هدرهای اضافه اختیاری
    ) -> None:
        """ارسال پاسخ با چانکینگ و هدرهای استاندارد."""
        # تبدیل payload به JSON بایت
        data = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")  # فشرده‌تر
        parts = self._chunk_bytes(data, self.settings.kafka_resp_max_part_bytes)                    # تقسیم به چانک
        total = len(parts)                                                                          # تعداد کل

        for i, part in enumerate(parts, start=1):                                                  # ارسال هر پارت
            headers = [                                                                            # ساخت هدرها
                ("corr_id", corr_id.encode("utf-8")),
                ("schema", schema.encode("utf-8")),
                ("seq", str(i).encode("utf-8")),
                ("total", str(total).encode("utf-8")),
                ("content_type", b"application/json"),
                ("encoding", b"utf-8"),
            ]
            if headers_extra:                                                                      # افزودن هدرهای اضافه
                headers.extend(headers_extra)

            self._producer.produce(                                                                # تولید پیام
                topic=self.settings.kafka_response_topic,                                          # تاپیک پاسخ
                key=key.encode("utf-8"),                                                           # کلید
                value=part,                                                                        # بدنه پارت
                headers=headers,                                                                   # هدرها
                on_delivery=self._delivery_cb,                                                     # کالبک تحویل
            )

        self._producer.flush()                                                                     # flush برای اطمینان
