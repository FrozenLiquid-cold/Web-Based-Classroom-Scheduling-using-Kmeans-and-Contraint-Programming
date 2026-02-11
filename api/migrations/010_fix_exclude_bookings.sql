-- Migration 010: Fix get_existing_bookings to support year-level exclusion
-- 
-- Problem: When scheduling Course 4 Year 1, the stored procedure excludes ALL
-- Course 4 bookings (including Year 2/3/4). This makes 98 room bookings invisible
-- to the scheduler, causing it to misestimate room availability.
--
-- Fix: Add p_exclude_years parameter so only the specific year levels being
-- rescheduled are excluded. Year 2/3/4 bookings remain visible as constraints.

DROP FUNCTION IF EXISTS "public"."get_existing_bookings"("p_semester" int4, "p_years" _int4, "p_exclude_course_id" int4);

CREATE OR REPLACE FUNCTION "public"."get_existing_bookings"(
    "p_semester" int4,
    "p_years" _int4 DEFAULT NULL::integer[],
    "p_exclude_course_id" int4 DEFAULT NULL::integer,
    "p_exclude_years" _int4 DEFAULT NULL::integer[]
)
RETURNS TABLE(
    "booking_type" text,
    "resource_id" int4,
    "resource_name" text,
    "day_id" int4,
    "time_label" text
) AS $BODY$
BEGIN
    RETURN QUERY
    -- Room bookings
    SELECT 
        'room'::TEXT AS booking_type,
        s.room_id AS resource_id,
        r.name::TEXT AS resource_name,
        s.day_id,
        s.time::TEXT AS time_label
    FROM schedules s
    INNER JOIN rooms r ON s.room_id = r.id
    WHERE s.semester = p_semester
      AND (p_years IS NULL OR s.year = ANY(p_years))
      -- Exclude only the specific course+year combination being rescheduled
      AND NOT (
          p_exclude_course_id IS NOT NULL
          AND s.course_id = p_exclude_course_id
          AND (p_exclude_years IS NULL OR s.year = ANY(p_exclude_years))
      )
      AND s.room_id IS NOT NULL
      AND s.day_id IS NOT NULL
      AND s.time IS NOT NULL
    
    UNION ALL
    
    -- Instructor bookings
    SELECT 
        'instructor'::TEXT AS booking_type,
        s.instructor_id AS resource_id,
        (i.first_name || ' ' || i.last_name)::TEXT AS resource_name,
        s.day_id,
        s.time::TEXT AS time_label
    FROM schedules s
    INNER JOIN instructors i ON s.instructor_id = i.id
    WHERE s.semester = p_semester
      AND (p_years IS NULL OR s.year = ANY(p_years))
      -- Exclude only the specific course+year combination being rescheduled
      AND NOT (
          p_exclude_course_id IS NOT NULL
          AND s.course_id = p_exclude_course_id
          AND (p_exclude_years IS NULL OR s.year = ANY(p_exclude_years))
      )
      AND s.instructor_id IS NOT NULL
      AND s.day_id IS NOT NULL
      AND s.time IS NOT NULL;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;
