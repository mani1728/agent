# config\_logging\_Guide.md (راهنمای جامع ماژول لاگ‌گذاری)

این راهنما تمام جزئیات ماژول `config_logging.py` را پوشش می‌دهد: فلسفهٔ طراحی، ورودی‌های پیکربندی از ENV، کلاس تنظیمات، فرمت‌ها و هندلرهای لاگ، و الگوهای استفاده در محیط توسعه و پروداکشن. کد مرجع همین ریپو است.

---

## ۱) خلاصهٔ ماژول

* **هدف:** یک نقطهٔ متمرکز و ایمن برای پیکربندی لاگ‌ها و خواندن تنظیمات اپلیکیشن از ENV.
* **خروجی اصلی:**

  * `AppSettings`: داده‌ساخت تنظیمات برنامه (Kafka، Logging، پارامترهای اختیاری MT5).
  * `load_settings_from_env()`: بارگذاری تنظیمات از ENV با پیش‌فرض‌های امن.
  * `setup_logging(settings)`: راه‌اندازی کامل لاگ‌گذاری (کنسول Human/JSON + فایل با Rotation) و برگرداندن یک logger سطح-اپ.

---

## ۲) ساختار کلی و اجزای کلیدی

### ۲.۱) AppSettings (dataclass)

کلاس تنظیمات سراسری که یک‌بار ساخته می‌شود و به سایر ماژول‌ها تزریق می‌گردد. مهم‌ترین فیلدها:

* **Kafka (پایه و پاسخ):**
  `kafka_servers`, `kafka_request_topic`, `kafka_response_topic`, `kafka_group_id`,
  `kafka_compression`, `kafka_linger_ms`, `kafka_batch_num`, `kafka_max_inflight`,
  `kafka_resp_max_part_bytes`.

* **Logging:**
  `log_level`, `log_json`, `log_file`, `log_max_bytes`, `log_backups`.

* **MT5 (اختیاری):**
  `mt5_path`, `mt5_login`, `mt5_password`, `mt5_server`.

### ۲.۲) توابع کمکی ENV

* `_get_bool_env(name, default)` → نگاشت امن `"true/1/yes/y"` به `True`.
* `_get_int_env(name, default)` → تبدیل امن رشته به `int` با fallback به مقدار پیش‌فرض.

### ۲.۳) بارگذاری تنظیمات از ENV

`load_settings_from_env()` تمام فیلدهای `AppSettings` را با خواندن ENV مقداردهی می‌کند و پیش‌فرض‌های امن اعمال می‌شود.

### ۲.۴) راه‌اندازی لاگ‌ها

`setup_logging(settings)`:

* پاکسازی هندلرهای قبلی روت لاگر
* ساخت **کنسول** با فرمت **Human** یا **JSON** (بر اساس `log_json`)
* ساخت **RotatingFileHandler** با اندازه و تعداد پشتیبان‌ها
* کاهش verbosity کتابخانه‌های پرحرف (مثل `confluent_kafka`, `urllib3`)
* ایجاد یک لاگر اپلیکیشن به نام `"App"` و ثبت پیام آغازین.

---

## ۳) متغیرهای محیطی (ENV) و مقادیر پیش‌فرض

