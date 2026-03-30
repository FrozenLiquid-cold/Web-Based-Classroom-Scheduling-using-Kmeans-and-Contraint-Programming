-- Migration: Add merge_tag column to schedules table
ALTER TABLE schedules ADD COLUMN merge_tag VARCHAR(200) NULL;
