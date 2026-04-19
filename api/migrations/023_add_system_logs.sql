-- Migration 023: Add system_logs table
-- Tracks all system activities for the admin logs page

CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL DEFAULT 'INFO',
    category VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    "user" VARCHAR(100),
    detail TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs (category);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs (level);

-- Seed some initial log entries
INSERT INTO system_logs (level, category, action, "user", detail) VALUES
('INFO', 'system', 'migration', 'system', 'System logs table created — migration 023 applied.');
