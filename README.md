# Support Ticket Management System

A Flask-based support ticket management application for Databricks Apps, powered by Lakebase (Databricks-managed Postgres).

## Features

- 📋 View all support tickets
- ➕ Create new tickets
- 💬 Add messages to tickets
- 🔄 Update ticket status (Open, In Progress, Closed)
- 🎯 Priority levels (Low, Medium, High)

## Prerequisites

- Databricks workspace with Apps V2 enabled
- Lakebase project with the following tables:
  - `tickets` (id, title, description, status, priority, created_at)
  - `ticket_messages` (id, ticket_id, message, created_at)

## Database Setup

Run these SQL commands in your Lakebase project to create the required tables:

```sql
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ticket_messages (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Deployment

1. **Update Database Credentials**: Edit `app.py` and update the `DB_CONFIG` dictionary with your Lakebase connection details.

2. **Create Databricks App**:
   - Go to Databricks workspace → Apps
   - Click "Create App"
   - Select this Git repository
   - Deploy

3. **Access the App**: Once deployed, click "Open App" to start managing tickets.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

The app will be available at `http://localhost:8080`

## File Structure

```
.
├── app.py              # Main Flask application
├── app.yaml            # Databricks App configuration
├── requirements.txt    # Python dependencies
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Health Check

The app includes a `/healthz` endpoint for Databricks Apps health checks.