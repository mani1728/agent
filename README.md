
---

# README.md

```markdown
<!--
📌 این فایل README.md برای ریپوی شماست
📌 شامل معرفی کامل، ساختار پروژه، نحوه اجرا، پیام‌های Kafka، معماری، نکات و عیب‌یابی
📌 تمام بخش‌ها با کامنت‌های فارسی توضیح داده شده تا تیم شما راحت‌تر نگهداری کند
-->
```

# 🎯 سیستم مدیریت MetaTrader5 با Kafka
<!-- معرفی پروژه -->
این پروژه یک معماری ماژولار برای اتصال به **MetaTrader5 (MT5)** و مدیریت داده‌ها/معاملات از طریق **پیام‌های Kafka** ارائه می‌دهد.  
تمامی بخش‌ها به زبان پایتون پیاده‌سازی شده و برای **مقیاس‌پذیری، مانیتورینگ، و نگهداری در محیط تولید** بهینه‌سازی شده‌اند.  

---

## 📂 ساختار پروژه
<!-- ساختار پوشه‌ها و فایل‌ها -->

---

```text
project/
├─ config.json                    # ← فایل تنظیمات مرکزیِ پروژه (جایگزین تمام ENVها)
│                                 #    - قابلیت «هات‌ریلُد»: بدون ری‌استارت، تغییرات اعمال می‌شود.
│                                 #    - همهٔ ماژول‌ها (کافکا/لاگ/MT5/اجر) از این فایل می‌خوانند.
│                                 #    - پشتیبانی از {client_id} در رشته‌ها (مثال: cmd.{client_id}.p0).
│
├─ config_manager.py              # ← ماژول مدیریت تنظیمات با هات‌ریلُد
│                                 #    - خواندن config.json (با پشتیبانی از کامنت‌ها: //, /* */, #).
│                                 #    - ادغام با مقادیر پیش‌فرض (DEFAULTS) اگر کلیدی در فایل نبود.
│                                 #    - متدهای کاربردی:
│                                 #         cfg().get("kafka.bootstrap_servers") → دسترسی نقطه‌ای
│                                 #         cfg().get_all() → دریافت اسنپ‌شات کامل کانفیگ
│                                 #    - نخِ ناظر (watcher) برای تشخیص تغییراتِ فایل و ریلود خودکار.
│
├─ config_logging.py              # ← راه‌اندازی لاگ‌گذاری بر اساس تنظیمات در config.json
│                                 #    - تنظیم سطح لاگ، JSON یا Human، و فایل‌لاگ با Rotation.
│                                 #    - فقط از cfg() می‌خواند؛ وابستگی به ENV حذف شده.
│                                 #    - خروجی یکنواخت برای همهٔ ماژول‌ها (کنسول + فایل logs/app.log).
│
├─ mt5_utils.py                   # ← توابع ابزار MT5
│                                 #    - parse_iso_dt: تبدیل امن رشته‌های ISO به datetime با timezone=UTC.
│                                 #    - to_mt5_const: نگاشت نام کانستنتِ رشته‌ای → کانستنت‌های mt5.*
│                                 #    - convert_params: تمیزکاری/تبدیل پارامترهای دریافتی قبل از فراخوانی متدها.
│                                 #    - safe_serialize: سریال‌سازی امن اشیاء (datetime/np/pd/… → JSON-safe).
│
├─ meta_trader_manager.py         # ← کلاس Mt5_Manager (هستهٔ تعامل با MetaTrader 5)
│                                 #    - متدهای مدیریت اتصال: initialize/login/version/account_info/…
│                                 #    - نمادها: total/get/info/tick/select
│                                 #    - مارکت‌بوک: add/get/release
│                                 #    - دادهٔ تاریخی: rates/ticks با روش‌های from / range / …
│                                 #    - معاملات: total/get/calc_margin/calc_profit/check/send
│                                 #    - پوزیشن‌ها/تاریخچه: positions_* و history_* (orders/deals)
│                                 #    - کاملاً ایمن‌سازی شده با لاگ و تبدیل خروجی‌ها به dict/DataFrame.
│
├─ priority_executor.py           # ← صف اولویت‌دار داخل کلاینت + Aging + قفل حوزه‌ای
│                                 #    - submit(): افزودن تسک با priority و ordering_scope و TTL.
│                                 #    - aging loop: ارتقای تدریجی تسک‌های منتظر (مثلاً هر ۵ ثانیه یک پله).
│                                 #    - ورکرهای موازی: بخشی رزرو برای Low (۶..۱۰) تا گرسنگی رخ ندهد.
│                                 #    - پارامترها از "executor.*" در config.json قابل تنظیم است:
│                                 #         max_workers / reserved_low_slots / aging_step_seconds / …
│
├─ client_auth.py                 # ← مدیریت ثبت‌نام کلاینت + توکن + heartbeat + ساخت هدر امن
│                                 #    - ارسال درخواست ثبت‌نام به topics.register و انتظار پاسخ از register_responses.
│                                 #    - نگهداشت client_id / auth_token / expires_at و ارسال دوره‌ای status.
│                                 #    - ساخت هدرهای خروجی استاندارد (ts/nonce/auth/kid/sig/…)
│                                 #    - همهٔ پارامترها از "client_auth.*" در config.json خوانده می‌شود.
│
├─ kafka_listener.py              # ← مصرف‌کنندهٔ دستورات (Kafka Consumer) و فراخوانی متدهای Mt5_Manager
│                                 #    - خواندن تاپیک‌های ورودی از "kafka.topics.commands" (پشتیبانی p0/p1/p2).
│                                 #    - parse امن بدنهٔ پیام (JSON یا literal_eval کنترل‌شده).
│                                 #    - تبدیل params با mt5_utils.convert_params و فراخوانی متد مناسب.
│                                 #    - ارسال پاسخ استاندارد با KafkaResponder (Envelope: schema/corr_id/…).
│                                 #    - تنظیمات کافکا/گروه/سکیوریتی از "kafka.*" در config.json.
│
├─ kafka_responder.py             # ← تولیدکنندهٔ پاسخ (Kafka Producer) با چانکینگ
│                                 #    - send_result(): تبدیل نتیجه به JSON → چانک کردن → ارسال با هدرهای استاندارد.
│                                 #    - هدرها: corr_id / schema / seq / total / content_type / encoding.
│                                 #    - پارامترهای producer از config.json (compression/linger/retries/…).
│                                 #    - تاپیک خروجی از "kafka.topics.replies".
│
├─ main.py                        # ← نقطهٔ شروع برنامه
│                                 #    - بارگذاری کانفیگ با cfg()
│                                 #    - راه‌اندازی لاگ‌گذاری (setup_logging(cfg))
│                                 #    - ساخت و اجرای KafkaListener(cfg)
│                                 #    - خاموشی ایمن با سیگنال‌ها (Ctrl+C / SIGTERM)
│
├─ Examples/                      # ← نمونه‌کدها و ابزارهای تست/دمو
│  ├─ sender.py                   #    - نمونهٔ ارسال پیام (Producer) برای تست فرمان‌ها/متدها
│  └─ consumer_example.py         #    - نمونهٔ دریافت پاسخ‌ها (Consumer) و مونتاژ چانک‌ها (seq/total)
│
├─ README.md                      # ← راهنمای پروژه: پیش‌نیازها، اجرا، مثال‌ها، نکات دیباگ
│                                 #    - توضیح استفاده از config.json، نحوه ارسال فرمان، ساخت پیام MT5 و …
│
├─ logs/                          # ← پوشهٔ پیش‌فرض لاگ‌ها (Rotation) – ایجاد خودکار در زمان اجرا
│  └─ app.log                     #    - فایل لاگِ اصلی (اگر logging.file_enabled=true باشد)
│
├─ .gitignore                     # ← نادیده‌گرفتن فایل‌ها/پوشه‌های حساس یا تولیدی (logs/، __pycache__/، …)
│
└─ requirements.txt               # ← وابستگی‌های پایتون (confluent-kafka / MetaTrader5 / pandas / pytz و …)
                                  #    - نصب با:  pip install -r requirements.txt

# نکات اجرایی سریع:
# 1) ابتدا config.json را با مقادیر مناسب پر کنید (bootstrap_servers، client_id، مسیر MT5 و …).
# 2) اجرای برنامه:
#       python -m project.main
#    یا اگر در ریشه هستید:
#       python project/main.py
# 3) برای تست مسیر Kafka:
#    - در Examples/sender.py یک پیام با key="Mt5_Manager" و body={"method": "...", "params": {...}} بفرستید.
#    - در Examples/consumer_example.py پاسخ‌ها را بخوانید و چانک‌ها را بر اساس seq/total مونتاژ کنید.
# 4) هر زمان config.json را ویرایش کنید، تغییرات در چند ثانیه بعد (app.hot_reload_check_sec) اعمال می‌شود.
#    نیازی به ری‌استارتِ برنامه نیست.

```

