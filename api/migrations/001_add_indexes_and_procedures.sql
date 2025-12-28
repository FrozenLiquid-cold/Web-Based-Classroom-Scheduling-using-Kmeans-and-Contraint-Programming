-- ============================================================================
-- PostgreSQL Database Optimization Migration
-- ============================================================================
-- This migration adds comprehensive indexes and stored procedures for
-- optimal query performance in the JRMSU Scheduler system.
--
-- Created: 2024
-- Purpose: Enforce PostgreSQL indexing and stored procedures for all
--          repeating queries as per optimization requirements.
-- ============================================================================

-- ============================================================================
-- SECTION 1: REMOVE REDUNDANT INDEXES
-- ============================================================================
-- Remove redundant indexes on primary keys (PK already creates an index)
-- SQLAlchemy may create these automatically, but they're redundant

DROP INDEX IF EXISTS ix_candidates_id;
DROP INDEX IF EXISTS ix_courses_id;
DROP INDEX IF EXISTS ix_days_id;
DROP INDEX IF EXISTS ix_instructors_id;
DROP INDEX IF EXISTS ix_rooms_id;
DROP INDEX IF EXISTS ix_schedules_id;
DROP INDEX IF EXISTS ix_subjects_id;
DROP INDEX IF EXISTS ix_timeslots_id;
DROP INDEX IF EXISTS ix_users_id;

-- ============================================================================
-- SECTION 2: INDEXES FOR FOREIGN KEYS
-- ============================================================================
-- Index all foreign key columns for faster JOIN operations

-- Users table
CREATE INDEX IF NOT EXISTS idx_users_instructor_id ON users(instructor_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Courses table
CREATE INDEX IF NOT EXISTS idx_courses_college_id ON courses(college_id);
CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code);
-- Note: year_level index - only create if column exists in courses table
-- CREATE INDEX IF NOT EXISTS idx_courses_year_level ON courses(year_level);
-- Optional composite for college + year filtering (if year_level exists)
-- CREATE INDEX IF NOT EXISTS idx_courses_college_year ON courses(college_id, year_level);

-- Instructors table
CREATE INDEX IF NOT EXISTS idx_instructors_college_id ON instructors(college_id);
CREATE INDEX IF NOT EXISTS idx_instructors_username ON instructors(username);

-- Subjects table
CREATE INDEX IF NOT EXISTS idx_subjects_course_id ON subjects(course_id);
CREATE INDEX IF NOT EXISTS idx_subjects_code ON subjects(code);
CREATE INDEX IF NOT EXISTS idx_subjects_type ON subjects(type);
CREATE INDEX IF NOT EXISTS idx_subjects_cluster ON subjects(cluster);
CREATE INDEX IF NOT EXISTS idx_subjects_year_level ON subjects(year_level);
CREATE INDEX IF NOT EXISTS idx_subjects_semester ON subjects(semester);
-- Note: block_id index - only create if column exists
-- CREATE INDEX IF NOT EXISTS idx_subjects_block_id ON subjects(block_id);
-- This index is commented out as block_id may not exist in all schema versions
-- Uncomment if your schema includes the block_id column

-- Composite indexes for common subject queries
CREATE INDEX IF NOT EXISTS idx_subjects_course_year_sem ON subjects(course_id, year_level, semester);
CREATE INDEX IF NOT EXISTS idx_subjects_course_cluster ON subjects(course_id, cluster);
CREATE INDEX IF NOT EXISTS idx_subjects_cluster_year_sem ON subjects(cluster, year_level, semester);

-- Rooms table
CREATE INDEX IF NOT EXISTS idx_rooms_type ON rooms(type);
CREATE INDEX IF NOT EXISTS idx_rooms_capacity ON rooms(capacity);
CREATE INDEX IF NOT EXISTS idx_rooms_cluster ON rooms(cluster);
CREATE INDEX IF NOT EXISTS idx_rooms_type_capacity ON rooms(type, capacity);

