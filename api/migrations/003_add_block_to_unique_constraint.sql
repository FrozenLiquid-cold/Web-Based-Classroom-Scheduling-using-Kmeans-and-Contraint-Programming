-- Migration: Add block to uq_room_time unique constraint
-- This allows multiple blocks (A, B, C, D) to share the same room/day/time
-- Required for NSTP where all blocks have the same Sunday 8-11am session in FIELD

-- Step 1: Drop the existing constraint
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_block;

-- Step 2: Create new constraint that includes block AND course_id
-- Now unique on (room_id, day_id, time, year, semester, block, course_id)
-- This allows different courses (IT, IS) to have NSTP at the same room/time/block
ALTER TABLE schedules ADD CONSTRAINT uq_room_time_block_course 
    UNIQUE (room_id, day_id, "time", year, semester, block, course_id);

-- Verify the change
SELECT 'Migration completed: uq_room_time_block replaced with uq_room_time_block_course (includes course_id)' AS status;
