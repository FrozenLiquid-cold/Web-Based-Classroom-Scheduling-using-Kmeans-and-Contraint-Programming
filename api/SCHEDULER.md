# OR-Tools Constraint Programming Scheduler

## Overview

The scheduler uses **Google OR-Tools Constraint Programming (CP-SAT)** to generate optimal class schedules. It automatically falls back to a greedy algorithm if OR-Tools is not available.

## Features

### Constraint Programming (CP) Solver
- **Optimal Solutions**: Finds the best possible schedule given constraints
- **Complex Constraints**: Handles multiple overlapping constraints simultaneously
- **Multi-objective Optimization**: Balances multiple scheduling preferences
- **Conflict Resolution**: Automatically avoids room and instructor double-booking
- **Time Limits**: Configurable solver time limits for large problems

### Greedy Algorithm (Fallback)
- **Fast**: Quick schedule generation for small problems
- **Simple**: Straightforward first-fit algorithm
- **Reliable**: Always produces a solution if one exists

## Constraints

### Hard Constraints (Must Satisfy)
1. **No Room Double-Booking**: Each room can only have one class at a time
2. **No Instructor Double-Booking**: Each instructor can only teach one class at a time
3. **Room Type Matching**: LAB subjects must use LAB rooms, LEC subjects must use LEC rooms
4. **Consecutive Time Slots**: Multi-slot subjects must be scheduled in consecutive time blocks
5. **Existing Bookings**: Respects previously scheduled classes for other courses

### Soft Constraints (Preferences)
1. **Maximize Scheduled Subjects**: Schedule as many subjects as possible
2. **Avoid Early Morning**: Prefer classes starting after 9:00 AM (avoid 7:30 AM)
3. **Afternoon Preference**: Encourage afternoon class scheduling
4. **Cluster Matching**: Prefer rooms that match subject clusters (if clustering is used)
5. **LEC/LAB Linking**: Prefer same instructor for linked LEC and LAB classes

## Usage

### Basic Usage

```python
from scheduler.scheduler import run_scheduler
from db import SessionLocal

db = SessionLocal()

# Generate schedule
schedule_items = run_scheduler(
    db=db,
    course_id=1,
    year=1,
    semester=1,
    subject_ids=None,  # None = schedule all subjects
    use_cp=True,       # Use CP solver (False for greedy)
    max_time_seconds=120.0
)

# Save schedule
from scheduler.scheduler import save_schedule
saved = save_schedule(db, course_id=1, year=1, semester=1, schedule_items=schedule_items)
```

### API Usage

```bash
# Generate schedule via API
curl -X POST http://localhost:8000/api/schedule/generate \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": 1,
    "year": 1,
    "semester": 1,
    "subject_ids": null
  }'

# Save schedule
curl -X POST http://localhost:8000/api/schedule/save \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": 1,
    "year": 1,
    "semester": 1,
    "items": [...]
  }'
```

## Configuration

### Subject Fields

- `recommended_slots` (Integer): Number of consecutive time slots needed (default: 1)
- `cluster` (Integer): Cluster ID for grouping subjects (default: -1)

### Instructor Fields

- `assignable_courses` (Text): Comma-separated list of course codes the instructor can teach
  - Example: "CC101,CC102,CC103"
  - If empty/null, instructor can teach all subjects

### Room Fields

- `capacity` (Integer): Maximum room capacity (optional)
- `cluster` (Integer): Cluster ID for room grouping (default: -1)

## Time Slots

Standard time blocks:
- `7:30–9:00`
- `9:00–10:30`
- `10:30–12:00`
- `1:00–2:30`
- `2:30–4:00`
- `4:00–5:30`

Multi-slot subjects will span consecutive time blocks (e.g., a 2-slot subject might use `7:30–10:30`).

## Objective Function

The CP solver maximizes:

```
w_schedule * scheduled_subjects
+ w_morning * morning_preference
+ w_afternoon * afternoon_preference
- w_cluster_penalty * cluster_mismatches
```

Where:
- `w_schedule = 1000.0 / num_subjects` (primary objective)
- `w_morning = 20.0 / num_subjects` (avoid 7:30 AM)
- `w_afternoon = 10.0 / num_subjects` (prefer afternoon)
- `w_cluster_penalty = 5.0` (penalize cluster mismatches)

## Solver Parameters

Default solver configuration:
- **Max Time**: 120 seconds
- **Workers**: Auto-detected (1-8 CPUs)
- **Search Strategy**: Portfolio search
- **Random Seed**: 42 (for reproducibility)

## Performance

### CP Solver
- **Small Problems** (< 50 subjects): Usually solves in < 10 seconds
- **Medium Problems** (50-200 subjects): 30-120 seconds
- **Large Problems** (> 200 subjects): May need time limit adjustment

### Greedy Algorithm
- **Speed**: Very fast (< 1 second for most problems)
- **Quality**: Suboptimal but always produces a solution

## Troubleshooting

### No Solution Found
- Check that subjects have eligible instructors and rooms
- Verify room types match subject types (LEC/LAB)
- Ensure time slots are available
- Check for conflicting existing schedules

### Slow Performance
- Reduce `max_time_seconds` for faster results (may reduce quality)
- Use greedy algorithm for quick results (`use_cp=False`)
- Filter subjects with `subject_ids` parameter

### Unscheduled Subjects
- Verify instructor eligibility (`assignable_courses`)
- Check room type matches subject type
- Ensure sufficient time slots available
- Check room capacity (if enabled)

## Migration

To add scheduler fields to existing database:

```bash
python migrate_add_scheduler_fields.py
```

This adds:
- `recommended_slots` to subjects
- `cluster` to subjects and rooms
- `assignable_courses` to instructors
- `capacity` to rooms

## Advanced Usage

### Custom Time Slots

Modify `scheduler/timeslots.py` to customize time blocks.

### Custom Objectives

Edit `scheduler/cp_scheduler.py` to adjust objective function weights.

### Clustering

Set `cluster` field on subjects and rooms to enable cluster-based scheduling preferences.

## References

- [OR-Tools Documentation](https://developers.google.com/optimization)
- [CP-SAT Solver Guide](https://developers.google.com/optimization/cp/cp_solver)

