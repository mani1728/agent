
---

# kafka\_responder\_Guide.md (راهنمای جامع Producer پاسخ + چانکینگ)

این راهنما جزئیات کامل ماژول `kafka_responder.py` را توضیح می‌دهد: فلسفهٔ طراحی، تنظیمات Producer، چانک‌کردن پاسخ‌های بزرگ، هدرهای استاندارد، و الگوهای استفاده و عیب‌یابی. کد مرجع همین ریپو است.

---

## ۱) مأموریت ماژول

**KafkaResponder** یک لایهٔ ساده و مطمئن برای **ارسال پاسخ‌ها** به تاپیک خروجی (پیش‌فرض: `agent-recive`) است؛ این کلاس:

* پیام‌های بزرگ را به **چانک‌های کوچک** تقسیم می‌کند (قابل تنظیم از طریق تنظیمات)،
* روی هر چانک **هدرهای استاندارد** (corr\_id/seq/total/…) می‌گذارد،
* از **تحویل دقیق و قابل‌اعتماد** با `enable.idempotence` و `acks=all` استفاده می‌کند.

این کلاس معمولاً توسط شنونده (Consumer) بعد از پردازش درخواست‌ها صدا زده می‌شود؛ در پروژهٔ شما، در `kafka_listener.py` از آن استفاده شده است.

---

## ۲) وابستگی به تنظیمات (AppSettings)

`KafkaResponder` تنظیمات خود را از شیء `AppSettings` می‌گیرد (که با `load_settings_from_env()` ساخته می‌شود). فیلدهای مرتبط عبارت‌اند از:

* `kafka_servers` (آدرس Kafka)
* `kafka_response_topic` (تاپیک خروجی، پیش‌فرض `agent-recive`)
* `kafka_compression` (نوع فشرده‌سازی Producer: `zstd|lz4|gzip|snappy`)
* `kafka_linger_ms`, `kafka_batch_num`, `kafka_max_inflight` (تنظیمات کارایی Producer)
* `kafka_resp_max_part_bytes` (حداکثر اندازهٔ هر چانک پاسخ، پیش‌فرض 900KB)

> این فیلدها هنگام ساخت Producer داخل کلاس استفاده می‌شوند.

---

## ۳) نمای کلی کلاس و متدها

### ۳.۱) سازندهٔ کلاس

```python
responder = KafkaResponder(settings)
```

* Producer با گزینه‌های زیر ساخته می‌شود:

  * `enable.idempotence=True`، `acks='all'` → تحویل مطمئن
  * `compression.type=settings.kafka_compression`
  * `linger.ms`, `batch.num.messages`, `max.in.flight.requests.per.connection` ← از تنظیمات
  * `retries=1000000` برای تاب‌آوری بالا در خطوط ناپایدار.

### ۳.۲) چانک‌کردن بایت‌ها: `_chunk_bytes(data, max_part) -> List[bytes]`

* ورودی: `data` (bytes)، اندازهٔ هر پارت (`max_part`)
* خروجی: لیست پارت‌ها؛ اگر داده خالی شد، حداقل یک چانک خالی برمی‌گرداند تا پروتکل طرف مقابل ساده بماند.

### ۳.۳) کال‌بک تحویل: `_delivery_cb(err, msg)`

* اگر خطا رخ دهد، اینجا قابل مشاهده است (در کد فعلی فقط no-op است).

### ۳.4) ارسال پاسخ: `send_result(corr_id, payload_obj, schema='Mt5ResultV1', key='Mt5_Manager', headers_extra=None)`

**Pipeline ارسال:**

1. `payload_obj` → `json.dumps(..., ensure_ascii=False, separators=(',', ':'))` → `bytes`
2. تقسیم به چانک‌ها با `_chunk_bytes(..., settings.kafka_resp_max_part_bytes)`
3. برای هر چانک هدرهای استاندارد ست می‌شود:

   * `corr_id`: همان ورودی تابع
   * `schema`: پیش‌فرض `"Mt5ResultV1"`
   * `seq`: شمارهٔ ترتیب چانک (۱…N)
   * `total`: تعداد کل چانک‌ها
   * `content_type`: `"application/json"`
   * `encoding`: `"utf-8"`
   * به‌علاوهٔ `headers_extra` در صورت نیاز
