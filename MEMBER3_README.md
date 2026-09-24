# Member 3 — Genetic Algorithm Scheduler

Builds on Member 1's data/API and Member 2's predictions
(`data/processed/predictions_processing_time.csv`,
`data/processed/predictions_machine_risk.csv`) to produce an optimized
job-to-machine schedule, and compares it against FCFS and priority-based
baselines as the project document asks for (section 12).

## Files added by Member 3

| File | Purpose |
|---|---|
| `scheduling_data.py` | Loads jobs/operations/machines/setup-times + Member 2's predictions into the structures the scheduler needs (times in hours since the earliest job's `created_at`). |
| `scheduler_core.py` | The shared serial schedule-builder (`decode`) and metrics used by **both** the GA and the baselines — this is where the hard constraints actually live. |
| `baselines.py` | FCFS and priority-based schedulers (greedy earliest-free-machine), for a fair "what would a simple rule do" comparison. |
| `ga_scheduler.py` | The Genetic Algorithm: chromosome, population, fitness, selection, crossover, mutation. |
| `compare.py` | Runs all three schedulers, prints/saves the comparison table, saves the GA's schedule, optionally POSTs it into Member 1's `/schedule` API. |

## How to run

```bash
# needs Member 1's DB (python db.py) and Member 2's predictions (predict.py) already done
python compare.py
#   ...or, with `uvicorn api:app --reload` running in another terminal:
python compare.py --post-to-api --api http://127.0.0.1:8000

# individual pieces, if useful:
python baselines.py        # just FCFS / priority
python ga_scheduler.py      # just the GA
```

## Constraint handling

Every constraint in section 6.2 of the project document is enforced **by
construction**, not by penalizing violations after the fact:

| Constraint | How it's enforced |
|---|---|
| A machine can't run two jobs at once | `decode()` is a serial schedule-builder: a machine's next job can only start once its current one ends (single-capacity simulation). |
| A job's operations follow their sequence | The chromosome encodes job IDs, not operations; `decode()` always takes "this job's next not-yet-scheduled operation," so sequence 2 physically cannot be scheduled before sequence 1. |
| A job only goes to a compatible machine | Candidate lists per operation (`data['candidates']`) only ever contain machines of the operation's `required_machine_type`. |
| Unavailable machines can't receive jobs | Candidate lists only include machines Member 1 marked `Available`/`Running` (this comes straight from Member 2's prediction step, which already filtered on machine status). |
| No job duplicated or omitted | The OS chromosome is a permutation of "job_id repeated once per operation" — every operation appears in every valid chromosome exactly once. |
| Deadlines / priorities respected | *Soft* constraint, handled in the fitness function (below) rather than a hard rule, since deadlines can be missed in the real world and the scheduler needs to *minimize* that, not treat it as illegal. |

## Genetic Algorithm design

- **Chromosome** — two parts, standard for flexible job-shop GAs:
  - **OS** (operation sequence): job IDs, each repeated once per operation —
    e.g. `[J3, J1, J3, J2, J1, ...]`.
  - **MS** (machine selection): for every operation, an index into its list
    of compatible/available candidate machines.
- **Initial population** — seeded with the FCFS and priority schedules
  (so the GA starts at least as good as the baselines it's compared
  against), plus random individuals for diversity.
- **Selection** — tournament (k=3).
- **Crossover** — Precedence-Preserving Order-based Crossover (POX) on OS
  (partitions jobs into two random sets, keeps each parent's relative order
  for its set — always produces a valid permutation) + uniform crossover
  on MS.
- **Mutation** — swap two positions in OS; reassign a random operation to a
  different candidate machine in MS.
- **Elitism** — top 2 chromosomes carried over unchanged each generation.
- **Fitness** (lower = better), matching section 6.1 of the document:

  ```
  fitness = 10 × weighted_tardiness + 1 × idle_time + 2 × setup_time + 5 × machine_risk_exposure
  ```

  `weighted_tardiness` multiplies each late job's tardiness by a priority
  weight (High=3, Medium=2, Low=1) so the GA protects urgent jobs first, not
  just whichever job happens to be easiest to finish on time.
  `machine_risk_exposure` is `Σ (operation duration × that machine's predicted
  failure risk)`, so the GA is nudged away from loading risky machines —
  the weights (10/1/2/5) are exactly the α/β/γ/δ in the document's cost
  function, tunable in `scheduler_core.compute_metrics`.

## Results (80 population × 200 generations, this dataset)

| Metric | FCFS | Priority | **GA** |
|---|---|---|---|
| Makespan (h) | 83.9 | 95.8 | 92.6 |
| Total tardiness (h) | 82.1 | 188.9 | **3.5** |
| Jobs late | 7 | 14 | **2** |
| Machine utilization | 65.0% | 56.7% | 58.4% |
| Setup time (h) | 0.0 | 0.0 | 0.0 |
| Fitness (cost) | 3517 | 3097 | **1159** |

See `reports/scheduler_comparison.csv` / `.json` for the exact numbers and
`reports/ga_run.json` for the generation-by-generation fitness curve.

**Honest read of the trade-off:** the GA cuts tardiness by ~96% and late
jobs from 7 to 2, at the cost of a slightly *higher* makespan and slightly
*lower* utilization than plain FCFS. That's the fitness function doing
exactly what it was told to do — it weights deadline delay 10× and machine
risk 5×, but idle time only 1×, so it happily trades a bit of idle machine
time for meeting more deadlines. That's a genuine, explainable trade-off
worth walking through in the report (and the weights in
`scheduler_core.compute_metrics` are the knob to turn if the factory cared
more about raw throughput than on-time delivery).

Setup time is 0 in all three schedules for this dataset — not a bug: with
only 8 machines, 6 products and 60 jobs, all three schedulers end up
naturally batching same-product jobs together on a machine before its next
job's operations become available, so no changeover is ever actually
triggered. The setup-time term still exists in the fitness function and
would activate on a dataset with more product churn per machine.

## Hand-off contract (what Member 4/5 receive)

- `data/processed/ga_schedule.json` / `.csv` — the winning schedule:
  `operation_id, job_id, machine_id, start_time, end_time` (ISO
  timestamps) plus `start_h/end_h/setup_h/duration_h` in relative hours,
  ready for Member 5's Gantt chart.
- `reports/scheduler_comparison.csv` / `.json` — the FCFS vs Priority vs GA
  table for the "Schedule Comparison" screen in the dashboard.
- With `--post-to-api`, the GA schedule is written into Member 1's
  `schedule` + `schedule_history` tables (`trigger_event="initial"`), so
  Member 4 has a real baseline schedule already sitting in the database to
  disrupt with a breakdown/urgent-order/delay event and re-optimize.

## Simplifications worth mentioning in the report

- Machine daily availability windows (`available_from`/`available_until` in
  `machines.csv`) aren't enforced as hard day/night boundaries — the
  scheduler treats each machine as continuously available from the
  production horizon's start. All machines share the same 08:00–20:00
  window in Member 1's synthetic data, so this doesn't distort the
  comparison between schedulers, but a real deployment would need to split
  operations across shift boundaries.
- Re-optimizing *after* a disruption (rather than from scratch) is Member
  4's job — this GA always solves the static, initial scheduling problem.
