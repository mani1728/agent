
---

# mt5\_utils\_Guide.md (راهنمای جامع کانورتورها و سریال‌سازی امن)

---
این راهنما تمام جزئیات ماژول `mt5_utils.py` را پوشش می‌دهد: تبدیل امن پارامترهای ورودی پیام‌های Kafka به کانستنت‌های MT5، پارس تاریخ‌های ISO به `datetime` با آگاهی از UTC، و سریال‌سازی امن خروجی‌ها برای لاگ/ارسال. کد مرجع همین ریپو است.

---

## ۱) خلاصهٔ ماژول

* **هدف:**
  یک لایهٔ ایمن و متمرکز برای:

  1. نگاشت رشته‌ها (مثل `"TIMEFRAME_H1"`, `"ORDER_TYPE_BUY"`) به کانستنت‌های واقعی MT5،
  2. پارس تاریخ‌های ISO و همسان‌سازی به UTC،
  3. آماده‌سازی امن ورودی‌ها (در سطوح `params` و `request`) برای متدهای کلاس‌های مدیریتی،
  4. سریال‌سازی ایمن نتایج پیچیده به فرم JSON-safe برای لاگ/پاسخ.

* **کجا استفاده می‌شود؟**
  `kafka_listener.py` قبل از فراخوانی متد مقصد، پارامترها را با `convert_params` تمیز می‌کند؛ سپس خروجی‌ها با `safe_serialize` قابل ثبت/ارسال هستند.

---

## ۲) وابستگی‌ها و ثابت‌ها

* `MetaTrader5 as mt5` برای دسترسی به کانستنت‌ها و انواع (مثل `ORDER_TYPE_*`, `TIMEFRAME_*`)
* `pytz` برای منطقه زمانی `UTC_TZ = Etc/UTC`
* `datetime as dt` برای کار با تاریخ‌/زمان

> نکته: تبدیل رشته به کانستنت با `getattr(mt5, name, default)` انجام می‌شود؛ اگر رشته معتبر نباشد، مقدار پیش‌فرض برمی‌گردد.

---

## ۳) توابع کلیدی

### ۳.۱) `parse_iso_dt(s: str) -> dt.datetime`

**کار:** پارس رشته‌های ISO (با پشتیبانی از `Z`) و تبدیل به `datetime` **UTC-aware**.
**جزئیات پیاده‌سازی:**

* اگر ورودی رشته نباشد → `ValueError`
* پشتیبانی از انتهای `"Z"` با جایگزینی به `+00:00`
* تلاش نخست با `fromisoformat` و fallback با جایگزینی فاصله به `T`
* اگر `tzinfo` نداشت → `UTC_TZ.localize(obj)`؛ در غیر این صورت → `astimezone(UTC)`

**مثال:**

```python
parse_iso_dt("2025-09-03T10:30:00Z")     # → 2025-09-03 10:30:00+00:00 (UTC-aware)
parse_iso_dt("2025-09-03 10:30:00")      # → با fallback، سپس UTC-aware
```

---

### ۳.۲) `to_mt5_const(name: str, default: Any) -> Any`

**کار:** نگاشت امن یک رشته به کانستنت متناظر در ماژول `mt5`.
**ویژگی:** اگر نام معتبر نباشد، `default` بازگردانده می‌شود؛ از کرش جلوگیری می‌کند.

**مثال:**

```python
to_mt5_const("TIMEFRAME_H1", mt5.TIMEFRAME_H4)  # → mt5.TIMEFRAME_H1 (اگر وجود داشته باشد)
to_mt5_const("TIMEFRAME_XYZ", mt5.TIMEFRAME_H4) # → mt5.TIMEFRAME_H4 (fallback)
```

---

### ۳.۳) `convert_request_fields(req: Dict[str, Any]) -> None`

**کار:** نرمال‌سازی فیلدهای درون `request` قبل از `order_check/order_send`.
**فیلدهای پوشش‌داده‌شده:**

* `action` → پیش‌فرض `TRADE_ACTION_DEAL`
* `type` → پیش‌فرض `ORDER_TYPE_BUY`
* `type_time` → پیش‌فرض `ORDER_TIME_GTC`
* `type_filling` → پیش‌فرض `ORDER_FILLING_IOC`

