# قابلیت اطمینان و انتقال داده

## Command lifecycle — پیاده‌سازی‌شده (پایهٔ پایدار)

`received → validated → authorized → accepted → execution_started → mt5_result_obtained → response_persisted → response_transmitted → server_acknowledged`

retry شبکه نباید معامله را دوباره اجرا کند. delivery می‌تواند at-least-once باشد، اما execution برای فرمان non-idempotent باید با command ID و idempotency key پایدار، دقیقاً یک‌بار از منظر Agent حفاظت شود. duplicate نتیجهٔ ثبت‌شده یا in-progress را می‌گیرد، نه اجرای مجدد.

اگر `order_send` timeout، response گم‌شده یا crash پس از submission رخ دهد، Agent نمی‌تواند failure را فرض کند. state `EXECUTION_AMBIGUOUS` durable می‌شود، سپس با order/deal/position/history و correlation محلی reconcile می‌شود. تا وقتی عدم اجرا اثبات نشده است، trade هرگز blind retry نمی‌شود. واقعیت مشاهده‌شده در MT5/Broker برای state بازار معتبرتر از انتظار Server است.

TTL یا `expires_at` durable است؛ expiration فرمان بر default مقدم است و فرمان expired پس از restart/retry اجرا نمی‌شود. CANCEL undo نیست: پیش از point of no return فرمان queued/bulk در safe point لغو می‌شود؛ پس از آن reverse کردن اثر trade یک فرمان جدید با authorization و TTL خودش است.

## SQLite / spooler — پیاده‌سازی‌شده (بخش پایه)

SQLite WAL برای command state، outbox، transfer metadata و telemetry pending پیشنهاد شده است. migration versioned، retention/quota، disk-full، corruption quarantine، restart recovery و cleanup الزامی‌اند. WAL به تنهایی تضمین delivery یا duplicate-prevention نیست؛ transaction و state-machine باید آزموده شوند.

SQLite authority محلیِ execution/idempotency/correlation است: `server_command_id → agent_execution_id → mt5_request_id → order/deal/position ticket`. comment کوتاه و non-sensitive در MT5 فقط evidence ثانویه است؛ broker ممکن است آن را تغییر دهد. retention configurable است ولی cleanup هرگز نباید safety property جلوگیری از duplicate trade را بشکند.

## Historical data و chunking — برنامه‌ریزی‌شده

MT5 data UTC است؛ bars با Max. bars in chart محدود می‌شوند و API NumPy array می‌دهد. بنابراین request بزرگ با بازهٔ زمان/count partition می‌شود و هر partition جداگانه خوانده/serialize می‌شود. دادهٔ یک گیگابایتی هرگز یکجا در RAM یا یک payload نمی‌رود. transfer دارای `transfer_id`، `chunk_index`، hash هر chunk، manifest/hash کل، ack، resume، duplicate/missing detection، cancel و backpressure است. اندازهٔ chunk configurable و با load test تعیین می‌شود؛ 2MB فقط مثال است.

## Priority / Kafka / Gateway — برنامه‌ریزی‌شده

urgent execution، normal control/read و bulk history classهای جدا دارند. deadline، aging و fairness مانع starvation می‌شوند؛ bulk بین partitionها yield می‌دهد. تا اثبات ایمنی concurrency، فراخوانی MT5 سریال است. Kafka transport اصلی high-throughput با durable inbound handling است؛ HTTPS/mTLS برای bootstrap/recovery است. هیچ‌کدام در v0.1.3 پیاده‌سازی نشده‌اند.
## ابهام و تأييد دریافت — پیاده‌سازی‌شده

شناسه يکتاي فرمان سرور و شناسه اجرای عامل به‌صورت پايدار
نگه‌داری می‌شوند. اگر اجرا پس از نقطهٔ بازگشت‌ناپذير مبهم شود، عامل آن را دوباره
اجرا نمی‌کند و تا تطبيق با شواهد در حالت مبهم باقی می‌ماند. صندوق خروجی نيز تا
دريافت تأييد صريح حذف نمی‌شود؛ ارسال، به معنی تأييد نيست.
