-- Migration: Create swap_requests table for instructor schedule swap feature
-- Allows instructors to request swapping time/day/room with another instructor

CREATE TABLE IF NOT EXISTS swap_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- The schedule the requester wants to swap away
    requester_schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    -- The schedule the requester wants to get (from target instructor)
    target_schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    
    -- The instructors involved
    requester_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    
    -- Request details
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    rejection_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_swap_requests_requester ON swap_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_swap_requests_target ON swap_requests(target_id);
CREATE INDEX IF NOT EXISTS idx_swap_requests_status ON swap_requests(status);
