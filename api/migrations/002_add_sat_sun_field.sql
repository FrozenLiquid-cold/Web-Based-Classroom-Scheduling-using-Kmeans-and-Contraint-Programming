-- Migration: Add Saturday, Sunday to days table and FIELD room
-- Run this migration to enable weekend scheduling and FIELD room

-- Add Saturday and Sunday to days table
INSERT INTO days (label) 
SELECT 'SAT' WHERE NOT EXISTS (SELECT 1 FROM days WHERE label = 'SAT');

INSERT INTO days (label) 
SELECT 'SUN' WHERE NOT EXISTS (SELECT 1 FROM days WHERE label = 'SUN');

-- Add FIELD room (type LEC since it's for NSTP which is typically lecture-style)
INSERT INTO rooms (name, type, capacity) 
SELECT 'FIELD', 'LEC', 100 WHERE NOT EXISTS (SELECT 1 FROM rooms WHERE name = 'FIELD');

-- Add time blocks for Saturday (8am - 9pm for flexibility)
-- First get the Saturday day_id
-- Note: This assumes the day_id for SAT was auto-generated
-- You may need to adjust the day_id value based on your actual data

-- For SQLite (common in dev environments):
-- Get Saturday day_id and insert time blocks

-- Add time blocks for SAT (same structure as other days)
-- These will be inserted with the Saturday day_id

SELECT 'Migration completed. Please verify:';
SELECT '- Days table should have SAT and SUN entries';
SELECT '- Rooms table should have FIELD entry';
