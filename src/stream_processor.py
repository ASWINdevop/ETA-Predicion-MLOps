import json
import time
import os
import redis
from kafka import KafkaConsumer

# --- Configuration ---
# Localhost because we are running this script from your machine, not inside Docker
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
TOPIC_NAME = "order_events"

# Window settings (from your architecture PDF)
BUCKET_SIZE_SECONDS = 300  # 5 Minutes
RETENTION_SECONDS = 3600   # Keep data for 1 hour, then expire

def get_redis_client():
    """Connects to Redis with retries"""
    r = None
    for i in range(5):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping() # Check connection
            print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return r
        except Exception as e:
            print(f"⚠️ Redis connection failed (attempt {i+1}/5): {e}")
            time.sleep(2)
    return None

def get_kafka_consumer():
    """Connects to Kafka Consumer Group"""
    consumer = None
    for i in range(5):
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BROKER,
                auto_offset_reset='latest', # Start reading from now
                enable_auto_commit=True,
                group_id='eta-feature-engine', # Worker Group ID
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print(f"✅ Connected to Kafka Topic: {TOPIC_NAME}")
            return consumer
        except Exception as e:
            print(f"⚠️ Kafka connection failed (attempt {i+1}/5): {e}")
            time.sleep(2)
    return None

def calculate_bucket_key(restaurant_id, timestamp):
    """
    Rounds timestamp down to the nearest 5-minute bucket.
    Example: 10:02:15 -> 10:00:00
    """
    bucket_start = int(timestamp // BUCKET_SIZE_SECONDS) * BUCKET_SIZE_SECONDS
    return f"load:{restaurant_id}:{bucket_start}"

def process_stream():
    # 1. Connect to Infrastructure
    r = get_redis_client()
    consumer = get_kafka_consumer()
    
    if not r or not consumer:
        print("❌ CRITICAL: Infrastructure not ready.")
        exit(1)

    print("🚀 Stream Processor Running... Waiting for events.")
    
    # 2. Main Loop
    for message in consumer:
        event = message.value
        
        # Extract core data
        r_id = event.get("restaurant_id")
        ts = event.get("timestamp")
        
        if r_id and ts:
            # 3. Sliding Window Logic
            # Identify the 5-minute bucket this order belongs to
            redis_key = calculate_bucket_key(r_id, ts)
            
            # 4. Atomic Update in Redis
            # INCR: Adds 1 to the counter (Thread-safe)
            # EXPIRE: Ensures the key deletes itself after 1 hour (Memory Management)
            pipe = r.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, RETENTION_SECONDS)
            result = pipe.execute()
            
            current_count = result[0]
            print(f"📥 Processed Order for {r_id} | Bucket: {redis_key.split(':')[-1]} | Count: {current_count}")

if __name__ == "__main__":
    try:
        process_stream()
    except KeyboardInterrupt:
        print("\n🛑 Processor stopped.")