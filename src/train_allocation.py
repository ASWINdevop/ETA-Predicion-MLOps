import pandas as pd
import xgboost as xgb
import mlflow
import mlflow.xgboost
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def train():
    mlflow.set_experiment("ETA_Allocation_Prediction")
    
    print("Loading Allocation Data...")
    df = pd.read_parquet("data/processed/allocation_train.parquet")
    
    # Feature Selection
    # Note: We treat delivery_zone as a category if we encode it, 
    # but for simplicity in this MVP, we use supply_index which captures the zone's status.
    X = df[['rider_supply_index', 'hour_of_day', 'day_of_week']]
    y = df['target_alloc_seconds']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    with mlflow.start_run(run_name="allocation_v1"):
        print("Training Allocation Model...")
        # Allocation is simpler, so we use a smaller model (depth=4)
        model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1)
        model.fit(X_train, y_train)
      
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        print(f"Allocation MAE: {mae:.2f} seconds")
        

        mlflow.log_metric("mae", mae)
        mlflow.xgboost.log_model(model, artifact_path="model")
        print("Model saved to MLflow.")

if __name__ == "__main__":
    train()