---

## ⚙️ پیش‌نیازها

<!-- وابستگی‌های اصلی -->

* Python 3.9+
* کتابخانه‌های:

  * `MetaTrader5`
  * `confluent-kafka`
  * `pandas`
  * `pytz`

```bash
pip install MetaTrader5 confluent-kafka pandas pytz
```

---

## 🔧 پیکربندی (ENV Variables)

<!-- لیست کامل متغیرهای محیطی با مقادیر پیش‌فرض -->

| نام                             | پیش‌فرض                | توضیح                      |
| ------------------------------- | ---------------------- | -------------------------- |
| `KAFKA_SERVERS`                 | `192.168.1.254:9092`   | آدرس سرور Kafka            |
| `KAFKA_TOPIC`                   | `agent-send`           | تاپیک مصرف                 |
| `KAFKA_RESPONSE_TOPIC`          | `agent-recive`         | تاپیک پاسخ                 |
| `KAFKA_GROUP_ID`                | `kafka_listener_group` | گروه Consumer              |
| `KAFKA_COMPRESSION`             | `zstd`                 | نوع فشرده‌سازی Producer    |
| `KAFKA_RESPONSE_MAX_PART_BYTES` | `921600`               | حداکثر سایز هر پارت پاسخ   |
| `LOG_LEVEL`                     | `INFO`                 | سطح لاگ                    |
| `LOG_JSON`                      | `false`                | فعال‌سازی خروجی JSON       |
| `LOG_FILE`                      | `logs/app.log`         | مسیر فایل لاگ              |
| `LOG_MAX_BYTES`                 | `10485760`             | حجم هر فایل لاگ (۱۰MB)     |
| `LOG_BACKUPS`                   | `10`                   | تعداد فایل‌های پشتیبان     |
| `MT5_PATH`                      | —                      | مسیر ترمینال MT5 (اختیاری) |
| `MT5_LOGIN`                     | —                      | لاگین حساب (اختیاری)       |
| `MT5_PASSWORD`                  | —                      | رمز حساب (اختیاری)         |
| `MT5_SERVER`                    | —                      | سرور بروکر (اختیاری)       |

