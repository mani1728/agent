
---

# kafka\_listener\_Guide.md (راهنمای جامع Consumer + فراخوانی متدها + Envelope پاسخ)

این راهنما همه‌چیز دربارهٔ ماژول `kafka_listener.py` را پوشش می‌دهد: معماری Consumer، پارس و نرمال‌سازی پیام‌ها، فراخوانی ایمن متدهای مقصد، بسته‌بندی استاندارد پاسخ (Envelope)، ارسال خروجی، مدیریت خطا و خاموشی ایمن. کد مرجع همین ریپو است.

---

## ۱) مأموریت ماژول

**KafkaListener** نقش «درگاه ورودی» را بر عهده دارد:

* اتصال به Kafka به‌عنوان **Consumer** و اشتراک تاپیک ورودی (پیش‌فرض: `agent-send`).
* دریافت پیام‌ها، پارس `key/value/headers` و **نرمال‌سازی پارامترها** با `mt5_utils.convert_params`.
* فراخوانی متدهای کلاس مقصد (مثل `Mt5_Manager`) بر اساس `method` هر فرمان.
* بسته‌بندی نتیجه در **Envelope استاندارد** و ارسال آن با `KafkaResponder` به تاپیک خروجی (پیش‌فرض: `agent-recive`).
* مدیریت سیگنال‌ها برای **خاموشی ایمن**.

---

## ۲) وابستگی‌ها و اجزای کلیدی

* **Kafka Consumer:** `confluent_kafka.Consumer` برای شنود تاپیک ورودی
* **مدیر مقصد:** `Mt5_Manager` (کلاس اصلی تعامل با MT5)
* **تنظیمات:** `AppSettings` از `config_logging.py` (آدرس‌ها، نام تاپیک‌ها، …)
* **پاسخ‌دهنده:** `KafkaResponder` برای ارسال Envelope به تاپیک خروجی
* **ابزار تبدیل/سریال‌سازی:** `convert_params` و `safe_serialize` از `mt5_utils.py`

> نگاشت کلاس‌ها در `CLASS_MAP` انجام می‌شود؛ فعلاً `"Mt5_Manager": Mt5_Manager` تعریف شده است و بعداً قابل گسترش است.

---

## ۳) چرخهٔ عمر Listener

1. **راه‌اندازی**

   * ساخت نمونه از کلاس‌های مقصد (`_init_managers`) و ذخیره در `manager_instances`
   * ساخت و اتصال Consumer به Kafka و **subscribe** به تاپیک ورودی (`_init_consumer`)
   * تنظیم هندلرهای سیگنال برای **SIGINT/SIGTERM** جهت خاموشی ایمن

2. **حلقهٔ شنود (`listen`)**

   * `poll(1.0)` با تایم‌اوت ۱ ثانیه
   * چک خطاهای Kafka (به‌جز EOF پارتیشن)
   * استخراج `key` (trim و پاکسازی کوتیشن‌ها)، `value` و `headers` (با decode امن)
   * تعیین `corr_id` از هدرها یا **ساخت UUID** در صورت نبود
   * فراخوانی `_process_one(...)` برای پردازش پیام

3. **پردازش هر پیام (`_process_one`)**

   * اعتبارسنجی نام کلاس (`key`) در `manager_instances`
   * پارس `value` با `json.loads` و **fallback** به `ast.literal_eval` برای انعطاف بیشتر
   * اطمینان از لیست بودن دستورات: اگر یک دیکشنری بود، به لیست تبدیل می‌شود
   * برای هر دستور:

     * اعتبارسنجی ساختار (`dict` بودن، وجود `method`)
     * تبدیل امن پارامترها با `convert_params` (timeframe/flags/order\_type/date\*/request.\*)
     * **فراخوانی متد واقعی** از نمونه کلاس مقصد با `**params`
     * ثبت لاگ‌های قبل/بعد از فراخوانی با `safe_serialize`
     * ارسال Envelope پاسخ با وضعیت `ok` یا `error` (جزئیات در بخش ۵)

4. **خاموشی ایمن**

   * در `finally`، `consumer.close()` با محافظ خطا صدا زده می‌شود.

---

## ۴) فرمت ورودی از Kafka

* **key:** نام کلاس مقصد. در این پروژه باید `"Mt5_Manager"` باشد تا به نمونهٔ همان کلاس نگاشت شود.
* **value:** یک **آرایه** از دستورات؛ هر دستور یک دیکشنری شامل `method` و `params` است.
* **headers (اختیاری):** شامل `corr_id`/`correlation_id` که برای هم‌بستگی پاسخ‌ها استفاده می‌شود؛ در نبود، به‌طور خودکار ساخته می‌شود.

