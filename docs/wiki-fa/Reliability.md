# قابلیت اطمینان و انتقال داده

## Command lifecycle — برنامه‌ریزی‌شده

`received → validated → authorized → accepted → execution_started → mt5_result_obtained → response_persisted → response_transmitted → server_acknowledged`

retry شبکه نباید معامله را دوباره اجرا کند. delivery می‌تواند at-least-once باشد، اما execution برای فرمان non-idempotent باید با command ID و idempotency key پایدار، دقیقاً یک‌بار از منظر Agent حفاظت شود. duplicate نتیجهٔ ثبت‌شده یا in-progress را می‌گیرد، نه اجرای مجدد.

## SQLite / spooler — برنامه‌ریزی‌شده

SQLite WAL برای command state، outbox، transfer metadata و telemetry pending پیشنهاد شده است. migration versioned، retention/quota، disk-full، corruption quarantine، restart recovery و cleanup الزامی‌اند. WAL به تنهایی تضمین delivery یا duplicate-prevention نیست؛ transaction و state-machine باید آزموده شوند.

## Historical data و chunking — برنامه‌ریزی‌شده

MT5 data UTC است؛ bars با Max. bars in chart محدود می‌شوند و API NumPy array می‌دهد. بنابراین request بزرگ با بازهٔ زمان/count partition می‌شود و هر partition جداگانه خوانده/serialize می‌شود. دادهٔ یک گیگابایتی هرگز یکجا در RAM یا یک payload نمی‌رود. transfer دارای `transfer_id`، `chunk_index`، hash هر chunk، manifest/hash کل، ack، resume، duplicate/missing detection، cancel و backpressure است. اندازهٔ chunk configurable و با load test تعیین می‌شود؛ 2MB فقط مثال است.

## Priority / Kafka / Gateway — برنامه‌ریزی‌شده

urgent execution، normal control/read و bulk history classهای جدا دارند. deadline، aging و fairness مانع starvation می‌شوند؛ bulk بین partitionها yield می‌دهد. تا اثبات ایمنی concurrency، فراخوانی MT5 سریال است. Kafka transport اصلی high-throughput با durable inbound handling است؛ HTTPS/mTLS برای bootstrap/recovery است. هیچ‌کدام در v0.1.3 پیاده‌سازی نشده‌اند.