---

## 🚀 اجرای برنامه

<!-- نحوه اجرا -->

اجرای ساده:

```bash
python main.py
```

اجرای با ENV سفارشی:

```bash
LOG_LEVEL=DEBUG LOG_JSON=true LOG_FILE=logs/app.log \
KAFKA_SERVERS="10.0.0.12:9092" \
python main.py
```

---

## 📨 نمونه پیام Kafka

<!-- مثال پیام ورودی با key و value -->

هر پیام شامل:

* **key**: باید `"Mt5_Manager"` باشد
* **value**: آرایه JSON از دستورات

### مثال: اتصال + دریافت تیک + ارسال سفارش

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
  }}
]
```

---

## 📊 معماری سیستم

<!-- دیاگرام مرمید (سازگار با گیت‌هاب) -->

```mermaid
flowchart TD
    A[main.py] --> B[config_logging.py]
    A --> C[kafka_listener.py]
    C --> D[meta_trader_manager.py]
    C --> E[kafka_responder.py]
    D -->|مدیریت MT5| MT5[(MetaTrader5 Terminal)]
    E -->|ارسال پاسخ‌ها| Kafka[(Kafka Broker)]
```

---

## ✅ Best Practices

<!-- نکات مهم برای استفاده در تولید -->

* همیشه **Magic Number** را در سفارش‌ها ست کن.
* در سفارش‌های مارکت، قیمت را خالی بگذار → سیستم به طور خودکار bid/ask را پر می‌کند.
* در محیط Production، **JSON Logging** را فعال کن.
* پیام‌های چند مرحله‌ای را با ترتیب صحیح بفرست (initialize → check → send).
* برای داده‌های حجیم تاریخچه، از **فیلتر group/ticket/position\_id** استفاده کن.

---

## 🐞 عیب‌یابی سریع

<!-- مشکلات رایج و راه‌حل سریع -->

| مشکل                            | علت                             | راه‌حل                                                     |
| ------------------------------- | ------------------------------- | ---------------------------------------------------------- |
| `MT5 not initialized/connected` | قبل از initialize فراخوانی کردی | اول `manage_connection/initialize` رو بزن                  |
| کانستنت نگاشت نمی‌شود           | رشته اشتباه است                 | مطمئن شو کانستنت دقیق است (مثل `ORDER_TYPE_BUY`)           |
| `order_send retcode != DONE`    | خطای بروکر یا پارامترها         | اول `check` بزن، بعد `send`؛ deviation/filling را تنظیم کن |
| داده تاریخی خالی                | بازه یا نماد نامعتبر            | تاریخ باید ISO/UTC باشد؛ نماد باید فعال باشد               |

---

## 🤝 مشارکت

<!-- راهنمای مشارکت در پروژه -->

۱. ریپو را fork کن.
۲. یک branch جدید بساز:

```bash
git checkout -b feature/my-change
```

۳. تغییراتت را commit کن و Pull Request بزن.

---

## 📜 مجوز

<!-- مجوز پروژه -->

این پروژه تحت لایسنس MIT ارائه می‌شود.

```
این نسخه:  
- ✅ تمیز برای نمایش در گیت‌هاب (کامنت‌ها در خروجی HTML نهایی نمایش داده نمی‌شوند).  
- ✅ خط به خط توضیح داده شده تا تیم شما راحت‌تر بخواند.  
- ✅ کامل‌تر از نسخه قبلی (جزئیات بیشتری در عیب‌یابی و Best Practices).  

