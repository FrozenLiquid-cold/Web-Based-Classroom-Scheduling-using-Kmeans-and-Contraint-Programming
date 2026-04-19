-- Migration 021: Add day_patterns table for configurable scheduling day patterns
CREATE TABLE IF NOT EXISTS day_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL,
    day_ids TEXT NOT NULL,           -- comma-separated day IDs e.g. "1,3"
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    applies_to VARCHAR(10) NOT NULL DEFAULT 'ALL'  -- 'LEC', 'LAB', or 'ALL'
);

-- Seed default patterns (M-W, T-TH, F)
-- Note: day IDs depend on your 'days' table. These assume M=1, T=2, W=3, TH=4, F=5
INSERT INTO day_patterns (name, day_ids, priority, is_active, applies_to)
SELECT 'M-W', 
       (SELECT id FROM days WHERE label='M') || ',' || (SELECT id FROM days WHERE label='W'),
       0, 1, 'ALL'
WHERE NOT EXISTS (SELECT 1 FROM day_patterns WHERE name='M-W');

INSERT INTO day_patterns (name, day_ids, priority, is_active, applies_to)
SELECT 'T-TH',
       (SELECT id FROM days WHERE label='T') || ',' || (SELECT id FROM days WHERE label='TH'),
       1, 1, 'ALL'
WHERE NOT EXISTS (SELECT 1 FROM day_patterns WHERE name='T-TH');

INSERT INTO day_patterns (name, day_ids, priority, is_active, applies_to)
SELECT 'F',
       CAST((SELECT id FROM days WHERE label='F') AS TEXT),
       2, 1, 'ALL'
WHERE NOT EXISTS (SELECT 1 FROM day_patterns WHERE name='F');
