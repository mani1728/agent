# C:\Users\Administrator\Desktop\agent_low\agent\main.py
# این اسکریپت یک شنونده (Consumer) برای کافکا است که به تاپیک مشخصی گوش می‌دهد
# و پیام‌های دریافتی را پردازش کرده و متدهای مربوطه از کلاس‌های مدیریتی را فراخوانی می‌کند.

# --- وارد کردن کتابخانه‌های مورد نیاز ---
from confluent_kafka import Consumer, KafkaException  # برای اتصال و دریافت پیام از کافکا
import json  # برای کار با داده‌های با فرمت JSON
from meta_trader_manager import Mt5_Manager  # وارد کردن کلاس مدیریت متاتریدر که خودمان نوشتیم
import MetaTrader5 as mt5  # کتابخانه رسمی برای اتصال به متاتریدر ۵
import datetime  # برای کار با تاریخ و زمان
import pytz  # برای کار با مناطق زمانی (Timezones)

# --- تنظیمات کلی و استاتیک برنامه ---
KAFKA_SERVERS = "192.168.1.254:9092"  # آدرس سرور یا سرورهای کافکا
TOPIC = "agent-send"  # نام تاپیکی که برنامه به آن گوش می‌دهد

# دیکشنری برای مپ کردن (متصل کردن) نام کلاس‌ها به آبجکت واقعی کلاس.
# این کار به ما اجازه می‌دهد تا بر اساس کلید (key) پیام کافکا، کلاس مورد نظر را به صورت داینامیک پیدا کنیم.
CLASS_MAP = {
    "Mt5_Manager": Mt5_Manager
}