-- Timeslots table
CREATE INDEX IF NOT EXISTS idx_timeslots_day ON timeslots(day);
CREATE INDEX IF NOT EXISTS idx_timeslots_start_min ON timeslots(start_min);
CREATE INDEX IF NOT EXISTS idx_timeslots_end_min ON timeslots(end_min);
CREATE INDEX IF NOT EXISTS idx_timeslots_day_start ON timeslots(day, start_min);

-- Candidates table
CREATE INDEX IF NOT EXISTS idx_candidates_course_id ON candidates(course_id);
CREATE INDEX IF NOT EXISTS idx_candidates_room_id ON candidates(room_id);
CREATE INDEX IF NOT EXISTS idx_candidates_timeslot_id ON candidates(timeslot_id);
CREATE INDEX IF NOT EXISTS idx_candidates_semester ON candidates(semester);
CREATE INDEX IF NOT EXISTS idx_candidates_year ON candidates(year);
CREATE INDEX IF NOT EXISTS idx_candidates_course_sem_year ON candidates(course_id, semester, year);

-- Schedules table (most critical for scheduling queries)
CREATE INDEX IF NOT EXISTS idx_schedules_subject_id ON schedules(subject_id);
CREATE INDEX IF NOT EXISTS idx_schedules_instructor_id ON schedules(instructor_id);
CREATE INDEX IF NOT EXISTS idx_schedules_room_id ON schedules(room_id);
CREATE INDEX IF NOT EXISTS idx_schedules_course_id ON schedules(course_id);
CREATE INDEX IF NOT EXISTS idx_schedules_day_id ON schedules(day_id);
CREATE INDEX IF NOT EXISTS idx_schedules_year ON schedules(year);
CREATE INDEX IF NOT EXISTS idx_schedules_semester ON schedules(semester);
CREATE INDEX IF NOT EXISTS idx_schedules_time ON schedules(time);

-- Composite indexes for common schedule queries
CREATE INDEX IF NOT EXISTS idx_schedules_course_year_sem ON schedules(course_id, year, semester);
CREATE INDEX IF NOT EXISTS idx_schedules_room_day_time ON schedules(room_id, day_id, time);
CREATE INDEX IF NOT EXISTS idx_schedules_instructor_day_time ON schedules(instructor_id, day_id, time);
CREATE INDEX IF NOT EXISTS idx_schedules_day_time ON schedules(day_id, time);
CREATE INDEX IF NOT EXISTS idx_schedules_semester_year ON schedules(semester, year);
CREATE INDEX IF NOT EXISTS idx_schedules_course_semester ON schedules(course_id, semester);
-- CRITICAL: Most common query pattern - conflict checking by semester + day + time
-- This index significantly reduces CP input lookup time for conflict detection
CREATE INDEX IF NOT EXISTS idx_schedules_sem_day_time ON schedules(semester, day_id, time);