می‌خوای برای هر ماژول (`Guide.md`‌ها) هم همین سبک **کامنت مخفی Markdown** رو اعمال کنم که تیم وقتی فایل‌ها رو توی GitHub می‌خونه، یادداشت‌های داخلی شما هم قابل دیدن باشه؟
```



---

# معماری کلان (High-level)

```mermaid
flowchart TB
    classDef external fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b;
    classDef core fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#4a148c;
    classDef module fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px,color:#1b5e20;
    classDef data fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100;

    subgraph Ext["🌐 External Systems"]
        direction LR
        MT5(("📊 MetaTrader 5<br/>Terminal & API"))
        KAFKA[("🔌 Kafka Cluster<br/>Brokers & Topics")]
    end

    subgraph App["🤖 Trading Agent (Python Application)"]
        direction TB
        
        subgraph Core["⚙️ Core Components"]
            MAIN[["🚀 main.py<br/>Application Entry Point"]]
            CFG[["⚡ config_logging.py<br/>Configuration & Logging"]]
        end
        
        subgraph Modules["📦 Functional Modules"]
            MGR[["👑 meta_trader_manager.py<br/>MT5 Manager Class"]]
            LST[["👂 kafka_listener.py<br/>Command Consumer & Router"]]
            RSP[["📤 kafka_responder.py<br/>Response Producer & Chunker"]]
            UTL[["🛠️ mt5_utils.py<br/>Serializers & Converters"]]
        end
    end

    %% External connections
    LST -.->|"📥 Consumes Commands"| KAFKA
    RSP -.->|"📤 Produces Responses"| KAFKA
    MGR <-->|"🔗 Trade Operations<br/>📈 Market Data<br/>💳 Account Info"| MT5

    %% Internal dependencies
    MAIN -->|"initializes"| CFG
    MAIN -->|"creates instance"| MGR
    MAIN -->|"starts"| LST
    MAIN -->|"configures"| RSP
    
    LST -->|"dispatches calls to"| MGR
    MGR -->|"uses utilities from"| UTL
    RSP -->|"uses chunking from"| UTL
    
    CFG -->|"provides logger to"| LST
    CFG -->|"provides logger to"| RSP
    CFG -->|"provides logger to"| MGR

    %% Styling
    class Ext external;
    class Core core;
    class Modules module;
    class MT5,KAFKA data;

    linkStyle 0,1,2,3 stroke:#ff6f00,stroke-width:2px;
    linkStyle 4,5,6,7,8,9,10,11 stroke:#7b1fa2,stroke-width:2px;
