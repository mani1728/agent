# نقشه‌راه، CI/CD و Testing

## Roadmap gateها

1. **v0.1.3 completion:** مستندات، evidence CI و protocol آزمایش Session 0.
2. **Architecture approved:** threat model، identity و schemaها.
3. **Runtime proven:** یک terminal و topology پشتیبانی‌شده در محیط demo.
4. **Durable/read/transfer:** SQLite state، read capability و bounded chunking.
5. **Transport/observability:** Kafka، HTTPS/mTLS و support controls.
6. **Execution/hardening:** execution sandbox، service/quiesce/recovery و v1.0.0 gate.

تاریخ تقویمی داده نمی‌شود؛ عبور از هر gate به acceptance evidence وابسته است. جزئیات dependency و issueهای پیشنهادی در [ROADMAP](../ROADMAP.md) و [GITLAB_PLAN](../GITLAB_PLAN.md) است.

## CI/CD فعلی

GitLab source of truth و GitHub mirror/archive است. pipeline: `validate → test → build → smoke → package`. runnerهای Windows شامل general، no-MT5 و reference-MT5 هستند. smoke terminal-available و runtime probe فقط inspection هستند و terminal را start/stop نمی‌کنند. Pipeline #16 به‌صورت گزارش‌شده 9/9 passed است؛ این به‌تنهایی proof اجرای Real-MT5 در Session 0 نیست.

## Testing strategy و release

لایه‌ها: unit، contract/schema، property/edge، persistence، transport، security، integration، controlled Real-MT5، Windows hosting، crash/restart، large transfer، idempotency، priority/failure injection و release acceptance. تست معامله فقط با approval صریح و محیط demo/safe؛ هرگز معاملهٔ مالی واقعی نه. مسیر release: GitLab `develop → staging → main` پس از review است؛ GitHub مستقیم تغییر نمی‌کند.
