"""Clean raw data and produce ML-ready files for Member 2."""
import pandas as pd
from pathlib import Path

RAW, OUT = Path("data/raw"), Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

def prep_history():
    df = pd.read_csv(RAW / "production_history.csv", parse_dates=["start_time", "end_time"])
    df = df.drop_duplicates("history_id").dropna(subset=["actual_time", "machine_id", "quantity"])
    df = df[(df.actual_time > 0) & (df.quantity > 0)].sort_values("start_time")
    df["time_per_unit"] = df.actual_time / df.quantity
    df = df[df.time_per_unit < df.time_per_unit.quantile(0.995)]           # remove extreme outliers
    # historical average per machine+operation using ONLY earlier rows (no data leakage)
    g = df.groupby(["machine_id", "operation_type"])["time_per_unit"]
    df["hist_avg_time_per_unit"] = g.transform(lambda s: s.shift().expanding().mean())
    df["hist_avg_time_per_unit"] = df["hist_avg_time_per_unit"].fillna(
        df.groupby("operation_type")["time_per_unit"].transform("mean"))
    df["delay_ratio"] = df.actual_time / df.planned_time
    return df

def prep_status():
    df = pd.read_csv(RAW / "machine_status.csv", parse_dates=["timestamp"]).drop_duplicates().dropna()
    df["temperature"] = df.temperature.clip(20, 120)
    df["vibration"] = df.vibration.clip(0, 15)
    df["current_workload"] = df.current_workload.clip(0, 1)
    return df.sort_values("timestamp")

if __name__ == "__main__":
    h, s = prep_history(), prep_status()
    h.to_csv(OUT / "ml_processing_time.csv", index=False)   # target: actual_time
    s.to_csv(OUT / "ml_failure_risk.csv", index=False)      # target: failure_within_24h
    print("processing-time rows:", len(h), "| failure rows:", len(s))
    print("failure class balance:\n", s.failure_within_24h.value_counts(normalize=True).round(3))