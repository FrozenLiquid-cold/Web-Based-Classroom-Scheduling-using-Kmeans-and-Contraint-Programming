-- Migration 014: Add is_block_shared flag to subjects table
-- When true, all blocks of this subject share the same room and time,
-- with only the instructor differing per block (e.g., NSTP, PE).

ALTER TABLE subjects ADD COLUMN is_block_shared BOOLEAN NOT NULL DEFAULT FALSE;
