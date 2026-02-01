from locust import HttpUser, task, between
import random

class ETALoadTest(HttpUser):
    # Simulate users waiting 1-3 seconds between requests (realistic)
    wait_time = between(1, 3)

    @task
    def predict_eta(self):
        # Generate random data to stop caching
        payload = {
            "restaurant_id": "r_123", # Uses the cached restaurant data
            "start_lat": 8.5241 + random.uniform(-0.01, 0.01),
            "start_lon": 76.9366 + random.uniform(-0.01, 0.01),
            "end_lat": 8.5241 + random.uniform(-0.01, 0.01),
            "end_lon": 76.9366 + random.uniform(-0.01, 0.01),
            "items_count": random.randint(1, 10),
            "cuisine_complexity": random.choice([1.0, 1.2, 1.5]),
            "rider_supply_index": random.uniform(0.5, 1.5),
            "hour_of_day": random.randint(10, 22),
            "day_of_week": 6
        }
        
        # Send POST request
        self.client.post("/predict", json=payload)