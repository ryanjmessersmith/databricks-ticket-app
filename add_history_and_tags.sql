-- Migration: Add ticket history tracking and tags support

-- 1. Create ticket_history table to track all changes
CREATE TABLE IF NOT EXISTS ticket_history (
    history_id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    change_type VARCHAR(50) NOT NULL,  -- 'status', 'priority', 'created', 'deleted'
    old_value VARCHAR(100),
    new_value VARCHAR(100),
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Add tags column to tickets table (comma-separated or JSON array)
ALTER TABLE tickets ADD COLUMN tags TEXT DEFAULT '';

-- 3. Create index for faster history queries
CREATE INDEX idx_ticket_history_ticket_id ON ticket_history(ticket_id);
CREATE INDEX idx_ticket_history_changed_at ON ticket_history(changed_at DESC);

-- 4. Add initial history entries for existing tickets (optional)
INSERT INTO ticket_history (ticket_id, change_type, new_value, changed_by, changed_at)
SELECT ticket_id, 'created', status, created_by, created_at
FROM tickets;

-- Verify tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name IN ('tickets', 'ticket_history', 'ticket_messages')
ORDER BY table_name;
