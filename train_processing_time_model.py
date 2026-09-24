"""
Member 2 — Model 1: Processing-Time Prediction.

Trains RandomForestRegressor and XGBRegressor on Member 1's
data/processed/ml_processing_time.csv, evaluates both with MAE / RMSE / R^2
on a chronological hold-out split, keeps the better model, and saves it
(preprocessing pipeline included) to models/processing_time_model.pkl.

Run: python train_processing_time_model.py
"""
import json
import joblib
import numpy as np
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from ml_features import TIME_CATEGORICAL, TIME_NUMERIC, TIME_TARGET, load_time_training_frame, time_split

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
MODELS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


def make_pipeline(estimator):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), TIME_CATEGORICAL),
        ("num", "passthrough", TIME_NUMERIC),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def evaluate(y_true, y_pred) -> dict:
    return {
        "MAE": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "R2": round(float(r2_score(y_true, y_pred)), 4),
    }


def main():
    df = load_time_training_frame()
    train, test = time_split(df)
    X_train, y_train = train[TIME_CATEGORICAL + TIME_NUMERIC], train[TIME_TARGET]
    X_test, y_test = test[TIME_CATEGORICAL + TIME_NUMERIC], test[TIME_TARGET]

    candidates = {
        "RandomForest": make_pipeline(
            RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=3,
                                   random_state=42, n_jobs=-1)),
        "XGBoost": make_pipeline(
            XGBRegressor(n_estimators=400, max_depth=5, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, random_state=42,
                         objective="reg:squarederror", n_jobs=-1)),
    }

    results = {}
    for name, pipe in candidates.items():
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        results[name] = evaluate(y_test, preds)
        print(f"{name:15s} -> {results[name]}")

    best_name = min(results, key=lambda n: results[n]["MAE"])
    best_pipe = candidates[best_name]
    print(f"\nSelected model: {best_name} (lowest MAE)")

    joblib.dump({"pipeline": best_pipe, "model_name": best_name,
                 "features": {"categorical": TIME_CATEGORICAL, "numeric": TIME_NUMERIC}},
                MODELS_DIR / "processing_time_model.pkl")

    report = {"task": "processing_time_regression", "train_rows": len(train),
              "test_rows": len(test), "results": results, "selected_model": best_name}
    with open(REPORTS_DIR / "processing_time_metrics.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved model -> models/processing_time_model.pkl")
    print(f"Saved metrics -> reports/processing_time_metrics.json")


if __name__ == "__main__":
    main()