```

---

# مؤلفه‌ها و وابستگی‌ها (Component Map)

```mermaid
graph LR
    classDef infra fill:#fff2cc,stroke:#d6b656,stroke-width:3px,stroke-dasharray:5 5,color:#000000;
    classDef core fill:#d5e8d4,stroke:#82b366,stroke-width:3px,color:#000000;
    classDef module fill:#e1d5e7,stroke:#9673a6,stroke-width:2px,color:#000000;
    classDef connection stroke:#ff6d00,stroke-width:2px;
    classDef dataConnection stroke:#3949ab,stroke-width:2px;
    classDef utilityConnection stroke:#7b1fa2,stroke-width:2px;

    subgraph Infra["🏗️ Infrastructure Layer"]
        K[Kafka Cluster<br/>Bootstrap Servers]
        T(MetaTrader 5<br/>Terminal API)
    end

    subgraph Agent["🤖 Trading Agent Microservice"]
        A1[main.py<br/>Application Orchestrator]
        A2[config_logging.py<br/>Config & Logger Factory]
        
        subgraph Modules["🛠️ Functional Modules"]
            A3[kafka_listener.py<br/>Command Consumer]
            A4[kafka_responder.py<br/>Response Producer]
            A5[meta_trader_manager.py<br/>MT5 Core Manager]
            A6[mt5_utils.py<br/>Utilities & Serializers]
        end
    end

    %% Core Dependencies
    A1-->A2
    A1-->A3
    A1-->A4
    A1-->A5

    %% External Communications
    A3-.->|📥 Consume Commands|K
    A4-.->|📤 Produce Responses|K

    %% Internal Processing
    A3==>|🚀 Route & Dispatch|A5
    A5==>|🔌 Execute Operations|T

    %% Utility Dependencies
    A5-->|🔄 Serialize Data|A6
    A4-->|📦 Chunking Logic|A6

    %% Logging Dependencies
    A3-->|📝 Structured Logging|A2
    A4-->|📊 Audit Trails|A2
    A5-->|⚡ Execution Logs|A2

    %% Styling
    class Infra infra;
    class Agent core;
    class Modules module;
    class K,T infra;
    class A1,A2 core;
    class A3,A4,A5,A6 module;

    linkStyle 0,1,2,3 stroke:#2e7d32,stroke-width:2px;
    linkStyle 4,5 stroke:#ff6f00,stroke-width:3px;
    linkStyle 6,7 stroke:#d32f2f,stroke-width:2px;
    linkStyle 8,9 stroke:#7b1fa2,stroke-width:2px;
    linkStyle 10,11,12 stroke:#0288d1,stroke-width:2px;
