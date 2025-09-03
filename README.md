```markdown
# 📖 دفترچهٔ راهنمای پیام‌های Kafka برای Mt5_Manager

این دفترچه تمام حالت‌های ممکن برای ارسال پیام به Kafka و اجرای متدهای کلاس Mt5_Manager را توضیح می‌دهد.
کلید (key) پیام همیشه باید `"Mt5_Manager"` باشد.

## 🗂 ساختار کلی پیام

هر پیام یک لیست JSON شامل یک یا چند دستور است:

```json
[
  {
    "method": "<نام متد>",
    "params": {
      "action": "<نوع عملیات>",
      "... سایر پارامترها ..."
    }
  }
]
```

- `method`: نام یکی از متدهای کلاس Mt5_Manager
- `params`: دیکشنری از پارامترها و تنظیمات موردنیاز آن متد  
- `action`: نوع عملیاتی که باید انجام شود (مثل `"initialize"`, `"get"`, `"send"` و …)

---

## 1️⃣ مدیریت اتصال (`manage_connection`)

### اکشن‌های مجاز:

- `initialize` → برقراری اتصال به متاتریدر
- `login` → لاگین با یوزر/پسورد/سرور مشخص
- `terminal_info` → دریافت اطلاعات ترمینال
- `version` → دریافت نسخه MT5
- `account_info` → دریافت اطلاعات حساب
- `shutdown` → قطع اتصال

### مثال‌ها

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

## 2️⃣ مدیریت نمادها (`manage_symbols`)

### اکشن‌های مجاز:

- `total` → تعداد کل نمادها
- `get` → لیست نمادها (فیلتر + گروه)
- `info` → اطلاعات کامل یک نماد
- `tick` → آخرین تیک قیمت
- `select` → فعال/غیرفعال کردن نماد در MarketWatch

### مثال‌ها

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

## 3️⃣ عمق بازار (`manage_market_book`)

### اکشن‌های مجاز:

- `add` → اشتراک در عمق بازار
- `get` → دریافت اسنپ‌شات عمق بازار
- `release` → لغو اشتراک

### مثال‌ها

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

## 4️⃣ داده‌های تاریخی (`fetch_data`)

### پارامترهای مهم:

- `symbol` (نماد)
- `data_type`: `"rates"` یا `"ticks"`
- `method`: `"from"`, `"from_pos"`, `"range"`
- `timeframe`: مثل `"TIMEFRAME_H1"` (رشته به کانستنت MT5 تبدیل می‌شود)
- `date_from`, `date_to`: به فرمت ISO (مثلاً `"2025-09-03T00:00:00"`)
- `count`, `flags`

### مثال‌ها

```json
[{ "method": "fetch_data", "params": { "symbol": "EURUSD", "data_type": "rates", "method": "from", "timeframe": "TIMEFRAME_H1", "count": 10 } }]
```

```json
[{ "method": "fetch_data", "params": { "symbol": "EURUSD", "data_type": "ticks", "method": "range", "date_from": "2025-09-03T00:00:00", "date_to": "2025-09-03T12:00:00", "flags": "COPY_TICKS_ALL" } }]
```

---

## 5️⃣ مدیریت معاملات (`trade_manager`)

### اکشن‌های مجاز:

- `total` → تعداد سفارش‌های باز
- `get` → گرفتن سفارش‌ها (با ticket, group, symbol)
- `calc_margin` → محاسبه مارجین
- `calc_profit` → محاسبه سود/زیان
- `check` → بررسی اعتبار سفارش قبل از ارسال
- `send` → ارسال سفارش (با منطق تأیید و تلاش مجدد)

### مثال‌ها

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

> 💡 نکته: اگر `price` ندهید و نماد Market Execution باشد، کد به‌صورت خودکار bid/ask را ست می‌کند.

---

## 6️⃣ پوزیشن‌ها و تاریخچه (`manage_positions_history`)

### اکشن‌های مجاز:

- `positions_total` → تعداد کل پوزیشن‌های باز
- `positions_get` → لیست پوزیشن‌ها (فیلتر با symbol, group, ticket)
- `history_orders_total` → تعداد سفارش‌های تاریخی در بازه
- `history_orders_get` → لیست سفارش‌های تاریخی (فیلتر با ticket, position_id, group)
- `history_deals_total` → تعداد دیل‌ها در بازه
- `history_deals_get` → لیست دیل‌ها (فیلتر با ticket, position_id, group)

### مثال‌ها

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

## 🔑 نکات مهم

- تمام رشته‌های کانستنت (مثل `"ORDER_TYPE_BUY"`, `"TRADE_ACTION_DEAL"`, `"TIMEFRAME_H1"`) به‌صورت خودکار در main.py به مقادیر MT5 تبدیل می‌شوند.
- تاریخ‌ها باید به فرمت ISO ارسال شوند (`YYYY-MM-DDTHH:MM:SS`) و به UTC تبدیل می‌شوند.
- برای اطمینان از ردیابی سفارش‌ها، همیشه یک magic number در سفارش‌های `check`/`send` بگذارید.
- اگر Market Execution باشد، قیمت توسط سیستم پر می‌شود؛ اگر Instant Execution باشد، باید خودتان `price` بدهید.
```
