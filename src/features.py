import pandas as pd
import os 

INPUT_FILE = "data/order_events.parquet"
OUTPUT_DIR = "data/processed"

def create_features():
    print(f"Loading data from {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # PREPARE COOKING DATASET
    print("Preparing cooking dataset...")
    df_cook = df[['order_id', 'restaurant_id', 'items_count','cuisine_complexity', 'hour_of_day', 'day_of_week']].copy()
    df_cook['target_cooking_seconds'] = (df['ready_at']- df['placed_at']).dt.total_seconds()
    df_cook.to_parquet(f"{OUTPUT_DIR}/cooking_train.parquet", index = False)

    # PREPARE ALLOCATION DATASET
    print("Preparing allocation dataset...")
    df_alloc = df[['order_id', 'delivery_zone', 'rider_supply_index', 'hour_of_day', 'day_of_week']].copy()
    df_alloc['target_alloc_seconds'] = (df['assigned_at'] - df['ready_at']).dt.total_seconds()
    df_alloc.to_parquet(f"{OUTPUT_DIR}/allocation_train.parquet", index = False)

    # PREPARE DELIVERY DATASET
    print("Preparing delivery dataset...")
    df_deliv = df[['order_id', 'osrm_distance', 'osrm_duration', 'traffic_factor', 'hour_of_day', 'day_of_week']].copy()
    df_deliv['target_delivery_seconds'] = (df['delivered_at'] - df['picked_at']).dt.total_seconds()
    df_deliv.to_parquet(f"{OUTPUT_DIR}/delivery_train.parquet", index = False)

    print("Feature datasets created successfully.")
    print(f"1. cooking: {len(df_cook)} records saved to {OUTPUT_DIR}/cooking_train.parquet")
    print(f"2. allocation: {len(df_alloc)} records saved to {OUTPUT_DIR}/allocation_train.parquet")
    print(f"3. delivery: {len(df_deliv)} records saved to {OUTPUT_DIR}/delivery_train.parquet")

if __name__ == "__main__":
    create_features()