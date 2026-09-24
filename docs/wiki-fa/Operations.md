# امنیت و عملیات

## Identity و authentication — برنامه‌ریزی‌شده

Installation ID به‌طور تصادفی هنگام provision ساخته می‌شود؛ Server Agent ID و credential را اختصاص می‌دهد. customer، subscription، installation، device fingerprint و credential یکی نیستند. fingerprint سخت‌افزار فقط signal بازیابی با بررسی privacy است، نه هویت اصلی. چرخه: provision → register → authenticate → rotate → revoke → reinstall/recover.

## Security — برنامه‌ریزی‌شده

mTLS و rotation/revocation certificate، ACL deny-by-default، replay resistance، payload/decompression bound، secrets OS-protected و recursive redaction لازم‌اند. secret، password، token، private key یا raw credential نه در source/CI و نه در log/telemetry ثبت نمی‌شود.

## Logging و observability

v0.1.3 logging lifecycle محدود دارد. هدف production: local structured JSON با timestamp/severity/agent/correlation/command/transfer/state/duration/error category، rotation/retention/max disk و support bundle redacted. server telemetry از local logs جداست.

heartbeat شامل version/uptime/lifecycle، MT5/transport/spool، queue age/bytes، active job، last success و CPU/memory/disk امن است. liveness یعنی process/supervisor alive؛ readiness یعنی پذیرش امن یک class کار.

## Windows Service و Session 0 — مسدود

Agent باید بعد از boot unattended شود، اما Pipeline #16 نشان داده Runner service در Session 0 است و MT5 Python IPC GUI-dependent است. direct service integration ادعا نمی‌شود. راه پیشنهادی برای آزمایش: service/control با broker session-bound و IPC authenticated؛ بدون desktop-interaction hack یا kill کردن `terminal64.exe`. تا experiment کنترل‌شده، تصمیم production مسدود است.

## Maintenance/quiesce — برنامه‌ریزی‌شده

RUNNING → QUIESCING → QUIESCED → RESUMING، با heartbeat/control channel حداقلی و policy صریح برای in-flight trade/transfer، timeout و restart recovery. این رفتار هنوز پیاده‌سازی نشده است.
