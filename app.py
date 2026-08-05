from flask import Flask, jsonify, render_template_string, request, redirect, url_for
from datetime import datetime
import lakebase

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    """Health check endpoint for Databricks Apps."""
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    """Home page - list all tickets with filtering, sorted by last message time."""
    try:
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        tag_filter = request.args.get('tag', 'all')
        
        # Base query with left join for messages
        base_query = """
            SELECT 
                t.ticket_id as id, 
                t.title, 
                t.status, 
                t.priority, 
                t.tags,
                t.created_by, 
                t.created_at,
                MAX(tm.created_at) as last_message_at
            FROM tickets t
            LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
        """
        
        # Build WHERE clause
        conditions = []
        params = []
        
        if status_filter != 'all':
            conditions.append("t.status = %s")
            params.append(status_filter)
        
        if tag_filter != 'all':
            conditions.append("t.tags LIKE %s")
            params.append(f'%{tag_filter}%')
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        query = f"""{base_query}
            {where_clause}
            GROUP BY t.ticket_id, t.title, t.status, t.priority, t.tags, t.created_by, t.created_at
            ORDER BY last_message_at NULLS FIRST, t.created_at DESC
        """
        
        tickets = lakebase.run_query(query, tuple(params)) if params else lakebase.run_query(query)
        
        # Get all unique tags for filter dropdown
        all_tags = set()
        for ticket in tickets:
            if ticket.get('tags'):
                tags = [t.strip() for t in ticket['tags'].split(',') if t.strip()]
                all_tags.update(tags)
        
        return render_template_string(HOME_TEMPLATE, 
                                     tickets=tickets, 
                                     status_filter=status_filter,
                                     tag_filter=tag_filter,
                                     all_tags=sorted(all_tags))
    except Exception as e:
        return f"<h1>Error loading tickets</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>')
def view_ticket(ticket_id):
    """View a single ticket with all messages and history."""
    try:
        tickets = lakebase.run_query("""
            SELECT ticket_id as id, title, status, priority, tags, created_by, created_at 
            FROM tickets 
            WHERE ticket_id = %s
        """, (ticket_id,))
        
        if not tickets:
            return "<h1>Ticket not found</h1>", 404
        
        ticket = tickets[0]
        
        # Parse tags
        ticket_tags = [t.strip() for t in (ticket.get('tags') or '').split(',') if t.strip()]
        
        messages = lakebase.run_query("""
            SELECT message_text as message, author, created_at 
            FROM ticket_messages 
            WHERE ticket_id = %s 
            ORDER BY created_at ASC
        """, (ticket_id,))
        
        # Get ticket history
        history = lakebase.run_query("""
            SELECT change_type, old_value, new_value, changed_by, changed_at
            FROM ticket_history
            WHERE ticket_id = %s
            ORDER BY changed_at DESC
        """, (ticket_id,))
        
        return render_template_string(TICKET_DETAIL_TEMPLATE, 
                                     ticket=ticket, 
                                     ticket_tags=ticket_tags,
                                     messages=messages,
                                     history=history)
    except Exception as e:
        return f"<h1>Error loading ticket</h1><p>{str(e)}</p>", 500

@app.route('/ticket/new', methods=['GET', 'POST'])
def new_ticket():
    """Create a new ticket."""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            created_by = request.form.get('created_by', 'Anonymous')
            priority = request.form.get('priority', 'medium')
            tags = request.form.get('tags', '').strip()
            
            with lakebase.get_connection() as conn:
                with conn.cursor() as cur:
                    # Insert ticket
                    cur.execute("""
                        INSERT INTO tickets (title, status, priority, tags, created_by) 
                        VALUES (%s, 'open', %s, %s, %s) 
                        RETURNING ticket_id
                    """, (title, priority, tags, created_by))
                    ticket_id = cur.fetchone()['ticket_id']
                    
                    # Log creation in history
                    cur.execute("""
                        INSERT INTO ticket_history (ticket_id, change_type, new_value, changed_by)
                        VALUES (%s, 'created', %s, %s)
                    """, (ticket_id, 'open', created_by))
                    
                    conn.commit()
            
            return redirect(url_for('view_ticket', ticket_id=ticket_id))
        except Exception as e:
            return f"<h1>Error creating ticket</h1><p>{str(e)}</p>", 500
    
    return render_template_string(NEW_TICKET_TEMPLATE)

