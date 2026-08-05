-- Add priority column to tickets table
-- Run this command to enable priority functionality in the ticket app

ALTER TABLE tickets ADD COLUMN priority VARCHAR(10) DEFAULT 'medium';

-- Update any existing tickets to have medium priority
UPDATE tickets SET priority = 'medium' WHERE priority IS NULL;

-- Verify the column was added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'tickets'
ORDER BY ordinal_position;
