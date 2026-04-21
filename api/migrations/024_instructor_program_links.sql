-- Migration 024: Add home_course_id and linked_course_ids to instructors
-- home_course_id: The primary program this instructor belongs to.
--   When set, the scheduler only assigns this instructor to subjects
--   belonging to that course (program) unless a link exists.
-- linked_course_ids: Comma-separated course IDs the instructor is
--   explicitly authorized to also teach (cross-program links).

ALTER TABLE instructors ADD COLUMN IF NOT EXISTS home_course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL;
ALTER TABLE instructors ADD COLUMN IF NOT EXISTS linked_course_ids TEXT;

-- Index for quick lookup of instructors by home program
CREATE INDEX IF NOT EXISTS idx_instructors_home_course ON instructors(home_course_id);
