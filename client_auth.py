# -*- coding: utf-8 -*-
"""
client_auth.py
---------------
ماژول مسئول «هویت و وضعیت کلاینت» با تکیه بر config.json (هات‌ریلُد):

1) ثبت‌نام کلاینت نزد سرور و دریافت client_id + auth_token
2) ارسال heartbeat دوره‌ای برای اعلام حضور به تاپیک compacted (clients.status)
3) ساخت هدرهای استاندارد امنیتی برای پیام‌های خروجی (ts, nonce, auth, sig, ...)
4) فراهم‌کردن نام تاپیک صندوق اختصاصی کلاینت: cmd.{client_id}

ویژگی‌های کلیدی این نسخه:
- بدون وابستگی به ENV؛ تمام تنظیمات از config.json خوانده می‌شود (با config_manager و هات‌ریلُد).
- اگر کلیدی در config.json نباشد، **پیش‌فرض** منطقی و امن می‌گذارد.
- از confluent_kafka استفاده می‌کند (headers به صورت [(k, v), ...]).

کلیدهای مربوط در config.json و مقادیر قابل قبول:
------------------------------------------------
[kafka.bootstrap_servers] : list[str]
    - مثال: ["localhost:9092"] یا ["10.0.0.10:9092","10.0.0.11:9092"]
    - برای confluent باید به رشتهٔ comma-separated تبدیل شود (داخل کد انجام می‌شود).

[kafka.client_id] : str
    - شناسه پیش‌فرض کلاینت در شروع؛ بعد از ثبت‌نام، مقدار دریافتی از سرور جایگزین می‌شود.

[kafka.topics.status] : str
    - تاپیک Heartbeat/Status (پیش‌فرض: "clients.status").

[kafka.topics.register] : str (اختیاری)
[kafka.topics.register_responses] : str (اختیاری)
    - اگر نبودند، پیش‌فرض‌ها استفاده می‌شود: "clients.register" / "clients.register.responses"

[client_auth.heartbeat_interval_sec] : int (اختیاری، پیش‌فرض 15)
[client_auth.register_timeout_sec] : int (اختیاری، پیش‌فرض 20)
[client_auth.token_refresh_margin_sec] : int (اختیاری، پیش‌فرض 120)
[client_auth.sig_alg] : str  (اختیاری، پیش‌فرض "HMAC-SHA256")
[client_auth.hmac_secret] : str (اختیاری، پیش‌فرض "changeme")
[client_auth.kid] : str (اختیاری، پیش‌فرض "k-2025-09")
[client_auth.consumer_group_prefix] : str (اختیاری، پیش‌فرض "client-register-waiter-")

نکات:
- این ماژول کار مصرف/اجرا/اولویت را انجام نمی‌دهد؛ فقط «هویت، وضعیت و هدرهای امن» را مدیریت می‌کند.
- در گام‌های بعدی آن را به priority_executor و kafka_listener متصل می‌کنیم.
"""

import json
import time
import uuid
import hmac
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# مدیریت کانفیگ با هات‌ریلُد
from config_manager import cfg

# اگر از confluent_kafka استفاده می‌کنید:
from confluent_kafka import Producer, Consumer, KafkaException


def _utcnow_iso() -> str:
    """زمان جاری به صورت ISO8601 در UTC (برای هدرها و رویدادها)."""
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _nonce() -> str:
    """تولید nonce تصادفی برای جلوگیری از replay-attack."""
    return uuid.uuid4().hex


