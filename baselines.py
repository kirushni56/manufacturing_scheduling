"""
Member 3 — baseline schedulers (FCFS and priority-based), used to show the
GA actually earns its complexity (section 12 of the project document:
"compare with simple baseline scheduling strategies such as FCFS and
priority-based scheduling").

Both baselines use the exact same `decode` engine as the GA (scheduler_core)
so the comparison is apples-to-apples: the only difference is *how the
decision is made*, not how the schedule is built or scored.

  FCFS      -> operations are attempted in job arrival order (created_at),
               machine chosen greedily as whichever compatible machine
               becomes free soonest.
  Priority  -> operations are attempted in (priority, deadline) order —
               high-priority / urgent jobs go first — same greedy machine
               choice.

Neither baseline does any lookahead or optimization; that's the point.
"""
from scheduler_core import decode
from scheduling_data import load_scheduling_data


def greedy_earliest_machine(op, candidates, machine_free):
    """Pick whichever compatible machine is free soonest; ties broken by predicted time."""
    return min(candidates, key=lambda c: (machine_free.get(c[0], 0.0), c[1]))


def _job_order_from_priority(jobs, key_fn):
    ordered_jobs = sorted(jobs.keys(), key=key_fn)
    order = []
    for j in ordered_jobs:
        order.extend([j] * jobs[j]["n_ops"])
    return order


def fcfs_order(data):
    return _job_order_from_priority(data["jobs"], key_fn=lambda j: data["jobs"][j]["created_h"])


def priority_order(data):
    return _job_order_from_priority(
        data["jobs"], key_fn=lambda j: (data["jobs"][j]["priority"], data["jobs"][j]["deadline_h"]))


def run_fcfs(data):
    return decode(fcfs_order(data), data, greedy_earliest_machine)


def run_priority(data):
    return decode(priority_order(data), data, greedy_earliest_machine)


if __name__ == "__main__":
    data = load_scheduling_data()
    for name, fn in [("FCFS", run_fcfs), ("Priority", run_priority)]:
        _, metrics = fn(data)
        print(f"\n{name} schedule metrics:")
        for k, v in metrics.items():
            print(f"  {k:20s} {v}")