> این تابع **درجا** (`in-place`) روی دیکشنری کار می‌کند و مقدار بازگشتی ندارد.

---

### ۳.۴) `convert_params(params: Dict[str, Any]) -> Dict[str, Any]`

**کار:** تبدیل امن پارامترهای سطح بالا که از Kafka می‌آیند، به شکل سازگار با متدهای مدیریت.
**قوانین تبدیل:**

* `timeframe` (str) → کانستنت MT5 با پیش‌فرض `TIMEFRAME_H4`
* `flags` (str) → کانستنت MT5 با پیش‌فرض `COPY_TICKS_ALL`
* `order_type` (str) → کانستنت MT5 با پیش‌فرض `ORDER_TYPE_BUY`
* `action` (str) → lowercase برای یکسان‌سازی
* `date_from` / `date_to` (str) → `parse_iso_dt` → `datetime` (UTC-aware)
* `request` (dict) → `convert_request_fields` روی فیلدهای داخلی اعمال می‌شود

> تابع یک **کپی ایمن** از ورودی می‌سازد و همان را برمی‌گرداند؛ ورودی اصلی دست‌نخورده می‌ماند.

**مثال ورودی/خروجی:**

```python
inp = {
  "action": "SEND",
  "timeframe": "TIMEFRAME_H1",
  "date_from": "2025-09-03T00:00:00Z",
  "request": {"action": "TRADE_ACTION_DEAL", "type": "ORDER_TYPE_SELL"}
}
out = convert_params(inp)
# out["action"] == "send"
# out["timeframe"] == mt5.TIMEFRAME_H1
# out["date_from"] == datetime(…, tzinfo=UTC)
# out["request"]["type_filling"] == mt5.ORDER_FILLING_IOC (ست‌شده توسط convert_request_fields)
```

---

### ۳.5) `safe_serialize(obj: Any, _depth: int = 0, _limit: int = 3) -> Any`

**کار:** سریال‌سازی **JSON-safe** برای انواع سخت‌سریال مانند `datetime`, `namedtuple`, `dict/list` تو در تو، `numpy`, `pandas`.
**قابلیت‌ها:**

* `datetime/date/time` → `isoformat()`
* `namedtuple` → دیکشنری
* `dict/list/tuple` → بازگشتی و محدود به `_limit` عمق برای جلوگیری از چرخه بی‌نهایت
* `numpy.generic` → مقدار اسکالر با `item()`
* `pandas.DataFrame` → پیش‌نمایش ۵۰ ردیف + `columns` + `rows`
* `pandas.Series` → `to_dict()`
* در نهایت تلاش برای `json.dumps`؛ اگر نشد → `str(obj)`

**کاربرد عملی:**

* در `kafka_listener.py` برای ثبت پارامترها و ارسال نتیجه در Envelope پاسخ استفاده می‌شود؛ خروجی همیشه JSON-safe می‌شود تا سمت مصرف‌کننده (logger/consumer دیگر) بدون استثنا داده را دریافت کند.

---

## ۴) جریان دادهٔ معمول (End-to-End)

1. پیام Kafka به `kafka_listener` می‌رسد.
2. قبل از فراخوانی متد مقصد، `convert_params` روی `params` اعمال می‌شود تا:

   * رشته‌ها به کانستنت‌ها نگاشت شوند،
   * تاریخ‌ها UTC-aware شوند،
   * `request.*` به کانستنت‌های MT5 تبدیل شود.
3. متد مقصد اجرا می‌شود.
4. نتیجه با `safe_serialize` به فرم JSON-safe تبدیل و در Envelope استاندارد ارسال/لاگ می‌شود.

---

## ۵) الگوهای استفاده (Usage Patterns)

### ۵.۱) تبدیل ورودی‌های نرخ/تیک

```python
params = {
  "symbol": "EURUSD",
  "data_type": "ticks",
  "method": "range",
  "date_from": "2025-09-03T00:00:00Z",
  "date_to": "2025-09-03T02:00:00Z",
  "flags": "COPY_TICKS_ALL"
}
clean = convert_params(params)  # flags → mt5.COPY_TICKS_ALL، تاریخ‌ها UTC-aware
```

### ۵.۲) آماده‌سازی سفارش مارکت

