-- Migration: Add indexes for optimizing instructor-related queries
-- These indexes improve performance when loading instructor schedules, swap requests, etc.

-- Index on schedules.instructor_id for filtering schedules by instructor
CREATE INDEX IF NOT EXISTS idx_schedules_instructor_id ON schedules(instructor_id);

-- Composite index for common schedule queries (instructor + semester + year)
CREATE INDEX IF NOT EXISTS idx_schedules_instructor_semester_year ON schedules(instructor_id, semester, year);

-- Index on schedules.day_id for day-based filtering
CREATE INDEX IF NOT EXISTS idx_schedules_day_id ON schedules(day_id);

-- Index on schedules.room_id for room-based filtering
CREATE INDEX IF NOT EXISTS idx_schedules_room_id ON schedules(room_id);

-- Index on schedules.course_id for course-based filtering
CREATE INDEX IF NOT EXISTS idx_schedules_course_id ON schedules(course_id);

-- Composite index for schedule conflict checking (room + day + time)
CREATE INDEX IF NOT EXISTS idx_schedules_room_day_time ON schedules(room_id, day_id, time);

-- Composite index for instructor conflict checking (instructor + day + time)
CREATE INDEX IF NOT EXISTS idx_schedules_instructor_day_time ON schedules(instructor_id, day_id, time);

-- Index on instructors.college_id for filtering by college
CREATE INDEX IF NOT EXISTS idx_instructors_college_id ON instructors(college_id);

-- Index on instructors.username for login lookups
CREATE INDEX IF NOT EXISTS idx_instructors_username ON instructors(username);

-- Index on users.instructor_id for user-instructor lookups
CREATE INDEX IF NOT EXISTS idx_users_instructor_id ON users(instructor_id);

-- Index on swap_requests for target instructor (incoming requests)
CREATE INDEX IF NOT EXISTS idx_swap_requests_target_id ON swap_requests(target_id);

-- Index on swap_requests for requester (outgoing requests)
CREATE INDEX IF NOT EXISTS idx_swap_requests_requester_id ON swap_requests(requester_id);

-- Composite index for pending swap requests
CREATE INDEX IF NOT EXISTS idx_swap_requests_target_status ON swap_requests(target_id, status);
