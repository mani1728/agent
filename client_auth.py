# -*- coding: utf-8 -*-
"""
client_auth.py
---------------
ماژول مسئول «ثبت‌نام/هویت» کلاینت و «ارسال heartbeat» با تکیه بر config.json (هات‌ریلُد).

قابلیت‌ها:
1) ثبت‌نام کلاینت نزد سرور و دریافت client_id + auth_token  (در اولین اجرا یا بوت‌های بعدی)
2) ارسال heartbeat دوره‌ای به تاپیک compacted برای اعلام حضور
3) ساخت هدرهای استاندارد امنیتی برای پیام‌های خروجی (ts, nonce, auth, sig, ...)
4) برگرداندن نام تاپیک inbox اختصاصی کلاینت: cmd.{client_id}
5) ⭐️ «client_id پایدار» با کش محلی روی دیسک → جلوگیری از ساخت client_id/تاپیکِ تازه در هر بوت

نکات مهم:
- تمام تنظیمات از config.json خوانده می‌شوند (با config_manager و هات‌ریلُد).
- اگر بعضی کلیدها در config.json نبودند، پیش‌فرض منطقی اعمال می‌شود.
- از confluent_kafka استفاده شده؛ headers باید لیست جفت‌تاپل (name, bytes) باشد.
"""

# --------------------------
# ایمپورت‌های استاندارد
# --------------------------
import os                     # کار با فایل/مسیر برای کش هویت
import json                   # سریال‌سازی/دیسریال‌سازی JSON
import hashlib                # ساخت اثرانگشت پایدار از ویژگی‌های ماشین
import platform               # تشخیص سیستم/hostname
import uuid                   # ساخت UUID برای nonce و client_tmp_id
import time                   # تایمر برای poll/timeout
import hmac                   # امضای HMAC
import threading              # ترد heartbeat
from datetime import datetime, timedelta, timezone  # زمان‌بندی/ISO
from typing import Optional, Dict, Any              # تایپ‌هینت

# تلاش برای ایمپورت MachineGuid در ویندوز (اختیاری)
try:
    import winreg            # فقط روی ویندوز در دسترس است
except Exception:
    winreg = None

# --------------------------
# تنظیمات/وابستگی‌ها
# --------------------------
from config_manager import cfg                                # هات‌ریلُد کانفیگ
from confluent_kafka import Producer, Consumer, KafkaException  # Kafka I/O

# --------------------------
# مسیر فایل کش هویت پایدار
# (کنار فایل جاری ماژول)
# --------------------------
_IDENTITY_PATH = os.path.join(os.path.dirname(__file__), "agent_identity.json")


# ------------------------------------------------------------
# ابزار: خواندن MachineGuid در ویندوز (شناسه‌ی پایدار سیستم)
# ------------------------------------------------------------
def _read_machine_guid_windows() -> str:
    """MachineGuid ویندوز (پایدار). اگر نبود/خطا → رشته‌ی خالی."""
    if winreg is None:
        return ""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(val or "").strip()
    except Exception:
        return ""


# --------------------------------------------------------------------------
# ابزار: تولید یک client_id پیشنهادیِ «پایدار» بر اساس ویژگی‌های ماشین
# - ابتدا MachineGuid (اگر ویندوز) + hostname + MAC را کنار هم می‌گذاریم
# - از آن‌ها SHA-256 می‌گیریم و 32کاراکتر اول را می‌گذاریم
# - نتیجه: client-<hash>  (کوتاه، خوانا، زیر 64کاراکتر)
# --------------------------------------------------------------------------
def _stable_suggested_client_id() -> str:
    parts = []
    if platform.system().lower().startswith("win"):
        parts.append(_read_machine_guid_windows())       # MachineGuid (در ویندوز)
    parts.append(platform.node() or "")                  # hostname
    try:
        parts.append(hex(uuid.getnode())[2:])           # MAC (تا حد امکان)
    except Exception:
        pass
    seed = "|".join([p for p in parts if p]) or str(uuid.uuid4())  # اگر هیچ چیز نبود، fallback به UUID تصادفی
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"client-{h[:32]}"


