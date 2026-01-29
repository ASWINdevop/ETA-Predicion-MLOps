import json
import os
import requests
import uvicorn
import numpy as np
import redis 
import onnxruntime as ort  # NEW: High Performance Runtime
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

# IMPORT SCHEMAS
from src.schemas import OrderRequest, ETAResponse

# --- Configuration ---
OSRM_HOST = os.getenv("OSRM_HOST", "http://localhost:5000")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Models Dictionary will now store ONNX Sessions, not XGBoost Boosters
models = {}
redis_client = None

# --- Helper Functions ---
def get_restaurant_load(restaurant_id: str) -> int:
    """Queries Redis for the last 4 buckets (20 mins) of order volume."""
    if not redis_client:
        return 0
    try:
        import time
        current_ts = int(time.time())
        bucket_size = 300
        current_bucket = (current_ts // bucket_size) * bucket_size
        keys = []
        for i in range(4):
            t = current_bucket - (i * bucket_size)
            keys.append(f"load:{restaurant_id}:{t}")
        values = redis_client.mget(keys)
        return sum([int(v) for v in values if v is not None])
    except Exception as e:
        print(f"⚠️ Redis Read Error: {e}")
        return 0

def get_osm_physics(start_coords, end_coords):
    url = f"{OSRM_HOST}/route/v1/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout=2.0)    
        if resp.status_code == 200 and resp.json()["code"] == "Ok":
            route = resp.json()["routes"][0]
            return route["distance"], route["duration"]
    except Exception as e:
        print(f"OSRM Connection Error: {e}")
    return 0.0, 0.0

def estimate_traffic_factor(hour_of_day: float) -> float:
    morning_peak = 0.4 * np.exp(-0.5 * ((hour_of_day - 9) / 2) ** 2)
    evening_peak = 0.5 * np.exp(-0.5 * ((hour_of_day - 18) / 2) ** 2)
    return 1.0 + morning_peak + evening_peak

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting ONNX ETA Engine...")
    
    # 1. Connect to Redis
    global redis_client
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.ping()
        print(f"✅ Connected to Redis at {REDIS_HOST}")
    except Exception as e:
        print(f"❌ Redis Connection Failed: {e}")

    # 2. Load ONNX Models
    # We look for onnx_manifest.json now
    if not os.path.exists("onnx_manifest.json"):
        print("❌ CRITICAL: onnx_manifest.json not found! Run convert_to_onnx.py first.")
    else:
        with open("onnx_manifest.json", "r") as f:
            manifest = json.load(f)

        key_map = {
            "ETA_Cooking_Prediction": "cooking",
            "ETA_Allocation_Prediction": "allocation",
            "ETA_LastMile_Prediction": "delivery"
        }

        for exp_name, app_key in key_map.items():
            if exp_name in manifest:
                path = manifest[exp_name].replace("\\", "/")
                if os.path.exists(path):
                    try:
                        # Load into ONNX Runtime
                        session = ort.InferenceSession(path)
                        models[app_key] = session
                        print(f"✅ {app_key} ONNX MODEL LOADED.")
                    except Exception as e:
                        print(f"❌ Error loading {app_key}: {e}")
                else:
                    print(f"⚠️ Missing file: {path}")

    yield
    print("Shutting down...")

app = FastAPI(title="ETA Prediction Engine", lifespan=lifespan)

# --- Prediction Endpoint ---
@app.post("/predict", response_model=ETAResponse)
def predict_eta(req: OrderRequest):
    if not models:
        raise HTTPException(status_code=503, detail="Models are not loaded.")
    
    # 1. Get Live Data
    active_orders = get_restaurant_load(req.restaurant_id)
    
    # 2. Physics & Traffic
    dist, duration = get_osm_physics((req.start_lon, req.start_lat), (req.end_lon, req.end_lat))
    traffic_factor = estimate_traffic_factor(req.hour_of_day)

    # 3. ONNX Inference
    # ONNX expects a Float32 Numpy Array of shape [1, N_features]
    
    # A. Cooking (4 features)
    input_cook = np.array([[
        req.items_count, 
        req.cuisine_complexity, 
        req.hour_of_day, 
        req.day_of_week
    ]], dtype=np.float32)
    
    # Run Inference
    # input_name is usually 'float_input' from our converter script
    input_name = models['cooking'].get_inputs()[0].name
    base_cooking_sec = models['cooking'].run(None, {input_name: input_cook})[0][0]
    
    kitchen_delay = active_orders * 60.0
    final_cooking_sec = base_cooking_sec + kitchen_delay

    # B. Allocation (3 features)
    input_alloc = np.array([[
        req.rider_supply_index, 
        req.hour_of_day, 
        req.day_of_week
    ]], dtype=np.float32)
    
    input_name = models['allocation'].get_inputs()[0].name
    alloc_sec = models['allocation'].run(None, {input_name: input_alloc})[0][0]

    # C. Delivery (4 features)
    input_deliv = np.array([[
        dist, 
        duration, 
        traffic_factor, 
        req.hour_of_day
    ]], dtype=np.float32)
    
    input_name = models['delivery'].get_inputs()[0].name
    travel_sec = models['delivery'].run(None, {input_name: input_deliv})[0][0]

    # 4. Total
    total = final_cooking_sec + alloc_sec + travel_sec

    return ETAResponse(
        breakdown={
            "cooking_seconds": int(base_cooking_sec),
            "kitchen_delay_seconds": int(kitchen_delay),
            "allocation_seconds": int(alloc_sec),
            "delivery_seconds": int(travel_sec)
        },
        total_eta_seconds=int(total),
        total_eta_minutes=round(total / 60.0, 1),
        physics_data={
            "distance_meters": dist,
            "base_duration": duration
        },
        live_context={
            "restaurant_id": req.restaurant_id,
            "active_orders_last_20m": active_orders,
            "data_source": "Redis Real-Time Store"
        }
    )

if __name__ == "__main__":  
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)