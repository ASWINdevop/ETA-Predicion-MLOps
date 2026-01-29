import requests
import random
import time
import os
import math
import uuid
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

OSRM_HOST = "http://localhost:5000"
TRIVANDRUM_BBOX =(76.8500, 8.4000, 77.0000, 8.6000)
OUTPUT_FILE = "data/order_events.parquet"
ZONES = ["Zone_A", "Zone_B", "Zone_C"]

@dataclass
class DeliveryLifecycle:
    """
    The Single Source of Truth.
    Contains all sigbals for 3 models.
    """
    order_id: str
    # for model 1: cooking time prediction
    restaurant_id: str
    items_count: int
    cuisine_complexity: float

    # for model 2: allocation time prediction
    rider_supply_index : float
    delivery_zone: str

    # for model 3: delivery time prediction
    osrm_distance: float
    osrm_duration: float
    traffic_factor: float

    hour_of_day: int
    day_of_week: int

    # the ground truth timestamps
    placed_at: datetime
    ready_at: datetime
    assigned_at: datetime
    picked_at: datetime
    delivered_at: datetime

def get_osm_route(start_coords, end_coords):
    url = f"{OSRM_HOST}/route/v1/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout = 0.5)    
        if resp.status_code == 200 and resp.json()["code"] == "Ok":
            route = resp.json()["routes"][0]
            return route["distance"], route["duration"]
    except:
        pass
    return None, None

def generate_random_point(bbox):
    return (random.uniform(bbox[0], bbox[2]), random.uniform(bbox[1], bbox[3]))

def get_traffic_multiplier(dt: datetime) -> float:
    hour = dt.hour + (dt.minute / 60.0)
    morning = 0.4 * math.exp(-0.5 * ((hour - 9) / 2) ** 2)
    evening = 0.5 * math.exp(-0.5 * ((hour - 18) / 2) ** 2)
    return 1.0 + morning + evening + random.uniform(0, 0.1)

def simulate_lifecycle():

    attempts = 0 
    dist, base_dur = None, None
    origin, dest = None, None

    while attempts < 3:
        origin = generate_random_point(TRIVANDRUM_BBOX)
        dest = generate_random_point(TRIVANDRUM_BBOX)
        dist, base_dur = get_osm_route(origin, dest)
        if dist:
            break
        attempts += 1

    if not dist:
        return None
    
    now = datetime.now()
    placed_time = now - timedelta(days = random.randint(0, 7), minutes = random.randint(0, 1400))

    # simulate cooking
    items = random.randint(1, 8)
    complexity = random.choice([1.0, 1.2, 1.5])
    cooking_seconds = (120 + (items * 90 * complexity)) * random.uniform(0.9, 1.2)
    ready_time = placed_time + timedelta(seconds = cooking_seconds)

    # simulate allocation
    rider_supply = random.uniform(0.5, 1.5)
    base_alloc_time = 60
    alloc_seconds = (base_alloc_time / rider_supply) * random.uniform(0.8, 3.0)
    assigned_time = ready_time + timedelta(seconds = alloc_seconds)

    # simulate pickup
    pickup_arrival_seconds = random.uniform(180, 480)
    picked_time = assigned_time + timedelta(seconds = pickup_arrival_seconds)

    # simulate delivery
    traffic = get_traffic_multiplier(picked_time)
    drive_seconds = base_dur * traffic * random.uniform(0.9, 1.1)
    final_seconds = drive_seconds + 120
    delivered_time = picked_time + timedelta(seconds = final_seconds)

    return DeliveryLifecycle(
        order_id = f"ORD_{uuid.uuid4().hex[:12]}",
        restaurant_id = f"REST_{random.randint(1, 50)}",
        items_count = items,
        cuisine_complexity= complexity,
        rider_supply_index=round(rider_supply, 2),
        delivery_zone=random.choice(ZONES),
        osrm_distance=round(dist, 1),
        osrm_duration=round(base_dur, 1),
        traffic_factor=round(traffic, 2),
        hour_of_day=placed_time.hour,
        day_of_week=placed_time.weekday(),
        placed_at=placed_time,
        ready_at=ready_time,
        assigned_at=assigned_time,
        picked_at=picked_time,
        delivered_at=delivered_time
    )

def generate_events(count = 10000):
    print(f"Generating {count} delivery lifecycles...")
    data = []
    
    start = time.time()
    for i in range(count):
        event = simulate_lifecycle()
        if event:
            data.append(asdict(event))
            
        if i% 500 == 0:
            print(f"\rGenerated {i}/{count}...", end="")
    
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index = False)

    elapsed = time.time() - start
    print(f"\n Saved {len(data)} events to {OUTPUT_FILE} in {elapsed:.1f} seconds. ")

if __name__ == "__main__":
    generate_events(10000)