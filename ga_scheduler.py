"""
Member 3 — Genetic Algorithm Scheduler.

Chromosome (two parts, standard flexible-job-shop GA encoding):

  OS (operation sequence): a permutation of job IDs where each job_id is
     repeated once per operation it has, e.g. [J3,J1,J3,J2,J1,...]. Reading
     left to right and always taking "this job's next not-yet-scheduled
     operation" turns this into a concrete, always-feasible operation order
     — job precedence can never be violated by construction, and every
     operation appears exactly once (no duplication/omission).

  MS (machine selection): for every operation, an index into that
     operation's list of compatible, available candidate machines
     (data['candidates'][operation_id], built by Member 2's predictions).

Fitness = 10*weighted_tardiness + 1*idle_time + 2*setup_time + 5*risk_exposure
(weighted_tardiness multiplies each job's lateness by a priority weight, so
high-priority jobs are protected first) — see scheduler_core.compute_metrics
for the exact formula. Lower is better.

Run: python ga_scheduler.py
"""
import argparse
import json
import random
from pathlib import Path

from scheduler_core import decode
from scheduling_data import load_scheduling_data

REPORTS_DIR = Path("reports")
PROCESSED_DIR = Path("data/processed")


# --------------------------------------------------------------- chromosome
def random_os(jobs):
    genes = []
    for job_id, info in jobs.items():
        genes.extend([job_id] * info["n_ops"])
    random.shuffle(genes)
    return genes


def random_ms(candidates):
    return {op_id: random.randrange(len(c)) if c else 0 for op_id, c in candidates.items()}


def init_population(data, pop_size):
    """
    Seed the initial population with the FCFS and priority-order schedules
    (encoded as chromosomes) so the GA never does *worse* than the greedy
    baselines it's compared against — then lets selection/crossover/mutation
    search from there for a better job order and machine assignment than
    either fixed heuristic uses. The rest of the population is random for
    diversity.
    """
    from baselines import fcfs_order, priority_order, greedy_earliest_machine

    def seed(job_order):
        rows, _ = decode(job_order, data, greedy_earliest_machine)
        ms = {}
        for r in rows:
            cand_list = data["candidates"][r["operation_id"]]
            ms[r["operation_id"]] = next(i for i, c in enumerate(cand_list) if c[0] == r["machine_id"])
        return (job_order, ms)

    seeds = [seed(fcfs_order(data)), seed(priority_order(data))]
    rest = [(random_os(data["jobs"]), random_ms(data["candidates"])) for _ in range(max(pop_size - len(seeds), 0))]
    return seeds + rest


# ------------------------------------------------------------------- decode
def fixed_machine_selector(ms):
    def select(op, candidates, machine_free):
        idx = ms[op["operation_id"]]
        idx = min(idx, len(candidates) - 1)
        return candidates[idx]
    return select


def evaluate(chromosome, data):
    os_, ms = chromosome
    _, metrics = decode(os_, data, fixed_machine_selector(ms))
    return metrics["fitness"]


# ------------------------------------------------------------ GA operators
def tournament_select(pop, fitnesses, k=3):
    idxs = random.sample(range(len(pop)), k)
    best = min(idxs, key=lambda i: fitnesses[i])
    return pop[best]


def pox_crossover(parent1, parent2, jobs):
    """Precedence-Preserving Order-based Crossover on the OS part."""
    os1, os2 = parent1[0], parent2[0]
    job_ids = list(jobs.keys())
    random.shuffle(job_ids)
    cut = random.randint(1, len(job_ids) - 1)
    j1 = set(job_ids[:cut])

    child_os = []
    p2_fill = [g for g in os2 if g not in j1]
    fill_iter = iter(p2_fill)
    for g in os1:
        child_os.append(g if g in j1 else next(fill_iter))
    return child_os


def uniform_ms_crossover(ms1, ms2):
    child = {}
    for op_id in ms1:
        child[op_id] = ms1[op_id] if random.random() < 0.5 else ms2.get(op_id, ms1[op_id])
    return child


def mutate_os(os_, rate):
    os_ = os_[:]
    if random.random() < rate and len(os_) > 1:
        i, j = random.sample(range(len(os_)), 2)
        os_[i], os_[j] = os_[j], os_[i]
    return os_


def mutate_ms(ms, candidates, rate):
    new_ms = dict(ms)
    for op_id, c in candidates.items():
        if len(c) > 1 and random.random() < rate:
            new_ms[op_id] = random.randrange(len(c))
    return new_ms


# ------------------------------------------------------------------ main GA
def run_ga(data, pop_size=80, generations=200, crossover_rate=0.85, mutation_rate=0.15,
           elite_size=2, seed=42, verbose=True):
    random.seed(seed)
    jobs, candidates = data["jobs"], data["candidates"]

    population = init_population(data, pop_size)
    fitnesses = [evaluate(c, data) for c in population]
    history = []

    for gen in range(generations):
        order = sorted(range(pop_size), key=lambda i: fitnesses[i])
        new_pop = [population[i] for i in order[:elite_size]]  # elitism

        while len(new_pop) < pop_size:
            p1 = tournament_select(population, fitnesses)
            p2 = tournament_select(population, fitnesses)
            if random.random() < crossover_rate:
                child_os = pox_crossover(p1, p2, jobs)
                child_ms = uniform_ms_crossover(p1[1], p2[1])
            else:
                child_os, child_ms = p1[0][:], dict(p1[1])
            child_os = mutate_os(child_os, mutation_rate)
            child_ms = mutate_ms(child_ms, candidates, mutation_rate)
            new_pop.append((child_os, child_ms))

        population = new_pop
        fitnesses = [evaluate(c, data) for c in population]
        best = min(fitnesses)
        history.append(round(best, 2))
        if verbose and (gen % 10 == 0 or gen == generations - 1):
            print(f"gen {gen:4d}  best fitness = {best:.2f}")

    best_idx = min(range(pop_size), key=lambda i: fitnesses[i])
    best_chromosome = population[best_idx]
    rows, metrics = decode(best_chromosome[0], data, fixed_machine_selector(best_chromosome[1]))
    return rows, metrics, history


def rows_to_records(rows, t0):
    out = []
    for r in rows:
        out.append(dict(
            operation_id=r["operation_id"], job_id=r["job_id"], machine_id=r["machine_id"],
            start_time=(t0 + __import__("pandas").Timedelta(hours=r["start"])).isoformat(),
            end_time=(t0 + __import__("pandas").Timedelta(hours=r["end"])).isoformat(),
            start_h=round(r["start"], 2), end_h=round(r["end"], 2),
            setup_h=round(r["setup"], 2), duration_h=round(r["duration"], 2),
        ))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop-size", type=int, default=80)
    ap.add_argument("--generations", type=int, default=200)
    args = ap.parse_args()

    data = load_scheduling_data()
    rows, metrics, history = run_ga(data, pop_size=args.pop_size, generations=args.generations)

    print("\nGA best schedule metrics:")
    for k, v in metrics.items():
        print(f"  {k:20s} {v}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    records = rows_to_records(rows, data["t0"])
    with open(PROCESSED_DIR / "ga_schedule.json", "w") as f:
        json.dump(records, f, indent=2)
    with open(REPORTS_DIR / "ga_run.json", "w") as f:
        json.dump(dict(metrics=metrics, fitness_history=history,
                       pop_size=args.pop_size, generations=args.generations), f, indent=2)
    print(f"\nSaved schedule -> data/processed/ga_schedule.json ({len(records)} operations)")
    print(f"Saved run log  -> reports/ga_run.json")


if __name__ == "__main__":
    main()
