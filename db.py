"""SQLite database: schema + loading the CSVs."""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/manufacturing.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (
    machine_id TEXT PRIMARY KEY, machine_type TEXT NOT NULL, speed_factor REAL DEFAULT 1.0,
    capacity INTEGER DEFAULT 1, available_from TEXT, available_until TEXT,
    status TEXT DEFAULT 'Available' CHECK (status IN ('Available','Running','Breakdown','Maintenance')),
    failure_risk REAL DEFAULT 0.0);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY, product TEXT NOT NULL, material TEXT, quantity INTEGER NOT NULL,
    priority INTEGER CHECK (priority BETWEEN 1 AND 3), created_at TEXT, deadline TEXT NOT NULL,
    status TEXT DEFAULT 'Created' CHECK (status IN ('Created','Pending','Scheduled','In Production','Delayed','Completed')));

CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(job_id),
    sequence INTEGER NOT NULL, operation_type TEXT, required_machine_type TEXT NOT NULL,
    processing_time REAL, status TEXT DEFAULT 'Pending');

CREATE TABLE IF NOT EXISTS setup_times (
    from_product TEXT, to_product TEXT, machine_type TEXT, setup_hours REAL,
    PRIMARY KEY (from_product, to_product, machine_type));

CREATE TABLE IF NOT EXISTS production_history (
    history_id TEXT PRIMARY KEY, product TEXT, material TEXT, operation_type TEXT,
    machine_id TEXT REFERENCES machines(machine_id), quantity INTEGER, planned_time REAL,
    actual_time REAL, machine_temp REAL, vibration REAL, start_time TEXT, end_time TEXT);

CREATE TABLE IF NOT EXISTS machine_status (
    status_id INTEGER PRIMARY KEY, machine_id TEXT REFERENCES machines(machine_id), timestamp TEXT,
    temperature REAL, vibration REAL, operating_hours REAL, previous_failures INTEGER,
    days_since_maintenance REAL, current_workload REAL, failure_within_24h INTEGER);

CREATE TABLE IF NOT EXISTS predictions (            -- written by Member 2
    operation_id TEXT REFERENCES operations(operation_id), machine_id TEXT REFERENCES machines(machine_id),
    predicted_time REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (operation_id, machine_id));

CREATE TABLE IF NOT EXISTS schedule (               -- written by Members 3 & 4
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
    operation_id TEXT REFERENCES operations(operation_id), machine_id TEXT REFERENCES machines(machine_id),
    start_time TEXT, end_time TEXT, is_active INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS schedule_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    trigger_event TEXT, algorithm TEXT, makespan REAL, total_delay REAL, utilization REAL);

CREATE TABLE IF NOT EXISTS job_status_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, old_status TEXT, new_status TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS events (                 -- Member 4: breakdowns, urgent jobs, delays
    event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, machine_id TEXT, job_id TEXT,
    event_time TEXT DEFAULT CURRENT_TIMESTAMP, details TEXT);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(reset=True):
    DB_PATH.parent.mkdir(exist_ok=True)
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with get_conn() as c:
        c.executescript(SCHEMA)

def load_csvs():
    raw = Path("data/raw")
    with get_conn() as c:
        for t in ["machines", "jobs", "operations", "setup_times", "production_history", "machine_status"]:
            df = pd.read_csv(raw / f"{t}.csv")
            df.to_sql(t, c, if_exists="append", index=False)
            print(f"loaded {t:20s} {len(df)} rows")

if __name__ == "__main__":
    init_db()
    load_csvs()
    print("Database ready:", DB_PATH)