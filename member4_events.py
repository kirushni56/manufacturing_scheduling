import json
from datetime import datetime

from db import get_conn
from workflow import change_job_status, set_machine_status


def record_event(event_type, machine_id=None, job_id=None, details=None):
    with get_conn() as c:
        cur = c.execute(
            """
            INSERT INTO events(event_type, machine_id, job_id, event_time, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_type,
                machine_id,
                job_id,
                datetime.now().isoformat(),
                json.dumps(details) if details else None
            )
        )
        return cur.lastrowid


def get_affected_jobs_by_machine(machine_id):
    with get_conn() as c:
        rows = c.execute(
            """
            SELECT DISTINCT o.job_id
            FROM schedule s
            JOIN operations o ON s.operation_id = o.operation_id
            JOIN jobs j ON o.job_id = j.job_id
            WHERE s.machine_id = ?
            AND s.is_active = 1
            AND j.status IN ('Scheduled', 'In Production', 'Delayed')
            """,
            (machine_id,)
        ).fetchall()

    return [row["job_id"] for row in rows]


def handle_machine_breakdown(machine_id, details=None):
    affected_jobs = get_affected_jobs_by_machine(machine_id)

    set_machine_status(machine_id, "Breakdown")

    changed_jobs = []

    for job_id in affected_jobs:
        with get_conn() as c:
            row = c.execute(
                "SELECT status FROM jobs WHERE job_id=?",
                (job_id,)
            ).fetchone()

        if row and row["status"] in ("Scheduled", "In Production"):
            changed_jobs.append(
                change_job_status(job_id, "Pending")
            )

    event_id = record_event(
        "Machine Breakdown",
        machine_id=machine_id,
        details={
            "affected_jobs": affected_jobs,
            "changed_jobs": [j["job_id"] for j in changed_jobs]
        }
    )

    return {
        "event_id": event_id,
        "event_type": "Machine Breakdown",
        "machine_id": machine_id,
        "affected_jobs": affected_jobs,
        "changed_jobs": changed_jobs
    }