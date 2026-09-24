# معماری و قابلیت‌ها

## معماری فعلی — پیاده‌سازی‌شده

```text
HTTPTransportAdapter → ApplicationBoundary → CommandDispatcher
                                      ├→ capability provider/registry
                                      └→ MT5 lifecycle + ApplicationHost
```

قراردادهای فعلی local هستند. registry در حافظه است و پیش‌فرض آن خالی است. این واقعیت، ادعای وجود Kafka، persistence، TLS یا order execution نیست.

## معماری هدف — برنامه‌ریزی‌شده

Server از طریق portهای transport-agnostic فرمان versioned می‌دهد. پس از validation، authentication و authorization، Agent state فرمان را durable می‌کند و آن را به یک lane سریال MT5 می‌سپارد. نتیجه یا chunkها ابتدا در outbox محلی ثبت می‌شوند و سپس transport آن‌ها را منتقل می‌کند. یک نصب/terminal MT5 برای هر client پشتیبانی می‌شود؛ multi-terminal خارج از محدوده است.

## مدل capability MT5

read-side به صورت allowlist رشد می‌کند: terminal/version/account، symbol/tick، bars/rates، positions/orders/deals/history و calculation. `symbol_select` یا market-book باید capability مستقل با policy صریح باشد. write-side شامل `order_send`، تغییر/لغو و SL/TP است و فقط پس از تصمیم Server، قرارداد و approval امنیتی وارد می‌شود. ارسال Python/code از Server ممنوع است.

## Command و Error model — برنامه‌ریزی‌شده

CommandEnvelope آینده شامل schema version، command/agent/correlation ID، operation، parameters، priority، deadline، idempotency key، reply metadata و security context است؛ هنوز freeze نشده است. Errorها باید protocol، validation، authentication، authorization، unsupported، busy/degraded، MT5/broker، execution، timeout، transport، persistence، partial transfer و cancellation را جدا کنند. اطلاعات safe از retcode/`last_error` حفظ می‌شود.

## تصمیم‌های نهایی Product Owner — تصمیم‌گرفته‌شده، پیاده‌سازی‌نشده

فقط commandهای محصولیِ explicit و allowlisted به API داخلی MT5 map می‌شوند؛ Server هرگز نام function دلخواه Python/MT5 نمی‌فرستد. command یا version ناشناخته fail-closed با `UNSUPPORTED_COMMAND` یا `UNSUPPORTED_COMMAND_VERSION` است. در handshake/resync، Capability Manifest نسخهٔ Agent/protocol، commandها و version آن‌ها، class و وضعیت enable/disable را اعلام می‌کند.

classها عبارت‌اند از `READ`، `LOCAL_STATE`، `TRADE_ANALYSIS`، `TRADE_EXECUTION` و آیندهٔ `CHART_TERMINAL`. اجازهٔ class جای validation فرمان منفرد را نمی‌گیرد. Server priority را request می‌کند، اما Agent طبق policy محلی priority نهایی را تعیین می‌کند.
