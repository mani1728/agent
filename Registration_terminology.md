# client(agent) --> server (kafka_topic"clients.register")
## method = client_auth.py.ClientAuth.register()
## message content => Hello
### key = client_tmp_id (generate client Random UUID)
### Value (JSON) : 
```json
{
  "schema": "ClientRegisterV1",
  "client_tmp_id": "b6d8e5f8b2e64d14b1cf2a5f6a4a8c4e",
  "meta": {
    // هرچی خودت در ClientAuth(...) به عنوان meta دادی
    "os": "Windows",
    "agent_version": "0.1.0",
    "capabilities": ["mt5", "reports"]
  },
  "ts": "2025-09-08T03:20:15+00:00",
  "nonce": "f0c6f5c2b5ad4e8f90d3b7e34e4a0a5a"
}
```
---
### Headers (string/UTF-8):
```text
schema: "ClientRegisterV1"

client_tmp_id: "<Random UUID>"

corr_id: "<یک UUID دیگر برای ردیابی درخواست/پاسخ>"

content_type: "application/json"

encoding: "utf-8"
```
---
# server(kafka_topic"clients.register.responses")
## گروه مصرف‌کنندهٔ موقت کلاینت:
>`client-register-waiter-<client_tmp_id>`

## فیلتر پاسخ سمت کلاینت: اگر در Headers یکی از این‌ها برابر باشد، پیام را قبول می‌کند: 
`corr_id == <همان corr_id درخواست>`
`client_tmp_id == <همان client_tmp_id>`

## Value (JSON):
```json
{
  "schema": "ClientRegisterResponseV1",
  "client_tmp_id": "b6d8e5f8b2e64d14b1cf2a5f6a4a8c4e",
  "client_id": "client-001",
  "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", 
  "expires_at": "2025-09-08T06:20:15+00:00",
  "reply_topic": "server.replies"
}
```
## *Headers پیشنهادی پاسخ:*:

```text
schema: "ClientRegisterResponseV1"

corr_id: "<همان corr_id درخواست>" (ترجیحاً ست کن)

client_tmp_id: "<client_tmp_id>" (برای اطمینان)

اگر client_id یا auth_token در پاسخ نباشد، کد کلاینت خطا می‌دهد.
```
---
# بعد از ثبت‌نام چه می‌فرستد؟ (Heartbeat)
## client --> server(kafka_topic"clients.status") (*بهتره compacted باشه*)
### Key: client_id
### Value (JSON):
```json
{
  "schema": "ClientStatusV1",
  "client_id": "client-001",
  "last_seen": "2025-09-08T03:20:30+00:00",
  "meta": { "os": "Windows", "agent_version": "0.1.0" }
}
```
### Headers: 
```text
schema=ClientStatusV1,
content_type=application/json, 
encoding=utf-8
```
تناوب: هر client_auth.heartbeat_interval_sec ثانیه (پیش‌فرض 15s)
---
---
___

* فایل: `client_auth.py`
* متد: `ClientAuth.register()`

# پیام درخواست ثبت‌نام (Hello)

* **Topic:** `clients.register`
* **Key:** `client_tmp_id` (یک UUID رندوم که کلاینت ساخته)
* **Headers (string/UTF-8):**

  * `schema: "ClientRegisterV1"`
  * `client_tmp_id: "<همون UUID>"`
  * `corr_id: "<یک UUID دیگر برای ردیابی درخواست/پاسخ>"`
  * `content_type: "application/json"`
  * `encoding: "utf-8"`
* **Value (JSON):**

```json
{
  "schema": "ClientRegisterV1",
  "client_tmp_id": "b6d8e5f8b2e64d14b1cf2a5f6a4a8c4e",
  "meta": {
    // هرچی خودت در ClientAuth(...) به عنوان meta دادی
    "os": "Windows",
    "agent_version": "0.1.0",
    "capabilities": ["mt5", "reports"]
  },
  "ts": "2025-09-08T03:20:15+00:00",
  "nonce": "f0c6f5c2b5ad4e8f90d3b7e34e4a0a5a"
}
```

> نکته: `ts` به فرمت ISO8601 با `+00:00` میاد (نه `Z`).

# کلاینت منتظر چه پاسخی است؟

* **Topic:** `clients.register.responses`

* **گروه مصرف‌کنندهٔ موقت کلاینت:**
  `client-register-waiter-<client_tmp_id>`

* **فیلتر پاسخ سمت کلاینت:** اگر در **Headers** یکی از این‌ها برابر باشد، پیام را قبول می‌کند:

  * `corr_id == <همان corr_id درخواست>`
  * یا `client_tmp_id == <همان client_tmp_id>`

* **Value (JSON) مورد انتظار:**

```json
{
  "schema": "ClientRegisterResponseV1",
  "client_tmp_id": "b6d8e5f8b2e64d14b1cf2a5f6a4a8c4e",
  "client_id": "client-001",
  "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", 
  "expires_at": "2025-09-08T06:20:15+00:00",
  "reply_topic": "server.replies"
}
```

* **Headers پیشنهادی پاسخ:**

  * `schema: "ClientRegisterResponseV1"`
  * `corr_id: "<همان corr_id درخواست>"` (ترجیحاً ست کن)
  * `client_tmp_id: "<client_tmp_id>"` (برای اطمینان)

> اگر `client_id` یا `auth_token` در پاسخ نباشد، کد کلاینت خطا می‌دهد.

# بعد از ثبت‌نام چه می‌فرستد؟ (Heartbeat)

* **Topic:** `clients.status` (بهتره compacted باشه)
* **Key:** `client_id`
* **Value (JSON):**

```json
{
  "schema": "ClientStatusV1",
  "client_id": "client-001",
  "last_seen": "2025-09-08T03:20:30+00:00",
  "meta": { "os": "Windows", "agent_version": "0.1.0" }
}
```

* **Headers:** `schema=ClientStatusV1`, `content_type=application/json`, `encoding=utf-8`
* **تناوب:** هر `client_auth.heartbeat_interval_sec` ثانیه (پیش‌فرض 15s)

---

## نکته‌ی مهم برای پیاده‌سازی سرور (agent-handler)

1. از `clients.register` مصرف کن → از **Headers**، `corr_id` و `client_tmp_id` رو بردار، و از **Value** فیلدهای `meta/ts/nonce` رو.
2. به `db-handler` روی تاپیک `db.register` یک درخواست **upsert** بده (مثلاً با `client_tmp_id` + هر شناسه‌ای که خودت تعریف می‌کنی).
3. بعد از upsert، روی `clients.register.responses` جواب بده و **حتماً** یکی از این دو Header را ست کن:

   * `corr_id` (ترجیحاً همون corr\_id درخواست)
   * یا `client_tmp_id`
4. در پاسخ `client_id` یکتا، `auth_token` و `expires_at` ISO بده.

> هشدار کوچک سمت کلاینت: در `ClientAuth.register()` موقع دریافت پاسخ، هدرها مستقیماً `dict(msg.headers())` می‌شن؛ اگر کتابخانه‌ات هدرها رو **بایت** برگردونه، تطبیق `corr_id`/`client_tmp_id` ممکنه نخوره. بهترین کار اینه که پاسخ رو با **Headerهای UTF-8 string** بفرستی (یا ما بعداً کلاینت رو طوری اصلاح کنیم که هدرها رو decode کنه).

اگر بخوای، قدم بعدی رو همین الان برای **agent-handler** (مصرف از `clients.register` → ارسال به `db.register` و برگشت پاسخ) هم برات اسکلت کد می‌نویسم.