```

---

# سکانس جریان درخواست/پاسخ (End-to-End Sequence)

```mermaid
sequenceDiagram
    box rgba(0, 100, 255, 0.1) External Systems
        participant Prod as 🚀 Kafka Producer (Client)
        participant K as 📥 Kafka Topic (requests)
        participant KO as 📤 Kafka Topic (responses)
        participant MT5 as 📊 MetaTrader 5 Terminal
    end

    box rgba(0, 200, 100, 0.1) Trading Agent Core
        participant L as 👂 kafka_listener.py
        participant M as 👑 Mt5_Manager
        participant U as 🛠️ mt5_utils.py
        participant R as 📤 kafka_responder.py
    end

    Note over Prod, KO: 🔄 Request-Response Cycle

    Prod->>K: 📨 Publish Request
    Note right of Prod: {request_id: "req_123",<br/>op: "place_order",<br/>params: {symbol: "EURUSD"}}

    K->>L: 🔔 Message Batch Available
    L->>K: ✅ Poll/Consume Messages
    L->>L: 🔍 Validate & Parse JSON
    Note right of L: Message validation<br/>Schema checking

    L->>M: 🚀 dispatch(op, params, request_id)
    Note right of L: Async method invocation<br/>Request tracking

    M->>MT5: ⚡ Execute Operation
    Note right of M: place_order/get_quote<br/>account_info/fetch_data

    MT5-->>M: 📋 Raw Response
    Note left of MT5: Native MT5 data structures<br/>Potential errors

    M->>U: 🛠️ normalize_response()
    Note right of M: Convert to JSON-safe<br/>Handle datetime objects

    U-->>M: 🎯 Normalized Result
    Note left of U: Serializable data<br/>Error formatting

    M-->>L: 📦 ResponsePayload
    Note left of M: {request_id: "req_123",<br/>result: {...},<br/>status: "success"}

    L->>R: 📥 enqueue_response()
    Note right of L: Async queue for<br/>response processing

    R->>U: 📏 chunk_if_needed()
    Note right of R: max_bytes=900000<br/>Split large responses

    U-->>R: 🧩 Chunk Array
    Note left of U: [{chunk_id: 1, total: 3, data: ...}]

    R->>KO: 🚀 Produce Chunks
    Note right of R: Keyed by request_id<br/>Maintains order

    KO-->>Prod: 🔄 Consumer Reassemblies
    Note left of KO: Client monitors topic<br/>Reconstructs full response

    Prod->>Prod: 🧠 Reassemble & Process
    Note right of Prod: Validate chunks<br/>Handle missing parts<br/>Final processing

    %% Styling for better visibility
    rect rgba(0, 0, 0, 0.05)
        Note over Prod, MT5: 💡 End-to-End Processing Time: ~100-500ms
    end
```

---

# دیاگرام کلاس‌ها (Class Diagram)

```mermaid
classDiagram
    direction TB
    
    class Mt5_Manager {
        +Mt5_Manager(config: Dict)
        +is_connected: bool
        +connect(): bool
        +shutdown(): void
        +get_account_info(): Dict
        +get_symbols(filter: str = "*"): List~Dict~
        +get_quote(symbol: str): Dict
        +place_order(req: OrderRequest): OrderResult
        +modify_order(id: int, params: Dict): OrderResult
        +close_order(id: int): OrderResult
        -_ensure_conn(): void
        -_map_error(code: int): str
    }

    class KafkaListener {
        +KafkaListener(cfg: Dict, manager: Mt5_Manager, responder: KafkaResponder)
        +start(): void
        +stop(): void
        +_handle_message(msg: Any): void
        -_parse_message(raw: bytes) Request
        -_validate(req: Request): void
        -_dispatch(req: Request): ResponsePayload
    }

    class KafkaResponder {
        +KafkaResponder(cfg: Dict)
        +send(payload: ResponsePayload): void
        +flush(): void
        -_chunk(data: bytes, max_size: int) List~Chunk~
        -_serialize(obj: Any): bytes
    }

    class ConfigLogging {
        +setup_logging(level: str, file: str?): Logger
        +load_env(): Dict
    }

    class Mt5Utils {
        <<utility>>
        +to_json_safe(obj: Any): Any
        +decimal_to_float(d: Decimal): float
        +datetime_to_iso(dt: datetime): str
        +chunks(data: bytes, chunk_size: int): List~bytes~
        +validate_order(req: Dict): None|Exception
    }

    class Request {
        +request_id: str
        +op: str
        +params: Dict
        +ts: datetime
    }

    class ResponsePayload {
        +request_id: str
        +ok: bool
        +result: Any
        +error: str?
        +meta: Dict
    }

    %% Relationships
    Mt5_Manager --|> Mt5Utils : uses
    KafkaResponder --|> Mt5Utils : uses
    KafkaListener --> Mt5_Manager : dispatches to
    KafkaListener --> KafkaResponder : enqueues to
    ConfigLogging --|> KafkaListener : provides logger
    ConfigLogging --|> KafkaResponder : provides logger
    ConfigLogging --|> Mt5_Manager : provides logger

    %% Styling for better visibility
    classDef mainClass fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000000
    classDef utilClass fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000000
    classDef dataClass fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000000
    classDef configClass fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#000000

    class Mt5_Manager mainClass
    class KafkaListener mainClass
    class KafkaResponder mainClass
    class Mt5Utils utilClass
    class Request dataClass
    class ResponsePayload dataClass
    class ConfigLogging configClass
