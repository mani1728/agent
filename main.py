# main.py
# =========================
# نقطهٔ شروع برنامه:
# - بارگذاری تنظیمات و راه‌اندازی لاگ‌گذاری
# - ساخت KafkaListener و شروع شنود
# =========================

from __future__ import annotations                # تایپ‌هینت‌های مدرن
from config_logging import load_settings_from_env, setup_logging  # پیکربندی/لاگ
from kafka_listener import KafkaListener          # شنوندهٔ کافکا

def main() -> None:
    settings = load_settings_from_env()           # خواندن تنظیمات از ENV با پیش‌فرض‌های امن
    setup_logging(settings)                       # راه‌اندازی لاگ‌گذاری مطابق تنظیمات
    listener = KafkaListener(settings)            # ساخت شنونده
    listener.listen()                             # شروع حلقهٔ شنود

if __name__ == "__main__":                        # اجرای مستقیم فایل
    main()                                        # فراخوانی main