| ENV                             | پیش‌فرض                | توضیح                                         |     |      |          |
| ------------------------------- | ---------------------- | --------------------------------------------- | --- | ---- | -------- |
| `KAFKA_SERVERS`                 | `192.168.1.254:9092`   | آدرس/های کافکا (Comma-separated)              |     |      |          |
| `KAFKA_TOPIC`                   | `agent-send`           | تاپیک درخواست (Consumer)                      |     |      |          |
| `KAFKA_RESPONSE_TOPIC`          | `agent-recive`         | تاپیک پاسخ (Producer)                         |     |      |          |
| `KAFKA_GROUP_ID`                | `kafka_listener_group` | گروه مصرف‌کننده                               |     |      |          |
| `KAFKA_COMPRESSION`             | `zstd`                 | نوع فشرده‌سازی Producer: \`zstd               | lz4 | gzip | snappy\` |
| `KAFKA_LINGER_MS`               | `10`                   | تجمیع میکروبچینگ (ms)                         |     |      |          |
| `KAFKA_BATCH_NUM`               | `1000`                 | حداکثر پیام در هر batch                       |     |      |          |
| `KAFKA_MAX_INFLIGHT`            | `5`                    | کنترل ترتیب تحویل (in-flight)                 |     |      |          |
| `KAFKA_RESPONSE_MAX_PART_BYTES` | `921600`               | سایز هر چانک پاسخ (قبل از فشرده‌سازی)         |     |      |          |
| `LOG_LEVEL`                     | `INFO`                 | سطح لاگ: `DEBUG/INFO/WARNING/ERROR/CRITICAL`  |     |      |          |
| `LOG_JSON`                      | `false`                | لاگ JSON در کنسول/فایل (true/false)           |     |      |          |
| `LOG_FILE`                      | `logs/app.log`         | مسیر فایل لاگ (پوشه به‌صورت امن ساخته می‌شود) |     |      |          |
| `LOG_MAX_BYTES`                 | `10485760`             | حداکثر حجم هر فایل (۱۰MB) برای Rotation       |     |      |          |
| `LOG_BACKUPS`                   | `10`                   | تعداد فایل‌های پشتیبان Rotation               |     |      |          |
| `MT5_PATH`                      | —                      | مسیر ترمینال (اختیاری)                        |     |      |          |
| `MT5_LOGIN`                     | —                      | لاگین حساب (اختیاری)                          |     |      |          |
| `MT5_PASSWORD`                  | —                      | رمز حساب (اختیاری)                            |     |      |          |
| `MT5_SERVER`                    | —                      | نام سرور بروکر (اختیاری)                      |     |      |          |

> نکته: نگاشت بولی‌ها و اعداد با توابع کمکی امن انجام می‌شود تا خطاهای فرمت ENV باعث کرش نشوند.

---

## ۴) فرمت‌کننده‌ها (Formatters)

### ۴.۱) Human Formatter

`"%(asctime)s | %(levelname)s | %(name)s | %(message)s"` با `datefmt="%Y-%m-%d %H:%M:%S"` برای خوانایی در توسعه.

### ۴.۲) JSON Formatter

کلاس داخلی `_JsonFormatter` که payload استاندارد شامل `ts`, `level`, `logger`, `msg` و در صورت وجود `exc`/`extra` را تولید می‌کند—سازگار با ELK/Graylog.

---

## ۵) هندلرها (Handlers)

* **StreamHandler (stdout):** سطح و فرمت بر اساس تنظیمات، همیشه فعال.
* **RotatingFileHandler:** مسیر فایل، اندازهٔ چرخش، تعداد پشتیبان‌ها؛ با همان فرمت Human/JSON تنظیم می‌شود.

> اگر ساخت پوشهٔ لاگ شکست بخورد، برنامه بدون خطا فقط با کنسول ادامه می‌دهد.

---

## ۶) ادغام با سایر ماژول‌ها

* `main.py` → ابتدا `load_settings_from_env()` و سپس `setup_logging(settings)` را فراخوانی می‌کند؛ بعد سایر اجزا را می‌سازد.
* `kafka_listener.py`، `kafka_responder.py` و … از تنظیمات آمادهٔ `AppSettings` بهره می‌برند (Kafka/Logging).

---

## ۷) الگوهای استفاده (Usage Patterns)

### ۷.۱) حداقل کد راه‌اندازی

```python
from config_logging import load_settings_from_env, setup_logging