### نمونهٔ value معتبر

```json
[
  {"method": "trade_manager", "params": {"action": "total"}},
  {"method": "manage_symbols", "params": {"action": "tick", "symbol": "EURUSD"}}
]
```

> اگر `value` JSON نبود، تلاش دوم با `ast.literal_eval` انجام می‌شود تا ورودی‌های سازگار ولی غیر-JSON نیز پوشش داده شوند.

---

## ۵) Envelope پاسخ (قرارداد خروجی)

برای هر دستور، پاسخی با ساختار زیر ارسال می‌شود (به‌ازای همان `corr_id` ورودی):

```json
{
  "schema": "Mt5ResultV1",
  "corr_id": "<uuid>",
  "class": "<class_name>",
  "method": "<method_name>",
  "request_index": <1-based index>,
  "status": "ok" | "error",
  "result": <JSON-safe object>,
  "meta": { "elapsed_ms": <int>, "in_headers": {...}, "src": {"partition": ..., "offset": ...} }
}
```

* `result` با `safe_serialize` تبدیل می‌شود تا شامل انواع غیر JSON نیز بدون خطا قابل ارسال باشد.
* Envelope با `KafkaResponder.send_result(...)` به تاپیک خروجی ارسال می‌شود؛ اگر بزرگ باشد، **چانک** می‌شود و هدرهای `seq/total` هم اضافه می‌گردد.

---

## ۶) مدیریت خطا و سناریوهای خاص

* **کلاس یافت نشد:** اگر `key` با هیچ نمونه‌ای در `manager_instances` مچ نشود، Envelope با `status="error"` و توضیح ارسال می‌شود.
* **پارس ناموفق:** خطای `Parse error` ثبت و پاسخ خطا برگردانده می‌شود.
* **دستور نامعتبر:** اگر آیتم لیست دیکشنری نباشد یا `method` در کلاس وجود نداشته باشد، پاسخ خطا برای همان ایندکس ارسال می‌شود.
* **تبدیل پارامترها:** اگر `convert_params` استثناء بدهد، پاسخ خطا با پیام «Parameter conversion failed» ارسال می‌شود.
* **TypeError در امضای متد:** هنگام عدم تطابق پارامترها، پاسخ خطا با پیام «Invalid parameters…» ارسال می‌شود.
* **خطای غیرمنتظره در اجرای متد:** لاگ استثنا و ارسال پاسخ خطا با `str(e)`.

> رویدادها و نتایج با لاگ‌های سطح INFO/ERROR/EXCEPTION ثبت می‌شوند تا در تولید قابل رهگیری باشند.

---

## ۷) یکپارچگی با سایر بخش‌ها

* **تنظیمات:**
  `AppSettings` از `config_logging.py` خوانده می‌شود (سرورها، تاپیک‌ها، گروه مصرف‌کننده، سطح لاگ)؛ در `main.py` ابتدا `setup_logging` و سپس ساخت Listener انجام می‌شود.

* **پاسخ‌دهنده:**
  همهٔ پاسخ‌ها از مسیر `KafkaResponder` عبور می‌کنند؛ این کلاس پیام‌های بزرگ را **چانک** و هدرهای `seq/total` را اضافه می‌کند.

* **کلاس مقصد (Mt5\_Manager):**
  متدهای اجرایی (manage\_connection/manage\_symbols/…/trade\_manager/…) آنجا پیاده‌سازی شده‌اند و ورودی‌ها پس از `convert_params` به آن‌ها داده می‌شوند.

* **ابزار تبدیل/سریال‌سازی:**
  `convert_params` و `safe_serialize` تضمین می‌کنند که ورودی/خروجی برای MT5/Kafka **ایمن و سازگار** باشند.

---

## ۸) الگوی راه‌اندازی و اجرا

### ۸.۱) از طریق `main.py`

```python
from config_logging import load_settings_from_env, setup_logging
from kafka_listener import KafkaListener

def main():
    settings = load_settings_from_env()
    setup_logging(settings)
    listener = KafkaListener(settings)
    listener.listen()

if __name__ == "__main__":
    main()
```

این الگو در پروژه موجود است و **نقطهٔ شروع** را شکل می‌دهد.

### ۸.۲) ENV نمونه (Linux/Mac)

