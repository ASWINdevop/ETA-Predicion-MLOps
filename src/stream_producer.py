import json
import time
import random
import os
import uuid
from kafka import KafkaProducer


KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_NAME = "order_events"


RESTAURANT_IDS = ["REST_1", "REST_2", "REST_3", "REST_4", "REST_5"]

def get_producer():
    """Tries to connect to Kafka with retries"""
    producer = None
    for i in range(5):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"✅ Connected to Kafka at {KAFKA_BROKER}")
            return producer
        except Exception as e:
            print(f"⚠️ Connection failed (attempt {i+1}/5): {e}")
            time.sleep(2)
    return None

def generate_event():
    """Creates a synthetic order event with Production IDs"""

    order_id = str(uuid.uuid4())
   
    r_id = random.choice(RESTAURANT_IDS)
    
    return {
        "event_type": "ORDER_CREATED",
        "order_id": order_id,      
        "restaurant_id": r_id,     
        "timestamp": time.time(),
        "items_count": random.randint(1, 5),
        "status": "NEW"
    }

if __name__ == "__main__":
    print(f"🔌 Connecting to Kafka...")
    producer = get_producer()
    
    if not producer:
        print("❌ CRITICAL: Could not connect to Kafka. Is Docker running?")
        exit(1)

    print("🚀 Starting Production Event Stream (Press Ctrl+C to stop)...")
    try:
        while True:
            event = generate_event()
            
         
            producer.send(TOPIC_NAME, event)
            
            print(f"📤 Sent Order: {event['order_id']} | Rest: {event['restaurant_id']}")
            
            producer.flush() 
            time.sleep(1) # 1 order per second
    except KeyboardInterrupt:
        print("\n🛑 Stream stopped.")
        producer.close()