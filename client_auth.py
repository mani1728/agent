# -*- coding: utf-8 -*-
"""
client_auth.py
---------------
ماژول مسئول:
1) ثبت‌نام کلاینت نزد سرور و دریافت client_id + auth_token
2) ارسال heartbeat دوره‌ای برای اعلام حضور
3) ساخت هدرهای استاندارد امنیتی برای پیام‌های خروجی (ts, nonce, auth, sig, ...)
4) فراهم‌کردن تاپیک صندوق اختصاصی کلاینت: cmd.{client_id}

نکات:
- این ماژول به تنهایی کار مصرف/اجرا/اولویت را انجام نمی‌دهد؛ فقط «هویت، وضعیت، و هدرهای امن» را مدیریت می‌کند.
- در گام‌های بعدی آن را به priority_executor و kafka_listener متصل می‌کنیم.
"""

import os
import json
import time
import uuid
import hmac
import hashlib
import threading
from datetime import datetime, timedelta, timezone

# اگر از confluent_kafka استفاده می‌کنید:
from confluent_kafka import Producer, Consumer, KafkaException


class ClientAuth(object):
    """
    کلاس اصلی مدیریت احراز هویت و ثبت‌نام کلاینت.

    مسئولیت‌ها:
    - ارسال درخواست ثبت‌نام به تاپیک `clients.register`
    - دریافت پاسخ ثبت‌نام از `clients.register.responses`
    - نگهداری client_id، auth_token، و expiry
    - ارسال heartbeat به `clients.status` (تاپیک compacted)
    - ساخت هدرهای استاندارد برای پیام‌های خروجی
    """

    def __init__(
        self,
        bootstrap_servers: str,
        client_meta: dict,
        # نام تاپیک‌ها (در صورت نیاز در محیط‌های مختلف تغییرپذیر)
        register_topic: str = "clients.register",
        register_responses_topic: str = "clients.register.responses",
        status_topic: str = "clients.status",
        # تنظیمات heartbeat
        heartbeat_interval_sec: int = 15,
        # تنظیمات امنیت و امضا
        sig_alg: str = "HMAC-SHA256",
        hmac_secret: str = None,
        # اگر بخواهیم kid یا الگوریتم‌ها را تغییر دهیم
        kid: str = "k-2025-09",
        # مهلت انتظار برای پاسخ ثبت‌نام
        register_timeout_sec: int = 20,
        # فاصلهٔ زمانی برای رفرش توکن قبل از انقضا (حاشیه امن)
        token_refresh_margin_sec: int = 120,
        # تنظیمات Kafka Consumer/Producer
        consumer_group_prefix: str = "client-register-waiter-",
        # لاگ ساده
        logger=None,
    ):
        # آدرس کلاستر کافکا
        self.bootstrap_servers = bootstrap_servers

        # اطلاعات متای کلاینت (نسخه، قابلیت‌ها، سیستم‌عامل، و ...)
        self.client_meta = client_meta or {}

        # نام تاپیک‌ها
        self.register_topic = register_topic
        self.register_responses_topic = register_responses_topic
        self.status_topic = status_topic

        # زمان‌بندی‌ها
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.register_timeout_sec = register_timeout_sec
        self.token_refresh_margin_sec = token_refresh_margin_sec

        # امنیت/امضا
        self.sig_alg = sig_alg
        self.hmac_secret = hmac_secret or os.getenv("CLIENT_HMAC_SECRET", "changeme")  # بهتره از ENV بیاد
        self.kid = kid

        # شناسه موقت کلاینت برای فاز ثبت‌نام (قبل از گرفتن client_id واقعی)
        self.client_tmp_id = str(uuid.uuid4())

        # پس از ثبت‌نام پر می‌شوند:
        self.client_id = None
        self.auth_token = None
        self.token_expires_at = None  # datetime UTC

        # کنترل ترد heartbeat
        self._stop_event = threading.Event()
        self._hb_thread = None

        # ابزارهای Kafka
        self._producer = Producer({"bootstrap.servers": self.bootstrap_servers})
        # برای مصرف پاسخ ثبت‌نام، یک group یکتا می‌گیریم تا پیام‌های دیگران مزاحم نشوند
        self._register_consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": f"{consumer_group_prefix}{self.client_tmp_id}",
            "auto.offset.reset": "earliest",
            "enable.partition.eof": False,
        })

        # logger ساده اختیاری
        self.log = logger or self._fallback_log

    # ---- ابزار لاگ ساده ----
    def _fallback_log(self, level, msg, **kw):
        print(f"[{level.upper()}] {msg} {kw if kw else ''}")

    # ---- کمک‌تابع زمان UTC ISO8601 ----
    @staticmethod
    def _utcnow_iso():
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    # ---- تولید nonce تصادفی ----
    @staticmethod
    def _nonce():
        return uuid.uuid4().hex

    # ---- ساخت امضای HMAC روی هدرهای حساس + بادی ----
    def _make_signature(self, body_bytes: bytes, headers: dict) -> str:
        """
        امضا روی ترکیب: body + چند هدر حساس
        توجه: ترتیب ثابت فیلدها مهم است تا امضا پایدار باشد.
        """
        parts = []
        # ترتیب را مشخص و ثابت نگه می‌داریم
        for key in ["corr_id", "client_id", "priority", "ts", "nonce"]:
            if key in headers and headers[key] is not None:
                parts.append(f"{key}={headers[key]}")

        # جداکنندهٔ ثابت بین هدرها و بادی
        header_str = "|".join(parts).encode("utf-8")
        digest = hmac.new(self.hmac_secret.encode("utf-8"), header_str + b"||" + body_bytes, hashlib.sha256).hexdigest()
        return digest

    # ---- شروع فرآیند ثبت‌نام ----
    def register(self):
        """
        1) ارسال درخواست به clients.register
        2) انتظار برای پاسخ در clients.register.responses
        3) ذخیره client_id و auth_token و زمان انقضا
        4) استارت ترد heartbeat
        """
        self.log("info", "Start client registration")

        corr_id = str(uuid.uuid4())
        req_ts = self._utcnow_iso()
        nonce = self._nonce()

        # بدنهٔ ثبت‌نام: اطلاعات متای کلاینت + زمان + nonce
        body = {
            "schema": "ClientRegisterV1",
            "client_tmp_id": self.client_tmp_id,
            "meta": self.client_meta,
            "ts": req_ts,
            "nonce": nonce,
        }
        body_bytes = json.dumps(body).encode("utf-8")

        # هدرهای پیام ثبت‌نام
        headers = [
            ("schema", "ClientRegisterV1"),
            ("client_tmp_id", self.client_tmp_id),
            ("corr_id", corr_id),
            ("content_type", "application/json"),
            ("encoding", "utf-8"),
        ]

        # ارسال درخواست ثبت‌نام
        try:
            self._producer.produce(
                topic=self.register_topic,
                key=self.client_tmp_id.encode("utf-8"),
                value=body_bytes,
                headers=headers,
            )
            self._producer.flush(5.0)
            self.log("info", "Registration request sent.", topic=self.register_topic, corr_id=corr_id)
        except Exception as e:
            raise RuntimeError(f"Registration submission failed: {e}")

        # گوش دادن برای پاسخ
        self._register_consumer.subscribe([self.register_responses_topic])
        deadline = time.time() + self.register_timeout_sec

        response = None
        while time.time() < deadline:
            msg = self._register_consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            # هدرها را می‌خوانیم
            hdrs = dict(msg.headers() or [])
            # فقط پاسخ‌هایی که corr_id یا client_tmp_id خودمان را دارند قبول می‌کنیم
            if hdrs.get("corr_id") != corr_id and hdrs.get("client_tmp_id") != self.client_tmp_id:
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:
                continue

            response = payload
            break

        if response is None:
            raise TimeoutError("Registration response not received within the specified time.")

        # انتظار داریم فیلدهای زیر را داشته باشیم:
        # { client_id, auth_token, expires_at (ISO8601), reply_topic (اختیاری) }
        self.client_id = response.get("client_id")
        self.auth_token = response.get("auth_token")
        exp_iso = response.get("expires_at")
        self.token_expires_at = datetime.fromisoformat(exp_iso) if exp_iso else (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=24))

        if not self.client_id or not self.auth_token:
            raise ValueError("The registration response is incomplete (client_id or auth_token not present)")

        self.log("info", "Successful registration", client_id=self.client_id, expires_at=self.token_expires_at.isoformat())

        # استارت heartbeat
        self._start_heartbeat()

    # ---- محاسبه نام تاپیک Inbox کلاینت ----
    def inbox_topic(self) -> str:
        if not self.client_id:
            raise RuntimeError("You are not registered yet; client_id is unknown.")
        return f"cmd.{self.client_id}"

    # ---- ساخت هدرهای استاندارد برای پیام‌های خروجی (مثلا پاسخ‌ها یا ACKها) ----
    def build_outgoing_headers(
        self,
        corr_id: str,
        priority: int = None,
        ordering_scope: str = None,
        ttl_ms: int = None,
        extra_headers: dict = None,
        body_bytes: bytes = b"",
    ) -> list:
        """
        هدرهای خروجی را می‌سازد:
        - ts, nonce, client_id, corr_id, auth (JWT)، kid
        - priority, ordering_scope, ttl_ms (در صورت وجود)
        - sig (امضای HMAC روی هدرهای کلیدی + بادی)
        """
        if not self.client_id or not self.auth_token:
            raise RuntimeError("client_id/auth_token is unknown; call register() first.")

        # رفرش توکن اگر نزدیک انقضاست (فاز ساده؛ در ادامه می‌توانیم درخواست رفرش واقعی اضافه کنیم)
        self._refresh_token_if_needed()

        ts = self._utcnow_iso()
        nonce = self._nonce()

        # ابتدا دیکشنری هدرها را برای ساخت امضا آماده می‌کنیم
        header_dict = {
            "schema": "ClientReplyV1",  # یا ClientCommandV1 در صورت استفاده برای فرمان‌های سرور؛ اینجا خروجی نمونه است
            "client_id": self.client_id,
            "corr_id": corr_id,
            "ts": ts,
            "nonce": nonce,
        }
        if priority is not None:
            header_dict["priority"] = str(priority)
        if ordering_scope:
            header_dict["ordering_scope"] = ordering_scope
        if ttl_ms is not None:
            header_dict["ttl_ms"] = str(ttl_ms)

        # امضا
        sig = self._make_signature(body_bytes=body_bytes, headers=header_dict)

        # سپس به لیست (name, value) تبدیل می‌کنیم (فرمت استاندارد confluent_kafka)
        headers = [
            ("schema", header_dict["schema"]),
            ("client_id", self.client_id),
            ("corr_id", corr_id),
            ("ts", ts),
            ("nonce", nonce),
            ("auth", self.auth_token),  # JWT
            ("kid", self.kid),
            ("sig_alg", self.sig_alg),
            ("sig", sig),
            ("content_type", "application/json"),
            ("encoding", "utf-8"),
        ]
        if priority is not None:
            headers.append(("priority", str(priority)))
        if ordering_scope:
            headers.append(("ordering_scope", ordering_scope))
        if ttl_ms is not None:
            headers.append(("ttl_ms", str(ttl_ms)))

        # هدرهای اضافی کاربر (اختیاری)
        if extra_headers:
            for k, v in extra_headers.items():
                headers.append((k, str(v)))

        return headers

    # ---- ترد heartbeat ----
    def _start_heartbeat(self):
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._stop_event.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, name="client-heartbeat", daemon=True)
        self._hb_thread.start()
        self.log("info", "heartbeat thread started")

    def stop(self):
        """ توقف امن (برای خاموش‌کردن سرویس) """
        self._stop_event.set()
        try:
            self._register_consumer.close()
        except Exception:
            pass
        try:
            self._producer.flush(2.0)
        except Exception:
            pass

    def _heartbeat_loop(self):
        """
        هر heartbeat یک رکورد فشرده‌شونده به تاپیک clients.status می‌فرستد:
        - key = client_id
        - value = { last_seen, version, capabilities, ... }
        """
        while not self._stop_event.is_set():
            try:
                if self.client_id:
                    status = {
                        "schema": "ClientStatusV1",
                        "client_id": self.client_id,
                        "last_seen": self._utcnow_iso(),
                        "meta": self.client_meta,
                    }
                    self._producer.produce(
                        topic=self.status_topic,
                        key=self.client_id.encode("utf-8"),
                        value=json.dumps(status).encode("utf-8"),
                        headers=[("schema", "ClientStatusV1"), ("content_type", "application/json"), ("encoding", "utf-8")],
                    )
                    self._producer.flush(1.0)
            except Exception as e:
                self.log("warn", "heartbeat send failed", error=str(e))
            # مکث تا ضربان بعدی
            time.sleep(self.heartbeat_interval_sec)

    # ---- رفرش توکن ساده (placeholder) ----
    def _refresh_token_if_needed(self):
        """
        اگر زمان باقی‌مانده تا انقضای توکن از حاشیه امن کمتر بود،
        فعلا فقط لاگ می‌زنیم. (در گام‌های بعدی مکانیزم واقعی رفرش را اضافه می‌کنیم.)
        """
        if not self.token_expires_at:
            return
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        if (self.token_expires_at - now) <= timedelta(seconds=self.token_refresh_margin_sec):
            # TODO: فراخوانی واقعی رفرش (مثلا روی تاپیک مخصوص یا HTTP به سرویس Auth)
            self.log("info", "Token is expiring - needs to be refreshed.", expires_at=self.token_expires_at.isoformat())

