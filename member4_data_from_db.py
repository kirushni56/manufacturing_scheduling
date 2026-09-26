import pandas as pd

from db import get_conn


def _hours(ts, t0):
    return (ts - t0).total_seconds() / 3600.0


def load_scheduling_data_from_db():
    with get_conn() as c:
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", c)
        ops_df = pd.read_sql_query(
            "SELECT * FROM operations ORDER BY job_id, sequence", c
        )
        machines_df = pd.read_sql_query("SELECT * FROM machines", c)
        setup_df = pd.read_sql_query("SELECT * FROM setup_times", c)
        predictions_df = pd.read_sql_query("SELECT * FROM predictions", c)

    jobs_df["created_at"] = pd.to_datetime(jobs_df["created_at"])
    jobs_df["deadline"] = pd.to_datetime(jobs_df["deadline"])

    t0 = jobs_df["created_at"].min()

    jobs = {}

    for _, r in jobs_df.iterrows():
        jobs[r["job_id"]] = dict(
            product=r["product"],
            priority=int(r["priority"]),
            created_h=_hours(r["created_at"], t0),
            deadline_h=_hours(r["deadline"], t0)
        )

    operations = ops_df.to_dict("records")

    for op in operations:
        jobs[op["job_id"]].setdefault("n_ops", 0)
        jobs[op["job_id"]]["n_ops"] += 1

    machine_type = dict(
        zip(machines_df["machine_id"], machines_df["machine_type"])
    )

    speed_factor = dict(
        zip(machines_df["machine_id"], machines_df["speed_factor"])
    )

    available_machines = set(
        machines_df[
            machines_df["status"].isin(["Available", "Running"])
        ]["machine_id"]
    )

    candidates = {}

    for op in operations:
        op_id = op["operation_id"]

        pred = predictions_df[
            predictions_df["operation_id"] == op_id
        ]

        if not pred.empty:
            predicted = {
                row["machine_id"]: float(row["predicted_time"])
                for _, row in pred.iterrows()
                if row["machine_id"] in available_machines
            }
        else:
            predicted = {}

        compat = [
            m
            for m, machine_t in machine_type.items()
            if machine_t == op["required_machine_type"]
            and m in available_machines
        ]

        candidates[op_id] = [
            (
                m,
                round(
                    predicted.get(
                        m,
                        op["processing_time"] / speed_factor[m]
                    ),
                    3
                )
            )
            for m in compat
        ]

    machine_risk = dict(
        zip(
            machines_df["machine_id"],
            machines_df["failure_risk"]
        )
    )

    for m in machines_df["machine_id"]:
        machine_risk.setdefault(m, 0.0)

    setup_lookup = {
        (
            r["from_product"],
            r["to_product"],
            r["machine_type"]
        ): r["setup_hours"]
        for _, r in setup_df.iterrows()
    }

    return dict(
        t0=t0,
        jobs=jobs,
        operations=operations,
        candidates=candidates,
        machine_risk=machine_risk,
        machine_type=machine_type,
        setup_lookup=setup_lookup
    )


def setup_time(
    setup_lookup,
    from_product,
    to_product,
    machine_type
):
    if from_product is None or from_product == to_product:
        return 0.0

    return float(
        setup_lookup.get(
            (from_product, to_product, machine_type),
            0.0
        )
    )