-- ============================================================================
-- SECTION 3: STORED PROCEDURES FOR COMMON QUERIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Procedure: get_instructor_availability
-- Purpose: Get available time slots for an instructor (excluding booked slots)
-- Used by: CP scheduler for instructor availability checks
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_instructor_availability(
    instr_id INT,
    p_semester INT,
    p_year INT DEFAULT NULL
)
RETURNS TABLE(
    day_id INT,
    day_label TEXT,
    time_label TEXT,
    start_min INT,
    end_min INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id AS day_id,
        d.label::TEXT AS day_label,
        t.label::TEXT AS time_label,
        t.start_min,
        t.end_min
    FROM timeslots t
    INNER JOIN days d ON t.day = d.id
    WHERE NOT EXISTS (
        SELECT 1
        FROM schedules s
        WHERE s.instructor_id = instr_id
          AND s.day_id = d.id
          AND s.time = t.label
          AND s.semester = p_semester
          AND (p_year IS NULL OR s.year = p_year)
    )
    ORDER BY d.id, t.start_min;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_available_rooms
-- Purpose: Get available rooms filtered by type and capacity
-- Used by: CP scheduler for room eligibility checks
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_available_rooms(
    p_type TEXT,
    p_min_capacity INT DEFAULT NULL,
    p_semester INT DEFAULT NULL,
    p_year INT DEFAULT NULL,
    p_day_id INT DEFAULT NULL,
    p_time_label TEXT DEFAULT NULL
)
RETURNS TABLE(
    room_id INT,
    room_name TEXT,
    room_type TEXT,
    capacity INT,
    cluster INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id AS room_id,
        r.name::TEXT AS room_name,
        r.type::TEXT AS room_type,
        r.capacity,
        r.cluster
    FROM rooms r
    WHERE r.type = p_type
      AND (p_min_capacity IS NULL OR r.capacity >= p_min_capacity)
      AND (
          -- If checking availability for specific time slot
          p_semester IS NULL OR p_day_id IS NULL OR p_time_label IS NULL OR
          NOT EXISTS (
              SELECT 1
              FROM schedules s
              WHERE s.room_id = r.id
                AND s.day_id = p_day_id
                AND s.time = p_time_label
                AND s.semester = p_semester
                AND (p_year IS NULL OR s.year = p_year)
          )
      )
    ORDER BY r.capacity DESC, r.id;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_existing_bookings
-- Purpose: Get all existing room and instructor bookings for conflict checking
-- Used by: CP scheduler to avoid double-booking
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_existing_bookings(
    p_semester INT,
    p_years INT[] DEFAULT NULL,
    p_exclude_course_id INT DEFAULT NULL
)
RETURNS TABLE(
    booking_type TEXT,
    resource_id INT,
    resource_name TEXT,
    day_id INT,
    time_label TEXT
)
AS $$
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
      AND (p_exclude_course_id IS NULL OR s.course_id != p_exclude_course_id)
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
      AND (p_exclude_course_id IS NULL OR s.course_id != p_exclude_course_id)
      AND s.instructor_id IS NOT NULL
      AND s.day_id IS NOT NULL
      AND s.time IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_subjects_for_scheduling
-- Purpose: Get subjects for CP solver with all necessary filters
-- Used by: CP scheduler to load subjects efficiently
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_subjects_for_scheduling(
    p_course_id INT DEFAULT NULL,
    p_college_id INT DEFAULT NULL,
    p_cluster_id INT DEFAULT NULL,
    p_subject_ids INT[] DEFAULT NULL,
    p_year_level INT DEFAULT NULL,
    p_semester INT DEFAULT NULL
)
RETURNS TABLE(
    subject_id INT,
    course_id INT,
    code TEXT,
    description TEXT,
    type TEXT,
    unit INT,
    recommended_slots INT,
    cluster INT,
    min_slots INT,
    max_slots INT,
    year_level INT,
    semester INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id AS subject_id,
        s.course_id,
        s.code::TEXT,
        s.description::TEXT,
        s.type::TEXT,
        s.unit,
        s.recommended_slots,
        s.cluster,
        s.min_slots,
        s.max_slots,
        s.year_level,
        s.semester
    FROM subjects s
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE (p_course_id IS NULL OR s.course_id = p_course_id)
      AND (p_college_id IS NULL OR c.college_id = p_college_id)
      AND (p_cluster_id IS NULL OR s.cluster = p_cluster_id)
      AND (p_subject_ids IS NULL OR s.id = ANY(p_subject_ids))
      AND (p_year_level IS NULL OR s.year_level = p_year_level)
      AND (p_semester IS NULL OR s.semester = p_semester)
    ORDER BY s.id;
END;
$$ LANGUAGE plpgsql;



-- ----------------------------------------------------------------------------
-- Procedure: get_instructor_eligibility
-- Purpose: Get instructors eligible to teach a subject based on college/course matching
-- Used by: CP scheduler to build eligibility maps
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_instructor_eligibility(
    p_subject_id INT
)
RETURNS TABLE(
    instructor_id INT,
    first_name TEXT,
    last_name TEXT,
    college_id INT,
    assignable_courses TEXT
)
AS $$
DECLARE
    v_subject_course_id INT;
    v_subject_college_id INT;
    v_subject_code TEXT;
BEGIN
    -- Get subject details
    SELECT s.course_id, c.college_id, s.code
    INTO v_subject_course_id, v_subject_college_id, v_subject_code
    FROM subjects s
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE s.id = p_subject_id;
    
    RETURN QUERY
    SELECT 
        i.id AS instructor_id,
        i.first_name::TEXT,
        i.last_name::TEXT,
        i.college_id,
        i.assignable_courses::TEXT
    FROM instructors i
    WHERE (
        -- Match by college
        (v_subject_college_id IS NOT NULL AND i.college_id = v_subject_college_id)
        OR
        -- Match by assignable_courses (comma-separated list)
        (i.assignable_courses IS NOT NULL AND 
         v_subject_code IS NOT NULL AND
         UPPER(TRIM(v_subject_code)) = ANY(
             SELECT UPPER(TRIM(unnest(string_to_array(i.assignable_courses, ','))))
         ))
        OR
        -- Fallback: no restrictions
        (v_subject_college_id IS NULL AND i.college_id IS NULL AND i.assignable_courses IS NULL)
    )
    ORDER BY i.id;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_room_eligibility
-- Purpose: Get rooms eligible for a subject based on type matching
-- Used by: CP scheduler to build eligibility maps
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_room_eligibility(
    p_subject_id INT,
    p_min_capacity INT DEFAULT NULL
)
RETURNS TABLE(
    room_id INT,
    room_name TEXT,
    room_type TEXT,
    capacity INT,
    cluster INT
)
AS $$
DECLARE
    v_subject_type TEXT;
BEGIN
    -- Get subject type
    SELECT s.type INTO v_subject_type
    FROM subjects s
    WHERE s.id = p_subject_id;
    
    RETURN QUERY
    SELECT 
        r.id AS room_id,
        r.name::TEXT AS room_name,
        r.type::TEXT AS room_type,
        r.capacity,
        r.cluster
    FROM rooms r
    WHERE r.type = v_subject_type
      AND (p_min_capacity IS NULL OR r.capacity >= p_min_capacity)
    ORDER BY r.capacity DESC, r.id;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_schedules_for_course
-- Purpose: Load schedules for a course with optional filters
-- Used by: Schedule loading endpoints
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_schedules_for_course(
    p_course_id INT,
    p_semester INT,
    p_year INT DEFAULT NULL,
    p_instructor_id INT DEFAULT NULL
)
RETURNS TABLE(
    schedule_id INT,
    subject_id INT,
    instructor_id INT,
    room_id INT,
    day_id INT,
    time_label TEXT,
    course_id INT,
    year INT,
    semester INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id AS schedule_id,
        s.subject_id,
        s.instructor_id,
        s.room_id,
        s.day_id,
        s.time::TEXT AS time_label,
        s.course_id,
        s.year,
        s.semester
    FROM schedules s
    WHERE s.course_id = p_course_id
      AND s.semester = p_semester
      AND (p_year IS NULL OR s.year = p_year)
      AND (p_instructor_id IS NULL OR s.instructor_id = p_instructor_id)
    ORDER BY s.year NULLS LAST, s.day_id, s.time;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_courses_by_college
-- Purpose: Get all courses for a college
-- Used by: CP scheduler for college-wide scheduling
-- ----------------------------------------------------------------------------
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
        c.code::TEXT,
        c.description::TEXT,
        c.college_id
    FROM courses c
    WHERE c.college_id = p_college_id
    ORDER BY c.code;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Procedure: get_timeslots_by_day
-- Purpose: Get all time slots for a specific day
-- Used by: CP scheduler for time slot generation
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_timeslots_by_day(
    p_day_id INT
)
RETURNS TABLE(
    timeslot_id INT,
    label TEXT,
    day INT,
    start_min INT,
    end_min INT
)
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id AS timeslot_id,
        t.label::TEXT,
        t.day,
        t.start_min,
        t.end_min
    FROM timeslots t
    WHERE t.day = p_day_id
    ORDER BY t.start_min;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 4: PERFORMANCE ANALYSIS
-- ============================================================================
-- Run ANALYZE to update statistics for query planner
ANALYZE users;
ANALYZE colleges;
ANALYZE courses;
ANALYZE instructors;
ANALYZE days;
ANALYZE subjects;
ANALYZE rooms;
ANALYZE timeslots;
ANALYZE candidates;
ANALYZE schedules;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================

