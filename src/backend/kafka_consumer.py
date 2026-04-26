import json
import os
import signal
import sys
import time
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
TOPIC = "chat_logs"
LOG_FILE = "/app/logs/chat_logs.jsonl"

# Ensure log directory exists
os.makedirs("/app/logs", exist_ok=True)

print(f"📊 Audit Consumer starting on topic '{TOPIC}'...")


def create_consumer():
    retries = 0

    while retries < 30:
        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=BROKER,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                group_id="audit-log-central",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                api_version=(2, 5, 0),
            )

            print("✅ Connected to Kafka!")
            return consumer

        except NoBrokersAvailable:
            retries += 1
            print(f"⌛ Kafka not ready ({retries}/30). Retrying in 5s...")
            time.sleep(5)

    return None


consumer = create_consumer()

if not consumer:
    print("❌ Could not connect to Kafka")
    sys.exit(1)


def shutdown(signum, frame):
    print("\n🛑 Shutting down consumer...")
    consumer.close()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

print("🚀 Consumer is RUNNING and waiting for messages...")


for msg in consumer:
    payload = msg.value

    print(f"📩 AUDIT: {payload}")

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    except Exception as e:
        print(f"⚠️ File write error: {e}")