# کلاس اصلی برنامه که وظیفه گوش دادن به کافکا و پردازش پیام‌ها را بر عهده دارد
class KafkaListener:
    # متد سازنده (Constructor) که در زمان ساختن یک نمونه از کلاس، به صورت خودکار فراخوانی می‌شود
    def __init__(self):
        # متغیر برای نگهداری نمونه Consumer کافکا
        self.consumer = None
        # یک فلگ برای کنترل حلقه اصلی شنونده
        self.running = False

        # --- بهینه‌سازی مهم: ساختن یک نمونه دائمی از کلاس‌های مدیریتی ---
        # یک دیکشنری برای نگهداری نمونه‌های ساخته‌شده از کلاس‌ها (مانند Mt5_Manager)
        self.manager_instances = {}
        # به ازای هر کلاس تعریف‌شده در CLASS_MAP، یک نمونه از آن می‌سازیم و در دیکشنری ذخیره می‌کنیم
        for name, cls in CLASS_MAP.items():
            self.manager_instances[name] = cls()
        # این کار باعث می‌شود به جای ساختن یک نمونه جدید برای هر پیام، از همین یک نمونه در طول اجرای برنامه استفاده شود.

        # فراخوانی متد برای آماده‌سازی و اتصال Consumer کافکا
        self.init_consumer()

    # متدی برای مقداردهی اولیه و اتصال به کافکا
    def init_consumer(self):
        # ایجاد Consumer با استفاده از تنظیمات اولیه
        try:
            # ساخت یک نمونه از Consumer با کانفیگ‌های لازم
            self.consumer = Consumer({
                'bootstrap.servers': KAFKA_SERVERS,  # آدرس سرور کافکا برای اتصال
                'group.id': 'kafka_listener_group',  # یک شناسه گروه برای این Consumer
                'auto.offset.reset': 'earliest'
                # مشخص می‌کند که اگر Consumer جدید بود، از اولین پیام موجود در تاپیک شروع به خواندن کند
            })
            # اشتراک (subscribe) در تاپیک مورد نظر برای دریافت پیام‌های آن
            self.consumer.subscribe([TOPIC])
            print(f"Connected to Kafka servers: {KAFKA_SERVERS}, topic: {TOPIC}")
        except KafkaException as e:
            # در صورت بروز خطا در اتصال به کافکا، آن را چاپ کن
            print(f"Failed to connect to Kafka: {e}")

    # متد اصلی که حلقه بی‌نهایت برای گوش دادن به پیام‌ها را اجرا می‌کند
    def listen(self):
        # اگر Consumer به درستی ساخته نشده بود، از متد خارج شو
        if not self.consumer:
            print("Consumer not initialized, cannot listen.")
            return
        # فلگ را برای شروع حلقه اصلی، true قرار بده
        self.running = True
        print("Starting to listen for messages...")
        try:
            # تا زمانی که فلگ running برابر true است، این حلقه ادامه پیدا می‌کند
            while self.running:
                # منتظر دریافت پیام جدید به مدت 1 ثانیه بمان
                msg = self.consumer.poll(1.0)
                # اگر در این 1 ثانیه پیامی دریافت نشد، به ابتدای حلقه برگرد
                if msg is None:
                    continue
                # اگر پیامی دریافت شد ولی حاوی خطا بود، خطا را چاپ کن و به ابتدای حلقه برگرد
                if msg.error():
                    print(f"Error: {msg.error()}")
                    continue

                # مقدار (value) و کلید (key) پیام را از آن استخراج کن
                value = msg.value().decode('utf-8') if msg.value() else "No value"
                key = msg.key().decode('utf-8') if msg.key() else "No key"

                # گاهی key پیام کافکا با " یا ' احاطه شده است، آنها را حذف می‌کنیم تا نام کلاس خالص به دست آید
                cleaned_key = key.strip('"').strip("'")

                # چاپ اطلاعات پیام دریافت شده برای دیباگ
                print(f"Received message: {value}")
                print(f"Raw Key: {key}. Key.type: {type(key)}")
                print(f"Cleaned Key: {cleaned_key}. Cleaned Key.type: {type(cleaned_key)}")

                # پیام دریافت شده را برای پردازش به متد process_message ارسال کن
                self.process_message(cleaned_key, value)

        except KeyboardInterrupt:
            # اگر کاربر با فشردن Ctrl+C برنامه را متوقف کرد، این بخش اجرا می‌شود
            print("Stopping listener...")
            self.running = False  # با false کردن فلگ، حلقه اصلی متوقف می‌شود
        except Exception as e:
            # در صورت بروز هر خطای پیش‌بینی‌نشده دیگر، آن را چاپ کن
            print(f"Error processing message: {e}")
        finally:
            # این بلوک کد در هر صورت (چه با خطا و چه بدون خطا) در انتهای کار اجرا می‌شود
            if self.consumer:
                self.consumer.close()  # بستن اتصال کافکا
                print("Kafka consumer closed.")

    # متدی برای پردازش پیام دریافت شده
    def process_message(self, class_name, value):
        try:
            # جایگزینی سینگل کوتیشن با دابل کوتیشن برای سازگاری با فرمت استاندارد JSON
            cleaned_value = value.replace("'", '"')
            print(f"Cleaned value: {cleaned_value}")

            # رشته JSON را به یک آبجکت پایتون (لیست یا دیکشنری) تبدیل می‌کنیم
            value_list = json.loads(cleaned_value)

            # برای سادگی، همیشه با پیام به عنوان یک لیست رفتار می‌کنیم
            if not isinstance(value_list, list):
                value_list = [value_list]

            # بررسی وجود کلاس در CLASS_MAP
            if class_name not in self.manager_instances:
                print(f"Class instance for '{class_name}' not found.")
                return

            # استفاده از نمونه از پیش ساخته شده کلاس برای جلوگیری از ساختن مکرر
            instance = self.manager_instances[class_name]

            # حلقه بر روی تمام دستورات موجود در پیام
            for command in value_list:
                method_name = command.get("method")
                params = command.get("params", {})

                # --- بخش تبدیل داده‌ها (Data Type Conversion) ---

                # تبدیل رشته تایم‌فریم به ثابت متاتریدر
                if "timeframe" in params and isinstance(params["timeframe"], str):
                    params["timeframe"] = getattr(mt5, params["timeframe"], mt5.TIMEFRAME_H4)

                # تعریف منطقه زمانی استاندارد UTC
                timezone = pytz.timezone("Etc/UTC")

                # تبدیل رشته تاریخ به آبجکت datetime آگاه از منطقه زمانی (Timezone-Aware)
                if "date_from" in params and isinstance(params["date_from"], str):
                    naive_dt = datetime.datetime.fromisoformat(params["date_from"])
                    params["date_from"] = timezone.localize(naive_dt)

                if "date_to" in params and isinstance(params["date_to"], str):
                    naive_dt = datetime.datetime.fromisoformat(params["date_to"])
                    params["date_to"] = timezone.localize(naive_dt)

                # تبدیل رشته فلگ به ثابت متاتریدر
                if "flags" in params and isinstance(params["flags"], str):
                    params["flags"] = getattr(mt5, params["flags"], mt5.COPY_TICKS_ALL)

                # تبدیل رشته action به حروف کوچک
                if "action" in params and isinstance(params["action"], str):
                    params["action"] = params["action"].lower()

                # تبدیل رشته نوع سفارش به ثابت متاتریدر
                if "order_type" in params and isinstance(params["order_type"], str):
                    params["order_type"] = getattr(mt5, params["order_type"], mt5.ORDER_TYPE_BUY)

                # تبدیل فیلدهای رشته‌ای داخل دیکشنری request به ثابت‌های متاتریدر
                if "request" in params and isinstance(params["request"], dict):
                    request = params["request"]
                    if "action" in request and isinstance(request["action"], str):
                        request["action"] = getattr(mt5, request["action"], mt5.TRADE_ACTION_DEAL)
                    if "type" in request and isinstance(request["type"], str):
                        request["type"] = getattr(mt5, request["type"], mt5.ORDER_TYPE_BUY)
                    if "type_time" in request and isinstance(request["type_time"], str):
                        request["type_time"] = getattr(mt5, request["type_time"], mt5.ORDER_TIME_GTC)
                    if "type_filling" in request and isinstance(request["type_filling"], str):
                        request["type_filling"] = getattr(mt5, request["type_filling"], mt5.ORDER_FILLING_IOC)

                # بررسی وجود متد در کلاس
                if not method_name or not hasattr(instance, method_name):
                    print(f"Method '{method_name}' not found in class '{class_name}'")
                    continue

                # دریافت آبجکت متد
                method = getattr(instance, method_name)

                try:
                    # فراخوانی داینامیک متد با پارامترهای استخراج شده
                    print(f"Calling {class_name}.{method_name} with params: {params}")
                    result = method(**params)
                    print(f"Result of {method_name}: {result}")

                except TypeError as e:
                    # مدیریت خطای عدم تطابق پارامترها
                    print(f"Error calling {method_name}: Invalid parameters - {e}")

        except json.JSONDecodeError:
            # مدیریت خطای نامعتبر بودن JSON
            print(f"Invalid JSON in value: {cleaned_value}")
        except Exception as e:
            # مدیریت سایر خطاهای پیش‌بینی‌نشده
            print(f"Error processing message: {e}")


# --- نقطه شروع اجرای برنامه ---
if __name__ == "__main__":
    # ساخت یک نمونه از شنونده کافکا
    listener = KafkaListener()
    # شروع به گوش دادن
    listener.listen()
