-- Migration: Add school_year column to schedules table
-- School year format: "2025-2026" (string)

-- Add school_year column with default value
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS school_year VARCHAR(10) NOT NULL DEFAULT '2025-2026';

-- Update existing unique constraints to include school_year
-- Drop old constraints first (they may or may not exist depending on prior migrations)

-- Drop old room time constraint
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_room_time_block;

-- Drop old instructor time constraint  
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time;
ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block;

-- Recreate constraints with school_year included
-- Room: same room, day, time, year, semester, school_year, block cannot double-book
ALTER TABLE schedules ADD CONSTRAINT uq_room_time_sy
    UNIQUE (room_id, day_id, time, year, semester, school_year, block);

-- Instructor: same instructor, day, time, year, semester, school_year, block cannot conflict
ALTER TABLE schedules ADD CONSTRAINT uq_instructor_time_sy
    UNIQUE (instructor_id, day_id, time, year, semester, school_year, block);

-- Index for fast lookups by school_year
CREATE INDEX IF NOT EXISTS idx_schedules_school_year ON schedules (school_year);
