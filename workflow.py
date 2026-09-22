"""Job + machine workflow (state machine)."""
from db import get_conn

JOB_TRANSITIONS = {
    "Created":       ["Pending"],
    "Pending":       ["Scheduled"],
    "Scheduled":     ["In Production", "Pending"],             # back to Pending = needs rescheduling
    "In Production": ["Completed", "Delayed", "Pending"],      # Pending if its machine breaks down
    "Delayed":       ["In Production", "Completed"],
    "Completed":     [],
}
MACHINE_STATUSES = {"Available", "Running", "Breakdown", "Maintenance"}

def change_job_status(job_id: str, new_status: str):
    with get_conn() as c:
        row = c.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Job {job_id} not found")
        old = row["status"]
        if new_status not in JOB_TRANSITIONS.get(old, []):
            raise ValueError(f"Invalid transition {old} -> {new_status}. Allowed: {JOB_TRANSITIONS[old]}")
        c.execute("UPDATE jobs SET status=? WHERE job_id=?", (new_status, job_id))
        c.execute("INSERT INTO job_status_log(job_id, old_status, new_status) VALUES (?,?,?)",
                  (job_id, old, new_status))
    return {"job_id": job_id, "old_status": old, "new_status": new_status}

def set_machine_status(machine_id: str, status: str):
    if status not in MACHINE_STATUSES:
        raise ValueError(f"Status must be one of {sorted(MACHINE_STATUSES)}")
    with get_conn() as c:
        cur = c.execute("UPDATE machines SET status=? WHERE machine_id=?", (status, machine_id))
        if cur.rowcount == 0:
            raise KeyError(f"Machine {machine_id} not found")
    return {"machine_id": machine_id, "status": status}

def mark_delayed_jobs(now_iso: str):
    """Flag in-production jobs whose deadline has passed."""
    with get_conn() as c:
        ids = [r["job_id"] for r in c.execute(
            "SELECT job_id FROM jobs WHERE status='In Production' AND deadline < ?", (now_iso,))]
    return [change_job_status(j, "Delayed") for j in ids]