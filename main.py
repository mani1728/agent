# ساده‌ترین کد برای گوش دادن به Kafka topic با confluent_kafka
from confluent_kafka import Consumer, KafkaException

# تنظیمات استاتیک
KAFKA_SERVERS = "192.168.1.254:9092"  # آدرس سرور Kafka
TOPIC = "agent-send"  # تاپیکی که گوش می‌دهیم

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
                value = msg.value().decode('utf-8')  # تبدیل پیام به string
                print(f"Received message: {value}")  # چاپ پیام
        except KeyboardInterrupt:
            print("Stopping listener...")  # توقف با Ctrl+C
            self.running = False
        finally:
            if self.consumer:
                self.consumer.close()  # بستن Consumer
                print("Kafka consumer closed.")

# اجرای برنامه
if __name__ == "__main__":
    listener = KafkaListener()  # ایجاد نمونه از KafkaListener
    listener.listen()  # شروع گوش دادن