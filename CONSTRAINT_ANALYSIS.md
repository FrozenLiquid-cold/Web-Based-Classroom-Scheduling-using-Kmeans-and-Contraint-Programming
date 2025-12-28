# CP-SAT Constraint Analysis

## Hard Constraints (MUST KEEP - Conflict Prevention & Requirements)

### 1. **Subject Assignment Constraints** (Lines 995-1010)
- Each subject scheduled at most once
- Mutual exclusivity: `sum(starts_for_s) <= 1`
- Links to `selected[subject_id]` variable
- **Status**: ✅ KEEP - Hard constraint

### 2. **Start Block Constraints** (Lines 1050-1065)
- Links assignment variables to start_block_id
- Ensures assignments fit within consecutive blocks
- **Status**: ✅ KEEP - Hard constraint

### 3. **Room Conflict Prevention** (Lines 1070-1128)
- No two classes in same room can overlap (NoOverlap)
- Uses CP-SAT intervals
- **Status**: ✅ KEEP - Hard constraint

### 4. **Instructor Conflict Prevention** (Lines 1130-1153)
- No instructor can teach overlapping classes (NoOverlap)
- Uses CP-SAT intervals
- **Status**: ✅ KEEP - Hard constraint

### 5. **Student Conflict Prevention** (Lines 1155-1215)
- No overlapping classes for same course/year_level/day
- Uses NoOverlap or Cumulative (based on capacity)
- **Status**: ✅ KEEP - Hard constraint

### 6. **LEC/LAB Linking Constraints** (Lines 1217-1250)
- LEC and LAB subjects with same code must have same instructor
- `sum(lec_vars) == sum(lab_vars)`
- **Status**: ✅ KEEP - Hard constraint

## Soft Constraints (SHOULD DISABLE - Preferences in Objective)

### 1. **Primary Objective: Maximize Scheduled Subjects** (Line 1308)
- `scheduled_sum = sum(selected.values())`
- **Question**: Should we keep this? Without it, solver has no optimization goal.
- **Options**:
  - A) Keep it (maximize number of scheduled subjects)
  - B) Remove it (solver will find any feasible solution)

### 2. **Pack Term** (Line 1309)
- Prefer later start times
- `pack_term_expr = sum(var * s for ...)`
- **Status**: ❌ DISABLE - Soft preference

### 3. **Cluster Penalty** (Line 1310)
- Penalize subject-room cluster mismatches
- `cluster_penalty_expr = sum(...)`
- **Status**: ❌ DISABLE - Soft preference

### 4. **Lunch Fill** (Line 1311)
- Prefer classes ending near lunch time
- `lunch_fill_expr = sum(...)`
- **Status**: ❌ DISABLE - Soft preference

### 5. **Morning Bias** (Line 1312)
- Avoid early morning (7:30 AM), prefer closer to 12:00
- `morning_bias_expr = sum(...)`
- **Status**: ❌ DISABLE - Soft preference

### 6. **Tail Fill** (Line 1313)
- Encourage classes after 5:00 PM
- `tail_fill_expr = sum(...)`
- **Status**: ❌ DISABLE - Soft preference

### 7. **Gap Compression** (Line 1314)
- Fill trailing holes in schedule
- `gap_penalty_expr = sum(...)`
- **Status**: ❌ DISABLE - Soft preference

### 8. **Block Utilization** (Line 1336)
- Encourage utilization of block capacity
- `block_utilization_expr` (computed at line 1163)
- **Status**: ❌ DISABLE - Soft preference

## Proposed Changes

1. **Keep all hard constraints** (Groups 1-6 above)
2. **Disable all soft constraints** (Groups 2-8 above)
3. **Question for user**: What to do with primary objective (maximize scheduled subjects)?

## Options for Primary Objective

### Option A: Keep Primary Objective (Recommended)
- Keep `scheduled_sum` in objective
- Solver will maximize number of scheduled subjects
- Still finds feasible solutions, but optimizes for coverage

### Option B: Remove All Objectives
- Remove all objective terms
- Solver will find any feasible solution (first one found)
- Faster, but no optimization

### Option C: Simple Count Only
- Keep only `scheduled_sum`
- Remove all preference terms
- Pure maximization of scheduled subjects

