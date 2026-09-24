# Member 2 — Machine Learning Prediction

Builds on Member 1's dataset, SQLite database and FastAPI service
(`db.py`, `api.py`, `data/raw/*.csv`, `data/processed/*.csv`) to produce the
two predictions the Genetic Algorithm (Member 3) needs.

## Files added by Member 2

| File | Purpose |
|---|---|
| `ml_features.py` | Shared feature lists + the leakage-safe historical-average lookup, used by both training and inference so they never drift apart. |
| `train_processing_time_model.py` | Trains RandomForest vs XGBoost regressors on `data/processed/ml_processing_time.csv`, evaluates MAE/RMSE/R², keeps the better model. |
| `train_failure_risk_model.py` | Trains RandomForest vs XGBoost classifiers on `data/processed/ml_failure_risk.csv`, evaluates accuracy/precision/recall/F1/ROC-AUC/confusion matrix, keeps the better model. |
| `predict.py` | Loads the two trained models, scores every pending operation against every compatible, available machine, scores every machine's current failure risk, and writes the results — optionally POSTing them straight into Member 1's `predictions` table via the API. |
| `models/*.pkl` | Saved pipelines (preprocessing + model) after training. |
| `reports/*.json` | Metrics for both models, model-vs-model comparison. |

## How to run (in order)

```bash
pip install -r requirements.txt

# 1. Build the database from Member 1's CSVs (skip if data/manufacturing.db already exists)
python db.py

# 2. Train both models
python train_processing_time_model.py
python train_failure_risk_model.py

# 3. Score every pending job's operations + every machine, save + hand off to Member 3
python predict.py
#   ...or, with Member 1's API running (`uvicorn api:app --reload`) in another terminal:
python predict.py --post-to-api --api http://127.0.0.1:8000
```

## Model 1 — Processing-Time Prediction (regression)

- **Target:** `actual_time` (hours) from `production_history`.
- **Features:** `product`, `material`, `operation_type`, `machine_type` (one-hot encoded) +
  `quantity`, `speed_factor`, `baseline_time`, `hist_avg_time_per_unit` (numeric).
  `hist_avg_time_per_unit` is the historical average time-per-unit for that
  machine + operation combination — computed with an **expanding mean over
  time-ordered rows only** (Member 1's `preprocess.py`), so the model is
  never trained on future information.
- **Split:** chronological 85/15 (train on older rows, test on the most
  recent 15%) instead of a random split, since a scheduler is always
  predicting forward in time.
- **Result:** XGBoost selected — MAE ≈ 0.19 h, RMSE ≈ 0.30 h, R² ≈ 0.97 on
  held-out data (see `reports/processing_time_metrics.json` for the full
  RandomForest-vs-XGBoost comparison).

## Model 2 — Machine Failure/Delay Risk (classification)

- **Target:** `failure_within_24h` from `machine_status`.
- **Features:** `temperature`, `vibration`, `operating_hours`,
  `previous_failures`, `days_since_maintenance`, `current_workload`.
- **Class imbalance:** the positive class is ~20% of rows, so RandomForest
  uses `class_weight="balanced"` and XGBoost uses `scale_pos_weight`; the
  better model is picked by **F1**, not accuracy, since a model that just
  predicts "no failure" would still look ~80% accurate.
- **Result:** XGBoost selected — F1 ≈ 0.40, recall ≈ 0.51 on held-out data
  (see `reports/failure_risk_metrics.json`).

## Hand-off contract (what Member 3 receives)

`predict.py` writes:

- `data/processed/predictions_processing_time.csv` — one row per
  `(operation_id, machine_id)` pair for every **compatible, available**
  machine, e.g. an operation needing a CNC gets a predicted time for each
  available CNC machine, not just one.
- `data/processed/predictions_machine_risk.csv` — one row per machine.
- `data/processed/scheduler_predictions.json` — the same data grouped by
  job, in the shape shown in the project document:

  ```json
  {
    "J1": [
      {"operation_id": "J1-O1", "machine_id": "M1", "predicted_time": 0.878, "machine_risk": 0.58},
      {"operation_id": "J1-O1", "machine_id": "M2", "predicted_time": 0.966, "machine_risk": 0.75}
    ]
  }
  ```

With `--post-to-api`, the same data is written into Member 1's `predictions`
table and `machines.failure_risk` column via `POST /predictions/processing-time`
and `POST /predictions/machine-risk`, so Member 3's GA can read everything
it needs from a single call to `GET /scheduler-input`.

## Notes / simplifications (worth mentioning in the report)

- `baseline_time` at inference is Member 1's `operations.processing_time`
  (a material-adjusted, machine-independent estimate). At training time the
  closest available analog is `production_history.planned_time`. The two are
  computed slightly differently upstream in the synthetic-data generator;
  the model still benefits from the feature, but this is a simplification
  worth calling out rather than hiding.
- Machine risk is scored from each machine's **latest** logged sensor
  snapshot in `machine_status`, standing in for a live sensor feed.