```bash
KAFKA_SERVERS="192.168.1.254:9092" \
KAFKA_TOPIC="agent-send" \
KAFKA_RESPONSE_TOPIC="agent-recive" \
KAFKA_GROUP_ID="kafka_listener_group" \
LOG_LEVEL=INFO LOG_JSON=true LOG_FILE=logs/app.log \
python main.py
```

> سطوح لاگ و JSON Logging را متناسب با محیط تنظیم کنید.

---

## ۹) بهترین‌عمل‌ها (Best Practices)

* **تک‌منبع حقیقت برای نگاشت کلاس‌ها:** فقط از `CLASS_MAP` استفاده کنید؛ افزودن کلاس جدید = تعریف آن و اضافه‌کردن به این دیکشنری.
* **Corr-ID الزامی:** اگر فرستنده نداد، خود Listener می‌سازد؛ سمت مصرف‌کنندهٔ پاسخ، **ترکیب مجدد** (reassemble) را با `(corr_id, seq, total)` انجام دهید.
* **تبدیل ورودی‌ها قبل از اجرا:** همیشه `convert_params` را برای جلوگیری از TypeError/ValueError اجرا کنید.
* **ایمن‌سازی خروجی‌ها:** برای لاگ و ارسال، `safe_serialize` را به‌کار ببرید تا انواع پیچیده مانند `datetime/DataFrame` باعث خطای JSON نشوند.
* **خاموشی ایمن:** هندلرهای SIGINT/SIGTERM را نگه دارید تا Consumer به‌درستی `close()` شود.

---

## ۱۰) عیب‌یابی سریع

| علامت/خطا                               | علت محتمل                                    | راه‌حل                                                                                          |
| --------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `Class 'X' not found…`                  | `key` اشتباه یا کلاس در `CLASS_MAP` ثبت نیست | `key` پیام و `CLASS_MAP` را بررسی کنید                                                          |
| `Parse error: …`                        | `value` JSON نامعتبر                         | ورودی را JSON معتبر بفرستید؛ یا مطمئن شوید literal\_eval هم آن را می‌فهمد                       |
| `Method 'm' not found in 'Mt5_Manager'` | متد در کلاس مقصد وجود ندارد                  | نام متد/نسخهٔ کلاس را بررسی کنید                                                                |
| `Parameter conversion failed: …`        | فرمت تاریخ/کانستنت/… نامعتبر                 | ورودی‌ها را طبق راهنمای `mt5_utils` بفرستید (ISO datetime، نام دقیق کانستنت‌ها)                 |
| `Invalid parameters for …`              | امضای تابع با ورودی نمی‌خواند                | شکل دقیق پارامترهای متد مقصد را با Guide آن بررسی کنید                                          |
| پاسخ خیلی بزرگ/قطع‌شده                  | محدودیت اندازهٔ پیام Kafka                   | سمت مصرف‌کننده **reassemble** با `seq/total` را پیاده کنید؛ سایز چانک را در تنظیمات افزایش دهید |

---

## ۱۱) پرسش‌های پرتکرار (FAQ)

**۱) چرا علاوه بر JSON، `ast.literal_eval` هم داریم؟**
برای انعطاف بیشتر در محیط‌های مختلف/نسخه‌های قدیمی که گاهی payloadها به‌شکل شبه‌پایتون ارسال می‌شوند؛ البته توصیهٔ اصلی همان JSON است.

**۲) آیا ترتیب اجرای دستورات مهم است؟**
بله، ترتیب آرایهٔ دستورات **حفظ** می‌شود و هر آیتم با `request_index` متناظر پاسخ داده می‌شود.

**۳) چه‌طور زمان اجرای هر دستور را می‌بینم؟**
در `meta` فیلد `elapsed_ms` قرار می‌گیرد تا در سمت مصرف‌کننده تحلیل شود.

---

## ۱۲) چک‌لیست استقرار

* [ ] `KAFKA_SERVERS`, `KAFKA_TOPIC`, `KAFKA_RESPONSE_TOPIC`, `KAFKA_GROUP_ID` درست تنظیم شده‌اند
* [ ] JSON Logging در تولید فعال (`LOG_JSON=true`) و سطح لاگ مناسب (`INFO/WARNING`)
* [ ] منطق reassemble پاسخ‌ها در سمت مصرف‌کننده بر اساس `(corr_id, seq, total)` آماده است
* [ ] کلاس‌های مقصد در `CLASS_MAP` ثبت و آماده‌اند
* [ ] مصرف‌کننده با سیگنال‌ها به‌صورت ایمن بسته می‌شود

---