```python
params = {
  "action": "send",
  "request": {
    "action": "TRADE_ACTION_DEAL",
    "type": "ORDER_TYPE_BUY",
    "symbol": "EURUSD",
    "volume": 0.1
  }
}
clean = convert_params(params)
# clean["request"]["type_filling"] == mt5.ORDER_FILLING_IOC
# clean["request"]["type_time"]   == mt5.ORDER_TIME_GTC
```

### ۵.۳) سریال‌سازی خروجی‌های دیتافریم

```python
result = {"frame": some_dataframe, "meta": {"t": dt.datetime.utcnow()}}
json_ready = safe_serialize(result)  # frame → preview + columns + rows، t → ISO
```

---

## ۶) Best Practices

* **همیشه** پارامترهای دریافتی از Kafka را با `convert_params` تمیز کنید تا از نوع‌ها و کانستنت‌های صحیح مطمئن شوید. این کار جلوی `TypeError` و `retcode`های عجیب را می‌گیرد.
* تاریخ‌ها را **به‌صورت ISO** ارسال کنید (`…Z` یا با offset)، و هرجا تردید دارید، UTC در نظر بگیرید؛ این ماژول همه‌چیز را UTC-aware می‌کند.
* برای سفارش‌های مارکت، اگر `price` خالی باشد، بخش ارسال سفارش (در کلاس مدیریتی) خودش بر اساس `bid/ask` آن را پر می‌کند؛ اینجا کافی‌ست `request` درست کانورت شود.
* در خروجی‌ها، `safe_serialize` را برای همهٔ مسیرهای لاگ/ارسال به کار ببرید تا داده‌های `pandas/numpy/datetime` باعث خطای JSON نشوند.

---

## ۷) عیب‌یابی سریع (Troubleshooting)

| علامت/خطا                     | علت محتمل                     | راه‌حل                                                                        |
| ----------------------------- | ----------------------------- | ----------------------------------------------------------------------------- |
| `datetime must be ISO string` | مقدار تاریخ رشته نیست         | قبل از ارسال تبدیل کنید یا رشتهٔ ISO بدهید؛ مثال: `"2025-09-03T00:00:00Z"`    |
| کانستنت نگاشت نمی‌شود         | تایپ اشتباه رشته              | از نام دقیق MT5 استفاده کنید یا مقدار پیش‌فرض مناسب بدهید (fallback فعال است) |
| `TypeError` در متد مقصد       | نوع‌های پارامترها ناسازگار    | مطمئن شوید `convert_params` قبل از فراخوانی اجرا می‌شود                       |
| JSON serialization error      | وجود `datetime`/`DataFrame`/… | به‌جای `json.dumps` مستقیم، از `safe_serialize` استفاده کنید                  |

---

## ۸) سؤالات پرتکرار (FAQ)

**۱) چرا تبدیل‌ها هم در سطح `params` و هم `request` انجام می‌شود؟**
چون برخی پارامترها مثل `timeframe/flags/order_type` در سطح بالا هستند، اما فیلدهای سفارش (مثل `type_time`, `type_filling`) داخل `request` قرار دارند. هرکدام به‌صورت هدفمند در جای مناسب تبدیل می‌شوند.

**۲) اگر ورودی تاریخ timezone نداشت چه می‌شود؟**
به‌صورت امن به UTC نسبت داده می‌شود (`UTC_TZ.localize`) تا رفتار یکدست داشته باشیم.

**۳) اگر عمق تو در توی دیکشنری‌ها زیاد باشد چه؟**
`safe_serialize` عمق را با `_limit=3` محدود کرده و در صورت تجاوز، `str(obj)` برمی‌گرداند تا از حلقه‌های بی‌نهایت جلوگیری شود.

---

## ۹) چک‌لیست قبل از پروداکشن

* [ ] تمام مسیرهای ورودی Kafka از `convert_params` عبور می‌کنند.
* [ ] تمام مسیرهای خروجی (لاگ/پاسخ) از `safe_serialize` استفاده می‌کنند.
* [ ] فرستادن تاریخ‌ها فقط به‌صورت ISO و بر مبنای UTC.
* [ ] نام کانستنت‌ها دقیقاً مطابق MT5 (در صورت تردید از پیش‌فرض‌های امن استفاده کنید).

---