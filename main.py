# ساده‌ترین کد برای گوش دادن به Kafka و فراخوانی متدهای کلاس
from confluent_kafka import Consumer, KafkaException
import json
from meta_trader_manager import Mt5_Manager
import MetaTrader5 as mt5
import datetime

# تنظیمات استاتیک
KAFKA_SERVERS = "192.168.1.254:9092"  # آدرس سرور Kafka
TOPIC = "agent-send"  # تاپیکی که گوش می‌دهیم

# مپ کردن نام کلاس به کلاس واقعی
CLASS_MAP = {
    "Mt5_Manager": Mt5_Manager
}

# کلاس اصلی برای گوش دادن به پیام‌ها
class KafkaListener:
    def __init__(self):
        # تنظیم Consumer با سرور و گروه
        self.consumer = None
        self.running = False
        self.init_consumer()

    def init_consumer(self):
        # ایجاد Consumer با تنظیمات اولیه
        try:
            self.consumer = Consumer({
                'bootstrap.servers': KAFKA_SERVERS,  # اتصال به سرور Kafka
                'group.id': 'kafka_listener_group',  # گروه Consumer
                'auto.offset.reset': 'earliest'  # شروع از اولین پیام‌ها
            })
            self.consumer.subscribe([TOPIC])  # اشتراک در تاپیک agent-send
            print(f"Connected to Kafka servers: {KAFKA_SERVERS}, topic: {TOPIC}")
        except KafkaException as e:
            print(f"Failed to connect to Kafka: {e}")

    def listen(self):
        # حلقه اصلی برای دریافت پیام‌ها
        if not self.consumer:
            print("Consumer not initialized, cannot listen.")
            return
        self.running = True
        print("Starting to listen for messages...")
        try:
            while self.running:
                msg = self.consumer.poll(1.0)  # بررسی پیام جدید هر 1 ثانیه
                if msg is None:
                    continue  # اگر پیامی نبود، ادامه بده
                if msg.error():
                    print(f"Error: {msg.error()}")  # نمایش خطا
                    continue
                # دریافت value و key
                value = msg.value().decode('utf-8') if msg.value() else "No value"
                key = msg.key().decode('utf-8') if msg.key() else "No key"
                # پاکسازی key از نقل‌قول‌های تک یا دوتایی
                cleaned_key = key.strip('"').strip("'")
                # چاپ برای دیباگ
                print(f"Received message: {value}")
                print(f"Raw Key: {key}. Key.type: {type(key)}")
                print(f"Cleaned Key: {cleaned_key}. Cleaned Key.type: {type(cleaned_key)}")
                # پردازش پیام
                self.process_message(cleaned_key, value)
        except KeyboardInterrupt:
            print("Stopping listener...")  # توقف با Ctrl+C
            self.running = False
        except Exception as e:
            print(f"Error processing message: {e}")
        finally:
            if self.consumer:
                self.consumer.close()  # بستن Consumer
                print("Kafka consumer closed.")

    def process_message(self, class_name, value):
        try:
            cleaned_value = value.replace("'", '"')
            print(f"Cleaned value: {cleaned_value}")
            value_list = json.loads(cleaned_value)
            if not isinstance(value_list, list):
                value_list = [value_list]
            if class_name not in CLASS_MAP:
                print(f"Class '{class_name}' not found in CLASS_MAP")
                return
            cls = CLASS_MAP[class_name]
            instance = cls()
            for command in value_list:
                method_name = command.get("method")
                params = command.get("params", {})
                # تبدیل timeframe به مقدار مناسب
                if "timeframe" in params and isinstance(params["timeframe"], str):
                    params["timeframe"] = getattr(mt5, params["timeframe"], mt5.TIMEFRAME_H4)
                # تبدیل date_from به datetime
                if "date_from" in params and isinstance(params["date_from"], str):
                    params["date_from"] = datetime.datetime.fromisoformat(params["date_from"])
                # تبدیل date_to به datetime (تغییر جدید برای رفع خطا)
                if "date_to" in params and isinstance(params["date_to"], str):
                    params["date_to"] = datetime.datetime.fromisoformat(params["date_to"])
                if "flags" in params and isinstance(params["flags"], str):
                    params["flags"] = getattr(mt5, params["flags"], mt5.COPY_TICKS_ALL)
                if not method_name or not hasattr(instance, method_name):
                    print(f"Method '{method_name}' not found in class '{class_name}'")
                    print(f"Available methods: {dir(instance)}")
                    continue
                method = getattr(instance, method_name)
                try:
                    print(f"Calling {class_name}.{method_name} with params: {params}")
                    result = method(**params)
                    print(f"Result of {method_name}: {result}")
                    if method_name == "login":
                        success, terminal_info, version = result
                        print(f"Stored terminal_info: {terminal_info}")
                        print(f"Stored version: {version}")
                except TypeError as e:
                    print(f"Error calling {method_name}: Invalid parameters - {e}")
        except json.JSONDecodeError:
            print(f"Invalid JSON in value: {cleaned_value}")
        except Exception as e:
            print(f"Error processing message: {e}")

# اجرای برنامه
if __name__ == "__main__":
    listener = KafkaListener()  # ایجاد نمونه از KafkaListener
    listener.listen()  # شروع گوش دادن