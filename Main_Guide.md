راهنمای جامع اسکریپت main.py

این فایل راهنمای استفاده، ساختار، و سفارشی‌سازی اسکریپت main.py است.
کدی که در این فایل پیاده‌سازی شده، وظیفه‌ی دریافت پیام‌ها از Kafka و پردازش آن‌ها با استفاده از کلاس مدیریتی Mt5_Manager را بر عهده دارد.

۱. معماری کلی

KafkaListener

به Kafka متصل می‌شود (Consumer).

به تاپیک مشخص گوش می‌دهد.

پیام‌ها را دریافت و بر اساس key پردازش می‌کند.

متد مربوطه از کلاس مقصد (مثل Mt5_Manager) را صدا می‌زند.

CLASS_MAP

یک دیکشنری که کلید (key) پیام Kafka را به کلاس واقعی مپ می‌کند.

به طور پیش‌فرض:

CLASS_MAP = {
    "Mt5_Manager": Mt5_Manager
}


سیستم لاگ‌گذاری

از طریق تابع setup_logging پیکربندی می‌شود.

پشتیبانی از خروجی Human یا JSON.

لاگ‌ها در کنسول و فایل (با Rotation) ذخیره می‌شوند.

۲. پیکربندی (Configuration)

تنظیمات از متغیرهای محیطی (ENV) خوانده می‌شود:

متغیر	توضیح	مقدار پیش‌فرض
KAFKA_SERVERS	آدرس سرور Kafka	"192.168.1.254:9092"
KAFKA_TOPIC	نام تاپیک	"agent-send"
KAFKA_GROUP_ID	شناسه گروه Consumer	"kafka_listener_group"
LOG_LEVEL	سطح لاگ (DEBUG, INFO, …)	"INFO"
LOG_JSON	فعال‌سازی خروجی JSON	"false"
LOG_FILE	مسیر فایل لاگ	"logs/app.log"
LOG_MAX_BYTES	حداکثر حجم هر فایل لاگ	10485760 (10MB)
LOG_BACKUPS	تعداد فایل‌های پشتیبان	10

مثال اجرا:

LOG_LEVEL=DEBUG \
LOG_JSON=true \
LOG_FILE=logs/app.log \
python main.py

۳. ساختار پیام‌های Kafka

هر پیام Kafka شامل دو بخش است:

key: نام کلاس مقصد (مثلاً "Mt5_Manager")

value: JSON شامل لیستی از دستورات

مثال ساده:
[
  {
    "method": "trade_manager",
    "params": {
      "action": "total"
    }
  }
]

چند دستور پشت سر هم:
[
  {"method": "trade_manager", "params": {"action": "total"}},
  {"method": "manage_symbols", "params": {"action": "info", "symbol": "EURUSD"}}
]

۴. مپ شدن متدها

بر اساس متدی که در method فرستاده می‌شود، توابع زیر از Mt5_Manager فراخوانی می‌شوند:

manage_connection

manage_symbols

manage_market_book

fetch_data

trade_manager

manage_positions_history

تمام این متدها در فایل meta_trader_manager.py پیاده‌سازی شده‌اند.

۵. پردازش پیام‌ها
مراحل

Kafka پیام را دریافت می‌کند.

مقدار key به نام کلاس نگاشت می‌شود.

مقدار value به JSON/لیست دیکشنری تبدیل می‌شود.

قبل از فراخوانی متد:

تاریخ‌ها (date_from, date_to) → datetime (UTC)

پارامترها مثل timeframe, flags, order_type → کانستنت‌های MT5

فیلد request → به مقادیر معتبر MT5 تبدیل می‌شود.

متد با **params صدا زده می‌شود.

نتیجه به صورت JSON-safe در لاگ ثبت می‌شود.

۶. مدیریت خطاها

اگر JSON نامعتبر باشد → پیام لاگ خطا.

اگر کلاس یا متد وجود نداشته باشد → پیام خطا در لاگ.

اگر پارامترها اشتباه باشند → خطای TypeError مدیریت می‌شود.

اگر اجرای متد خطا بدهد → LOGGER.exception جزئیات را ثبت می‌کند.

۷. سیگنال‌ها و خاموشی ایمن

برنامه به سیگنال‌های SIGINT و SIGTERM گوش می‌دهد.

هنگام دریافت (مثل Ctrl+C) → حلقه‌ی اصلی متوقف می‌شود.

Consumer به‌طور ایمن بسته می‌شود.

۸. تست و دیباگ

برای تست می‌توانی از اسکریپت sender.py استفاده کنی که یک Producer Kafka است:

from confluent_kafka import Producer
import json

conf = {"bootstrap.servers": "192.168.1.254:9092"}
producer = Producer(**conf)

msg = [
    {
        "method": "trade_manager",
        "params": {
            "action": "send",
            "symbol": "EURUSD",
            "request": {
                "action": "TRADE_ACTION_DEAL",
                "type": "ORDER_TYPE_BUY",
                "volume": 0.1
            }
        }
    }
]

producer.produce("agent-send", key="Mt5_Manager", value=json.dumps(msg))
producer.flush()

۹. نکات حرفه‌ای

JSON Logging را در محیط Production فعال کن → راحت‌تر به ELK/Graylog وصل می‌شود.

برای جلوگیری از خطای تکراری MT5:

یکبار در ابتدای برنامه initialize انجام می‌شود.

شیء Mt5_Manager به‌صورت Singleton نگهداری می‌شود.

اگر نیاز به افزودن کلاس جدید داری:

کلاس را در فایل خودش تعریف کن.

آن را در CLASS_MAP اضافه کن.

توصیه: لاگ‌ها را با ابزارهایی مثل Grafana Loki مانیتور کن.