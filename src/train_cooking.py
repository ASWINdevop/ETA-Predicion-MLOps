import pandas  as pd
import os
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import mlflow
import mlflow.xgboost

TRAIN_DATA = "data/processed/cooking_train.parquet"
MODEL_NAME = 'cooking_model'
 

def train():
    mlflow.set_experiment("ETA_Cooking_Prediction")
    print(f"Loading training data from {TRAIN_DATA}...")
    df = pd.read_parquet(TRAIN_DATA)

    features = ['items_count', 'cuisine_complexity', 'hour_of_day', 'day_of_week']
    target = 'target_cooking_seconds'

    X = df[features]
    y = df[target]

    Xtrain, Xtest, ytrain, ytest = train_test_split(X, y, test_size=0.2, random_state=42)  
    with mlflow.start_run():
        print("Training XGBoost model...")

        params = {
            "objective": "reg:squarederror",
            "n_estimators": 100,
            "learning_rate": 0.1,
            "max_depth": 6,
            "subsample": 0.8,
        }
        mlflow.log_params(params)
        model = xgb.XGBRegressor(**params)
        model.fit(Xtrain, ytrain)   

        predictions = model.predict(Xtest)
        mae = mean_absolute_error(ytest, predictions)
        print(f"The model is off by an average of {mae:.1f} seconds on average")

        mlflow.log_metric("mae", mae)
        mlflow.xgboost.log_model(model, artifact_path="model")

        print("Model training completed and logged to MLflow.")
if __name__ == "__main__":
    train()