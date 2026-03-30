-- Migration 016: Fix unique constraints to properly prevent double-booking
-- The old constraints included course_id, which allowed the same room or
-- instructor to be double-booked across different courses at the same time.
-- 
-- We keep `block` because shared rooms (FIELD) legitimately host multiple
-- blocks simultaneously (Block A NSTP + Block B NSTP on the same Sunday).

-- Drop the old (flawed) constraints
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_block_course;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block_course;

-- Also drop any older constraint names in case they exist
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_block;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time;

-- Create corrected constraints: remove course_id, keep block
-- A room can only be used once per (day, time, year, semester, block)
ALTER TABLE schedules ADD CONSTRAINT uq_room_time_block
    UNIQUE (room_id, day_id, "time", year, semester, block);

-- An instructor can only teach once per (day, time, year, semester, block)
ALTER TABLE schedules ADD CONSTRAINT uq_instructor_time_block
    UNIQUE (instructor_id, day_id, "time", year, semester, block);

SELECT 'Migration 016 completed: Fixed room and instructor unique constraints (removed course_id, kept block)' AS status;
