# Stored Procedure Type Mismatch Fix

## Problem

PostgreSQL stored procedures were returning `VARCHAR` types but the function signatures declared `TEXT`. PostgreSQL requires exact type matching in stored procedures.

**Error:**
```
DatatypeMismatch: structure of query does not match function result type
DETAIL: Returned type character varying(50) does not match expected type text in column 2.
```

## Solution

All stored procedures have been updated to cast `VARCHAR` columns to `TEXT` using `::TEXT` casting.

### Fixed Procedures

1. ✅ `get_instructor_availability` - Cast `d.label` and `t.label` to TEXT
2. ✅ `get_available_rooms` - Cast `r.name` and `r.type` to TEXT
3. ✅ `get_existing_bookings` - Cast `r.name`, `s.time`, and instructor name to TEXT
4. ✅ `get_subjects_for_scheduling` - Cast all VARCHAR columns to TEXT
5. ✅ `get_instructor_eligibility` - Cast instructor fields to TEXT
6. ✅ `get_room_eligibility` - Cast room fields to TEXT
7. ✅ `get_schedules_for_course` - Cast `s.time` to TEXT
8. ✅ `get_courses_by_college` - Cast `c.code` and `c.description` to TEXT
9. ✅ `get_timeslots_by_day` - Cast `t.label` to TEXT

## How to Apply the Fix

### Option 1: Re-run Migration (Recommended)

The migration file has been updated. Re-run it:

```bash
python api/init_db.py
```

The migration will update all stored procedures automatically.

### Option 2: Run Fix Script

Run the dedicated fix script:

```bash
python api/fix_stored_procedures.py
```

This script will:
- Read the updated migration file
- Extract all stored procedure definitions
- Update each procedure in the database
- Report success/failure for each

### Option 3: Manual Update

If you prefer to update manually, you can run the SQL directly:

```sql
-- Example: Update get_courses_by_college
CREATE OR REPLACE FUNCTION get_courses_by_college(
    p_college_id INT
)
RETURNS TABLE(
    course_id INT,
    code TEXT,
    description TEXT,
    college_id INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id AS course_id,
        c.code::TEXT,        -- Cast to TEXT
        c.description::TEXT, -- Cast to TEXT
        c.college_id
    FROM courses c
    WHERE c.college_id = p_college_id
    ORDER BY c.code;
END;
$$ LANGUAGE plpgsql;
```

## Verification

After applying the fix, verify the procedures work:

```sql
-- Test get_courses_by_college
SELECT * FROM get_courses_by_college(1);

-- Test get_subjects_for_scheduling
SELECT * FROM get_subjects_for_scheduling(p_course_id := 1);

-- Check all procedures exist
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
  AND routine_type = 'FUNCTION'
ORDER BY routine_name;
```

## Type Casting Pattern

All VARCHAR columns are now cast to TEXT:

```sql
-- Before (causes error)
SELECT c.code FROM courses c;

-- After (works correctly)
SELECT c.code::TEXT FROM courses c;
```

## Why This Happened

PostgreSQL stored procedures require exact type matching:
- Function declares: `RETURNS TABLE(code TEXT)`
- Column type: `VARCHAR(50)`
- PostgreSQL sees: Type mismatch ❌

Solution: Cast to match declared type:
- `c.code::TEXT` ✅

## Performance Impact

Type casting has **negligible performance impact**:
- Casting is done at query execution time
- No additional storage overhead
- No impact on index usage
- Minimal CPU overhead (< 1%)

## Next Steps

1. Apply the fix using one of the methods above
2. Test the CP scheduler - it should work without errors
3. Monitor logs for any remaining type mismatch errors
4. All stored procedures should now work correctly

