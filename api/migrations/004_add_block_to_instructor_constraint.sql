-- Migration: Add block and course_id to uq_instructor_time unique constraint
-- This allows the same instructor to teach multiple blocks/courses at the same time
-- Required for NSTP where one instructor teaches all blocks/courses on Sunday 8-11am

-- Step 1: Drop the existing instructor constraint
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block;

-- Step 2: Create new constraint that includes block AND course_id
-- Now unique on (instructor_id, day_id, time, year, semester, block, course_id)
-- This allows different courses (IT, IS) to have NSTP with same instructor at same time
ALTER TABLE schedules ADD CONSTRAINT uq_instructor_time_block_course 
    UNIQUE (instructor_id, day_id, "time", year, semester, block, course_id);

-- Verify the change
SELECT 'Migration completed: uq_instructor_time_block replaced with uq_instructor_time_block_course (includes course_id)' AS status;
