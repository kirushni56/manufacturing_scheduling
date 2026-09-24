"""
Shared feature definitions for Member 2 (ML Prediction).

Two models are built on top of Member 1's data:

1. Processing-time regressor
   Target : production_history.actual_time (hours)
   Features: product, material, operation_type, machine_type   (categorical)
             quantity, speed_factor, baseline_time, hist_avg_time_per_unit (numeric)

2. Machine failure/delay-risk classifier
   Target : machine_status.failure_within_24h (0/1)
   Features: temperature, vibration, operating_hours,
             previous_failures, days_since_maintenance, current_workload

Keeping the feature lists in one place means train_*.py and predict.py can
never drift apart.
"""
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
PROCESSED = Path("data/processed")

# ---------------------------------------------------------------- time model
TIME_CATEGORICAL = ["product", "material", "operation_type", "machine_type"]
TIME_NUMERIC = ["quantity", "speed_factor", "baseline_time", "hist_avg_time_per_unit"]
TIME_TARGET = "actual_time"

# ------------------------------------------------------------- risk model
RISK_NUMERIC = ["temperature", "vibration", "operating_hours",
                 "previous_failures", "days_since_maintenance", "current_workload"]
RISK_TARGET = "failure_within_24h"


def load_time_training_frame() -> pd.DataFrame:
    """Member 1's preprocessed history + machine_type, ready for the time model."""
    hist = pd.read_csv(PROCESSED / "ml_processing_time.csv", parse_dates=["start_time"])
    machines = pd.read_csv(RAW / "machines.csv")[["machine_id", "machine_type", "speed_factor"]]
    df = hist.merge(machines, on="machine_id", how="left", suffixes=("", "_m"))
    # keep column names aligned with TIME_NUMERIC/TIME_CATEGORICAL
    df = df.rename(columns={"planned_time": "baseline_time"})
    df = df.sort_values("start_time").reset_index(drop=True)
    return df


def load_risk_training_frame() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "ml_failure_risk.csv", parse_dates=["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def time_split(df: pd.DataFrame, test_frac: float = 0.15):
    """Chronological split (no shuffling) so the test set is always 'the future'."""
    cut = int(len(df) * (1 - test_frac))
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def build_history_lookup() -> pd.DataFrame:
    """
    machine_id + operation_type -> mean time_per_unit, computed from ALL logged
    production history. Used at inference time (everything in the log is "past").
    Mirrors preprocess.py's leakage-safe expanding-mean feature used at training time.
    """
    hist = pd.read_csv(RAW / "production_history.csv")
    hist["time_per_unit"] = hist.actual_time / hist.quantity
    by_pair = hist.groupby(["machine_id", "operation_type"])["time_per_unit"].mean()
    by_op = hist.groupby("operation_type")["time_per_unit"].mean()
    return by_pair, by_op


def lookup_hist_avg(machine_id: str, operation_type: str, by_pair, by_op) -> float:
    if (machine_id, operation_type) in by_pair.index:
        return float(by_pair.loc[(machine_id, operation_type)])
    return float(by_op.loc[operation_type])
