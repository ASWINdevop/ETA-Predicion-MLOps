import pandas as pd
import xgboost as xgb
import mlflow
import mlflow.xgboost
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def train():
    mlflow.set_experiment("ETA_LastMile_Prediction")
    
    print("Loading Delivery Data...")
    df = pd.read_parquet("data/processed/delivery_train.parquet")

    X = df[['osrm_distance', 'osrm_duration', 'traffic_factor', 'hour_of_day']]
    y = df['target_delivery_seconds']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    with mlflow.start_run(run_name="delivery_v1"):
        print("Training Last Mile Model...")
        model = xgb.XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.1)
        model.fit(X_train, y_train)
        

        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        print(f"Delivery MAE: {mae:.2f} seconds")
 
        mlflow.log_metric("mae", mae)
        mlflow.xgboost.log_model(model, artifact_path="model")
        print("Model saved to MLflow.")

if __name__ == "__main__":
    train()