@app.route('/ticket/<int:ticket_id>/message', methods=['POST'])
def add_message(ticket_id):
    """Add a message to a ticket."""
    try:
        message = request.form.get('message')
        author = request.form.get('author', 'Anonymous')
        lakebase.run_write("""
            INSERT INTO ticket_messages (ticket_id, message_text, author) 
            VALUES (%s, %s, %s)
        """, (ticket_id, message, author))
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error adding message</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>/status', methods=['POST'])
def update_status(ticket_id):
    """Update ticket status."""
    try:
        new_status = request.form.get('status')
        changed_by = request.form.get('changed_by', 'Anonymous')
        
        # Get old status
        tickets = lakebase.run_query("""
            SELECT status FROM tickets WHERE ticket_id = %s
        """, (ticket_id,))
        old_status = tickets[0]['status'] if tickets else None
        
        with lakebase.get_connection() as conn:
            with conn.cursor() as cur:
                # Update status
                cur.execute("""
                    UPDATE tickets 
                    SET status = %s 
                    WHERE ticket_id = %s
                """, (new_status, ticket_id))
                
                # Log change in history
                cur.execute("""
                    INSERT INTO ticket_history (ticket_id, change_type, old_value, new_value, changed_by)
                    VALUES (%s, 'status', %s, %s, %s)
                """, (ticket_id, old_status, new_status, changed_by))
                
                conn.commit()
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating status</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>/priority', methods=['POST'])
def update_priority(ticket_id):
    """Update ticket priority."""
    try:
        new_priority = request.form.get('priority')
        changed_by = request.form.get('changed_by', 'Anonymous')
        
        # Get old priority
        tickets = lakebase.run_query("""
            SELECT priority FROM tickets WHERE ticket_id = %s
        """, (ticket_id,))
        old_priority = tickets[0].get('priority') if tickets else None
        
        with lakebase.get_connection() as conn:
            with conn.cursor() as cur:
                # Update priority
                cur.execute("""
                    UPDATE tickets 
                    SET priority = %s 
                    WHERE ticket_id = %s
                """, (new_priority, ticket_id))
                
                # Log change in history
                cur.execute("""
                    INSERT INTO ticket_history (ticket_id, change_type, old_value, new_value, changed_by)
                    VALUES (%s, 'priority', %s, %s, %s)
                """, (ticket_id, old_priority, new_priority, changed_by))
                
                conn.commit()
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating priority</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>/tags', methods=['POST'])
def update_tags(ticket_id):
    """Update ticket tags."""
    try:
        tags = request.form.get('tags', '').strip()
        lakebase.run_write("""
            UPDATE tickets 
            SET tags = %s 
            WHERE ticket_id = %s
        """, (tags, ticket_id))
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating tags</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
def delete_ticket(ticket_id):
    """Delete a ticket."""
    try:
        deleted_by = request.form.get('deleted_by', 'Anonymous')
        
        with lakebase.get_connection() as conn:
            with conn.cursor() as cur:
                # Log deletion in history before deleting
                cur.execute("""
                    INSERT INTO ticket_history (ticket_id, change_type, changed_by)
                    VALUES (%s, 'deleted', %s)
                """, (ticket_id, deleted_by))
                
                # Delete ticket (CASCADE will handle messages and history)
                cur.execute("""
                    DELETE FROM tickets WHERE ticket_id = %s
                """, (ticket_id,))
                
                conn.commit()
        
        return redirect(url_for('home'))
    except Exception as e:
        return f"<h1>Error deleting ticket</h1><p>{str(e)}</p>", 500

