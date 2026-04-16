-- Add major column to courses table
ALTER TABLE courses ADD COLUMN IF NOT EXISTS major VARCHAR(200);
