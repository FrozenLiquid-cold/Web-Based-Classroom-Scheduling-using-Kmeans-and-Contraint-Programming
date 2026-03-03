-- Migration 013: Add is_shared flag to buildings table
-- A shared building allows multiple subjects to use its rooms at the same time
-- (no room/instructor conflict checks). Used for FIELD/GRANDSTAND rooms.

ALTER TABLE buildings ADD COLUMN is_shared BOOLEAN NOT NULL DEFAULT FALSE;
