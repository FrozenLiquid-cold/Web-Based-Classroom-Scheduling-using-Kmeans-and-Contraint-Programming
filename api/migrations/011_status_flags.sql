-- Add status flags for instructors and rooms
-- Instructors: is_active (default active)
-- Rooms: is_available (default available)

ALTER TABLE instructors ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1;
ALTER TABLE rooms ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT 1;
