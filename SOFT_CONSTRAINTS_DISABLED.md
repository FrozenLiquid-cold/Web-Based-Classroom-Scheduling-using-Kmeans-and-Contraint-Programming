# Soft Constraints Disabled - Refactoring Summary

## ✅ Changes Made

Successfully refactored the CP-SAT model to disable all soft constraints while keeping hard constraints and variable definitions intact.

### Removed Soft Constraints (Preference Terms)

All preference/optimization terms have been removed from the objective function:

1. ❌ **Pack Term** - Prefer later start times
2. ❌ **Cluster Penalty** - Penalize subject-room cluster mismatches
3. ❌ **Lunch Fill** - Prefer classes ending near lunch time
4. ❌ **Morning Bias** - Avoid early morning (7:30 AM), prefer closer to 12:00
5. ❌ **Tail Fill** - Encourage classes after 5:00 PM
6. ❌ **Gap Compression** - Fill trailing holes in schedule
7. ❌ **Block Utilization** - Encourage utilization of block capacity

### Kept Primary Objective

✅ **Maximize Scheduled Subjects** - The primary objective remains:
```python
scheduled_sum = sum(selected.values())
model.Maximize(scheduled_sum)
```

This ensures the solver still optimizes to schedule as many subjects as possible, but without any time/location preferences.

### Hard Constraints (All Preserved)

All hard constraints remain intact and unchanged:

1. ✅ **Subject Assignment Constraints** (Lines 995-1010)
   - Each subject scheduled at most once
   - Mutual exclusivity: `sum(starts_for_s) <= 1`

2. ✅ **Start Block Constraints** (Lines 1050-1065)
   - Links assignment variables to start_block_id
   - Ensures assignments fit within consecutive blocks

3. ✅ **Room Conflict Prevention** (Lines 1070-1128)
   - No two classes in same room can overlap (NoOverlap)
   - Uses CP-SAT intervals

4. ✅ **Instructor Conflict Prevention** (Lines 1130-1153)
   - No instructor can teach overlapping classes (NoOverlap)
   - Uses CP-SAT intervals

5. ✅ **Student Conflict Prevention** (Lines 1155-1215)
   - No overlapping classes for same course/year_level/day
   - Uses NoOverlap or Cumulative (based on capacity)

6. ✅ **LEC/LAB Linking Constraints** (Lines 1217-1250)
   - LEC and LAB subjects with same code must have same instructor
   - `sum(lec_vars) == sum(lab_vars)`

### Variable Definitions (All Preserved)

- ✅ All variable creation logic unchanged
- ✅ All `start_vars` definitions intact
- ✅ All `selected` variables intact
- ✅ All `subject_start_block_vars` intact
- ✅ All interval variables intact

### Scheduling Algorithm Architecture (Unchanged)

- ✅ Cluster-based processing unchanged
- ✅ Greedy warm-start hints unchanged
- ✅ Retry pass for unscheduled subjects unchanged
- ✅ Solver configuration unchanged

## 📊 Impact

### Before
- Objective: Maximize scheduled subjects + 7 preference terms
- Solver optimized for both coverage and preferences
- More complex objective function

### After
- Objective: Maximize scheduled subjects only
- Solver optimizes purely for coverage
- Simpler, faster objective evaluation
- No time/location preferences

## 🔍 Code Changes

### Objective Function (Lines 1252-1261)

**Before:**
```python
# Complex objective with 7 preference terms
objective = (
    w_schedule * scheduled_sum
    - w_cluster_penalty * cluster_penalty_expr
    + w_pack * pack_term_expr
    + w_lunch * lunch_fill_expr
    + w_morning * morning_bias_expr
    + w_tail * tail_fill_expr
    + w_gap * gap_penalty_expr
    + w_block_util * block_utilization_expr
)
model.Maximize(objective)
```

**After:**
```python
# Simple objective - only maximize scheduled subjects
scheduled_sum = sum(selected.values())
model.Maximize(scheduled_sum)
```

### Removed Code

- Removed all preference term calculations (pack_terms, cluster_penalty_terms, etc.)
- Removed all weight calculations (w_pack, w_cluster_penalty, etc.)
- Removed `block_utilization_expr` calculation (line 1163)

## ✅ Verification

- ✅ No linter errors
- ✅ All hard constraints preserved
- ✅ Variable definitions intact
- ✅ Scheduling algorithm architecture unchanged
- ✅ Primary objective maintained
- ✅ All soft constraints removed

## 📝 Notes

The solver will now:
- Still maximize the number of scheduled subjects
- Still enforce all conflict prevention rules
- Still enforce LEC/LAB linking requirements
- **No longer** prefer specific times or locations
- **No longer** penalize cluster mismatches
- **No longer** optimize for schedule compactness

This makes the solver faster and simpler, focusing purely on feasibility and coverage rather than preferences.

