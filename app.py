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
    """Home page - list all tickets."""
    try:
        tickets = lakebase.run_query("""
            SELECT ticket_id as id, title, status, created_by, created_at 
            FROM tickets 
            ORDER BY created_at DESC
        """)
        return render_template_string(HOME_TEMPLATE, tickets=tickets)
    except Exception as e:
        return f"<h1>Error loading tickets</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>')
def view_ticket(ticket_id):
    """View a single ticket with all messages."""
    try:
        tickets = lakebase.run_query("""
            SELECT ticket_id as id, title, status, created_by, created_at 
            FROM tickets 
            WHERE ticket_id = %s
        """, (ticket_id,))
        
        if not tickets:
            return "<h1>Ticket not found</h1>", 404
        
        ticket = tickets[0]
        
        messages = lakebase.run_query("""
            SELECT message_text as message, author, created_at 
            FROM ticket_messages 
            WHERE ticket_id = %s 
            ORDER BY created_at ASC
        """, (ticket_id,))
        
        return render_template_string(TICKET_DETAIL_TEMPLATE, ticket=ticket, messages=messages)
    except Exception as e:
        return f"<h1>Error loading ticket</h1><p>{str(e)}</p>", 500

@app.route('/ticket/new', methods=['GET', 'POST'])
def new_ticket():
    """Create a new ticket."""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            created_by = request.form.get('created_by', 'Anonymous')
            
            with lakebase.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO tickets (title, status, created_by) 
                        VALUES (%s, 'open', %s) 
                        RETURNING ticket_id
                    """, (title, created_by))
                    ticket_id = cur.fetchone()['ticket_id']
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
        status = request.form.get('status')
        lakebase.run_write("""
            UPDATE tickets 
            SET status = %s 
            WHERE ticket_id = %s
        """, (status, ticket_id))
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating status</h1><p>{str(e)}</p>", 500

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
            grid-template-columns: auto 1fr auto auto auto;
            gap: 20px;
            align-items: center;
        }
        
        .ticket-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.1);
            border-color: #667eea;
        }
        
        .ticket-id {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.1rem;
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
        
        .empty-state svg {
            width: 120px;
            height: 120px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Support Tickets</h1>
            <a href="/ticket/new" class="btn">
                <span>➕</span>
                Create Ticket
            </a>
        </div>
        
        <div class="ticket-grid">
            {% if tickets %}
                {% for ticket in tickets %}
                <div class="ticket-card">
                    <div class="ticket-id">#{{ ticket.id }}</div>
                    <div class="ticket-title">
                        <a href="/ticket/{{ ticket.id }}">{{ ticket.title }}</a>
                    </div>
                    <span class="status-badge status-{{ ticket.status }}">{{ ticket.status }}</span>
                    <div class="ticket-meta">{{ ticket.created_by }}</div>
                    <div class="ticket-meta">{{ ticket.created_at.strftime('%b %d, %Y') if ticket.created_at else 'N/A' }}</div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <div style="font-size: 4rem; margin-bottom: 20px;">📭</div>
                    <h2 style="margin-bottom: 12px; color: #495057;">No tickets yet</h2>
                    <p>Create your first support ticket to get started</p>
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
    <title>Ticket #{{ ticket.id }}</title>
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
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        h1 {
            font-size: 1.75rem;
            color: #1a1a1a;
            font-weight: 700;
        }
        
        .back-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        
        .back-link:hover {
            gap: 10px;
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
        
        .status-selector {
            display: flex;
            align-items: center;
            gap: 12px;
            padding-top: 20px;
            border-top: 1px solid rgba(0,0,0,0.1);
        }
        
        .status-selector select {
            padding: 8px 16px;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            background: white;
        }
        
        .status-selector select:hover {
            border-color: #667eea;
        }
        
        .messages-section {
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Ticket #{{ ticket.id }}: {{ ticket.title }}</h1>
            <a href="/" class="back-link">← Back to list</a>
        </div>
        
        <div class="ticket-info">
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Status</span>
                    <span class="info-value" style="text-transform: capitalize;">{{ ticket.status }}</span>
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
            
            <form method="POST" action="/ticket/{{ ticket.id }}/status" class="status-selector">
                <span class="info-label">Update Status:</span>
                <select name="status" onchange="this.form.submit()">
                    <option value="open" {% if ticket.status == 'open' %}selected{% endif %}>Open</option>
                    <option value="in-progress" {% if ticket.status == 'in-progress' %}selected{% endif %}>In Progress</option>
                    <option value="closed" {% if ticket.status == 'closed' %}selected{% endif %}>Closed</option>
                </select>
            </form>
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
        
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-family: inherit;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
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
