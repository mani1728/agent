# واژه‌نامه، پیکربندی و پشتیبانی

| اصطلاح | معنی |
| --- | --- |
| Control Plane | Server که تصمیم و سیاست را دارد. |
| Agent | worker ویندوزی؛ تصمیم معاملاتی نمی‌گیرد. |
| Command ID | شناسه immutable فرمان و محور audit/idempotency. |
| Correlation ID | اتصال command، result، log و transfer. |
| Idempotency | retry پیام، side effect معامله را تکرار نکند. |
| Outbox | نتیجهٔ durable منتظر ارسال. |
| Liveness / Readiness | alive بودن process / آمادگی امن برای کار. |
| Quiesced | توقف کار عادی با control/heartbeat محدود فعال. |

## Configuration فعلی

تنها environment settings مستند‌شده عبارت‌اند از HTTP host/port/max bytes و log level/file؛ [CONFIGURATION](../CONFIGURATION.md) مرجع است. JSONC، Kafka و credential production configuration فعال نیست.

## Error handling و support

برای incident ابتدا version/diagnostics، state lifecycle، terminal discovery، HTTP binding و logهای redacted را بررسی کنید. secret یا private material را در ticket نگذارید. MT5 نبودن، Session 0، terminal history limit و broker outcome را به‌عنوان category جدا ثبت کنید. [KNOWN_ISSUES](../KNOWN_ISSUES.md) محدودیت‌های فعلی را نگه می‌دارد.

## منابع

- [MQL5 Python integration](https://www.mql5.com/en/docs/python_metatrader5)
- [copy_rates_range و UTC/history limit](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py)
- [معماری هدف](../TARGET_ARCHITECTURE.md)
