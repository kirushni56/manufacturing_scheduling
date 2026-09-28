from member4_events import handle_machine_breakdown
from member4_reschedule import (
    get_affected_job_risk,
    reschedule_after_event,
    save_schedule_to_db
)
from member4_data_from_db import load_scheduling_data_from_db
from ga_scheduler import run_ga
from db import get_conn
from workflow import change_job_status

GENERATIONS = 50  # 10 is too few for the GA to improve on its seeded FCFS/priority schedules


def reset_simulation_state():
    """Start every simulation from a clean factory: all machines up, all jobs Pending.

    Without this, a breakdown from a previous run stays in the DB, so the next
    'initial' schedule is built with that machine already excluded.
    """
    with get_conn() as c:
        c.execute("UPDATE machines SET status='Available'")
        c.execute("UPDATE jobs SET status='Pending'")
        c.execute("UPDATE schedule SET is_active=0 WHERE is_active=1")


def simulate():
    print("Starting Member 4 dynamic rescheduling simulation")
    reset_simulation_state()
    print("Creating initial schedule")

    data = load_scheduling_data_from_db()

    rows, metrics, history = run_ga(
        data,
        generations=GENERATIONS
    )

    save_schedule_to_db(
        rows,
        data["t0"],
        metrics,
        "Initial Schedule"
    )

    # Jobs must be 'Scheduled' or the breakdown handler can't see them as affected
    with get_conn() as c:
        pending = [r["job_id"] for r in c.execute(
            "SELECT job_id FROM jobs WHERE status='Pending'")]
    for job_id in pending:
        change_job_status(job_id, "Scheduled")

    print("Initial schedule created:", len(rows), "operations")

    result = handle_machine_breakdown(
        "M2",
        {"reason": "Simulated machine breakdown"}
    )

    print("Machine:", result["machine_id"])
    print("Affected jobs:", len(result["affected_jobs"]))

    risk = get_affected_job_risk(
        result["affected_jobs"]
    )

    print("Affected jobs at risk:", risk["at_risk_count"])
    print("Should reschedule:", risk["should_reschedule"])

    # Any job with operations on the broken machine must be moved, even if its
    # old deadline wasn't at risk - the machine is gone.
    if result["affected_jobs"] or risk["should_reschedule"]:
        result = reschedule_after_event(
            "Machine Breakdown - M2",
            generations=GENERATIONS
        )

        print("Rescheduling completed")
        print("Run ID:", result["run_id"])
        print("Operations scheduled:", result["operations_scheduled"])
        print("New makespan:", result["metrics"]["makespan"])
        print("New total tardiness:", result["metrics"]["total_tardiness"])
    else:
        print("No rescheduling required")


if __name__ == "__main__":
    simulate()