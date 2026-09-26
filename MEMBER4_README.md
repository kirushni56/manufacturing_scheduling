# Member 4 – Dynamic Rescheduling and Event Handling

## Overview

Member 4 is responsible for handling unexpected production events and dynamically updating the manufacturing schedule.

The module detects machine breakdown events, identifies affected jobs, checks deadline risk, reruns the Genetic Algorithm scheduler when required, and stores the updated schedule and scheduling history in the database.

## Responsibilities

* Detect and record machine breakdown events
* Identify jobs affected by a machine breakdown
* Update affected job statuses
* Check whether affected jobs are at risk of missing their deadlines
* Trigger dynamic rescheduling when required
* Generate a new schedule using the Genetic Algorithm
* Store the updated schedule in the database
* Maintain schedule history for different scheduling runs
* Simulate the complete dynamic rescheduling workflow

## Files

### `member4_data_from_db.py`

Loads the scheduling information required by the Genetic Algorithm directly from the SQLite database.

It retrieves:

* Jobs
* Operations
* Machines
* Setup times
* Predicted processing times

It also:

* Filters machines based on availability
* Generates compatible machine candidates for each operation
* Uses predicted processing time when available
* Uses baseline processing time and machine speed when prediction is unavailable
* Calculates machine failure-risk information
* Provides setup-time lookup functionality

### `member4_events.py`

Handles production events related to machine failures.

Main functions:

* `record_event()`
* `get_affected_jobs_by_machine()`
* `handle_machine_breakdown()`

When a machine breakdown occurs, the module:

1. Finds active scheduled operations assigned to the affected machine.
2. Identifies the corresponding jobs.
3. Changes applicable jobs from `Scheduled` or `In Production` to `Pending`.
4. Changes the machine status to `Breakdown`.
5. Records the event in the `events` table.

### `member4_reschedule.py`

Handles schedule generation, database storage, and deadline-risk analysis.

Main functions:

* `save_schedule_to_db()`
* `reschedule_after_event()`
* `get_deadline_risk()`
* `should_reschedule()`
* `get_affected_job_risk()`

The module:

1. Loads the latest scheduling data from the database.
2. Runs the Genetic Algorithm.
3. Deactivates the previous active schedule.
4. Saves the new schedule.
5. Stores scheduling metrics in `schedule_history`.
6. Changes pending jobs back to `Scheduled`.
7. Checks deadline risk for affected jobs.

### `member4_simulate.py`

Provides an end-to-end simulation of the dynamic rescheduling process.

The simulation performs:

1. Initial schedule generation.
2. Storage of the initial schedule.
3. Simulation of a machine breakdown.
4. Detection of affected jobs.
5. Deadline-risk analysis.
6. Conditional rescheduling.
7. Storage of the new schedule.
8. Display of scheduling metrics.

## Workflow

```text
Database
   |
   v
Load Scheduling Data
   |
   v
Generate Initial Schedule
   |
   v
Machine Breakdown Event
   |
   v
Identify Affected Jobs
   |
   v
Update Job Status
   |
   v
Check Deadline Risk
   |
   +----------------------+
   |                      |
   | No Risk              | At Risk
   v                      v
No Rescheduling      Run Genetic Algorithm
                          |
                          v
                    Generate New Schedule
                          |
                          v
                    Save to Database
                          |
                          v
                    Update Job Status
```

## Database Tables Used

Member 4 interacts with the following database tables:

### `machines`

Used to read machine availability and update machine status during breakdown events.

### `jobs`

Used to identify affected jobs and update their production status.

### `operations`

Used to identify which jobs are associated with scheduled operations.

### `schedule`

Stores the currently active production schedule.

Previous active schedules are marked inactive before a new schedule is saved.

### `schedule_history`

Stores information about each scheduling run, including:

* Run ID
* Trigger event
* Algorithm
* Makespan
* Total tardiness
* Utilization

### `events`

Stores production events such as machine breakdowns.

## Machine Breakdown Handling

For a machine breakdown:

```text
Machine Available
       |
       v
Machine Breakdown Event
       |
       v
Machine Status → Breakdown
       |
       v
Find Active Operations
       |
       v
Find Affected Jobs
       |
       v
Scheduled/In Production → Pending
```

The affected jobs are then evaluated for deadline risk.

## Deadline Risk

For each scheduled job, the latest scheduled operation end time is compared with the job deadline.

The delay is calculated in hours.

A job is considered at risk when:

```text
Scheduled End > Deadline
```

The risk information includes:

* Job ID
* Deadline
* Scheduled completion time
* Delay in hours
* Risk status

## Dynamic Rescheduling

Rescheduling is triggered when affected jobs are found to be at risk of missing their deadlines.

The updated scheduling process uses the existing Genetic Algorithm scheduler:

```text
Machine Breakdown
       |
       v
Affected Jobs
       |
       v
Deadline Risk Check
       |
       v
Risk Detected
       |
       v
Run Genetic Algorithm
       |
       v
New Schedule
       |
       v
Deactivate Old Schedule
       |
       v
Save New Active Schedule
       |
       v
Save Schedule History
```

## Running the Simulation

Make sure the project environment is activated and the required database is available.

Before running a machine breakdown simulation, the machine being used for the simulation should initially be available.

For the current simulation, machine `M2` is used.

Run:

```powershell
python member4_simulate.py
```

Expected workflow:

```text
Starting Member 4 dynamic rescheduling simulation
Creating initial schedule
Initial schedule created: 203 operations
Machine: M2
Affected jobs: ...
Affected jobs at risk: ...
Should reschedule: True
Rescheduling completed
Run ID: ...
Operations scheduled: 203
New makespan: ...
New total tardiness: ...
```

## Verification

After rescheduling, the active schedule can be verified using the database.

The expected result is:

```text
M2 active: 0
Active operations: 203
```

This confirms that:

* The breakdown machine is no longer assigned active operations.
* A complete new schedule has been generated.
* The new schedule contains all 203 operations.

## Member 4 Integration

Member 4 connects the following components:

```text
Member 1
Database
   |
   v
Member 2
Predictions
   |
   v
Member 3
Genetic Algorithm Scheduler
   |
   v
Member 4
Dynamic Rescheduling
   |
   v
Member 5
Dashboard / Visualization
```

Member 4 therefore acts as the event-handling and dynamic rescheduling layer between the scheduling system and the final dashboard.

## Current Implementation

The current implementation has been tested using a simulated `M2` machine breakdown.

The end-to-end workflow successfully:

* Generated an initial schedule for 203 operations
* Detected affected jobs
* Identified affected jobs at deadline risk
* Triggered rescheduling
* Generated a new schedule for 203 operations
* Stored the new schedule in the database
* Recorded scheduling history
* Removed active assignments from the broken machine