# HTML Templates with Modern CSS
HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Support Tickets</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        h1 {
            font-size: 2rem;
            color: #1a1a1a;
            font-weight: 700;
        }
        
        .controls {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .filter-select {
            padding: 10px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .filter-select:hover {
            border-color: #667eea;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .ticket-grid {
            display: grid;
            gap: 16px;
        }
        
        .ticket-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            display: grid;
            grid-template-columns: 1fr auto auto auto;
            gap: 20px;
            align-items: center;
        }
        
        .ticket-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.1);
            border-color: #667eea;
        }
        
        .ticket-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #1a1a1a;
        }
        
        .ticket-title a {
            color: inherit;
            text-decoration: none;
            transition: color 0.2s;
        }
        
        .ticket-title a:hover {
            color: #667eea;
        }
        
        .ticket-tags {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 8px;
        }
        
        .tag {
            background: #e3f2fd;
            color: #1976d2;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .tag.bug { background: #ffebee; color: #c62828; }
        .tag.feature { background: #e8f5e9; color: #2e7d32; }
        .tag.question { background: #fff3e0; color: #e65100; }
        
        .priority-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .priority-low {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .priority-medium {
            background: #fff3e0;
            color: #e65100;
        }
        
        .priority-high {
            background: #ffebee;
            color: #c62828;
        }
        
        .status-badge {
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: capitalize;
        }
        
        .status-open {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-closed {
            background: #d4edda;
            color: #155724;
        }
        
        .status-in-progress {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        .ticket-meta {
            color: #6c757d;
            font-size: 0.9rem;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
    </style>
    <script>
        function updateFilters() {
            const status = document.getElementById('statusFilter').value;
            const tag = document.getElementById('tagFilter').value;
            window.location.href = `/?status=${status}&tag=${tag}`;
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Support Tickets</h1>
            <div class="controls">
                <select id="statusFilter" class="filter-select" onchange="updateFilters()">
                    <option value="all" {% if status_filter == 'all' %}selected{% endif %}>All Status</option>
                    <option value="open" {% if status_filter == 'open' %}selected{% endif %}>Open</option>
                    <option value="in-progress" {% if status_filter == 'in-progress' %}selected{% endif %}>In Progress</option>
                    <option value="closed" {% if status_filter == 'closed' %}selected{% endif %}>Closed</option>
                </select>
                
                <select id="tagFilter" class="filter-select" onchange="updateFilters()">
                    <option value="all" {% if tag_filter == 'all' %}selected{% endif %}>All Tags</option>
                    {% for tag in all_tags %}
                    <option value="{{ tag }}" {% if tag_filter == tag %}selected{% endif %}>{{ tag.capitalize() }}</option>
                    {% endfor %}
                </select>
                
                <a href="/ticket/new" class="btn">
                    <span>➕</span>
                    Create Ticket
                </a>
            </div>
        </div>
        
        <div class="ticket-grid">
            {% if tickets %}
                {% for ticket in tickets %}
                <div class="ticket-card">
                    <div>
                        <div class="ticket-title">
                            <a href="/ticket/{{ ticket.id }}">{{ ticket.title }}</a>
                        </div>
                        <div class="ticket-meta" style="margin-top: 4px;">{{ ticket.created_by }} • {{ ticket.created_at.strftime('%b %d, %Y') if ticket.created_at else 'N/A' }}</div>
                        {% if ticket.tags %}
                        <div class="ticket-tags">
                            {% for tag in ticket.tags.split(',') %}
                            {% set tag_name = tag.strip() %}
                            {% if tag_name %}
                            <span class="tag {{ tag_name.lower() }}">{{ tag_name.capitalize() }}</span>
                            {% endif %}
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                    <span class="priority-badge priority-{{ ticket.priority or 'medium' }}">{{ ticket.priority or 'medium' }}</span>
                    <span class="status-badge status-{{ ticket.status }}">{{ ticket.status }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <div style="font-size: 4rem; margin-bottom: 20px;">📭</div>
                    <h2 style="margin-bottom: 12px; color: #495057;">No tickets found</h2>
                    <p>Try adjusting your filters or create a new ticket</p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

TICKET_DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ticket: {{ ticket.title }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        h1 {
            font-size: 1.75rem;
            color: #1a1a1a;
            font-weight: 700;
            flex: 1;
        }
        
        .header-actions {
            display: flex;
            gap: 12px;
        }
        
        .back-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .back-link:hover {
            gap: 10px;
        }
        
        .btn-delete {
            background: #dc3545;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        
        .btn-delete:hover {
            background: #c82333;
        }
        
        .ticket-info {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 32px;
            border-left: 4px solid #667eea;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        
        .info-label {
            font-size: 0.85rem;
            color: #6c757d;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .info-value {
            font-size: 1.1rem;
            color: #1a1a1a;
            font-weight: 600;
        }
        
        .ticket-tags {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .tag {
            background: #e3f2fd;
            color: #1976d2;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .tag.bug { background: #ffebee; color: #c62828; }
        .tag.feature { background: #e8f5e9; color: #2e7d32; }
        .tag.question { background: #fff3e0; color: #e65100; }
        
        .tag-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .tag-button {
            background: white;
            border: 2px solid #e0e0e0;
            color: #495057;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tag-button:hover {
            border-color: #667eea;
        }
        
        .tag-button.active {
            border-color: transparent;
        }
        
        .tag-button.active.bug {
            background: #ffebee;
            color: #c62828;
        }
        
        .tag-button.active.feature {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .tag-button.active.question {
            background: #fff3e0;
            color: #e65100;
        }
        
        .priority-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
        }
        
        .priority-low {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .priority-medium {
            background: #fff3e0;
            color: #e65100;
        }
        
        .priority-high {
            background: #ffebee;
            color: #c62828;
        }
        
        .controls {
            display: flex;
            gap: 24px;
            align-items: center;
            padding-top: 20px;
            border-top: 1px solid rgba(0,0,0,0.1);
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .control-group select {
            padding: 8px 16px;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            background: white;
        }
        
        .control-group select:hover {
            border-color: #667eea;
        }
        
        .btn-small {
            background: #667eea;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        
        .btn-small:hover {
            background: #5568d3;
        }
        
        .messages-section, .history-section {
            margin-top: 32px;
        }
        
        h2 {
            font-size: 1.5rem;
            color: #1a1a1a;
            margin-bottom: 20px;
        }
        
        .message {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            border-left: 4px solid #667eea;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .message-author {
            font-weight: 700;
            color: #667eea;
            font-size: 1rem;
        }
        
        .message-time {
            color: #6c757d;
            font-size: 0.85rem;
        }
        
        .message-text {
            color: #495057;
            line-height: 1.6;
        }
        
        .history-entry {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            font-size: 0.9rem;
            color: #495057;
            border-left: 3px solid #6c757d;
        }
        
        .history-entry .change-type {
            font-weight: 600;
            color: #1a1a1a;
        }
        
        .history-entry .timestamp {
            color: #6c757d;
            font-size: 0.8rem;
            float: right;
        }
        
        .form-card {
            background: linear-gradient(135deg, #667eea08 0%, #764ba208 100%);
            border-radius: 12px;
            padding: 28px;
            margin-top: 24px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #495057;
        }
        
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: inherit;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 32px;
            border-radius: 8px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .empty-messages {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 15% auto;
            padding: 30px;
            border-radius: 12px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        
        .modal-buttons {
            display: flex;
            gap: 12px;
            margin-top: 24px;
            justify-content: flex-end;
        }
        
        .btn-cancel {
            background: #6c757d;
            color: white;
            padding: 10px 24px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
        }
    </style>
    <script>
        let selectedTags = new Set({{ ticket_tags | tojson }});
        
        function toggleTag(tagName) {
            const button = document.querySelector(`.tag-button[data-tag="${tagName}"]`);
            if (selectedTags.has(tagName)) {
                selectedTags.delete(tagName);
                button.classList.remove('active');
            } else {
                selectedTags.add(tagName);
                button.classList.add('active');
            }
            document.getElementById('tagsInput').value = Array.from(selectedTags).join(',');
        }
        
        function confirmDelete() {
            document.getElementById('deleteModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('deleteModal').style.display = 'none';
        }
        
        function submitDelete() {
            document.getElementById('deleteForm').submit();
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('deleteModal');
            if (event.target == modal) {
                closeModal();
            }
        }
        
        // Initialize active tags on load
        window.onload = function() {
            selectedTags.forEach(tag => {
                const button = document.querySelector(`.tag-button[data-tag="${tag}"]`);
                if (button) {
                    button.classList.add('active');
                }
            });
            document.getElementById('tagsInput').value = Array.from(selectedTags).join(',');
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 {{ ticket.title }}</h1>
            <div class="header-actions">
                <button onclick="confirmDelete()" class="btn-delete">🗑️ Delete</button>
                <a href="/" class="back-link">← Back</a>
            </div>
        </div>
        
        <div class="ticket-info">
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Status</span>
                    <span class="info-value" style="text-transform: capitalize;">{{ ticket.status }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Priority</span>
                    <span class="priority-badge priority-{{ ticket.priority or 'medium' }}">{{ ticket.priority or 'medium' }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Created By</span>
                    <span class="info-value">{{ ticket.created_by }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Created</span>
                    <span class="info-value">{{ ticket.created_at.strftime('%b %d, %Y %H:%M') if ticket.created_at else 'N/A' }}</span>
                </div>
            </div>
            
            <div class="info-item" style="margin-bottom: 20px;">
                <span class="info-label">Tags</span>
                <div class="ticket-tags">
                    {% if ticket_tags %}
                        {% for tag in ticket_tags %}
                        <span class="tag {{ tag.lower() }}">{{ tag.capitalize() }}</span>
                        {% endfor %}
                    {% else %}
                        <span style="color: #6c757d; font-size: 0.9rem;">No tags</span>
                    {% endif %}
                </div>
            </div>
            
            <div class="controls">
                <form method="POST" action="/ticket/{{ ticket.id }}/status" class="control-group">
                    <input type="hidden" name="changed_by" value="Anonymous">
                    <span class="info-label">Status:</span>
                    <select name="status" onchange="this.form.submit()">
                        <option value="open" {% if ticket.status == 'open' %}selected{% endif %}>Open</option>
                        <option value="in-progress" {% if ticket.status == 'in-progress' %}selected{% endif %}>In Progress</option>
                        <option value="closed" {% if ticket.status == 'closed' %}selected{% endif %}>Closed</option>
                    </select>
                </form>
                
                <form method="POST" action="/ticket/{{ ticket.id }}/priority" class="control-group">
                    <input type="hidden" name="changed_by" value="Anonymous">
                    <span class="info-label">Priority:</span>
                    <select name="priority" onchange="this.form.submit()">
                        <option value="low" {% if ticket.priority == 'low' %}selected{% endif %}>Low</option>
                        <option value="medium" {% if ticket.priority == 'medium' or not ticket.priority %}selected{% endif %}>Medium</option>
                        <option value="high" {% if ticket.priority == 'high' %}selected{% endif %}>High</option>
                    </select>
                </form>
            </div>
            
            <form method="POST" action="/ticket/{{ ticket.id }}/tags" style="margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(0,0,0,0.1);">
                <div style="margin-bottom: 12px;">
                    <span class="info-label">Edit Tags:</span>
                </div>
                <div class="tag-buttons">
                    <button type="button" class="tag-button bug" data-tag="bug" onclick="toggleTag('bug')">🐛 Bug</button>
                    <button type="button" class="tag-button feature" data-tag="feature" onclick="toggleTag('feature')">✨ Feature</button>
                    <button type="button" class="tag-button question" data-tag="question" onclick="toggleTag('question')">❓ Question</button>
                </div>
                <input type="hidden" id="tagsInput" name="tags" value="">
                <button type="submit" class="btn-small" style="margin-top: 12px;">Save Tags</button>
            </form>
        </div>
        
        <div class="history-section">
            <h2>📜 Ticket History</h2>
            {% if history %}
                {% for entry in history %}
                <div class="history-entry">
                    <span class="timestamp">{{ entry.changed_at.strftime('%b %d, %Y %H:%M') if entry.changed_at else 'N/A' }}</span>
                    <span class="change-type">{{ entry.change_type.title() }}:</span>
                    {% if entry.old_value and entry.new_value %}
                        changed from <strong>{{ entry.old_value }}</strong> to <strong>{{ entry.new_value }}</strong>
                    {% elif entry.new_value %}
                        set to <strong>{{ entry.new_value }}</strong>
                    {% else %}
                        {{ entry.change_type }}
                    {% endif %}
                    by {{ entry.changed_by }}
                </div>
                {% endfor %}
            {% else %}
                <p style="color: #6c757d; padding: 20px; text-align: center;">No history yet</p>
            {% endif %}
        </div>
        
        <div class="messages-section">
            <h2>💬 Messages</h2>
            {% if messages %}
                {% for msg in messages %}
                <div class="message">
                    <div class="message-header">
                        <span class="message-author">{{ msg.author }}</span>
                        <span class="message-time">{{ msg.created_at.strftime('%b %d, %Y %H:%M') if msg.created_at else 'N/A' }}</span>
                    </div>
                    <div class="message-text">{{ msg.message }}</div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-messages">
                    <div style="font-size: 3rem; margin-bottom: 12px;">💭</div>
                    <p>No messages yet. Be the first to comment!</p>
                </div>
            {% endif %}
            
            <form method="POST" action="/ticket/{{ ticket.id }}/message" class="form-card">
                <h3 style="margin-bottom: 20px; color: #1a1a1a;">Add a Message</h3>
                <div class="form-group">
                    <label>Your Name</label>
                    <input type="text" name="author" value="Anonymous" required>
                </div>
                <div class="form-group">
                    <label>Message</label>
                    <textarea name="message" rows="4" required placeholder="Type your message here..."></textarea>
                </div>
                <button type="submit" class="btn">Send Message</button>
            </form>
        </div>
    </div>
    
    <!-- Delete Confirmation Modal -->
    <div id="deleteModal" class="modal">
        <div class="modal-content">
            <h2 style="margin-bottom: 16px; color: #dc3545;">⚠️ Confirm Deletion</h2>
            <p style="margin-bottom: 24px; color: #495057;">
                Are you sure you want to delete this ticket? This action cannot be undone. 
                All messages and history will be permanently deleted.
            </p>
            <form id="deleteForm" method="POST" action="/ticket/{{ ticket.id }}/delete">
                <input type="hidden" name="deleted_by" value="Anonymous">
                <div class="modal-buttons">
                    <button type="button" onclick="closeModal()" class="btn-cancel">Cancel</button>
                    <button type="button" onclick="submitDelete()" class="btn-delete" style="padding: 10px 24px;">Delete Ticket</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

NEW_TICKET_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>New Ticket</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .container {
            max-width: 600px;
            width: 100%;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }
        
        .header {
            margin-bottom: 32px;
            text-align: center;
        }
        
        h1 {
            font-size: 2rem;
            color: #1a1a1a;
            font-weight: 700;
            margin-bottom: 12px;
        }
        
        .back-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        
        .back-link:hover {
            gap: 10px;
        }
        
        .form-group {
            margin-bottom: 24px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #495057;
            font-size: 0.95rem;
        }
        
        .help-text {
            font-size: 0.85rem;
            color: #6c757d;
            margin-top: 4px;
        }
        
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-family: inherit;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .form-group input:focus,
        .form-group select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .tag-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .tag-button {
            background: white;
            border: 2px solid #e0e0e0;
            color: #495057;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tag-button:hover {
            border-color: #667eea;
        }
        
        .tag-button.active {
            border-color: transparent;
        }
        
        .tag-button.active.bug {
            background: #ffebee;
            color: #c62828;
        }
        
        .tag-button.active.feature {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .tag-button.active.question {
            background: #fff3e0;
            color: #e65100;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 14px 0;
            border-radius: 10px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            font-size: 1.05rem;
            width: 100%;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .icon {
            font-size: 3rem;
            margin-bottom: 16px;
        }
    </style>
    <script>
        let selectedTags = new Set();
        
        function toggleTag(tagName) {
            const button = document.querySelector(`.tag-button[data-tag="${tagName}"]`);
            if (selectedTags.has(tagName)) {
                selectedTags.delete(tagName);
                button.classList.remove('active');
            } else {
                selectedTags.add(tagName);
                button.classList.add('active');
            }
            document.getElementById('tagsInput').value = Array.from(selectedTags).join(',');
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="icon">🎫</div>
            <h1>Create New Ticket</h1>
            <a href="/" class="back-link">← Back to list</a>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label>Your Name</label>
                <input type="text" name="created_by" value="Anonymous" required placeholder="Enter your name">
            </div>
            
            <div class="form-group">
                <label>Ticket Title</label>
                <input type="text" name="title" required placeholder="Brief description of your issue">
            </div>
            
            <div class="form-group">
                <label>Priority</label>
                <select name="priority" required>
                    <option value="low">Low</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Tags</label>
                <div class="tag-buttons">
                    <button type="button" class="tag-button bug" data-tag="bug" onclick="toggleTag('bug')">🐛 Bug</button>
                    <button type="button" class="tag-button feature" data-tag="feature" onclick="toggleTag('feature')">✨ Feature</button>
                    <button type="button" class="tag-button question" data-tag="question" onclick="toggleTag('question')">❓ Question</button>
                </div>
                <input type="hidden" id="tagsInput" name="tags" value="">
                <div class="help-text">Click to select multiple tags</div>
            </div>
            
            <button type="submit" class="btn">Create Ticket</button>
        </form>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    import os
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)