settings = load_settings_from_env()
logger = setup_logging(settings)
logger.info("App started")
```

### ۷.۲) اجرای اپ با ENV سفارشی (مثال Linux/Mac)

```bash
LOG_LEVEL=DEBUG \
LOG_JSON=true \
LOG_FILE=logs/app.log \
KAFKA_SERVERS="10.0.0.12:9092,10.0.0.13:9092" \
python main.py
```

### ۷.۳) JSON Logging در پروداکشن

* `LOG_JSON=true` → خروجی JSON برای الحاق به **ELK/Graylog/Grafana Loki** بسیار مناسب است.
* سطح لاگ مناسب Production معمولاً `INFO` یا `WARNING` است.

---

## ۸) نکات امنیتی و Best Practices

* **Rotation فعال** است؛ از پر شدن دیسک جلوگیری می‌کند. حجم و تعداد پشتیبان‌ها را با توجه به محیط تنظیم کنید.
* مسیر `LOG_FILE` را روی یک دیسک/پارتیشن مطمئن و مانیتور‌شده قرار دهید.
* در صورت نیاز به ساختار **json** برای SIEM، `LOG_JSON=true` را الزامی کنید.
* سطح لاگ بالا (`DEBUG`) را در محیط Production محدود کنید؛ ممکن است دادهٔ حساس در لاگ بیاید.
* لاگ‌های کتابخانه‌های پرحجم را کاهش می‌دهیم (`confluent_kafka`, `urllib3`) تا نویز خروجی کم شود.

---

## ۹) عیب‌یابی سریع (Troubleshooting)

| مشکل                     | علت محتمل                 | راه‌حل                                                                                                                  |
| ------------------------ | ------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| لاگ فایل ساخته نمی‌شود   | عدم دسترسی/مسیر نامعتبر   | مسیر `LOG_FILE` را بررسی کنید؛ پوشه به‌صورت best-effort ساخته می‌شود اما خطاها نادیده گرفته می‌شوند—مسیر را درست بدهید. |
| لاگ‌ها JSON نیستند       | `LOG_JSON=false` یا unset | `LOG_JSON=true` بگذارید و اپ را ری‌استارت کنید.                                                                         |
| حجم لاگ زیاد است         | `LOG_LEVEL=DEBUG`         | در Production سطح را `INFO` یا `WARNING` کنید؛ Rotation را هم افزایش دهید.                                              |
| نویز زیاد از کتابخانه‌ها | سطح لاگ پیش‌فرض آن‌ها     | این ماژول سطح برخی کتابخانه‌ها را کاهش داده است؛ اگر کافی نیست، در ابتدای اپ سطح‌شان را پایین‌تر ببرید.                 |

---

## ۱۰) سؤالات پرتکرار (FAQ)

**۱) چرا JSON Formatter جدا نوشته شده؟**
برای کنترل دقیق payload و هماهنگی با ابزارهای مانیتورینگ/تحلیل لاگ، و جلوگیری از سربار غیرضروری.

**۲) اگر پوشهٔ لاگ وجود نداشت چه می‌شود؟**
تلاش برای ساخت انجام می‌شود؛ اگر شکست بخورد اپ همچنان با کنسول ادامه می‌دهد (Fail-open).

**۳) چگونه extra fields را در JSON لاگ کنم؟**
با `logger.info("msg", extra={"extra": {"key": "value"}})`—\_JsonFormatter در صورت وجود `record.extra` آن را merge می‌کند.

---

## ۱۱) چک‌لیست پیش از پروداکشن

* [ ] `LOG_JSON=true`
* [ ] `LOG_LEVEL=INFO` یا بالاتر
* [ ] مسیر امن برای `LOG_FILE` و مانیتورینگ حجم دیسک
* [ ] اندازهٔ مناسب برای `LOG_MAX_BYTES` و `LOG_BACKUPS`
* [ ] پیکربندی Kafka (`KAFKA_SERVERS`, …) مطابق زیرساخت تولید

---

## ۱۲) تغییرات و نسخه‌گذاری

* **نسخهٔ فعلی:** مطابق کد در ریپو.
* تغییرات آیندهٔ محتمل: پشتیبانی از Structured Logging با key/value بیشتر؛ ارسال مستقیم به sinkهای راه‌دور (Syslog/HTTP) برحسب نیاز.

---
