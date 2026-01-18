-- Migration: Add instructor teaching preferences columns
-- Adds preferred_start_time, preferred_end_time, and max_units to instructors table

-- Add preferred_start_time column
ALTER TABLE instructors ADD COLUMN IF NOT EXISTS preferred_start_time VARCHAR(10) NULL;

-- Add preferred_end_time column
ALTER TABLE instructors ADD COLUMN IF NOT EXISTS preferred_end_time VARCHAR(10) NULL;

-- Add max_units column
ALTER TABLE instructors ADD COLUMN IF NOT EXISTS max_units INTEGER NULL;
