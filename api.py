"""Data API for Members 2-5.   Run: uvicorn api:app --reload"""
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from db import get_conn
from workflow import change_job_status, set_machine_status

app = FastAPI(title="Manufacturing Data API")

def q(sql, params=()):
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]

# ---------- read endpoints ----------
@app.get("/jobs")
def jobs(status: Optional[str] = None):
    return q("SELECT * FROM jobs WHERE status=?", (status,)) if status else q("SELECT * FROM jobs")

@app.get("/jobs/{job_id}")
def job(job_id: str):
    j = q("SELECT * FROM jobs WHERE job_id=?", (job_id,))
    if not j: raise HTTPException(404, "Job not found")
    return {**j[0], "operations": q("SELECT * FROM operations WHERE job_id=? ORDER BY sequence", (job_id,))}

@app.get("/machines")
def machines():
    return q("SELECT * FROM machines")

@app.get("/scheduler-input")            # Member 3 & 4 call this
def scheduler_input():
    return {
        "jobs": [{**j, "operations": q("SELECT * FROM operations WHERE job_id=? ORDER BY sequence", (j["job_id"],))}
                 for j in q("SELECT * FROM jobs WHERE status IN ('Pending','Scheduled')")],
        "machines": q("SELECT * FROM machines WHERE status IN ('Available','Running')"),
        "setup_times": q("SELECT * FROM setup_times"),
        "predicted_times": q("SELECT operation_id, machine_id, predicted_time FROM predictions"),
    }

@app.get("/schedule")                   # Member 5 calls this for the Gantt chart
def schedule():
    return q("""SELECT s.*, o.job_id FROM schedule s JOIN operations o USING(operation_id)
                WHERE s.is_active=1 ORDER BY s.machine_id, s.start_time""")

@app.get("/dashboard/summary")
def summary():
    return {"jobs": {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) n FROM jobs GROUP BY status")},
            "total_jobs": q("SELECT COUNT(*) n FROM jobs")[0]["n"],
            "machines": q("SELECT machine_id, machine_type, status, failure_risk FROM machines")}

# ---------- status updates ----------
class StatusIn(BaseModel):
    status: str

@app.patch("/jobs/{job_id}/status")
def job_status(job_id: str, body: StatusIn):
    try: return change_job_status(job_id, body.status)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

@app.patch("/machines/{machine_id}/status")
def machine_status(machine_id: str, body: StatusIn):
    try: return set_machine_status(machine_id, body.status)
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))

# ---------- Member 2 writes predictions ----------
class TimePred(BaseModel):
    operation_id: str; machine_id: str; predicted_time: float
class RiskPred(BaseModel):
    machine_id: str; machine_risk: float

@app.post("/predictions/processing-time")
def save_time_preds(items: List[TimePred]):
    with get_conn() as c:
        c.executemany("INSERT OR REPLACE INTO predictions(operation_id,machine_id,predicted_time) VALUES (?,?,?)",
                      [(i.operation_id, i.machine_id, i.predicted_time) for i in items])
    return {"saved": len(items)}

@app.post("/predictions/machine-risk")
def save_risk_preds(items: List[RiskPred]):
    with get_conn() as c:
        c.executemany("UPDATE machines SET failure_risk=? WHERE machine_id=?",
                      [(i.machine_risk, i.machine_id) for i in items])
    return {"saved": len(items)}

# ---------- Members 3 & 4 write schedules ----------
class Item(BaseModel):
    operation_id: str; machine_id: str; start_time: str; end_time: str
class SchedulePayload(BaseModel):
    algorithm: str = "GA"
    trigger_event: str = "initial"
    makespan: Optional[float] = None
    total_delay: Optional[float] = None
    utilization: Optional[float] = None
    items: List[Item]

@app.post("/schedule")
def save_schedule(p: SchedulePayload):
    run_id = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
    with get_conn() as c:
        c.execute("UPDATE schedule SET is_active=0 WHERE is_active=1")
        c.executemany("INSERT INTO schedule(run_id,operation_id,machine_id,start_time,end_time) VALUES (?,?,?,?,?)",
                      [(run_id, i.operation_id, i.machine_id, i.start_time, i.end_time) for i in p.items])
        c.execute("INSERT INTO schedule_history(run_id,trigger_event,algorithm,makespan,total_delay,utilization) "
                  "VALUES (?,?,?,?,?,?)", (run_id, p.trigger_event, p.algorithm, p.makespan, p.total_delay, p.utilization))
        ids = [r[0] for r in c.execute(
            "SELECT DISTINCT o.job_id FROM schedule s JOIN operations o USING(operation_id) "
            "JOIN jobs j ON j.job_id=o.job_id WHERE s.run_id=? AND j.status='Pending'", (run_id,))]
        for jid in ids:
            c.execute("UPDATE jobs SET status='Scheduled' WHERE job_id=?", (jid,))
            c.execute("INSERT INTO job_status_log(job_id,old_status,new_status) VALUES (?,'Pending','Scheduled')", (jid,))
    return {"run_id": run_id, "operations_saved": len(p.items)}

# ---------- Member 4 logs events ----------
class EventIn(BaseModel):
    event_type: str
    machine_id: Optional[str] = None
    job_id: Optional[str] = None
    details: Optional[str] = None

@app.post("/events")
def add_event(e: EventIn):
    with get_conn() as c:
        c.execute("INSERT INTO events(event_type,machine_id,job_id,details) VALUES (?,?,?,?)",
                  (e.event_type, e.machine_id, e.job_id, e.details))
    return {"logged": e.event_type}

@app.get("/events")
def events():
    return q("SELECT * FROM events ORDER BY event_id DESC")
class OperationIn(BaseModel):
    sequence: int
    operation_type: str
    required_machine_type: str
    processing_time: float

class JobIn(BaseModel):
    job_id: str
    product: str
    material: str
    quantity: int
    priority: int  # 1=High, 2=Medium, 3=Low
    deadline: str  # ISO format, e.g. "2026-01-10T14:00:00"
    operations: List[OperationIn]

@app.post("/jobs")
def create_job(j: JobIn):
    with get_conn() as c:
        exists = c.execute("SELECT 1 FROM jobs WHERE job_id=?", (j.job_id,)).fetchone()
        if exists:
            raise HTTPException(400, f"Job {j.job_id} already exists")
        c.execute(
            "INSERT INTO jobs(job_id, product, material, quantity, priority, created_at, deadline, status) "
            "VALUES (?,?,?,?,?,?,?,'Pending')",
            (j.job_id, j.product, j.material, j.quantity, j.priority,
             datetime.now().isoformat(), j.deadline)
        )
        for op in j.operations:
            c.execute(
                "INSERT INTO operations(operation_id, job_id, sequence, operation_type, "
                "required_machine_type, processing_time, status) VALUES (?,?,?,?,?,?,'Pending')",
                (f"{j.job_id}-O{op.sequence}", j.job_id, op.sequence,
                 op.operation_type, op.required_machine_type, op.processing_time)
            )
        c.execute("INSERT INTO job_status_log(job_id, old_status, new_status) VALUES (?,'Created','Pending')",
                  (j.job_id,))
    return {"created": j.job_id, "operations": len(j.operations)}