4. هر چانک با `produce` به `settings.kafka_response_topic` ارسال می‌شود (کلید پیش‌فرض: `"Mt5_Manager"`)، سپس `flush()` فراخوانی می‌شود.

> این طرح هدرها باعث می‌شود مصرف‌کنندهٔ پاسخ بتواند به‌سادگی پیام را **ترکیب مجدد (reassemble)** کند: با `corr_id` گروه‌بندی، سپس بر اساس `seq` مرتب، تا رسیدن به `total` تکمیل شود.

---

## ۴) قرارداد Envelope پاسخ

در شنونده (`kafka_listener.py`) خروجی هر فراخوانی متد به یک **Envelope استاندارد** تبدیل می‌شود و با همین کلاس ارسال می‌گردد. ساختار Envelope نمونه (سمت Listener) شامل موارد زیر است:
`schema`, `corr_id`, `class`, `method`, `request_index`, `status`, `result`, و گاهی `meta` (مثل زمان اجرا، هدرهای ورودی).
این Envelope سپس در `send_result(...)` به JSON تبدیل و چانک/ارسال می‌شود.

---

## ۵) نمونه‌های کاربرد

### ۵.۱) سناریوی معمول (داخل Listener)

```python
from kafka_responder import KafkaResponder
from config_logging import load_settings_from_env

settings = load_settings_from_env()
responder = KafkaResponder(settings)

payload = {
  "schema": "Mt5ResultV1",
  "corr_id": "123e4567-…",
  "class": "Mt5_Manager",
  "method": "trade_manager",
  "request_index": 1,
  "status": "ok",
  "result": {"retcode": 10009, "comment": "DONE"}
}
responder.send_result(
  corr_id=payload["corr_id"],
  payload_obj=payload,
  key=payload["class"],  # برای پارتیشنینگ سازگار
)
```

* اگر خروجی بسیار بزرگ باشد، به‌طور خودکار به چند پارت تقسیم می‌شود؛ هر پارت هدرهای `seq/total` خواهد داشت.

### ۵.۲) افزودن هدرهای سفارشی

```python
responder.send_result(
  corr_id=corr_id,
  payload_obj=payload_obj,
  headers_extra=[("debug", b"1"), ("src", b"listener")],
)
```

* این هدرها علاوه بر هدرهای استاندارد ارسال می‌شوند.

---

## ۶) نکات کارایی و تحویل

* **Idempotence + acks=all**: مقاومت بالا در برابر تکرار و از دست‌دادن پیام‌ها.
* **Compression**: حجم شبکه و هزینهٔ ذخیره‌سازی را کم می‌کند؛ مقدار را با `KAFKA_COMPRESSION` تنظیم کنید.
* **Micro-batching**: با `linger.ms` و `batch.num.messages` تاخیر و throughput را بالانس کنید.
* **Inflight محدود**: `max.in.flight.requests.per.connection` برای حفظ ترتیب پیام‌ها روی Producer کنترل می‌شود.
* **Chunk Size**: `kafka_resp_max_part_bytes` را متناسب با حداکثر اندازهٔ پیام مجاز بروکر/شبکه تنظیم کنید (پیش‌فرض: 900KB).

---

## ۷) Best Practices

