"""Generate a synthetic but realistic manufacturing dataset -> data/raw/*.csv"""
import numpy as np, pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
RAW = Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)
BASE = pd.Timestamp("2026-01-05 08:00")   # start of the scheduling horizon

OP_TO_MTYPE = {"Cutting": "CNC", "Turning": "Lathe", "Drilling": "Drill", "Assembly": "Assembly"}
OP_RATE = {"Cutting": 0.010, "Turning": 0.008, "Drilling": 0.005, "Assembly": 0.012}  # hours/unit
OP_FIXED = 0.3                                                                          # hours
MATERIAL_FACTOR = {"Aluminium": 0.8, "Steel": 1.0, "Titanium": 1.5, "Plastic": 0.6}
PRODUCTS = {  # product: (material, route of operations)
    "Gear":    ("Steel",     ["Cutting", "Turning", "Drilling", "Assembly"]),
    "Shaft":   ("Steel",     ["Cutting", "Turning", "Drilling"]),
    "Bracket": ("Aluminium", ["Cutting", "Drilling", "Assembly"]),
    "Housing": ("Aluminium", ["Cutting", "Turning", "Assembly"]),
    "Valve":   ("Titanium",  ["Cutting", "Turning", "Drilling", "Assembly"]),
    "Cover":   ("Plastic",   ["Cutting", "Drilling", "Assembly"]),
}

def base_time(op, qty, material, speed=1.0):
    return (OP_FIXED + OP_RATE[op] * qty) * MATERIAL_FACTOR[material] / speed

# ---------------- machines ----------------
types = ["CNC", "CNC", "Lathe", "Lathe", "Drill", "Drill", "Assembly", "Assembly"]
machines = [dict(machine_id=f"M{i}", machine_type=t, speed_factor=round(float(rng.uniform(0.85, 1.2)), 2),
                 capacity=1, available_from="08:00", available_until="20:00", status="Available")
            for i, t in enumerate(types, 1)]
by_type = {}
for m in machines:
    by_type.setdefault(m["machine_type"], []).append(m)

# ---------------- jobs + operations ----------------
jobs, ops = [], []
for j in range(1, 61):
    prod = str(rng.choice(list(PRODUCTS)))
    material, route = PRODUCTS[prod]
    qty = int(rng.integers(50, 501))
    prio = int(rng.choice([1, 2, 3], p=[0.2, 0.5, 0.3]))          # 1=High, 2=Medium, 3=Low
    created = BASE + pd.Timedelta(hours=float(rng.uniform(0, 24)))
    total = 0.0
    for seq, op in enumerate(route, 1):
        t = base_time(op, qty, material)
        total += t
        ops.append(dict(operation_id=f"J{j}-O{seq}", job_id=f"J{j}", sequence=seq, operation_type=op,
                        required_machine_type=OP_TO_MTYPE[op], processing_time=round(t, 2)))
    slack = rng.uniform(8, 40) if prio == 1 else rng.uniform(30, 110)
    jobs.append(dict(job_id=f"J{j}", product=prod, material=material, quantity=qty, priority=prio,
                     created_at=created.isoformat(), deadline=(created + pd.Timedelta(hours=total + slack)).isoformat(),
                     status="Pending"))

# ---------------- setup times (product changeover per machine type) ----------------
setup = [dict(from_product=a, to_product=b, machine_type=mt,
              setup_hours=0.0 if a == b else round(float(rng.uniform(0.1, 0.6)), 2))
         for a in PRODUCTS for b in PRODUCTS for mt in OP_TO_MTYPE.values()]

# ---------------- production history (past runs, with actual times) ----------------
hist = []
for k in range(1, 3001):
    prod = str(rng.choice(list(PRODUCTS)))
    material, route = PRODUCTS[prod]
    op = str(rng.choice(route))
    m = by_type[OP_TO_MTYPE[op]][int(rng.integers(0, 2))]
    qty = int(rng.integers(20, 600))
    temp, vib = rng.normal(65, 8), max(0.2, rng.normal(2.5, 0.8))
    stress = 1 + 0.004 * max(temp - 70, 0) + 0.03 * max(vib - 3, 0)   # hot/vibrating machines run slower
    actual = base_time(op, qty, material, m["speed_factor"]) * stress * rng.lognormal(0, 0.08)
    start = BASE - pd.Timedelta(days=int(rng.integers(1, 180)), hours=int(rng.integers(0, 12)))
    hist.append(dict(history_id=f"H{k}", product=prod, material=material, operation_type=op,
                     machine_id=m["machine_id"], quantity=qty,
                     planned_time=round(OP_FIXED + OP_RATE[op] * qty, 3), actual_time=round(float(actual), 3),
                     machine_temp=round(float(temp), 1), vibration=round(float(vib), 2),
                     start_time=start.isoformat(), end_time=(start + pd.Timedelta(hours=float(actual))).isoformat()))

# ---------------- machine sensor logs + failure label ----------------
def sigmoid(z): return 1 / (1 + np.exp(-z))
status = []
sid = 1
for m in machines:
    for r in range(250):
        temp = rng.normal(65, 8); vib = max(0.2, rng.normal(2.5, 0.8))
        hrs = rng.uniform(100, 6000); prev = int(rng.poisson(1.5))
        days = rng.uniform(0, 90); load = rng.uniform(0.3, 1.0)
        z = -4.2 + 0.07*(temp-65) + 0.9*(vib-2.5) + 0.0002*hrs + 0.25*prev + 0.015*days + 1.2*load
        status.append(dict(status_id=sid, machine_id=m["machine_id"],
                           timestamp=(BASE - pd.Timedelta(hours=(250 - r) * 6)).isoformat(),
                           temperature=round(float(temp), 1), vibration=round(float(vib), 2),
                           operating_hours=round(float(hrs), 1), previous_failures=prev,
                           days_since_maintenance=round(float(days), 1), current_workload=round(float(load), 2),
                           failure_within_24h=int(rng.random() < sigmoid(z))))
        sid += 1

for name, rows in [("machines", machines), ("jobs", jobs), ("operations", ops), ("setup_times", setup),
                   ("production_history", hist), ("machine_status", status)]:
    pd.DataFrame(rows).to_csv(RAW / f"{name}.csv", index=False)
    print(f"{name:20s} {len(rows):5d} rows")
print("Failure rate:", round(np.mean([s['failure_within_24h'] for s in status]), 3))