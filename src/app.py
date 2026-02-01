import json
import os
import time
import requests
import uvicorn
import numpy as np
import redis 
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge


from src.schemas import OrderRequest, ETAResponse

print("🚀 -------------------------------------------------")
print("🚀 STARTING NEW VERSION (With Clean Paths)")
print("🚀 -------------------------------------------------")
# --- Configuration ---
OSRM_HOST = os.getenv("OSRM_HOST", "http://localhost:5000")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Models Dictionary
models = {}
redis_client = None

# --- New Schema for Simulation ---
class TrafficSimulation(BaseModel):
    restaurant_id: str
    orders_added: int

# --- Helper Functions ---
def get_restaurant_load(restaurant_id: str) -> int:
    """Queries Redis for the last 4 buckets (20 mins) + Simulated Load."""
    if not redis_client:
        return 0
    try:
        current_ts = int(time.time())
        bucket_size = 300
        current_bucket = (current_ts // bucket_size) * bucket_size
        
        # 1. Get Real Traffic (Time Buckets)
        keys = []
        for i in range(4):
            t = current_bucket - (i * bucket_size)
            keys.append(f"load:{restaurant_id}:{t}")
        
        # 2. Get Simulated Traffic (The key we inject during testing)
        sim_key = f"simulation:{restaurant_id}"
        keys.append(sim_key)

        values = redis_client.mget(keys)
        
        # Sum up all valid numbers
        total_load = sum([int(v) for v in values if v is not None])
        return total_load

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
    return 5000.0, 900.0 # Fallback default

def estimate_traffic_factor(hour_of_day: float) -> float:
    morning_peak = 0.4 * np.exp(-0.5 * ((hour_of_day - 9) / 2) ** 2)
    evening_peak = 0.5 * np.exp(-0.5 * ((hour_of_day - 18) / 2) ** 2)
    return 1.0 + morning_peak + evening_peak

# --- DEBUG ENDPOINT (Add this to see inside the container) ---


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting ONNX ETA Engine (HARDCODED PATHS)...")
    
    # 1. Connect to Redis
    global redis_client
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.ping()
        print(f"✅ Connected to Redis at {REDIS_HOST}")
    except Exception as e:
        print(f"❌ Redis Connection Failed: {e}")

    # 2. Load ONNX Models (Direct Load - No Manifest)
    # This forces the app to look in the current folder.
    model_files = {
        "cooking": "cooking.onnx",
        "allocation": "allocation.onnx",
        "delivery": "delivery.onnx"
    }

    for name, filename in model_files.items():
        print(f"🔹 Attempting to load {name} from ./{filename}...")
        try:
            if os.path.exists(filename):
                # Load the model
                session = ort.InferenceSession(filename)
                models[name] = session
                print(f"✅ {name} LOADED SUCCESSFULLY!")
            else:
                print(f"❌ CRITICAL: File not found: {filename}")
                # List files to see what IS there
                print(f"   (Files in folder: {os.listdir('.')})")
        except Exception as e:
            print(f"❌ Error loading {name}: {e}")

    yield
    print("Shutting down...")

app = FastAPI(title="ETA Prediction Engine", lifespan=lifespan)


Instrumentator().instrument(app).expose(app)

TRAFFIC_GAUGE = Gauge('eta_traffic_factor', 'Current Traffic Factor detected by the system')

@app.get("/debug_files")
def debug_files():
    """Lists all files in the current directory."""
    files = os.listdir('.')
    manifest_exists = os.path.exists("onnx_manifest.json")
    
    # Check if models are loaded
    loaded_models = list(models.keys())
    
    return {
        "current_directory": os.getcwd(),
        "files_present": files,
        "manifest_found": manifest_exists,
        "models_loaded": loaded_models
    }
# --- NEW ENDPOINT: Simulate Traffic ---
@app.post("/simulate_traffic")
def simulate_traffic(payload: TrafficSimulation):
    """Injects fake load into Redis for testing."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    # We write to a special 'simulation' key that get_restaurant_load reads
    key = f"simulation:{payload.restaurant_id}"
    redis_client.set(key, payload.orders_added, ex=1200) # Expires in 20 mins
    
    return {"message": f"Injected {payload.orders_added} fake orders for {payload.restaurant_id}"}

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

    TRAFFIC_GAUGE.set(traffic_factor)
    # 3. ONNX Inference (WITH .item() FIXES)
    
    # A. Cooking
    input_cook = np.array([[req.items_count, req.cuisine_complexity, req.hour_of_day, req.day_of_week]], dtype=np.float32)
    input_name = models['cooking'].get_inputs()[0].name
    # 👇 FIX HERE: Add .item()
    base_cooking_sec = models['cooking'].run(None, {input_name: input_cook})[0][0].item()
    
    kitchen_delay = active_orders * 120.0 
    final_cooking_sec = base_cooking_sec + kitchen_delay

    # B. Allocation
    input_alloc = np.array([[req.rider_supply_index, req.hour_of_day, req.day_of_week]], dtype=np.float32)
    input_name = models['allocation'].get_inputs()[0].name
    # 👇 FIX HERE: Add .item()
    alloc_sec = models['allocation'].run(None, {input_name: input_alloc})[0][0].item()

    # C. Delivery
    input_deliv = np.array([[dist, duration, traffic_factor, req.hour_of_day]], dtype=np.float32)
    input_name = models['delivery'].get_inputs()[0].name
    # 👇 FIX HERE: Add .item()
    travel_sec = models['delivery'].run(None, {input_name: input_deliv})[0][0].item()

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