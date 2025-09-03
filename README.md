
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
├─ config_logging.py          # مرحله ۱: تنظیمات و لاگ‌گذاری
├─ mt5_utils.py               # مرحله ۲: نگاشت کانستنت‌ها، تاریخ‌ها، سریال‌سازی امن
├─ kafka_responder.py         # مرحله ۳: تولیدکنندهٔ پاسخ (Producer) + چانکینگ
├─ kafka_listener.py          # مرحله ۴: مصرف‌کنندهٔ دستورات (Consumer) + فراخوانی متدها
├─ meta_trader_manager.py     # همون نسخهٔ بهینه‌ی قبلی شما
├─ main.py                    # مرحله ۵: نقطهٔ شروع برنامه
└─ Examples/                  # پوشهٔ نمونه‌ها
   ├─ sender.py
   └─ consumer_example.py
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
  subgraph Infra
    K[(Kafka)]
    T((MT5))
  end

  subgraph Agent
    A1[main.py]
    A2[config_logging.py]
    A3[kafka_listener.py]
    A4[kafka_responder.py]
    A5[meta_trader_manager.py]
    A6[mt5_utils.py]
  end

  A1-->A2
  A1-->A3
  A1-->A4
  A1-->A5

  A3-- consume -->K
  A4-- produce -->K

  A3-- route -->A5
  A5-- call/receive -->T

  A5-- uses -->A6
  A4-- uses -->A6
  A3-- uses logger -->A2
  A4-- uses logger -->A2
  A5-- uses logger -->A2
```

---

# سکانس جریان درخواست/پاسخ (End-to-End Sequence)

```mermaid
sequenceDiagram
  autonumber
  participant Prod as Kafka Producer (Client)
  participant K as Kafka Topic (requests)
  participant L as kafka_listener.py
  participant M as Mt5_Manager (meta_trader_manager.py)
  participant MT5 as MetaTrader 5
  participant U as mt5_utils.py
  participant R as kafka_responder.py
  participant KO as Kafka Topic (responses)

  Prod->>K: Publish Request {request_id, op, params}
  L->>K: Poll/Consume batch
  L->>L: Validate & Parse message
  L->>M: dispatch(op, params, request_id)
  M->>MT5: Execute op (e.g., place_order/get_quote)
  MT5-->>M: Raw result / error
  M->>U: normalize/convert to json-safe
  U-->>M: normalized_result
  M-->>L: ResponsePayload {request_id, result|error}
  L->>R: enqueue for sending
  R->>U: chunk_if_needed(payload, max_bytes)
  U-->>R: [{part_no, total, data}, ...]
  R->>KO: Produce chunks keyed by request_id
  KO-->>Prod: Client consumes & reassembles
```

---

# دیاگرام کلاس‌ها (Class Diagram)

```mermaid
classDiagram
  class Mt5_Manager {
    +Mt5_Manager(config)
    +connect(): bool
    +is_connected: bool
    +get_account_info(): Dict
    +get_symbols(filter:str="*"): List~Dict~
    +get_quote(symbol:str): Dict
    +place_order(req: OrderRequest): OrderResult
    +modify_order(id:int, params:Dict): OrderResult
    +close_order(id:int): OrderResult
    +shutdown(): void
    -_ensure_conn(): void
    -_map_error(code:int): str
  }

  class KafkaListener {
    +KafkaListener(cfg, manager, responder)
    +start(): void
    +stop(): void
    +_handle_message(msg): void
    -_parse_message(raw)->Request
    -_validate(req)->void
    -_dispatch(req)->ResponsePayload
  }

  class KafkaResponder {
    +KafkaResponder(cfg)
    +send(payload: ResponsePayload): void
    +flush(): void
    -_chunk(bytes, max_size)->List~Chunk~
    -_serialize(obj)->bytes
  }

  class ConfigLogging {
    +setup_logging(level:str, file:str?): Logger
    +load_env()->Dict
  }

  class Mt5Utils {
    <<utility>>
    +to_json_safe(obj)->Any
    +decimal_to_float(d)->float
    +datetime_to_iso(dt)->str
    +chunks(b:bytes, n:int)->List~bytes~
    +validate_order(req)->None|Error
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

  Mt5_Manager <.. Mt5Utils : uses
  KafkaResponder <.. Mt5Utils : uses
  KafkaListener --> Mt5_Manager : dispatch()
  KafkaListener --> KafkaResponder : enqueue()
  ConfigLogging <.. KafkaListener : logger
  ConfigLogging <.. KafkaResponder : logger
  ConfigLogging <.. Mt5_Manager : logger
```

---

# وضعیت و چرخهٔ chunking در پاسخ‌گو (State Machine)

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

