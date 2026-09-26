import uuid
from datetime import datetime

import pandas as pd

from db import get_conn
from ga_scheduler import run_ga
from member4_data_from_db import load_scheduling_data_from_db
from workflow import change_job_status


def save_schedule_to_db(rows, t0, metrics=None, trigger_event="Initial Schedule"):
    run_id = str(uuid.uuid4())

    with get_conn() as c:
        c.execute("UPDATE schedule SET is_active=0 WHERE is_active=1")

        for r in rows:
            start_time = (
                t0 + pd.Timedelta(hours=r["start"])
            ).isoformat()

            end_time = (
                t0 + pd.Timedelta(hours=r["end"])
            ).isoformat()

            c.execute(
                """
                INSERT INTO schedule(
                    run_id,
                    operation_id,
                    machine_id,
                    start_time,
                    end_time,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    run_id,
                    r["operation_id"],
                    r["machine_id"],
                    start_time,
                    end_time
                )
            )

        if metrics:
            c.execute(
                """
                INSERT INTO schedule_history(
                    run_id,
                    trigger_event,
                    algorithm,
                    makespan,
                    total_delay,
                    utilization
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    trigger_event,
                    "Genetic Algorithm",
                    metrics.get("makespan"),
                    metrics.get("total_tardiness"),
                    metrics.get("utilization")
                )
            )

    return run_id


def reschedule_after_event(trigger_event="Machine Breakdown", generations=10):
    data = load_scheduling_data_from_db()

    rows, metrics, history = run_ga(
        data,
        generations=generations
    )

    run_id = save_schedule_to_db(
        rows,
        data["t0"],
        metrics,
        trigger_event
    )

    with get_conn() as c:
        pending_jobs = c.execute(
            "SELECT job_id FROM jobs WHERE status='Pending'"
        ).fetchall()

    for row in pending_jobs:
        change_job_status(row["job_id"], "Scheduled")

    return {
        "run_id": run_id,
        "trigger_event": trigger_event,
        "metrics": metrics,
        "operations_scheduled": len(rows)
    }


def get_deadline_risk():
    with get_conn() as c:
        rows = c.execute(
            """
            SELECT
                j.job_id,
                j.deadline,
                MAX(s.end_time) AS scheduled_end
            FROM jobs j
            JOIN operations o ON j.job_id = o.job_id
            JOIN schedule s ON o.operation_id = s.operation_id
            WHERE s.is_active = 1
            GROUP BY j.job_id
            """
        ).fetchall()

    risk = []

    for row in rows:
        deadline = datetime.fromisoformat(row["deadline"])
        scheduled_end = datetime.fromisoformat(row["scheduled_end"])

        delay_hours = (
            scheduled_end - deadline
        ).total_seconds() / 3600

        risk.append({
            "job_id": row["job_id"],
            "deadline": row["deadline"],
            "scheduled_end": row["scheduled_end"],
            "delay_hours": round(max(delay_hours, 0), 2),
            "at_risk": delay_hours > 0
        })

    return risk


def should_reschedule():
    risk = get_deadline_risk()

    at_risk_jobs = [
        r for r in risk
        if r["at_risk"]
    ]

    return {
        "should_reschedule": len(at_risk_jobs) > 0,
        "at_risk_jobs": at_risk_jobs,
        "at_risk_count": len(at_risk_jobs)
    }


def get_affected_job_risk(affected_jobs):
    risk = get_deadline_risk()

    affected = {
        r["job_id"]: r
        for r in risk
        if r["job_id"] in affected_jobs
    }

    at_risk = [
        r for r in affected.values()
        if r["at_risk"]
    ]

    return {
        "affected_jobs": affected_jobs,
        "at_risk_jobs": at_risk,
        "at_risk_count": len(at_risk),
        "should_reschedule": len(at_risk) > 0
    }