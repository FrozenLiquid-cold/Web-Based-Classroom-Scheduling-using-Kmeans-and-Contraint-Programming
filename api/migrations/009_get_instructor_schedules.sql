-- Migration: Add stored procedure for fetching instructor schedules
-- This procedure returns all schedules for an instructor in a single optimized query
-- Uses the idx_schedules_instructor_id index for fast lookups

CREATE OR REPLACE FUNCTION get_instructor_schedules(
    p_instructor_id INTEGER,
    p_semester INTEGER DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    subject_id INTEGER,
    instructor_id INTEGER,
    room_id INTEGER,
    day_id INTEGER,
    time VARCHAR,
    course_id INTEGER,
    year INTEGER,
    semester INTEGER,
    block VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id::INTEGER, 
        s.subject_id::INTEGER, 
        s.instructor_id::INTEGER, 
        s.room_id::INTEGER, 
        s.day_id::INTEGER, 
        s.time::VARCHAR, 
        s.course_id::INTEGER, 
        s.year::INTEGER, 
        s.semester::INTEGER, 
        s.block::VARCHAR
    FROM schedules s
    WHERE s.instructor_id = p_instructor_id
      AND (p_semester IS NULL OR s.semester = p_semester)
    ORDER BY s.course_id, s.semester, s.year, s.day_id, s.time;
END;
$$ LANGUAGE plpgsql;
