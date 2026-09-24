"""
Member 2 -> Member 3 hand-off.

Loads the trained models, scores every (pending operation x compatible
machine) pair for processing time, scores every machine for failure/delay
risk, and writes the results in exactly the shape Member 3's Genetic
Algorithm and Member 1's `predictions` table expect:

    {"operation_id": "J12-O2", "machine_id": "M3", "predicted_time": 2.7}
    {"machine_id": "M3", "machine_risk": 0.18}

Outputs:
    data/processed/predictions_processing_time.csv
    data/processed/predictions_machine_risk.csv
    data/processed/scheduler_predictions.json   (combined, for a quick look)

Run: python predict.py [--post-to-api] [--api http://localhost:8000]
"""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from db import get_conn, init_db, load_csvs
from ml_features import build_history_lookup, lookup_hist_avg

MODELS_DIR = Path("models")
OUT_DIR = Path("data/processed")


def ensure_db():
    if not Path("data/manufacturing.db").exists():
        print("No database found -> initializing from Member 1's CSVs...")
        init_db()
        load_csvs()


def load_models():
    time_path, risk_path = MODELS_DIR / "processing_time_model.pkl", MODELS_DIR / "failure_risk_model.pkl"
    if not time_path.exists() or not risk_path.exists():
        raise SystemExit(
            "Trained models not found. Run:\n"
            "  python train_processing_time_model.py\n"
            "  python train_failure_risk_model.py\n"
            "first.")
    return joblib.load(time_path), joblib.load(risk_path)


def fetch_pending_operations(conn):
    """Pending/Scheduled jobs joined to their operations and job attributes."""
    sql = """
        SELECT o.operation_id, o.job_id, o.sequence, o.operation_type,
               o.required_machine_type, o.processing_time AS baseline_time,
               j.product, j.material, j.quantity, j.priority, j.deadline
        FROM operations o
        JOIN jobs j ON j.job_id = o.job_id
        WHERE j.status IN ('Pending', 'Scheduled')
        ORDER BY o.job_id, o.sequence
    """
    return pd.DataFrame([dict(r) for r in conn.execute(sql).fetchall()])


def fetch_machines(conn):
    sql = "SELECT machine_id, machine_type, speed_factor, status FROM machines"
    return pd.DataFrame([dict(r) for r in conn.execute(sql).fetchall()])


def fetch_latest_machine_status(conn):
    """Most recent sensor snapshot per machine -> input to the risk model."""
    sql = """
        SELECT ms.machine_id, ms.temperature, ms.vibration, ms.operating_hours,
               ms.previous_failures, ms.days_since_maintenance, ms.current_workload
        FROM machine_status ms
        JOIN (SELECT machine_id, MAX(timestamp) ts FROM machine_status GROUP BY machine_id) latest
          ON latest.machine_id = ms.machine_id AND latest.ts = ms.timestamp
    """
    return pd.DataFrame([dict(r) for r in conn.execute(sql).fetchall()])


def predict_processing_times(time_model_bundle, ops_df, machines_df):
    pipe = time_model_bundle["pipeline"]
    by_pair, by_op = build_history_lookup()

    available = machines_df[machines_df.status.isin(["Available", "Running"])]
    rows = []
    for _, op in ops_df.iterrows():
        candidates = available[available.machine_type == op.required_machine_type]
        for _, m in candidates.iterrows():
            rows.append({
                "operation_id": op.operation_id, "job_id": op.job_id, "machine_id": m.machine_id,
                "product": op.product, "material": op.material, "operation_type": op.operation_type,
                "machine_type": m.machine_type, "quantity": op.quantity, "speed_factor": m.speed_factor,
                "baseline_time": op.baseline_time,
                "hist_avg_time_per_unit": lookup_hist_avg(m.machine_id, op.operation_type, by_pair, by_op),
            })
    if not rows:
        return pd.DataFrame(columns=["operation_id", "job_id", "machine_id", "predicted_time"])

    X = pd.DataFrame(rows)
    preds = pipe.predict(
        X[["product", "material", "operation_type", "machine_type", "quantity", "speed_factor",
           "baseline_time", "hist_avg_time_per_unit"]])
    X["predicted_time"] = [round(float(p), 3) for p in preds]  # avoid float32->JSON artifacts
    return X[["operation_id", "job_id", "machine_id", "predicted_time"]]


def predict_machine_risk(risk_model_bundle, status_df):
    clf, features = risk_model_bundle["model"], risk_model_bundle["features"]
    if status_df.empty:
        return pd.DataFrame(columns=["machine_id", "machine_risk"])
    # XGBoost returns float32; round via plain Python floats to avoid ugly float32->JSON artifacts
    probs = [round(float(p), 3) for p in clf.predict_proba(status_df[features])[:, 1]]
    return pd.DataFrame({"machine_id": status_df.machine_id, "machine_risk": probs})


def post_to_api(base_url, time_preds: pd.DataFrame, risk_preds: pd.DataFrame):
    import requests
    try:
        t = requests.post(f"{base_url}/predictions/processing-time",
                          json=time_preds[["operation_id", "machine_id", "predicted_time"]].to_dict("records"),
                          timeout=5)
        r = requests.post(f"{base_url}/predictions/machine-risk",
                          json=risk_preds.rename(columns={"machine_risk": "machine_risk"}).to_dict("records"),
                          timeout=5)
        print(f"POST /predictions/processing-time -> {t.status_code} {t.json()}")
        print(f"POST /predictions/machine-risk -> {r.status_code} {r.json()}")
    except Exception as e:
        print(f"Could not reach API at {base_url} ({e}). Predictions were still saved to disk.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-to-api", action="store_true", help="also POST results to Member 1's FastAPI service")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()

    ensure_db()
    time_bundle, risk_bundle = load_models()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with get_conn() as conn:
        ops_df = fetch_pending_operations(conn)
        machines_df = fetch_machines(conn)
        status_df = fetch_latest_machine_status(conn)

    if ops_df.empty:
        print("No Pending/Scheduled operations found — nothing to predict.")
        return

    time_preds = predict_processing_times(time_bundle, ops_df, machines_df)
    risk_preds = predict_machine_risk(risk_bundle, status_df)

    time_preds.to_csv(OUT_DIR / "predictions_processing_time.csv", index=False)
    risk_preds.to_csv(OUT_DIR / "predictions_machine_risk.csv", index=False)

    # combined per-job view, in the format shown in the project document
    risk_by_machine = risk_preds.set_index("machine_id").machine_risk.to_dict()
    combined = (time_preds.assign(machine_risk=time_preds.machine_id.map(risk_by_machine))
                          .groupby("job_id")
                          .apply(lambda g: g[["operation_id", "machine_id", "predicted_time", "machine_risk"]]
                                 .to_dict("records"))
                          .to_dict())
    with open(OUT_DIR / "scheduler_predictions.json", "w") as f:
        json.dump(combined, f, indent=2)

    print(f"Processing-time predictions: {len(time_preds)} (operation x compatible-machine) pairs")
    print(f"Machine-risk predictions:    {len(risk_preds)} machines")
    print("Saved:")
    print("  data/processed/predictions_processing_time.csv")
    print("  data/processed/predictions_machine_risk.csv")
    print("  data/processed/scheduler_predictions.json")

    if args.post_to_api:
        post_to_api(args.api, time_preds, risk_preds)


if __name__ == "__main__":
    main()
