import mlflow.xgboost
import pandas as pd
import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager  
import numpy as np

from src.schemas import OrderRequest, ETAResponse


OSRM_HOST = "http://localhost:5000"

models = {}

def get_latest_model_uri(experiment_name):
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if not experiment:
        raise ValueError(f"Experiment '{experiment_name}' does not exist.")
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by = ["start_time DESC"],
        max_results=1
    )
    if runs.empty:
        raise ValueError(f"No runs found in experiment '{experiment_name}'")
    return f"runs:/{runs.iloc[0]['run_id']}/model"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading models from MLflow...")
    try:
        models['cooking'] = mlflow.xgboost.load_model(get_latest_model_uri("ETA_Cooking_Prediction"))
        models['allocation'] = mlflow.xgboost.load_model(get_latest_model_uri("ETA_Allocation_Prediction"))
        models['delivery'] = mlflow.xgboost.load_model(get_latest_model_uri("ETA_LastMile_Prediction"))
        print("Models loaded successfully.")
    except Exception as e:
        print(f"❌Error loading models: {e}")
        
    yield
    print("Shutting down application...")

app = FastAPI(title = "ETA Prediction Engine", lifespan=lifespan)

def get_osm_physics(start_coords, end_coords):
    url = f"{OSRM_HOST}/route/v1/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout = 1.0)    
        if resp.status_code == 200 and resp.json()["code"] == "Ok":
            route = resp.json()["routes"][0]
            return route["distance"], route["duration"]
    except:
        return 0,0
    return 0,0

# --- Helper: Traffic Logic ---
def estimate_traffic_factor(hour_of_day: float) -> float:
    """
    Estimates traffic based on the time of day using the same 
    Gaussian logic as our training data.
    """
   
    morning_peak = 0.4 * np.exp(-0.5 * ((hour_of_day - 9) / 2) ** 2)
   
    evening_peak = 0.5 * np.exp(-0.5 * ((hour_of_day - 18) / 2) ** 2)
    
    return 1.0 + morning_peak + evening_peak

@app.post("/predict", response_model = ETAResponse)
def predict_eta(req: OrderRequest):
    if "cooking" not in models:
        raise HTTPException(status_code=503, detail="Models are not loaded .")
    
    dist, duration = get_osm_physics(
        (req.start_lon, req.start_lat),
        (req.end_lon, req.end_lat)
    )

    df_cook = pd.DataFrame([{
        'items_count': req.items_count,
        'cuisine_complexity': req.cuisine_complexity,
        'hour_of_day': req.hour_of_day,
        'day_of_week': req.day_of_week
    }])

    cook_pred = models['cooking'].predict(df_cook)[0]

    df_alloc = pd.DataFrame([{
        "rider_supply_index": req.rider_supply_index,
        "hour_of_day": req.hour_of_day,
        "day_of_week": req.day_of_week
    }])
    alloc_pred = models['allocation'].predict(df_alloc)[0]

    estimated_traffic = estimate_traffic_factor(req.hour_of_day)

    df_deliv = pd.DataFrame([{
        "osrm_distance": dist,
        "osrm_duration": duration,
        "traffic_factor": estimated_traffic,
        "hour_of_day": req.hour_of_day,

    }])

    deliv_pred = models['delivery'].predict(df_deliv)[0]

    total_seconds = cook_pred + alloc_pred + deliv_pred

    return{
        "breakdown":{
            "cooking_seconds": int(cook_pred),
            "allocation_seconds": int(alloc_pred),
            "delivery_seconds": int(deliv_pred)
        },
        "total_eta_seconds": int(total_seconds),
        "total_eta_minutes": round(total_seconds / 60.0, 1),
        "physics_data":{
            "distance_meters": dist,
            "base_duration": duration
        }
    }

if __name__ == "__main__":  
    uvicorn.run("src.app:app", host = "0.0.0.0", port=8000, reload=True)

