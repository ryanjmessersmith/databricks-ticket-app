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
            SELECT id, title, description, status, priority, created_at 
            FROM tickets 
            WHERE id = %s
        """, (ticket_id,))
        
        if not tickets:
            return "<h1>Ticket not found</h1>", 404
        
        ticket = tickets[0]
        
        messages = lakebase.run_query("""
            SELECT message, created_at 
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
            description = request.form.get('description')
            priority = request.form.get('priority', 'medium')
            
            with lakebase.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO tickets (title, description, status, priority) 
                        VALUES (%s, %s, 'open', %s) 
                        RETURNING id
                    """, (title, description, priority))
                    ticket_id = cur.fetchone()['id']
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
        lakebase.run_write("""
            INSERT INTO ticket_messages (ticket_id, message) 
            VALUES (%s, %s)
        """, (ticket_id, message))
        
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
            WHERE id = %s
        """, (status, ticket_id))
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating status</h1><p>{str(e)}</p>", 500

# HTML Templates
HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Support Tickets</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .ticket-list { border-collapse: collapse; width: 100%; margin-top: 20px; }
        .ticket-list th, .ticket-list td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        .ticket-list th { background-color: #4CAF50; color: white; }
        .ticket-list tr:hover { background-color: #f5f5f5; }
        .btn { background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 20px; }
        .btn:hover { background-color: #45a049; }
        .status-open { color: #ff9800; font-weight: bold; }
        .status-closed { color: #4CAF50; font-weight: bold; }
        .status-in-progress { color: #2196F3; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🎫 Support Tickets</h1>
    <a href="/ticket/new" class="btn">➕ Create New Ticket</a>
    
    <table class="ticket-list">
        <thead>
            <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Status</th>
                <th>Created By</th>
                <th>Created</th>
            </tr>
        </thead>
        <tbody>
            {% for ticket in tickets %}
            <tr>
                <td>{{ ticket.id }}</td>
                <td><a href="/ticket/{{ ticket.id }}">{{ ticket.title }}</a></td>
                <td class="status-{{ ticket.status }}">{{ ticket.status }}</td>
                <td>{{ ticket.priority }}</td>
                <td>{{ ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else 'N/A' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

TICKET_DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ticket #{{ ticket.id }}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .ticket-info { background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .messages { margin-top: 30px; }
        .message { background: white; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 4px; }
        .message-time { color: #666; font-size: 0.9em; }
        .form-group { margin: 15px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: Arial, sans-serif; }
        .btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background-color: #45a049; }
        .btn-secondary { background-color: #2196F3; }
        .status-form { display: inline-block; margin-left: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎫 Ticket #{{ ticket.id }}: {{ ticket.title }}</h1>
        <a href="/" style="text-decoration: none;">← Back to list</a>
    </div>
    
    <div class="ticket-info">
        <p><strong>Status:</strong> {{ ticket.status }}</p>
        <p><strong>Priority:</strong> {{ ticket.priority }}</p>
        <p><strong>Created:</strong> {{ ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else 'N/A' }}</p>
        <p><strong>Description:</strong></p>
        <p>{{ ticket.description }}</p>
        
        <form method="POST" action="/ticket/{{ ticket.id }}/status" class="status-form">
            <label>Update Status:</label>
            <select name="status" onchange="this.form.submit()">
                <option value="open" {% if ticket.status == 'open' %}selected{% endif %}>Open</option>
                <option value="in-progress" {% if ticket.status == 'in-progress' %}selected{% endif %}>In Progress</option>
                <option value="closed" {% if ticket.status == 'closed' %}selected{% endif %}>Closed</option>
            </select>
        </form>
    </div>
    
    <div class="messages">
        <h2>Messages</h2>
        {% for msg in messages %}
        <div class="message">
            <div class="message-time">{{ msg.created_at.strftime('%Y-%m-%d %H:%M') if msg.created_at else 'N/A' }}</div>
            <p>{{ msg.message }}</p>
        </div>
        {% endfor %}
        
        <form method="POST" action="/ticket/{{ ticket.id }}/message">
            <div class="form-group">
                <label>Add Message:</label>
                <textarea name="message" rows="4" required></textarea>
            </div>
            <button type="submit" class="btn">Send Message</button>
        </form>
    </div>
</body>
</html>
"""

NEW_TICKET_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>New Ticket</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; }
        .form-group { margin: 20px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group textarea, .form-group select { 
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: Arial, sans-serif; 
        }
        .btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background-color: #45a049; }
    </style>
</head>
<body>
    <h1>➕ Create New Ticket</h1>
    <a href="/" style="text-decoration: none;">← Back to list</a>
    
    <form method="POST">
        <div class="form-group">
            <label>Title:</label>
            <input type="text" name="title" required>
        </div>
        
        <div class="form-group">
            <label>Description:</label>
            <textarea name="description" rows="6" required></textarea>
        </div>
        
        <div class="form-group">
            <label>Priority:</label>
            <select name="priority">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
            </select>
        </div>
        
        <button type="submit" class="btn">Create Ticket</button>
    </form>
</body>
</html>
"""

if __name__ == '__main__':
    import os
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)
