import psycopg2
from flask import Flask, jsonify, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# Lakebase connection parameters (tested and working)
DB_CONFIG = {
    'host': 'ep-divine-forest-d82jgu9t.database.us-east-2.cloud.databricks.com',
    'database': 'databricks_postgres',
    'user': 'student',
    'password': 'npg_qWNBumC13JhY',
    'port': 5432,
    'sslmode': 'require'
}

def get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(**DB_CONFIG)

@app.route('/healthz')
def healthz():
    """Health check endpoint for Databricks Apps."""
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    """Home page - list all tickets."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, status, priority, created_at 
            FROM tickets 
            ORDER BY created_at DESC
        """)
        tickets = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template_string(HOME_TEMPLATE, tickets=tickets)
    except Exception as e:
        return f"<h1>Error loading tickets</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>')
def view_ticket(ticket_id):
    """View a single ticket with all messages."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get ticket details
        cur.execute("""
            SELECT id, title, description, status, priority, created_at 
            FROM tickets 
            WHERE id = %s
        """, (ticket_id,))
        ticket = cur.fetchone()
        
        if not ticket:
            return "<h1>Ticket not found</h1>", 404
        
        # Get messages
        cur.execute("""
            SELECT message, created_at 
            FROM ticket_messages 
            WHERE ticket_id = %s 
            ORDER BY created_at ASC
        """, (ticket_id,))
        messages = cur.fetchall()
        
        cur.close()
        conn.close()
        
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
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO tickets (title, description, status, priority) 
                VALUES (%s, %s, 'open', %s) 
                RETURNING id
            """, (title, description, priority))
            ticket_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            
            return redirect(url_for('view_ticket', ticket_id=ticket_id))
        except Exception as e:
            return f"<h1>Error creating ticket</h1><p>{str(e)}</p>", 500
    
    return render_template_string(NEW_TICKET_TEMPLATE)

@app.route('/ticket/<int:ticket_id>/message', methods=['POST'])
def add_message(ticket_id):
    """Add a message to a ticket."""
    try:
        message = request.form.get('message')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ticket_messages (ticket_id, message) 
            VALUES (%s, %s)
        """, (ticket_id, message))
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error adding message</h1><p>{str(e)}</p>", 500

@app.route('/ticket/<int:ticket_id>/status', methods=['POST'])
def update_status(ticket_id):
    """Update ticket status."""
    try:
        status = request.form.get('status')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE tickets 
            SET status = %s 
            WHERE id = %s
        """, (status, ticket_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    except Exception as e:
        return f"<h1>Error updating status</h1><p>{str(e)}</p>", 500

# HTML Templates
HOME_TEMPLATE = '''
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
                <th>Priority</th>
                <th>Created</th>
            </tr>
        </thead>
        <tbody>
            {% for ticket in tickets %}
            <tr>
                <td>{{ ticket[0] }}</td>
                <td><a href="/ticket/{{ ticket[0] }}">{{ ticket[1] }}</a></td>
                <td class="status-{{ ticket[2] }}">{{ ticket[2] }}</td>
                <td>{{ ticket[3] }}</td>
                <td>{{ ticket[4].strftime('%Y-%m-%d %H:%M') if ticket[4] else 'N/A' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
'''

TICKET_DETAIL_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Ticket #{{ ticket[0] }}</title>
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
        <h1>🎫 Ticket #{{ ticket[0] }}: {{ ticket[1] }}</h1>
        <a href="/" style="text-decoration: none;">← Back to list</a>
    </div>
    
    <div class="ticket-info">
        <p><strong>Status:</strong> {{ ticket[3] }}</p>
        <p><strong>Priority:</strong> {{ ticket[4] }}</p>
        <p><strong>Created:</strong> {{ ticket[5].strftime('%Y-%m-%d %H:%M') if ticket[5] else 'N/A' }}</p>
        <p><strong>Description:</strong></p>
        <p>{{ ticket[2] }}</p>
        
        <form method="POST" action="/ticket/{{ ticket[0] }}/status" class="status-form">
            <label>Update Status:</label>
            <select name="status">
                <option value="open" {% if ticket[3] == 'open' %}selected{% endif %}>Open</option>
                <option value="in-progress" {% if ticket[3] == 'in-progress' %}selected{% endif %}>In Progress</option>
                <option value="closed" {% if ticket[3] == 'closed' %}selected{% endif %}>Closed</option>
            </select>
            <button type="submit" class="btn btn-secondary">Update</button>
        </form>
    </div>
    
    <div class="messages">
        <h2>💬 Messages</h2>
        {% for message in messages %}
        <div class="message">
            <p>{{ message[0] }}</p>
            <p class="message-time">{{ message[1].strftime('%Y-%m-%d %H:%M') if message[1] else 'N/A' }}</p>
        </div>
        {% endfor %}
        
        <form method="POST" action="/ticket/{{ ticket[0] }}/message">
            <div class="form-group">
                <label>Add Message:</label>
                <textarea name="message" rows="4" required></textarea>
            </div>
            <button type="submit" class="btn">Send Message</button>
        </form>
    </div>
</body>
</html>
'''

NEW_TICKET_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Create New Ticket</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; }
        .form-group { margin: 20px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: Arial, sans-serif; }
        .btn { background-color: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .btn:hover { background-color: #45a049; }
    </style>
</head>
<body>
    <h1>➕ Create New Ticket</h1>
    <a href="/">← Back to list</a>
    
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
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)