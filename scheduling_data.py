"""
Member 3 — shared data loading.

Reads Member 1's raw tables + Member 2's predictions (whichever is on disk;
falls back to a baseline formula if predictions are missing for a pair) and
turns them into the structures the scheduler needs:

  jobs[job_id]      -> dict(product, priority, created_h, deadline_h, n_ops)
  operations        -> list of dicts, ordered by (job_id, sequence)
  candidates[op_id] -> list of (machine_id, predicted_time) for every
                        compatible, available machine
  machine_risk[machine_id]  -> predicted failure/delay risk (0-1)
  machine_type[machine_id]  -> for setup-time lookups
  setup_lookup[(from_product,to_product,machine_type)] -> hours

All times are expressed as float hours since T0 = the earliest job's
created_at, so the optimizer only ever deals with plain numbers.
"""
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
PROCESSED = Path("data/processed")


def _hours(ts, t0):
    return (ts - t0).total_seconds() / 3600.0


def load_scheduling_data():
    jobs_df = pd.read_csv(RAW / "jobs.csv", parse_dates=["created_at", "deadline"])
    ops_df = pd.read_csv(RAW / "operations.csv").sort_values(["job_id", "sequence"])
    machines_df = pd.read_csv(RAW / "machines.csv")
    setup_df = pd.read_csv(RAW / "setup_times.csv")

    t0 = jobs_df.created_at.min()

    jobs = {}
    for _, r in jobs_df.iterrows():
        jobs[r.job_id] = dict(
            product=r.product, priority=int(r.priority),
            created_h=_hours(r.created_at, t0), deadline_h=_hours(r.deadline, t0),
        )

    operations = ops_df.to_dict("records")
    for op in operations:
        jobs[op["job_id"]].setdefault("n_ops", 0)
        jobs[op["job_id"]]["n_ops"] += 1

    machine_type = dict(zip(machines_df.machine_id, machines_df.machine_type))
    speed_factor = dict(zip(machines_df.machine_id, machines_df.speed_factor))
    available_machines = set(machines_df[machines_df.status.isin(["Available", "Running"])].machine_id)

    # --- candidate (machine, predicted_time) pairs per operation ---
    candidates = {}
    pred_path = PROCESSED / "predictions_processing_time.csv"
    preds = pd.read_csv(pred_path) if pred_path.exists() else pd.DataFrame(
        columns=["operation_id", "machine_id", "predicted_time"])
    preds_by_op = preds.groupby("operation_id")

    for op in operations:
        op_id = op["operation_id"]
        if op_id in preds_by_op.groups:
            g = preds_by_op.get_group(op_id)
            candidates[op_id] = list(zip(g.machine_id, g.predicted_time))
        else:
            # Member 2's predictions aren't available for this op (e.g. re-run before
            # predict.py) -> fall back to Member 1's baseline time / machine speed.
            compat = [m for m, t in machine_type.items()
                      if t == op["required_machine_type"] and m in available_machines]
            candidates[op_id] = [(m, round(op["processing_time"] / speed_factor[m], 3)) for m in compat]

    # --- machine risk, from Member 2 ---
    risk_path = PROCESSED / "predictions_machine_risk.csv"
    if risk_path.exists():
        risk_df = pd.read_csv(risk_path)
        machine_risk = dict(zip(risk_df.machine_id, risk_df.machine_risk))
    else:
        machine_risk = {m: 0.0 for m in machines_df.machine_id}
    for m in machines_df.machine_id:
        machine_risk.setdefault(m, 0.0)

    setup_lookup = {(r.from_product, r.to_product, r.machine_type): r.setup_hours
                     for r in setup_df.itertuples()}

    return dict(t0=t0, jobs=jobs, operations=operations, candidates=candidates,
                machine_risk=machine_risk, machine_type=machine_type, setup_lookup=setup_lookup)


def setup_time(setup_lookup, from_product, to_product, machine_type):
    if from_product is None or from_product == to_product:
        return 0.0
    return float(setup_lookup.get((from_product, to_product, machine_type), 0.0))