# ------------------------------------------------------------
# ابزار: بارگذاری/ذخیره‌ی کش هویت پایدار روی دیسک
# - ساختار فایل: { "client_id": "...", "auth_token": "...", "expires_at": "ISO" }
# ------------------------------------------------------------
def _load_cached_identity() -> Dict[str, Any]:
    """اگر فایل کش وجود داشت، دیکشنری آن را برمی‌گرداند؛ در غیر این صورت {}."""
    try:
        if os.path.exists(_IDENTITY_PATH):
            with open(_IDENTITY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_cached_identity(client_id: str, auth_token: Optional[str] = None, expires_at: Optional[str] = None) -> None:
    """ذخیره‌ی هویت پایدار در فایل کش برای بوت‌های بعدی."""
    data = {
        "client_id": client_id,
        "auth_token": auth_token,
        "expires_at": expires_at,
    }
    try:
        with open(_IDENTITY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # خطای نوشتن کش نباید اجرای سرویس را متوقف کند
        pass


# ------------------------------------------------------------
# ابزارهای کوچک زمان/nonce
# ------------------------------------------------------------
def _utcnow_iso() -> str:
    """زمان جاری UTC به ISO8601 (با offset +00:00)."""
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def _nonce() -> str:
    """تولید nonce تصادفی برای جلوگیری از replay-attack."""
    return uuid.uuid4().hex


# ============================================================
#                         ClientAuth
# ============================================================
class ClientAuth(object):
    """
    کلاس اصلی مدیریت احراز هویت و وضعیت کلاینت.

    مسئولیت‌ها:
    - ارسال درخواست ثبت‌نام به تاپیک `clients.register`
    - دریافت پاسخ ثبت‌نام از `clients.register.responses`
    - نگهداری client_id/auth_token/expiry
    - ارسال heartbeat به تاپیک status (compacted)
    - ساخت هدرهای استاندارد برای پیام‌های خروجی

    ⭐️ با کش محلی، client_id پایدار می‌ماند و هر بار ری‌استارت منجر به ساخت تاپیک/رکورد جدید نمی‌شود.
    """

    # --------------------------------------------------------
    # خواندن تنظیمات از config.json (با مقادیر پیش‌فرض امن)
    # --------------------------------------------------------
    @staticmethod
    def _read_conf() -> Dict[str, Any]:
        c = cfg()  # خواندن snapshot لحظه‌ای از config.json

        # --- Kafka ---
        bs_list = c.get("kafka.bootstrap_servers", ["localhost:9092"])
        bootstrap_servers = ",".join(bs_list) if isinstance(bs_list, list) else str(bs_list)

        register_topic = c.get("kafka.topics.register", "clients.register")
        register_responses_topic = c.get("kafka.topics.register_responses", "clients.register.responses")
        status_topic = c.get("kafka.topics.status", "clients.status")
        initial_client_id = c.get("kafka.client_id", "client-001")  # فقط اگر هیچ client_id کش/پیشنهادی نداشتیم

        # --- ClientAuth specific ---
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

    # --------------------------------------------------------
    # سازنده‌ی کلاس
    # --------------------------------------------------------
    def __init__(self, client_meta: Optional[dict] = None, logger=None):
        """
        - پارامتر اتصال/تاپیک نمی‌گیرد؛ همه‌چیز از config.json خوانده می‌شود.
        - client_meta اختیاری است (OS/نسخه/قابلیت‌ها و ...)
        """
        self._conf = self._read_conf()         # snapshot اولیه از config
        self.client_meta = client_meta or {}   # متادیتای اختیاری برای رجیستر/heartbeat

        # شناسه‌ی موقت برای این فرآیند رجیستر (فقط جهت correlate با پاسخ)
        self.client_tmp_id = str(uuid.uuid4())

        # --- هویت پایدار محلی: cache یا پیشنهاد پایدار ---
        _cached = _load_cached_identity()
        suggested = _stable_suggested_client_id()
        # اگر قبلاً ثبت‌نام کرده‌ایم، همان client_id را برگردان؛ وگرنه پیشنهادیِ پایدار
        self.client_id: Optional[str] = _cached.get("client_id") or suggested or self._conf["initial_client_id"]

        # اگر توکن کش‌شده داشتیم، نگه‌داری (ممکن است در رجیستر جدید بی‌اثر باشد)
        self.auth_token: Optional[str] = _cached.get("auth_token")
        try:
            self.token_expires_at: Optional[datetime] = (
                datetime.fromisoformat(_cached["expires_at"]) if _cached.get("expires_at") else None
            )
        except Exception:
            self.token_expires_at = None

        # کنترل ترد heartbeat
        self._stop_event = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None

        # ابزار Kafka: Producer برای ارسال و Consumer برای دریافت پاسخ رجیستر
        self._producer = Producer({"bootstrap.servers": self._conf["bootstrap_servers"]})
        self._register_consumer = Consumer({
            "bootstrap.servers": self._conf["bootstrap_servers"],
            "group.id": f"{self._conf['consumer_group_prefix']}{self.client_tmp_id}",  # گروه موقت مخصوص همین رجیستر
            "auto.offset.reset": "earliest",
            "enable.partition.eof": False,
        })

        # logger اختیاری (اگر ندادید، یک لاگر ساده‌ی stdout استفاده می‌شود)
        self.log = logger or self._fallback_log

    # --------------------------------------------------------
    # لاگر ساده‌ی پیش‌فرض (stdout)
    # --------------------------------------------------------
    def _fallback_log(self, level: str, msg: str, **kw):
        print(f"[{level.upper()}] {msg} {kw if kw else ''}")

    # --------------------------------------------------------
    # امضای HMAC روی هدرهای حساس + بادی (برای پیام‌های خروجی)
    # --------------------------------------------------------
    def _make_signature(self, body_bytes: bytes, headers: Dict[str, Any]) -> str:
        """
        امضا روی ترکیب: body + هدرهای مهم (corr_id, client_id, priority, ts, nonce)
        ترتیب ثابت کلیدها مهم است تا امضا پایدار باشد.
        """
        secret = self._conf["hmac_secret"]
        parts = []
        for key in ["corr_id", "client_id", "priority", "ts", "nonce"]:
            if key in headers and headers[key] is not None:
                parts.append(f"{key}={headers[key]}")
        header_str = "|".join(parts).encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), header_str + b"||" + body_bytes, hashlib.sha256).hexdigest()
        return digest

    # --------------------------------------------------------
    # رفرش تنظیمات (هر بار نقطه‌ی اتصال حیاتی)
    # --------------------------------------------------------
    def _refresh_conf_if_needed(self):
        """بارخوانی تنظیمات از config.json (هات‌ریلُد)."""
        self._conf = self._read_conf()

    # --------------------------------------------------------
    # شروع فرآیند ثبت‌نام
    # --------------------------------------------------------
    def register(self):
        """
        1) ارسال درخواست رجیستر به تاپیک register
        2) گوش‌دادن پاسخ در تاپیک register_responses
        3) ذخیره‌ی client_id/auth_token/expiry
        4) استارت ترد heartbeat
        """
        self._refresh_conf_if_needed()
        self.log("info", "Start client registration")

        # شناسه‌ی همبستگی درخواست/پاسخ + زمان/nonce
        corr_id = str(uuid.uuid4())
        req_ts = _utcnow_iso()
        nonce = _nonce()

        # --- بدنه‌ی درخواست: meta + ts/nonce + tmp_id ---
        # ⚠️ این‌جا client_id «پایدار» را داخل meta هم می‌فرستیم
        meta = dict(self.client_meta or {})
        meta.setdefault("client_id", self.client_id)
        meta.setdefault("hostname", platform.node() or "")
        # اگر بخواهید، می‌توانید مقادیر زیر را هم اضافه/ارسال کنید:
        # meta["machine_guid"] = _read_machine_guid_windows() or None

        body = {
            "schema": "ClientRegisterV1",
            "client_tmp_id": self.client_tmp_id,
            "meta": meta,           # ← حتماً meta با client_id پایدار
            "ts": req_ts,
            "nonce": nonce,
        }
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

        # --- هدرهای درخواست: حتماً client_id پایدار را هم در هدر بفرست ---
        headers = [
            ("schema", "ClientRegisterV1"),
            ("client_tmp_id", self.client_tmp_id),
            ("client_id", self.client_id),         # ← برای Identity keys: header.client_id
            ("corr_id", corr_id),
            ("content_type", "application/json"),
            ("encoding", "utf-8"),
        ]
        # Kafka باید bytes بگیرد:
        headers_bytes = [(k, v.encode("utf-8")) for (k, v) in headers]

        # --- ارسال درخواست رجیستر ---
        try:
            self._producer.produce(
                topic=self._conf["register_topic"],
                key=self.client_tmp_id.encode("utf-8"),  # key پیام = client_tmp_id (UUID)
                value=body_bytes,
                headers=headers_bytes,
            )
            self._producer.flush(5.0)  # ارسال فوری (در رجیستر بهتر است بلاکینگ باشد)
            self.log("info", "Registration request sent.",
                     topic=self._conf["register_topic"], corr_id=corr_id)
        except Exception as e:
            raise RuntimeError(f"Registration submission failed: {e}")

        # --- دریافت پاسخ رجیستر ---
        self._register_consumer.subscribe([self._conf["register_responses_topic"]])
        deadline = time.time() + self._conf["register_timeout_sec"]

        response = None
        while time.time() < deadline:
            msg = self._register_consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            # دیکود هدرهای دریافتی به str
            raw_headers = msg.headers() or []
            hdrs = {k: (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v) for k, v in raw_headers}

            # باید corr_id یا client_tmp_id خودمان را داشته باشد تا پاسخِ ما باشد
            if hdrs.get("corr_id") != corr_id and hdrs.get("client_tmp_id") != self.client_tmp_id:
                self.log("debug", "register response seen but header mismatch", hdrs=hdrs)
                continue

            # دیکود payload
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:
                continue

            response = payload
            break

        if response is None:
            raise TimeoutError("Registration response not received within the specified time.")

        # --- پردازش پاسخ رجیستر ---
        # انتظار می‌رود: { client_id, auth_token, expires_at (ISO8601), ... }
        server_client_id = response.get("client_id") or self.client_id
        self.client_id = server_client_id
        self.auth_token = response.get("auth_token")
        exp_iso = response.get("expires_at")
        self.token_expires_at = (
            datetime.fromisoformat(exp_iso)
            if exp_iso else (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=24))
        )

        if not self.client_id or not self.auth_token:
            raise ValueError("The registration response is incomplete (client_id or auth_token not present)")

        # ⭐️ ذخیره‌ی هویت برای بوت‌های بعدی (پایداری client_id)
        _save_cached_identity(
            client_id=self.client_id,
            auth_token=self.auth_token,
            expires_at=self.token_expires_at.isoformat()
        )

        self.log("info", "Successful registration",
                 client_id=self.client_id, expires_at=self.token_expires_at.isoformat())

        # --- استارت heartbeat پس از رجیستر موفق ---
        self._start_heartbeat()

    # --------------------------------------------------------
    # نام تاپیک Inbox اختصاصی کلاینت
    # --------------------------------------------------------
    def inbox_topic(self) -> str:
        """
        نام تاپیک دستورات اختصاصی کلاینت (بر اساس قرارداد cmd.{client_id}).
        فقط بعد از register() معتبر است.
        """
        if not self.client_id:
            raise RuntimeError("You are not registered yet; client_id is unknown.")
        return f"cmd.{self.client_id}"

    # --------------------------------------------------------
    # ساخت هدرهای استاندارد برای پیام‌های خروجی (ACK/Reply/Command)
    # خروجی: لیست [(name: str, value: bytes), ...] آماده برای Kafka
    # --------------------------------------------------------
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
        - ts, nonce, client_id, corr_id, auth(JWT), kid, sig_alg, sig (+ اختیاری‌ها)
        - sig = امضای HMAC روی هدرهای کلیدی + بادی
        - خروجی را به bytes انکود می‌کنیم تا مستقیم قابل‌ارسال با Producer باشد
        """
        if not self.client_id or not self.auth_token:
            raise RuntimeError("client_id/auth_token is unknown; call register() first.")

        self._refresh_conf_if_needed()
        self._refresh_token_if_needed()

        ts = _utcnow_iso()
        nonce = _nonce()

        # دیکشنری پایه برای محاسبه‌ی امضا
        header_dict = {
            "schema": "ClientReplyV1",   # یا "ClientCommandV1" بسته به قرارداد
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

        # محاسبه‌ی امضا (HMAC-SHA256)
        sig = self._make_signature(body_bytes=body_bytes, headers=header_dict)

        # ساخت هدرهای خروجی و تبدیل به bytes
        headers = [
            ("schema", header_dict["schema"]),
            ("client_id", self.client_id),
            ("corr_id", corr_id),
            ("ts", ts),
            ("nonce", nonce),
            ("auth", self.auth_token),           # توکن (مثلاً JWT)
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

        # هدرهای اضافه‌ی کاربر
        if extra_headers:
            for k, v in extra_headers.items():
                headers.append((str(k), str(v)))

        # Kafka باید bytes بگیرد:
        return [(k, str(v).encode("utf-8")) for (k, v) in headers]

    # --------------------------------------------------------
    # راه‌اندازی ترد heartbeat (اگر قبلاً فعال نیست)
    # --------------------------------------------------------
    def _start_heartbeat(self):
        """ترد ضربان وضعیت را استارت می‌کند (یک پیام compacted دوره‌ای)."""
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._stop_event.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, name="client-heartbeat", daemon=True)
        self._hb_thread.start()
        self.log("info", "heartbeat thread started")

    # --------------------------------------------------------
    # توقف امن (برای خاموش‌سازی سرویس)
    # --------------------------------------------------------
    def stop(self):
        """بستن consumer و تخلیه‌ی producer."""
        self._stop_event.set()
        try:
            self._register_consumer.close()
        except Exception:
            pass
        try:
            self._producer.flush(2.0)
        except Exception:
            pass

    # --------------------------------------------------------
    # حلقه‌ی heartbeat: هر N ثانیه یک پیام status (compacted) می‌فرستد
    # key=client_id  , value={schema, client_id, last_seen, meta}
    # --------------------------------------------------------
    def _heartbeat_loop(self):
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
                    # هدرهای ساده برای status (نیاز به امضای HMAC نداریم)
                    headers = [
                        ("schema", "ClientStatusV1"),
                        ("content_type", "application/json"),
                        ("encoding", "utf-8"),
                    ]
                    headers_bytes = [(k, v.encode("utf-8")) for (k, v) in headers]

                    self._producer.produce(
                        topic=self._conf["status_topic"],
                        key=self.client_id.encode("utf-8"),
                        value=json.dumps(status, ensure_ascii=False).encode("utf-8"),
                        headers=headers_bytes,
                    )
                    self._producer.flush(1.0)
            except Exception as e:
                self.log("warn", "heartbeat send failed", error=str(e))

            # فاصله‌ی ارسال بعدی (هات‌ریلُد)
            time.sleep(max(1, int(self._conf["heartbeat_interval_sec"])))

    # --------------------------------------------------------
    # رفرش توکن ساده (placeholder)
    # --------------------------------------------------------
    def _refresh_token_if_needed(self):
        """
        اگر زمان باقی‌مانده تا انقضای توکن از «حاشیه‌ی امن» کمتر شد،
        فعلاً فقط لاگ می‌زنیم (TODO: پیاده‌سازی رفرش واقعی).
        """
        if not self.token_expires_at:
            return
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        margin = timedelta(seconds=int(self._conf["token_refresh_margin_sec"]))
        if (self.token_expires_at - now) <= margin:
            self.log("info", "Token is expiring - needs to be refreshed.",
                     expires_at=self.token_expires_at.isoformat())
