
-- ============================================================================
-- DATA VALIDATION QUERIES FOR TICKET MANAGEMENT SYSTEM
-- ============================================================================

-- Query 1: Verify all tickets have at least 2 messages
-- ============================================================================
SELECT 
    t.ticket_id,
    t.title,
    t.status,
    t.priority,
    COUNT(tm.message_id) as message_count,
    CASE 
        WHEN COUNT(tm.message_id) >= 2 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END as validation_status
FROM tickets t
LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
GROUP BY t.ticket_id, t.title, t.status, t.priority
ORDER BY t.ticket_id;


-- Query 2: Show all tickets with their message details
-- ============================================================================
SELECT 
    t.ticket_id,
    t.title,
    t.status,
    t.priority,
    tm.message_id,
    tm.author,
    tm.message_text,
    tm.created_at as message_created_at
FROM tickets t
LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
ORDER BY t.ticket_id, tm.created_at;


-- Query 3: Verify status changes are tracked in history
-- ============================================================================
SELECT 
    th.history_id,
    th.ticket_id,
    t.title,
    th.change_type,
    th.old_value,
    th.new_value,
    th.changed_by,
    th.changed_at
FROM ticket_history th
JOIN tickets t ON th.ticket_id = t.ticket_id
WHERE th.change_type = 'status'
ORDER BY th.changed_at DESC;


-- Query 4: Database integrity summary
-- ============================================================================
SELECT 
    'Total Tickets' as metric,
    COUNT(*)::text as value
FROM tickets

UNION ALL

SELECT 
    'Total Messages',
    COUNT(*)::text
FROM ticket_messages

UNION ALL

SELECT 
    'Total History Entries',
    COUNT(*)::text
FROM ticket_history

UNION ALL

SELECT 
    'Avg Messages Per Ticket',
    ROUND(AVG(message_count), 1)::text
FROM (
    SELECT ticket_id, COUNT(*) as message_count
    FROM ticket_messages
    GROUP BY ticket_id
) sub

UNION ALL

SELECT 
    'Tickets With <2 Messages',
    COUNT(*)::text
FROM (
    SELECT t.ticket_id, COUNT(tm.message_id) as cnt
    FROM tickets t
    LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
    GROUP BY t.ticket_id
    HAVING COUNT(tm.message_id) < 2
) sub;


-- Query 5: Find tickets with no messages (should return empty)
-- ============================================================================
SELECT 
    t.ticket_id,
    t.title,
    t.status,
    'WARNING: No messages' as issue
FROM tickets t
LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
GROUP BY t.ticket_id, t.title, t.status
HAVING COUNT(tm.message_id) = 0;


-- Query 6: Tag usage analysis
-- ============================================================================
SELECT 
    CASE 
        WHEN tags IS NULL OR tags = '' THEN '(no tags)'
        ELSE tags 
    END as tag_value,
    COUNT(*) as ticket_count
FROM tickets
GROUP BY tags
ORDER BY ticket_count DESC;


-- Query 7: Status distribution
-- ============================================================================
SELECT 
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
FROM tickets
GROUP BY status
ORDER BY count DESC;


-- Query 8: Priority distribution
-- ============================================================================
SELECT 
    priority,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
FROM tickets
GROUP BY priority
ORDER BY 
    CASE priority
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
    END;
