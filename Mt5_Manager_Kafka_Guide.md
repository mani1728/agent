

# `meta_trader_manager.py`

# 📖 دفترچهٔ راهنمای پیام‌های Kafka برای **Mt5\_Manager**
---

این دفترچه تمام حالت‌های ممکن برای ارسال پیام به **Kafka** و اجرای متدهای کلاس **`Mt5_Manager`** را توضیح می‌دهد.
**کلید (key)** پیام همیشه باید دقیقا `"Mt5_Manager"` باشد.

> این راهنما با نسخه‌های بهینه‌شده‌ی `main.py` و `meta_trader_manager.py` که شامل:
>
> * نگاشت امن کانستنت‌های MT5 از رشته به مقدار واقعی
> * پارس ایمن تاریخ‌ها به UTC
> * لاگ‌گذاری Human/JSON با Rotation
> * مدیریت خطا و سیگنال‌ها
>   نوشته شده است.

---

## فهرست مطالب

* [ساختار کلی پیام](#ساختار-کلی-پیام)
* [نگاشت کانستنت‌ها و تاریخ‌ها](#نگاشت-کانستنتها-و-تاریخها)
* [متدها و اکشن‌ها](#متدها-و-اکشنها)

  * [1) manage\_connection](#1-manage_connection)
  * [2) manage\_symbols](#2-manage_symbols)
  * [3) manage\_market\_book](#3-manage_market_book)
  * [4) fetch\_data](#4-fetch_data)
  * [5) trade\_manager](#5-trade_manager)
  * [6) manage\_positions\_history](#6-manage_positions_history)
* [نمونه پیام‌های آماده (کامل)](#نمونه-پیامهای-آماده-کامل)
* [پیکربندی و اجرا](#پیکربندی-و-اجرا)
* [Best Practices](#best-practices)
* [عیب‌یابی سریع](#عیبیابی-سریع)
* [راهنمای سریع کانستنت‌ها](#راهنمای-سریع-کانستنتها)
* [واژه‌نامه مختصر](#واژهنامه-مختصر)

---

## ساختار کلی پیام

هر پیام Kafka شامل **key** و **value** است:

* **key**: باید دقیقا `"Mt5_Manager"` باشد (برای انتخاب کلاس مقصد).
* **value**: یک **آرایه JSON** از یک یا چند دستور.

```json
[
  {
    "method": "<نام متد Mt5_Manager>",
    "params": {
      "action": "<نوع عملیات>",
      "... پارامترهای دیگر ..."
    }
  }
]
```

**نکات:**

* می‌توانی **چند دستور** را در یک پیام ارسال کنی (به ترتیبی که در آرایه آمده اجرا می‌شوند).
* فیلد `method` باید یکی از متدهای کلاس `Mt5_Manager` باشد (لیست کامل در ادامه).
* فیلد `params` یک دیکشنری از پارامترهای لازم برای آن متد است.
* فیلد `action` نوع عملیات را تعیین می‌کند (مثلاً `"initialize"`, `"get"`, `"send"`).

---

## نگاشت کانستنت‌ها و تاریخ‌ها

### 1) نگاشت کانستنت‌ها (در `main.py`)

رشته‌هایی مثل `"ORDER_TYPE_BUY"`, `"TRADE_ACTION_DEAL"`, `"TIMEFRAME_H1"`, `"COPY_TICKS_ALL"` به صورت **خودکار** به مقادیر واقعی MT5 تبدیل می‌شوند.
این تبدیل در توابع کمکی `convert_params` و `convert_request_fields` انجام می‌شود.

> پس در پیام‌ها می‌توانی **رشته** بفرستی؛ `main.py` آن را به **کانستنت MT5** تبدیل می‌کند.

### 2) تاریخ‌ها و زمان (UTC-aware)

* فیلدهای تاریخ مانند `date_from` و `date_to` را به فرمت **ISO** بفرست (مثال: `"2025-09-03T00:00:00"`).
* `main.py` آن‌ها را به `datetime` **با منطقه زمانی UTC** تبدیل می‌کند. از `...Z` نیز پشتیبانی می‌شود.

---

## متدها و اکشن‌ها

### 1) `manage_connection`

**اکشن‌های مجاز:**

* `initialize` → برقراری اتصال به ترمینال MT5
* `login` → ورود به حساب با `login`/`password`/`server`
* `terminal_info` → دریافت اطلاعات ترمینال
* `version` → دریافت نسخه MT5
* `account_info` → دریافت اطلاعات حساب فعلی
* `shutdown` → قطع اتصال

**پارامترهای رایج (اختیاری برای بعضی اکشن‌ها):**

| پارامتر    | نوع    | توضیح                       |
| ---------- | ------ | --------------------------- |
| `path`     | string | مسیر ترمینال (در صورت نیاز) |
| `login`    | int    | شماره حساب                  |
| `password` | string | رمز حساب                    |
| `server`   | string | نام سرور بروکر              |
| `timeout`  | int    | پیش‌فرض 60000 میلی‌ثانیه    |
| `portable` | bool   | حالت Portable در صورت نیاز  |

**نمونه‌ها:**

```json
[{ "method": "manage_connection", "params": { "action": "initialize" } }]
```

```json
[{ "method": "manage_connection", "params": { "action": "login", "login": 123456, "password": "mypw", "server": "Broker-Server" } }]
```

```json
[{ "method": "manage_connection", "params": { "action": "account_info" } }]
```

```json
[{ "method": "manage_connection", "params": { "action": "shutdown" } }]
```

---

### 2) `manage_symbols`

**اکشن‌های مجاز:**

* `total` → تعداد کل نمادها
* `get` → دریافت لیست نمادها (با `group` اختیاری)
* `info` → اطلاعات کامل یک نماد
* `tick` → آخرین تیک قیمت
* `select` → فعال/غیرفعال کردن نماد در MarketWatch

**پارامترها (بسته به اکشن):**

| پارامتر  | نوع    | توضیح                                           |
| -------- | ------ | ----------------------------------------------- |
| `symbol` | string | نام نماد (برای info/tick/select)                |
| `group`  | string | فیلتر گروه (برای get)، مثال: `"Forex"` یا `"*"` |
| `enable` | bool   | برای `select` → `true/false`                    |

**نمونه‌ها:**

```json
[{ "method": "manage_symbols", "params": { "action": "total" } }]
```

```json
[{ "method": "manage_symbols", "params": { "action": "get", "group": "Forex" } }]
```

```json
[{ "method": "manage_symbols", "params": { "action": "info", "symbol": "EURUSD" } }]
```

```json
[{ "method": "manage_symbols", "params": { "action": "tick", "symbol": "EURUSD" } }]
```

```json
[{ "method": "manage_symbols", "params": { "action": "select", "symbol": "EURUSD", "enable": true } }]
```

---

### 3) `manage_market_book`

**اکشن‌های مجاز:**

* `add` → اشتراک در عمق بازار نماد
* `get` → دریافت اسنپ‌شات عمق بازار
* `release` → لغو اشتراک

**پارامترها:**

| پارامتر  | نوع    | توضیح        |
| -------- | ------ | ------------ |
| `symbol` | string | نام نماد هدف |

**نمونه‌ها:**

```json
[{ "method": "manage_market_book", "params": { "action": "add", "symbol": "EURUSD" } }]
```

```json
[{ "method": "manage_market_book", "params": { "action": "get", "symbol": "EURUSD" } }]
```

```json
[{ "method": "manage_market_book", "params": { "action": "release", "symbol": "EURUSD" } }]
```

---

### 4) `fetch_data`

**نوع داده‌ها:**

* `rates` (OHLCV) با تایم‌فریم
* `ticks` (Bid/Ask/Last/Flags/…)

**روش‌ها (`method`):**

* `from` → از تاریخ مشخص با `count`
* `from_pos` → از اندیس صفر با `count` (برای ticks پشتیبانی مستقیم MT5 ندارد؛ در کد با fallback پوشش داده شده)
* `range` → بازه‌ی زمانی (`date_from` تا `date_to`)

**پارامترها:**

| پارامتر                | نوع           | توضیح                                   |
| ---------------------- | ------------- | --------------------------------------- |
| `symbol`               | string        | نام نماد                                |
| `data_type`            | string        | `"rates"` یا `"ticks"`                  |
| `method`               | string        | `"from"`, `"from_pos"`, `"range"`       |
| `timeframe`            | string \| int | برای `rates` (مثلاً `"TIMEFRAME_H1"`)   |
| `date_from`, `date_to` | ISO datetime  | ورودی ISO، در `main.py` → UTC           |
| `count`                | int           | تعداد رکورد                             |
| `flags`                | string \| int | برای `ticks` (مثلاً `"COPY_TICKS_ALL"`) |

**نمونه‌ها:**

```json
[{ "method": "fetch_data", "params": { "symbol": "EURUSD", "data_type": "rates", "method": "from", "timeframe": "TIMEFRAME_H1", "count": 10 } }]
```

```json
[{ "method": "fetch_data", "params": { "symbol": "EURUSD", "data_type": "ticks", "method": "range", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T12:00:00", "flags": "COPY_TICKS_ALL" } }]
```

> ℹ️ خروجی شامل `frame` (DataFrame) برای استفاده داخلی و `raw` (لیست دیکشنری‌های تمیز) برای مصرف مستقیم است.

---

### 5) `trade_manager`

**اکشن‌های مجاز:**

* `total` → تعداد سفارش‌های باز
* `get` → دریافت سفارش‌ها (با فیلتر `symbol`)
* `calc_margin` → محاسبه مارجین
* `calc_profit` → محاسبه سود/زیان
* `check` → بررسی اعتبار سفارش قبل از ارسال
* `send` → ارسال سفارش (با تلاش مجدد در صورت نیاز)

**پارامترها (بسته به اکشن):**

| پارامتر                | نوع           | توضیح                                               |
| ---------------------- | ------------- | --------------------------------------------------- |
| `symbol`               | string        | نماد (برای `get`/`calc*`)                           |
| `order_type`           | string \| int | `"ORDER_TYPE_BUY"` / `"ORDER_TYPE_SELL"`            |
| `volume`               | float         | حجم                                                 |
| `price`, `price_close` | float         | برای `calc_*`                                       |
| `request`              | dict          | درخواست کامل MT5 برای `check/send` (نمونه در پایین) |

**نمونه‌ها:**

```json
[{ "method": "trade_manager", "params": { "action": "total" } }]
```

```json
[{ "method": "trade_manager", "params": { "action": "get", "symbol": "EURUSD" } }]
```

```json
[{ "method": "trade_manager", "params": { "action": "calc_margin", "order_type": "ORDER_TYPE_BUY", "symbol": "EURUSD", "volume": 0.1, "price": 1.1000 } }]
```

```json
[{ "method": "trade_manager", "params": { "action": "calc_profit", "order_type": "ORDER_TYPE_SELL", "symbol": "EURUSD", "volume": 0.1, "price": 1.1000, "price_close": 1.0900 } }]
```

```json
[{ "method": "trade_manager", "params": { "action": "check", "request": { "action": "TRADE_ACTION_DEAL", "type": "ORDER_TYPE_BUY", "symbol": "EURUSD", "volume": 0.1, "magic": 123456 } } }]
```

```json
[{ "method": "trade_manager", "params": { "action": "send", "request": { "action": "TRADE_ACTION_DEAL", "type": "ORDER_TYPE_BUY", "symbol": "EURUSD", "volume": 0.1, "magic": 123456 } } }]
```

> 💡 اگر `price` ندهی و سفارش از نوع **Market Execution** باشد، کد به‌صورت خودکار بر اساس `type` (BUY→Ask / SELL→Bid) قیمت را ست می‌کند.
> `deviation`, `type_filling`, `type_time` نیز با مقادیر امن پیش‌فرض می‌شوند و قابل override هستند.

---

### 6) `manage_positions_history`

**اکشن‌های مجاز:**

* `positions_total` → تعداد کل پوزیشن‌های باز
* `positions_get` → لیست پوزیشن‌ها (فیلتر با `symbol` یا `ticket`)
* `history_orders_total` → تعداد سفارش‌های تاریخی در بازه
* `history_orders_get` → لیست سفارش‌های تاریخی (فیلتر با `ticket`, `position_id`, `group`)
* `history_deals_total` → تعداد دیل‌ها در بازه
* `history_deals_get` → لیست دیل‌ها (فیلتر با `ticket`, `position_id`, `group`)

**پارامترها:**

| پارامتر                | نوع          | توضیح                                                                        |
| ---------------------- | ------------ | ---------------------------------------------------------------------------- |
| `symbol`               | string       | فیلتر اختیاری برای `positions_get`                                           |
| `ticket`               | int          | فیلتر دقیق برای `positions_get` یا history\_\*\_get                          |
| `position_id`          | int          | فیلتر تاریخچه بر اساس شناسه پوزیشن                                           |
| `group`                | string       | فیلتر گروه/نماد در history\_\*\_get (مثلاً `"EURUSD"` یا `"Forex"` یا `"*"`) |
| `date_from`, `date_to` | ISO datetime | بازه زمانی (UTC-aware)                                                       |

**نمونه‌ها:**

```json
[{ "method": "manage_positions_history", "params": { "action": "positions_total" } }]
```

```json
[{ "method": "manage_positions_history", "params": { "action": "positions_get", "symbol": "EURUSD" } }]
```

```json
[{ "method": "manage_positions_history", "params": { "action": "history_orders_total", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T23:59:59" } }]
```

```json
[{ "method": "manage_positions_history", "params": { "action": "history_orders_get", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T23:59:59", "group": "EURUSD" } }]
```

```json
[{ "method": "manage_positions_history", "params": { "action": "history_deals_total", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T23:59:59" } }]
```

```json
[{ "method": "manage_positions_history", "params": { "action": "history_deals_get", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T23:59:59" } }]
```

---

## نمونه پیام‌های آماده (کامل)

### سناریو: اتصال، دریافت تیک، ارسال سفارش، بررسی تاریخچه

```json
[
  { "method": "manage_connection", "params": { "action": "initialize" } },
  { "method": "manage_symbols", "params": { "action": "tick", "symbol": "EURUSD" } },
  { "method": "trade_manager", "params": {
      "action": "check",
      "request": {
        "action": "TRADE_ACTION_DEAL",
        "type": "ORDER_TYPE_BUY",
        "symbol": "EURUSD",
        "volume": 0.10,
        "magic": 987654
      }
  }},
  { "method": "trade_manager", "params": {
      "action": "send",
      "request": {
        "action": "TRADE_ACTION_DEAL",
        "type": "ORDER_TYPE_BUY",
        "symbol": "EURUSD",
        "volume": 0.10,
        "magic": 987654
      }
  }},
  { "method": "manage_positions_history", "params": {
      "action": "history_orders_get",
      "date_from": "2025-09-03T00:00:00",
      "date_to": "2025-09-03T23:59:59",
      "group": "*"
  }},
  { "method": "manage_positions_history", "params": {
      "action": "history_deals_get",
      "date_from": "2025-09-03T00:00:00",
      "date_to": "2025-09-03T23:59:59"
  }}
]
```

---

## پیکربندی و اجرا

### متغیرهای محیطی (ENV) برای `main.py`

| نام              | پیش‌فرض                | توضیح                     |
| ---------------- | ---------------------- | ------------------------- |
| `KAFKA_SERVERS`  | `192.168.1.254:9092`   | آدرس Kafka                |
| `KAFKA_TOPIC`    | `agent-send`           | نام تاپیک مصرف            |
| `KAFKA_GROUP_ID` | `kafka_listener_group` | گروه Consumer             |
| `LOG_LEVEL`      | `INFO`                 | سطح لاگ: `DEBUG/INFO/...` |
| `LOG_JSON`       | `false`                | خروجی JSON در لاگ‌ها      |
| `LOG_FILE`       | `logs/app.log`         | مسیر فایل لاگ             |
| `LOG_MAX_BYTES`  | `10485760`             | حجم چرخش (Rotation)       |
| `LOG_BACKUPS`    | `10`                   | تعداد فایل‌های پشتیبان    |

**مثال اجرا (Linux/Mac):**

```bash
LOG_LEVEL=INFO \
LOG_JSON=true \
LOG_FILE=logs/app.log \
python main.py
```

**Producer نمونه (`sender.py` ساده):**

```python
from confluent_kafka import Producer
import json

p = Producer({"bootstrap.servers": "192.168.1.254:9092"})
msg = [{"method": "manage_connection", "params": {"action": "initialize"}}]
p.produce("agent-send", key="Mt5_Manager", value=json.dumps(msg))
p.flush()
```

---

## Best Practices

* **Magic Number** را همیشه در سفارش‌ها ست کن تا ردیابی معاملات ساده باشد.
* برای **Market Execution** قیمت را خالی بگذار؛ کد خودش با `bid/ask` پر می‌کند.
  برای **Instant Execution**، قیمت را **خودت** بده.
* پیام‌های چند مرحله‌ای را به ترتیبی بچین که وابستگی‌ها رعایت شوند (مثلاً: initialize → check → send).
* در تولید، **JSON Logging** را فعال کن؛ برای مانیتورینگ با ELK/Graylog/Grafana سازگار است.
* برای حجم‌های بزرگ تاریخچه، **فیلتر group/ticket/position\_id** را استفاده کن تا پاسخ‌ها سبک بمانند.

---

## عیب‌یابی سریع

| مشکل                            | راه‌حل سریع                                                                                                      |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `MT5 not initialized/connected` | قبل از هر کاری `manage_connection/initialize` را صدا بزن.                                                        |
| عدم نگاشت کانستنت از رشته       | مطمئن شو رشته را درست تایپ کرده‌ای (`ORDER_TYPE_BUY`، `TIMEFRAME_H1`، …).                                        |
| `order_send` retcode != DONE    | ابتدا `trade_manager/check` را نگاه کن؛ `type_filling`/`deviation` را تنظیم کن؛ یک تلاش مجدد ارسال انجام می‌شود. |
| داده تاریخی خالی                | بازه زمانی و `symbol` را بررسی کن؛ برای `ticks/from_pos` محدودیت MT5 را در نظر بگیر (fallback فعال است).         |
| تاریخچه صفر                     | `date_from/date_to` را به UTC و بازه صحیح بده؛ `group` درست باشد (مثلاً `"*"` برای همه).                         |

---

## راهنمای سریع کانستنت‌ها

* **Order Types**: `ORDER_TYPE_BUY`, `ORDER_TYPE_SELL`, `ORDER_TYPE_BUY_LIMIT`, `ORDER_TYPE_SELL_LIMIT`, `ORDER_TYPE_BUY_STOP`, `ORDER_TYPE_SELL_STOP`, …
* **Trade Actions**: `TRADE_ACTION_DEAL` (مارکت)، `TRADE_ACTION_PENDING` (سفارش معلق)، …
* **Filling Modes**: `ORDER_FILLING_IOC`, `ORDER_FILLING_FOK`, `ORDER_FILLING_RETURN`
* **Time Modes**: `ORDER_TIME_GTC`, `ORDER_TIME_DAY`, `ORDER_TIME_SPECIFIED`, …
* **Timeframes**: `TIMEFRAME_M1`, `TIMEFRAME_M5`, `TIMEFRAME_M15`, `TIMEFRAME_H1`, `TIMEFRAME_H4`, `TIMEFRAME_D1`, …
* **Ticks Flags**: `COPY_TICKS_ALL`, `COPY_TICKS_INFO`, `COPY_TICKS_TRADE`

> همه‌ی موارد فوق را می‌توانی **به‌صورت رشته** در پیام بفرستی؛ `main.py` آن‌ها را به مقدار MT5 تبدیل می‌کند.

---

## واژه‌نامه مختصر

* **Market Watch**: لیست نمادهای فعال در ترمینال.
* **Market Execution**: سفارش مارکتی که با قیمت لحظه‌ای انجام می‌شود.
* **Instant Execution**: سفارش با قیمت مشخص؛ اختلاف قیمت منجر به Requote می‌شود.
* **Magic Number**: شناسه‌ی ربات/استراتژی برای ردیابی معاملات.
* **Deal / Order / Position**: تفکیک رکوردهای معاملاتی MT5 (ثبت انجام معامله/ثبت سفارش/وضعیت پوزیشن).

---