```

---

***
# وضعیت و چرخهٔ chunking در پاسخ‌گو (State Machine)
***

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Serializing : send(payload)
  Serializing --> NeedsChunking : size > MAX
  Serializing --> ReadyToSend : size <= MAX

  NeedsChunking --> Chunking
  Chunking --> ReadyToSend : produced parts[N]

  ReadyToSend --> Sending : produce() per part
  Sending --> Flushing : last part sent
  Flushing --> Idle : ack/flush ok
  Sending --> Error : broker exception
  Flushing --> Error : timeout
  Error --> Idle : recover/retry
```

---

# کانال‌ها و کانفیگ کافکا (Topic/Config Map)

```mermaid
flowchart LR
  subgraph Kafka
    REQ[requests.<env/app>]
    RES[responses.<env/app>]
    DLQ[requests.dlq]
  end

  subgraph App
    L[kafka_listener.py]
    R[kafka_responder.py]
  end

  L -- consume --> REQ
  L -- on-parse-error --> DLQ
  R -- produce --> RES

  classDef t fill:#eef,stroke:#88f
  class REQ,RES,DLQ t
```

---

# خط لولهٔ راه‌اندازی برنامه (Startup Pipeline)

```mermaid
sequenceDiagram
  participant Main as main.py
  participant Conf as config_logging.py
  participant M as Mt5_Manager
  participant L as KafkaListener
  participant R as KafkaResponder

  Main->>Conf: load_env() + setup_logging()
  Main->>M: Mt5_Manager(env/config)
  M-->>Main: is_connected = true/false
  Main->>R: KafkaResponder(env/config)
  Main->>L: KafkaListener(env/config, M, R)
  Main->>L: start()
  Main-->>Main: run_until_sigint()
  Main->>L: stop() (on shutdown)
  Main->>R: flush()
  Main->>M: shutdown()
```

---

# قرارداد پیام‌ها (Schemas – پیشنهادی/متعارف)

> اگر اسکیمای دقیق‌تون فرق داره، همین بلوک رو با کلیدهای واقعی‌تون جایگزین کن.

```mermaid
erDiagram
  REQUEST {
    string request_id PK
    string op
    json   params
    string reply_to  "optional"
    string corr_key  "optional"
    string ts_iso
  }

  RESPONSE {
    string request_id
    boolean ok
    json result
    string error
    int part_no
    int total_parts
    string ts_iso
  }

  REQUEST ||--o{ RESPONSE : "request_id"
```

---

# ماتریس عملیات (Op Routing)

```mermaid
flowchart TB
  subgraph Listener
    IN[Request.op]
    RT{Match op}
  end
  subgraph Manager
    ACC[get_account_info]
    SYM[get_symbols]
    QTE[get_quote]
    PLC[place_order]
    MOD[modify_order]
    CLS[close_order]
  end

  IN --> RT
  RT -->|account.info| ACC
  RT -->|symbols.list| SYM
  RT -->|quote.get| QTE
  RT -->|order.place| PLC
  RT -->|order.modify| MOD
  RT -->|order.close| CLS
```

---

