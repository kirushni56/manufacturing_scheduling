from member4_events import handle_machine_breakdown
from member4_reschedule import (
    get_affected_job_risk,
    reschedule_after_event,
    save_schedule_to_db
)
from member4_data_from_db import load_scheduling_data_from_db
from ga_scheduler import run_ga


def simulate():
    print("Starting Member 4 dynamic rescheduling simulation")
    print("Creating initial schedule")

    data = load_scheduling_data_from_db()

    rows, metrics, history = run_ga(
        data,
        generations=10
    )

    save_schedule_to_db(
        rows,
        data["t0"],
        metrics,
        "Initial Schedule"
    )

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

    if risk["should_reschedule"]:
        result = reschedule_after_event(
            "Machine Breakdown - M2",
            generations=10
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