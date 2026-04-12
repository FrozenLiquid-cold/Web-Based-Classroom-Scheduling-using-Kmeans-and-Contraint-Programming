-- Migration 019: Fix unique constraints to support shared rooms/instructors across courses
-- 
-- Problem: Constraints excluded course_id, which prevented shared rooms (FIELD, GYM)
-- and NSTP instructors from being used by multiple courses at the same time.
-- NSTP is a mass activity where one instructor teaches multiple course groups
-- simultaneously in a shared venue like FIELD.
--
-- Fix: Add course_id to BOTH constraints. The CP scheduler itself enforces
-- real room and instructor non-overlap for non-shared/non-NSTP subjects.

-- Room constraint: add course_id
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_sy;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_block;
ALTER TABLE schedules ADD CONSTRAINT uq_room_time_sy
    UNIQUE (room_id, day_id, "time", year, semester, school_year, block, course_id);

-- Instructor constraint: add course_id
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_sy;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block;
ALTER TABLE schedules ADD CONSTRAINT uq_instructor_time_sy
    UNIQUE (instructor_id, day_id, "time", year, semester, school_year, block, course_id);

SELECT 'Migration 019 completed: Both constraints now include course_id' AS status;
