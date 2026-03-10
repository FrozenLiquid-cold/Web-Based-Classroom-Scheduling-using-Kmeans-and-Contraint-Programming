-- Migration: Add subject_room_preferences join table
-- Allows registrars to configure which rooms a subject can use (replaces hardcoded PE room logic)

CREATE TABLE IF NOT EXISTS subject_room_preferences (
    id SERIAL PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    UNIQUE(subject_id, room_id)
);

CREATE INDEX IF NOT EXISTS idx_srp_subject ON subject_room_preferences(subject_id);
CREATE INDEX IF NOT EXISTS idx_srp_room ON subject_room_preferences(room_id);
