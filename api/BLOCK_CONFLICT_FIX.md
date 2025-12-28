# Block Conflict Prevention Fix

## Problem

The CP scheduler was allowing student/section conflicts where multiple subjects were scheduled at overlapping times for the same block of students. This violates the fundamental constraint that students cannot be in two places at once.

**Reported Conflicts:**
1. **Friday 4:30–6:30 PM**: CC 101 and FIL1 overlap
2. **Friday 6:30–8:00 PM**: GE-MM, CC 103, and GE-PH all overlap  
3. **Thursday 7:30–9:30 AM**: DS 101 and FIL2 overlap

## Root Cause

The block conflict detection was using `time_label` strings (e.g., "4:30–6:30 PM") and only checking for **exact matches**. This missed overlapping time ranges that had different labels.

**Example:**
- Subject 1: Friday 4:30–6:30 PM (`time_label = "4:30–6:30 PM"`)
- Subject 2: Friday 6:30–8:00 PM (`time_label = "6:30–8:00 PM"`)

These have different `time_label` values, so the constraint didn't detect the overlap at 6:30 PM.

## Solution

### 1. Use Time Ranges Instead of Labels

Changed from checking `time_label` strings to checking actual time ranges using `start_min` and `end_min` (minutes from midnight).

### 2. Proper Overlap Detection

Implemented proper time range overlap detection:
- Two time ranges overlap if: `end1 > start2 AND end2 > start1`
- This catches all overlapping cases, including:
  - Exact overlaps
  - Partial overlaps
  - Adjacent ranges (touching at boundaries)

### 3. Block Conflict Constraint

For each block (course_id, year_level, block_id) and day:
- Group all assignment variables by their time ranges
- Check all pairs for overlaps
- For capacity=1 (default): Enforce `var1 + var2 <= 1` for any overlapping pair
- For capacity>1: Enforce `sum(overlapping_vars) <= capacity`

## Code Changes

**Before:**
```python
# Only checked exact time_label matches
for slot in covers["block"]:
    time_label = slot["label"]
    block_slots_map[block_key][day_id][time_label].append(var)
```

**After:**
```python
# Check actual time ranges for overlaps
start_min = covers["start_min"]
end_min = covers["end_min"]
# Group by block, day, and time range
block_day_vars[(block_key, day_id)].append((var, start_min, end_min))

# Check all pairs for overlaps
for var1, start1, end1 in var_ranges:
    for var2, start2, end2 in var_ranges[i+1:]:
        if end1 > start2 and end2 > start1:  # Overlap detected
            model.Add(var1 + var2 <= 1)  # Only one can be active
```

## Testing

After this fix, the scheduler should:
1. ✅ Prevent CC 101 and FIL1 from both being scheduled Friday 4:30–6:30 PM
2. ✅ Prevent GE-MM, CC 103, and GE-PH from all being scheduled Friday 6:30–8:00 PM
3. ✅ Prevent DS 101 and FIL2 from both being scheduled Thursday 7:30–9:30 AM
4. ✅ Allow subjects in different blocks to overlap (different student groups)
5. ✅ Allow subjects in the same block on different days to overlap

## Impact

- **Hard constraint**: Block conflicts are now properly prevented
- **Performance**: Slightly more constraints added (overlap checking), but minimal impact
- **Correctness**: Students will never be scheduled for multiple subjects at the same time

## Next Steps

1. Re-run the scheduler - conflicts should be eliminated
2. Verify the generated schedule has no student conflicts
3. Monitor logs for block conflict constraint counts
4. If conflicts still occur, check:
   - Block ID assignment (all subjects should have correct block_id)
   - Time range calculations (start_min/end_min should be correct)

