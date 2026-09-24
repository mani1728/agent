# ویکی مهندسی MT5 Agent

> وضعیت: منبع نسخه‌دار برای انتقال به GitLab Wiki. این صفحات قابلیتِ پیاده‌سازی‌شده را با «پیاده‌سازی‌شده» و طرح‌ها را با «برنامه‌ریزی‌شده/مسدود» جدا می‌کنند.

## معرفی و هدف محصول

MT5 Agent نمایندهٔ فنی Server/Control Plane روی ویندوز است: فرمان مجاز را اجرا می‌کند، دادهٔ MT5 را بازیابی می‌کند، نتیجهٔ دقیق را برمی‌گرداند و در آینده در برابر قطع ارتباط بازیابی می‌شود. **Agent نه AI دارد، نه استراتژی معامله، نه تصمیم BUY/SELL/HOLD، و نه مدیریت ریسک یا سرمایه.** این مسئولیت‌ها منحصراً متعلق به Server هستند.

```text
Server: AI, strategy, risk, capital, scheduling, authorization
                │ command / acknowledgement
                ▼
MT5 Agent: validate, execute, retrieve, persist, report, recover
                ▼
        one MetaTrader 5 terminal
```

## نقشهٔ ویکی

- [معماری و قابلیت‌ها](Architecture.md)
- [قابلیت اطمینان و انتقال داده](Reliability.md)
- [امنیت و عملیات](Operations.md)
- [نقشه‌راه و فرایند انتشار](Roadmap.md)
- [واژه‌نامه و عیب‌یابی](Reference.md)

## وضعیت فعلی v0.1.3

**پیاده‌سازی‌شده:** lifecycle محلی MT5، HTTP/JSON `POST /command`، ترتیب Validation → Authentication → Authorization → Dispatch، diagnostics و logging محدود، capability discovery و CI چندمرحله‌ای. **پیاده‌سازی‌نشده:** Kafka، Gateway/mTLS، SQLite spooler، اجرای معامله، اولویت‌بندی، Windows Service و دستورهای راه‌دور production. مرجع دقیق: [README](../../README.md)، [معماری هدف](../TARGET_ARCHITECTURE.md) و [نقشه‌راه](../ROADMAP.md).
