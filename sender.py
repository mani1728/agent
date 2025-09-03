from confluent_kafka import Producer
import json

# کانفیگ Producer
conf = {
    'bootstrap.servers': '192.168.1.254:9092'
}
producer = Producer(**conf)

# نمونه پیام برای متد trade_manager
message = [
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

# تبدیل به JSON
json_message = json.dumps(message)

# ارسال پیام
producer.produce('agent-send', key='Mt5_Manager', value=json_message)
producer.flush()
print("Message sent!")
