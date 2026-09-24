# امنیت و عملیات

## Identity و authentication — برنامه‌ریزی‌شده

Installation ID به‌طور تصادفی هنگام provision ساخته می‌شود؛ Server Agent ID و credential را اختصاص می‌دهد. customer، subscription، installation، device fingerprint و credential یکی نیستند. fingerprint سخت‌افزار فقط signal بازیابی با بررسی privacy است، نه هویت اصلی. چرخه: provision → register → authenticate → rotate → revoke → reinstall/recover.

## Security — برنامه‌ریزی‌شده

mTLS و rotation/revocation certificate، ACL deny-by-default، replay resistance، payload/decompression bound، secrets OS-protected و recursive redaction لازم‌اند. secret، password، token، private key یا raw credential نه در source/CI و نه در log/telemetry ثبت نمی‌شود.

remote configuration سه قلمرو دارد: `LOCAL_ONLY` برای trust root و anchor امنیتی، `SERVER_MANAGED` برای operation و `SERVER_MANAGED_WITH_LIMITS` برای مقادیر bounded مانند chunk/retention. candidate باید authenticate/authorize/schema/policy/compatibility validate، durable stage، atomic apply، health-check و در failure rollback به last-known-good شود. config معمولی هرگز مرز local security را بازنویسی نمی‌کند.

## Logging و observability

v0.1.3 logging lifecycle محدود دارد. هدف production: local structured JSON با timestamp/severity/agent/correlation/command/transfer/state/duration/error category، rotation/retention/max disk و support bundle redacted. server telemetry از local logs جداست.

heartbeat شامل version/uptime/lifecycle، MT5/transport/spool، queue age/bytes، active job، last success و CPU/memory/disk امن است. liveness یعنی process/supervisor alive؛ readiness یعنی پذیرش امن یک class کار.

## Windows Service و Session 0 — مسدود

Agent باید بعد از boot unattended شود، اما Runner service در Session 0 است و MT5 Python IPC GUI-dependent است. experiment کنترل‌شده در Session 1 با Worker مستقیم، `initialize`، `version`، `terminal_info` و presence-only `account_info` موفق بود؛ `shutdown` API نیز terminal را نکشت. این فقط viability interactive را اثبات می‌کند، نه boot/logon/locked/disconnected session یا launcher unattended. direct service integration ادعا نمی‌شود. راه بعدی: service/control با Worker session-bound و IPC authenticated، بدون desktop-interaction hack یا kill کردن `terminal64.exe`.

## Maintenance/quiesce — برنامه‌ریزی‌شده

RUNNING → QUIESCING → QUIESCED → RESUMING، با heartbeat/control channel حداقلی و policy صریح برای in-flight trade/transfer، timeout و restart recovery. این رفتار هنوز پیاده‌سازی نشده است.
