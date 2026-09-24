"""
Member 3 — the schedule builder shared by the GA and the baselines.

Both the Genetic Algorithm and the FCFS/priority baselines produce a
schedule the same way: walk operations in some order, and for each one pick
a machine and the earliest legal start time. What differs between them is
only (a) the order operations are considered in, and (b) how the machine is
picked. That shared logic lives here (`decode`) so the GA and the baselines
are scored on an apples-to-apples basis, and every schedule they produce
automatically satisfies the hard constraints from the project document:

  - a machine never runs two operations at once (single-capacity SGS)
  - a job's operations always run in their required sequence
  - an operation only ever goes to a machine of its required, available type
  - every operation is scheduled exactly once (guaranteed by construction)
"""
from scheduling_data import setup_time


def decode(job_order, data, machine_selector):
    """
    job_order: list of job_ids, each job_id repeated data['jobs'][job_id]['n_ops']
               times, in the order its operations should be attempted. This
               alone fixes a feasible *sequence*; precedence is enforced by
               always taking each job's next pending operation.
    machine_selector(op, candidate_list, machine_free_time) -> (machine_id, predicted_time)
               candidate_list is [(machine_id, predicted_time), ...] for this op.

    Returns (schedule_rows, metrics).
    """
    jobs, operations, setup_lookup = data["jobs"], data["operations"], data["setup_lookup"]
    machine_type, machine_risk = data["machine_type"], data["machine_risk"]

    ops_by_job = {}
    for op in operations:
        ops_by_job.setdefault(op["job_id"], []).append(op)
    for j in ops_by_job:
        ops_by_job[j].sort(key=lambda o: o["sequence"])

    next_idx = {j: 0 for j in jobs}
    job_ready = {j: jobs[j]["created_h"] for j in jobs}
    machine_free = {}
    machine_last_product = {}

    rows = []
    for job_id in job_order:
        op = ops_by_job[job_id][next_idx[job_id]]
        next_idx[job_id] += 1
        op_id = op["operation_id"]
        candidates = data["candidates"][op_id]
        if not candidates:
            continue  # no compatible/available machine right now (rare edge case)

        machine_id, duration = machine_selector(op, candidates, machine_free)
        m_free = machine_free.get(machine_id, 0.0)
        last_product = machine_last_product.get(machine_id)
        setup = setup_time(setup_lookup, last_product, jobs[job_id]["product"], machine_type[machine_id])

        start = max(m_free, job_ready[job_id]) + setup
        end = start + duration

        rows.append(dict(operation_id=op_id, job_id=job_id, machine_id=machine_id,
                          start=start, end=end, setup=setup, duration=duration,
                          risk=machine_risk.get(machine_id, 0.0)))

        machine_free[machine_id] = end
        machine_last_product[machine_id] = jobs[job_id]["product"]
        job_ready[job_id] = end

    return rows, compute_metrics(rows, jobs, machine_free)


PRIORITY_WEIGHT = {1: 3.0, 2: 2.0, 3: 1.0}   # 1 = High .. 3 = Low


def compute_metrics(rows, jobs, machine_free):
    if not rows:
        return dict(makespan=0, total_tardiness=0, weighted_tardiness=0, jobs_late=0,
                    setup_total=0, idle_time=0, utilization=0, risk_exposure=0, fitness=0)

    makespan = max(r["end"] for r in rows)

    job_finish = {}
    for r in rows:
        job_finish[r["job_id"]] = max(job_finish.get(r["job_id"], 0.0), r["end"])

    total_tardiness, weighted_tardiness, jobs_late = 0.0, 0.0, 0
    for j, finish in job_finish.items():
        tardiness = max(0.0, finish - jobs[j]["deadline_h"])
        total_tardiness += tardiness
        weighted_tardiness += tardiness * PRIORITY_WEIGHT[jobs[j]["priority"]]
        jobs_late += 1 if tardiness > 0 else 0

    setup_total = sum(r["setup"] for r in rows)
    risk_exposure = sum(r["duration"] * r["risk"] for r in rows)

    busy = {}
    for r in rows:
        busy[r["machine_id"]] = busy.get(r["machine_id"], 0.0) + r["duration"] + r["setup"]
    n_machines = max(len(machine_free), 1)
    idle_time = sum(makespan - busy.get(m, 0.0) for m in machine_free) if machine_free else 0.0
    utilization = (sum(busy.values()) / (makespan * n_machines)) if makespan > 0 else 0.0

    fitness = (10.0 * weighted_tardiness + 1.0 * idle_time + 2.0 * setup_total + 5.0 * risk_exposure)

    return dict(makespan=round(makespan, 2), total_tardiness=round(total_tardiness, 2),
                weighted_tardiness=round(weighted_tardiness, 2), jobs_late=jobs_late,
                setup_total=round(setup_total, 2), idle_time=round(idle_time, 2),
                utilization=round(utilization, 4), risk_exposure=round(risk_exposure, 2),
                fitness=round(fitness, 2))