class ClientAuth(object):
    """
    کلاس اصلی مدیریت احراز هویت و ثبت‌نام کلاینت.
    همهٔ تنظیمات از config.json (هات‌ریلُد) خوانده می‌شود.

    مسئولیت‌ها:
    - ارسال درخواست ثبت‌نام به تاپیک `clients.register` یا مقدار تنظیم‌شده در `kafka.topics.register`
    - دریافت پاسخ ثبت‌نام از `clients.register.responses` یا مقدار تنظیم‌شده در `kafka.topics.register_responses`
    - نگهداری client_id، auth_token، و expires_at
    - ارسال heartbeat به `kafka.topics.status`
    - ساخت هدرهای استاندارد برای پیام‌های خروجی
    """

    # --------- ابزار داخلی: خواندن تنظیمات با پیش‌فرض‌های امن ----------
    @staticmethod
    def _read_conf() -> Dict[str, Any]:
        c = cfg()
        # --- Kafka ---
        bs_list = c.get("kafka.bootstrap_servers", ["localhost:9092"])
        # confluent_kafka "bootstrap.servers" باید رشته باشد
        bootstrap_servers = ",".join(bs_list) if isinstance(bs_list, list) else str(bs_list)

        register_topic = c.get("kafka.topics.register", "clients.register")
        register_responses_topic = c.get("kafka.topics.register_responses", "clients.register.responses")
        status_topic = c.get("kafka.topics.status", "clients.status")
        initial_client_id = c.get("kafka.client_id", "client-001")

        # --- ClientAuth specific (اختیاری) ---
        heartbeat_interval_sec = int(c.get("client_auth.heartbeat_interval_sec", 15))
        register_timeout_sec = int(c.get("client_auth.register_timeout_sec", 20))
        token_refresh_margin_sec = int(c.get("client_auth.token_refresh_margin_sec", 120))
        sig_alg = str(c.get("client_auth.sig_alg", "HMAC-SHA256"))
        hmac_secret = str(c.get("client_auth.hmac_secret", "changeme"))
        kid = str(c.get("client_auth.kid", "k-2025-09"))
        consumer_group_prefix = str(c.get("client_auth.consumer_group_prefix", "client-register-waiter-"))

        return {
            "bootstrap_servers": bootstrap_servers,
            "register_topic": register_topic,
            "register_responses_topic": register_responses_topic,
            "status_topic": status_topic,
            "initial_client_id": initial_client_id,
            "heartbeat_interval_sec": heartbeat_interval_sec,
            "register_timeout_sec": register_timeout_sec,
            "token_refresh_margin_sec": token_refresh_margin_sec,
            "sig_alg": sig_alg,
            "hmac_secret": hmac_secret,
            "kid": kid,
            "consumer_group_prefix": consumer_group_prefix,
        }

    def __init__(self, client_meta: Optional[dict] = None, logger=None):
        """
        سازنده:
        - هیچ پارامیتر اتصال/تاپیکی نمی‌گیرد؛ همه چیز از config.json خوانده می‌شود.
        - فقط meta اختیاری است (مثل نسخه، قابلیت‌ها، سیستم‌عامل و ...).
        """
        self._conf = self._read_conf()

        # متادیتای کلاینت (برای ثبت‌نام/heartbeat)
        self.client_meta = client_meta or {}

        # شناسه موقت کلاینت (قبل از گرفتن client_id واقعی)
        self.client_tmp_id = str(uuid.uuid4())

        # پس از ثبت‌نام پر می‌شوند:
        self.client_id: Optional[str] = self._conf["initial_client_id"]  # قبل از ثبت‌نام از مقدار اولیه استفاده می‌کنیم
        self.auth_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None  # datetime (UTC)

        # کنترل ترد heartbeat
        self._stop_event = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None

        # ابزارهای Kafka (Producer/Consumer) بر اساس آخرین کانفیگ
        self._producer = Producer({"bootstrap.servers": self._conf["bootstrap_servers"]})
        self._register_consumer = Consumer({
            "bootstrap.servers": self._conf["bootstrap_servers"],
            "group.id": f"{self._conf['consumer_group_prefix']}{self.client_tmp_id}",
            "auto.offset.reset": "earliest",
            "enable.partition.eof": False,
        })

        # logger ساده اختیاری
        self.log = logger or self._fallback_log

    # ---- ابزار لاگ ساده ----
    def _fallback_log(self, level, msg, **kw):
        print(f"[{level.upper()}] {msg} {kw if kw else ''}")

    # ---- امضای HMAC روی هدرهای حساس + بادی ----
    def _make_signature(self, body_bytes: bytes, headers: Dict[str, Any]) -> str:
        """
        امضا روی ترکیب: body + چند هدر حساس
        توجه: ترتیب ثابت فیلدها مهم است تا امضا پایدار باشد.
        """
        secret = self._conf["hmac_secret"]  # از کانفیگ (هات‌ریلُد) آمده
        parts = []
        for key in ["corr_id", "client_id", "priority", "ts", "nonce"]:
            if key in headers and headers[key] is not None:
                parts.append(f"{key}={headers[key]}")
        header_str = "|".join(parts).encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), header_str + b"||" + body_bytes, hashlib.sha256).hexdigest()
        return digest

    # ---- رفرش تنظیمات هنگام نیاز (هات‌ریلُد) ----
    def _refresh_conf_if_needed(self):
        """
        هر بار که نقطهٔ اتصال حیاتی داریم، کانفیگ را از config.json می‌خوانیم.
        این کار باعث می‌شود تغییرات بدون ری‌استارت اعمال شوند.
        """
        self._conf = self._read_conf()

    # ---- شروع فرآیند ثبت‌نام ----
    def register(self):
        """
        1) ارسال درخواست به تاپیک ثبت‌نام (clients.register یا مقدار کانفیگ)
        2) انتظار برای پاسخ در تاپیک پاسخ ثبت‌نام
        3) ذخیره client_id و auth_token و زمان انقضا
        4) شروع ترد heartbeat
        """
        self._refresh_conf_if_needed()
        self.log("info", "Start client registration")

        corr_id = str(uuid.uuid4())
        req_ts = _utcnow_iso()
        nonce = _nonce()

        # بدنهٔ ثبت‌نام: اطلاعات متای کلاینت + زمان + nonce
        body = {
            "schema": "ClientRegisterV1",
            "client_tmp_id": self.client_tmp_id,
            "meta": self.client_meta,
            "ts": req_ts,
            "nonce": nonce,
        }
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

        # هدرهای پیام ثبت‌نام
        headers = [
            ("schema", "ClientRegisterV1"),
            ("client_tmp_id", self.client_tmp_id),
            ("corr_id", corr_id),
            ("content_type", "application/json"),
            ("encoding", "utf-8"),
        ]

        # ⬇️ تبدیل به bytes
        headers_bytes = [(k, v.encode("utf-8")) for (k, v) in headers]

        # ارسال درخواست ثبت‌نام
        try:
            self._producer.produce(
                topic=self._conf["register_topic"],
                key=self.client_tmp_id.encode("utf-8"),
                value=body_bytes,
                headers=headers_bytes,
            )
            self._producer.flush(5.0)
            self.log("info", "Registration request sent.",
                     topic=self._conf["register_topic"], corr_id=corr_id)
        except Exception as e:
            raise RuntimeError(f"Registration submission failed: {e}")

        # گوش دادن برای پاسخ
        self._register_consumer.subscribe([self._conf["register_responses_topic"]])
        deadline = time.time() + self._conf["register_timeout_sec"]

        response = None
        while time.time() < deadline:
            msg = self._register_consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

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
        self.client_id = response.get("client_id") or self.client_id  # اگر سرور مقدار داد، جایگزین کن
        self.auth_token = response.get("auth_token")
        exp_iso = response.get("expires_at")
        self.token_expires_at = (
            datetime.fromisoformat(exp_iso)
            if exp_iso else (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=24))
        )

        if not self.client_id or not self.auth_token:
            raise ValueError("The registration response is incomplete (client_id or auth_token not present)")

        self.log("info", "Successful registration",
                 client_id=self.client_id, expires_at=self.token_expires_at.isoformat())

        # استارت heartbeat
        self._start_heartbeat()

    # ---- محاسبه نام تاپیک Inbox کلاینت ----
    def inbox_topic(self) -> str:
        """
        نام تاپیک صندوق ورودی اختصاصی کلاینت (بر اساس قرارداد cmd.{client_id}).
        توجه: client_id بعد از register() معتبر است.
        """
        if not self.client_id:
            raise RuntimeError("You are not registered yet; client_id is unknown.")
        return f"cmd.{self.client_id}"

    # ---- ساخت هدرهای استاندارد برای پیام‌های خروجی (مثلا پاسخ‌ها یا ACKها) ----
    def build_outgoing_headers(
        self,
        corr_id: str,
        priority: Optional[int] = None,
        ordering_scope: Optional[str] = None,
        ttl_ms: Optional[int] = None,
        extra_headers: Optional[dict] = None,
        body_bytes: bytes = b"",
    ) -> list:
        """
        هدرهای خروجی را می‌سازد:
        - ts, nonce, client_id, corr_id, auth (JWT)، kid
        - priority, ordering_scope, ttl_ms (در صورت وجود)
        - sig (امضای HMAC روی هدرهای کلیدی + بادی)

        ورودی‌ها:
        - corr_id: شناسه همبستگی برای ردیابی درخواست/پاسخ
        - priority: سطح اهمیت پیام (اختیاری)
        - ordering_scope: دامنه نظم (برای تضمین ترتیب نسبی در یک scope خاص)
        - ttl_ms: زمان ماندگاری پیام (اختیاری)
        - extra_headers: افزودن هدرهای دلخواه
        - body_bytes: بایت‌های بدنه برای لحاظ در امضا
        """
        if not self.client_id or not self.auth_token:
            raise RuntimeError("client_id/auth_token is unknown; call register() first.")

        self._refresh_conf_if_needed()
        self._refresh_token_if_needed()

        ts = _utcnow_iso()
        nonce = _nonce()

        # ابتدا دیکشنری پایه برای امضا
        header_dict = {
            "schema": "ClientReplyV1",  # یا "ClientCommandV1" بسته به قرارداد شما
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

        # محاسبه امضا
        sig = self._make_signature(body_bytes=body_bytes, headers=header_dict)

        # سپس به لیست (name, value) تبدیل می‌کنیم (فرمت استاندارد confluent_kafka)
        headers = [
            ("schema", header_dict["schema"]),
            ("client_id", self.client_id),
            ("corr_id", corr_id),
            ("ts", ts),
            ("nonce", nonce),
            ("auth", self.auth_token),              # JWT
            ("kid", self._conf["kid"]),
            ("sig_alg", self._conf["sig_alg"]),
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

        # هدرهای اضافهٔ کاربر
        if extra_headers:
            for k, v in extra_headers.items():
                headers.append((str(k), str(v)))

        return headers

    # ---- ترد heartbeat ----
    def _start_heartbeat(self):
        """راه‌اندازی ترد ضربان وضعیت (به تاپیک compacted)."""
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._stop_event.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, name="client-heartbeat", daemon=True)
        self._hb_thread.start()
        self.log("info", "heartbeat thread started")

    def stop(self):
        """توقف امن (برای خاموش‌کردن سرویس)"""
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
        هر heartbeat یک رکورد فشرده‌شونده به تاپیک status می‌فرستد:
        - key = client_id
        - value = { last_seen, meta, ... }
        - تاپیک از کانفیگ خوانده می‌شود (هات‌ریلُد).
        """
        while not self._stop_event.is_set():
            try:
                self._refresh_conf_if_needed()
                if self.client_id:
                    status = {
                        "schema": "ClientStatusV1",
                        "client_id": self.client_id,
                        "last_seen": _utcnow_iso(),
                        "meta": self.client_meta,
                    }
                    self._producer.produce(
                        topic=self._conf["status_topic"],
                        key=self.client_id.encode("utf-8"),
                        value=json.dumps(status, ensure_ascii=False).encode("utf-8"),
                        headers=[("schema", "ClientStatusV1"),
                                 ("content_type", "application/json"),
                                 ("encoding", "utf-8")],
                    )
                    self._producer.flush(1.0)
            except Exception as e:
                self.log("warn", "heartbeat send failed", error=str(e))
            # مکث تا ضربان بعدی؛ از کانفیگ خوانده می‌شود (هات‌ریلُد)
            time.sleep(max(1, int(self._conf["heartbeat_interval_sec"])))

    # ---- رفرش توکن ساده (placeholder) ----
    def _refresh_token_if_needed(self):
        """
        اگر زمان باقی‌مانده تا انقضای توکن از حاشیه امن کمتر بود،
        فعلاً فقط لاگ می‌زنیم. (در گام‌های بعدی مکانیزم واقعی رفرش اضافه می‌شود.)
        """
        if not self.token_expires_at:
            return
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        margin = timedelta(seconds=int(self._conf["token_refresh_margin_sec"]))
        if (self.token_expires_at - now) <= margin:
            # TODO: فراخوانی واقعی رفرش (مثلاً روی تاپیک مخصوص یا HTTP به سرویس Auth)
            self.log("info", "Token is expiring - needs to be refreshed.",
                     expires_at=self.token_expires_at.isoformat())
