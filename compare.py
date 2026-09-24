"""
Member 3 — side-by-side comparison (project document, section 12).

Runs FCFS, priority-based, and the GA scheduler on the same jobs/machines/
predictions and reports makespan, tardiness, machine utilization and idle
time for each — the "important experiment" the project document asks for.

Also writes the GA's schedule to data/processed/ga_schedule.json /.csv (for
Member 5's Gantt chart) and, if Member 1's API is running, POSTs it to
`/schedule` so Member 4 has a live baseline to disrupt.

Run: python compare.py [--post-to-api] [--api http://127.0.0.1:8000]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from baselines import run_fcfs, run_priority
from ga_scheduler import run_ga, rows_to_records
from scheduling_data import load_scheduling_data

REPORTS_DIR = Path("reports")
PROCESSED_DIR = Path("data/processed")


def post_schedule_to_api(base_url, records, metrics, algorithm):
    import requests
    payload = dict(
        algorithm=algorithm, trigger_event="initial",
        makespan=metrics["makespan"], total_delay=metrics["total_tardiness"],
        utilization=metrics["utilization"],
        items=[dict(operation_id=r["operation_id"], machine_id=r["machine_id"],
                    start_time=r["start_time"], end_time=r["end_time"]) for r in records])
    try:
        resp = requests.post(f"{base_url}/schedule", json=payload, timeout=10)
        print(f"POST /schedule -> {resp.status_code} {resp.json()}")
    except Exception as e:
        print(f"Could not reach API at {base_url} ({e}). Schedule was still saved to disk.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop-size", type=int, default=80)
    ap.add_argument("--generations", type=int, default=200)
    ap.add_argument("--post-to-api", action="store_true")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    data = load_scheduling_data()

    print("Running FCFS...")
    fcfs_rows, fcfs_metrics = run_fcfs(data)
    print("Running priority-based...")
    prio_rows, prio_metrics = run_priority(data)
    print(f"Running GA ({args.pop_size} pop x {args.generations} gens)...")
    ga_rows, ga_metrics, ga_history = run_ga(data, pop_size=args.pop_size,
                                              generations=args.generations, verbose=False)

    table = pd.DataFrame({
        "FCFS": fcfs_metrics, "Priority": prio_metrics, "GA": ga_metrics,
    }).T[["makespan", "total_tardiness", "jobs_late", "utilization", "idle_time",
          "setup_total", "risk_exposure", "fitness"]]

    print("\n=== Scheduler comparison ===")
    print(table.to_string())

    improvement = {
        "makespan_vs_fcfs_%": round(100 * (fcfs_metrics["makespan"] - ga_metrics["makespan"]) / fcfs_metrics["makespan"], 1),
        "tardiness_vs_fcfs_%": round(100 * (fcfs_metrics["total_tardiness"] - ga_metrics["total_tardiness"]) / max(fcfs_metrics["total_tardiness"], 1e-9), 1),
        "utilization_vs_fcfs_%": round(100 * (ga_metrics["utilization"] - fcfs_metrics["utilization"]) / max(fcfs_metrics["utilization"], 1e-9), 1),
    }
    print("\nGA improvement over FCFS:", improvement)

    REPORTS_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    table.to_csv(REPORTS_DIR / "scheduler_comparison.csv")
    with open(REPORTS_DIR / "scheduler_comparison.json", "w") as f:
        json.dump({"FCFS": fcfs_metrics, "Priority": prio_metrics, "GA": ga_metrics,
                   "ga_improvement_over_fcfs": improvement, "ga_fitness_history": ga_history}, f, indent=2)

    ga_records = rows_to_records(ga_rows, data["t0"])
    with open(PROCESSED_DIR / "ga_schedule.json", "w") as f:
        json.dump(ga_records, f, indent=2)
    pd.DataFrame(ga_records).to_csv(PROCESSED_DIR / "ga_schedule.csv", index=False)

    print("\nSaved:")
    print("  reports/scheduler_comparison.csv / .json")
    print("  data/processed/ga_schedule.json / .csv")

    if args.post_to_api:
        post_schedule_to_api(args.api, ga_records, ga_metrics, algorithm="GA")


if __name__ == "__main__":
    main()