* `key` را با نام کلاس مقصد (مثل `"Mt5_Manager"`) ست کنید تا پارتیشنینگ و مسیر‌دهی پیام‌ها **سازگار** بماند.
* اگر مصرف‌کنندهٔ سمت مقابل **ترکیب مجدد** انجام می‌دهد، حتماً منطق reassemble را بر اساس `(corr_id, seq, total)` پیاده‌سازی کنید.
* اگر پاسخ‌ها بزرگ هستند (DataFrameهای حجیم)، قبل از ارسال، خلاصه‌سازی/پیش‌نمایش کنید و دادهٔ کامل را در استوریج جانبی بگذارید (در صورت نیاز).
* از `ensure_ascii=False` استفاده می‌شود؛ بنابراین یونیکد (فارسی) به‌صورت صحیح ارسال می‌شود.
* بعد از `produce(...)` در هر نوبت، در پایان آرایهٔ پارت‌ها `flush()` انجام می‌شود؛ اگر throughput شما بالاست و latency کمی اهمیت دارد، امکان **batching** سطح بالاتری را در نظر بگیرید.

---

## ۸) عیب‌یابی سریع

| علامت/خطا                        | علت محتمل                          | راه‌حل                                                                                               |
| -------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| مصرف‌کننده پیام‌های ناقص می‌بیند | reassemble نشده                    | در سمت مصرف‌کننده بر اساس `corr_id` گروه‌بندی و با `seq/total` ترکیب کنید.                           |
| ترتیب چانک‌ها به‌هم ریخته        | ترتیب تحویل Kafka بین پارتیشن‌ها   | `key` یکسان نگه دارید تا همهٔ چانک‌ها در یک پارتیشن بیفتند؛ `max.in.flight` پایین نگه داشته شده است. |
| فشار شبکه/CPU بالاست             | فشرده‌سازی غیرفعال یا نامناسب      | `KAFKA_COMPRESSION` را (مثلاً `zstd`) تنظیم کنید.                                                    |
| تأخیر زیاد                       | `linger.ms` زیاد یا flush‌های مکرر | `linger.ms` را کاهش دهید، یا طراحی batch را بازنگری کنید.                                            |
| خطاهای پراکندهٔ تحویل            | ناپایداری شبکه/بروکر               | مقدار `retries` بسیار بالا است؛ لاگ بروکر/شبکه را بررسی کنید؛ ظرفیت کلاستر را بسنجید.                |

---

## ۹) پرسش‌های پرتکرار (FAQ)

**۱) چرا از چانک‌کردن استفاده می‌کنیم؟**
برای رعایت محدودیت اندازهٔ پیام در Kafka و جلوگیری از drop/خطاهای `MessageSizeTooLarge`، پاسخ‌های بزرگ به چند پیام کوچک تقسیم می‌شوند و با `seq/total` دوباره کنار هم قرار می‌گیرند.

**۲) چرا `idempotence` و `acks=all` فعال هستند؟**
برای **تحویل دقیق** (Exactly-Once Semantics در سطح Producer) و اطمینان از پایایی پیام‌ها—این ترکیب احتمال از دست رفتن یا تکراری‌شدن ناخواستهٔ پیام‌ها را کم می‌کند.

**۳) چطور اندازهٔ چانک را تنظیم کنم؟**
با `KAFKA_RESPONSE_MAX_PART_BYTES` (در `AppSettings`)؛ مقدار پیش‌فرض 900KB است.

---

## ۱۰) چک‌لیست استقرار (Production)

* [ ] `KAFKA_SERVERS` مطابق کلاستر تولید
* [ ] `KAFKA_RESPONSE_TOPIC` درست مقداردهی شده
* [ ] `KAFKA_COMPRESSION=zstd` یا گزینهٔ مناسب زیرساخت
* [ ] `KAFKA_RESPONSE_MAX_PART_BYTES` متناسب با `message.max.bytes` بروکر
* [ ] مانیتورینگ نرخ ارسال/تاخیر/خطاهای تحویل

---

## ۱۱) ارتباط با سایر اجزا

* **Listener**: در `kafka_listener.py`، پس از اجرای متد مقصد و سریال‌سازی امن نتیجه، با `KafkaResponder.send_result(...)` پاسخ ارسال می‌شود.
* **Logging/Settings**: پارامترهای Kafka از `AppSettings` می‌آیند که در `config_logging.py` تعریف/خوانده شده‌اند.

---

