# 🎫 Support Ticket Management System

A modern, full-featured support ticket management application built with Flask and PostgreSQL (Lakebase), deployed as a Databricks App.

![Databricks](https://img.shields.io/badge/Databricks-Apps-FF3621?logo=databricks)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Lakebase-336791?logo=postgresql)
![Flask](https://img.shields.io/badge/Flask-2.3-000000?logo=flask)

## ✨ Features

### Core Functionality
* 📋 **Ticket Management** - Create, view, update, and delete support tickets
* 💬 **Messaging System** - Thread-based conversations on each ticket
* 🔄 **Status Tracking** - Open, In Progress, Closed
* 🎯 **Priority Levels** - Low, Medium, High with visual badges
* 🏷️ **Tag System** - Categorize tickets (Bug, Feature, Question) with toggle buttons
* 📜 **Audit History** - Complete change log for status, priority, and deletion events
* 🗑️ **Soft Delete** - Delete tickets with confirmation modal

### UI/UX
* 🎨 Modern responsive design with gradient backgrounds
* 📱 Mobile-friendly card-based layout
* 🔍 Filter by status and tags
* 🔝 Smart sorting (unattended tickets first)
* 🎨 Color-coded badges for status, priority, and tags

## 🏗️ Architecture

### Tech Stack
* **Backend**: Flask 2.3
* **Database**: PostgreSQL (Databricks Lakebase)
* **Frontend**: HTML5 with embedded CSS/JavaScript
* **Deployment**: Databricks Apps V2
* **Connection**: psycopg2 with custom lakebase module

### Database Schema

```sql
-- Tickets table
CREATE TABLE tickets (
    ticket_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    tags TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table
CREATE TABLE ticket_messages (
    message_id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- History/audit table
CREATE TABLE ticket_history (
    history_id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🚀 Setup & Deployment

### Prerequisites
* Databricks workspace with Apps V2 enabled
* Lakebase Postgres project
* Git repository (connected to workspace)

### Database Setup

1. **Create tables** - Run the SQL schema above in your Lakebase Postgres database

2. **Apply migrations** (if needed):
   ```sql
   -- Add priority column (if upgrading from older version)
   ALTER TABLE tickets ADD COLUMN priority TEXT DEFAULT 'medium';
   
   -- Add tags column
   ALTER TABLE tickets ADD COLUMN tags TEXT;
   
   -- Create history table (see schema above)
   ```

   Or use the provided migration files:
   * `add_priority_column.sql`
   * `add_history_and_tags.sql`

### Secret Configuration

Store your database connection URL in Databricks secrets:

```bash
# The lakebase.py module expects:
# Scope: database
# Key: lakebase-url
# Value: postgresql://user:password@host:5432/databricks_postgres?sslmode=require

databricks secrets put-secret database lakebase-url --string-value "postgresql://..."
```

### Deploy to Databricks Apps

1. **Commit your code** to the Git repository
   ```bash
   git add .
   git commit -m "Deploy ticket app"
   git push
   ```

2. **Create the app** (first time only):
   ```bash
   databricks apps create ticket-service-app \
     --source-code-path /Workspace/Users/<your-email>/databricks-ticket-app
   ```

3. **Deploy updates**:
   ```bash
   databricks apps deploy ticket-service-app \
     --source-code-path /Workspace/Users/<your-email>/databricks-ticket-app
   ```

4. **Check status**:
   ```bash
   databricks apps get ticket-service-app
   ```

## 📂 Project Structure

```
databricks-ticket-app/
├── app.py                        # Main Flask application
├── app.yaml                      # Databricks App configuration
├── lakebase.py                   # PostgreSQL connection helper
├── requirements.txt              # Python dependencies
├── validation_queries.sql        # Data validation queries
├── add_priority_column.sql       # Migration: add priority
├── add_history_and_tags.sql      # Migration: add history & tags
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## 🔌 Database Connection

### Using the lakebase Module

The `lakebase.py` module provides a simple interface to your PostgreSQL database:

```python
import lakebase

# Read data
tickets = lakebase.run_query(
    "SELECT * FROM tickets WHERE status = %s",
    ('open',)
)

# Write data
rows_affected = lakebase.run_write(
    "UPDATE tickets SET status = %s WHERE ticket_id = %s",
    ('closed', 5)
)

# Context manager for transactions
with lakebase.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickets ...")
        conn.commit()
```

### Important: PostgreSQL vs Spark SQL

⚠️ **Common Mistake**: Your `tickets` tables are in **PostgreSQL**, not Unity Catalog.

```python
# ✅ CORRECT - Use lakebase module
import lakebase
tickets = lakebase.run_query("SELECT * FROM tickets")

# ❌ WRONG - This searches Unity Catalog
spark.sql("SELECT * FROM tickets")  # Error: table not found
```

**Notebook SQL cells use Spark SQL** - they cannot access your PostgreSQL tables. Always use Python with the `lakebase` module.

## 🧪 Data Validation

Use the provided validation queries to verify your data:

```python
import sys
sys.path.insert(0, '/Workspace/Users/<your-email>/databricks-ticket-app')
import lakebase

# Verify all tickets have 2+ messages
results = lakebase.run_query("""
    SELECT 
        t.ticket_id,
        t.title,
        COUNT(tm.message_id) as message_count
    FROM tickets t
    LEFT JOIN ticket_messages tm ON t.ticket_id = tm.ticket_id
    GROUP BY t.ticket_id, t.title
    HAVING COUNT(tm.message_id) >= 2
""")
```

See `validation_queries.sql` for more examples.

## 🎨 UI Features

### Home Page
* Grid layout of all tickets
* Filter dropdowns for status and tags
* Color-coded status badges
* Priority indicators
* Click any ticket to view details

### Ticket Detail Page
* Complete message thread
* Status and priority dropdowns (live update)
* Toggle tag buttons (Bug/Feature/Question)
* Add new messages
* Delete ticket (with confirmation)
* Full change history log

### Tag System
* Three predefined tags: 🐛 Bug, ✨ Feature, ❓ Question
* Multiple tags per ticket
* Toggle on/off with clickable buttons
* Color-coded badges throughout UI
* Filterable on home page

## 📊 Monitoring & Maintenance

### Health Check
```bash
curl https://<your-app-url>/healthz
```

### View Logs
```bash
databricks apps logs ticket-service-app
```

### Database Stats
```python
import lakebase

# Get summary statistics
stats = lakebase.run_query("""
    SELECT 
        'Total Tickets' as metric,
        COUNT(*)::text as value
    FROM tickets
    
    UNION ALL
    
    SELECT 
        'Total Messages',
        COUNT(*)::text
    FROM ticket_messages
""")
```

## 🐛 Troubleshooting

### "Table or view cannot be found" error

**Problem**: Running SQL in a notebook cell returns:
```
[TABLE_OR_VIEW_NOT_FOUND] The table or view `tickets` cannot be found.
```

**Solution**: Use the lakebase module in Python cells:
```python
import sys
sys.path.insert(0, '/Workspace/Users/<your-email>/databricks-ticket-app')
import lakebase

tickets = lakebase.run_query("SELECT * FROM tickets")
```

### App won't start

1. Check logs: `databricks apps logs ticket-service-app`
2. Verify secret exists: `databricks secrets list-secrets database`
3. Test database connection:
   ```python
   import lakebase
   lakebase.run_query("SELECT 1")  # Should return [{'?column?': 1}]
   ```

## 📝 Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable (for local testing only)
export LAKEBASE_URL="postgresql://user:pass@host:5432/databricks_postgres?sslmode=require"

# Run Flask app
python app.py
```

**Note**: In production (Databricks Apps), the connection URL comes from secrets, not environment variables.

### Adding New Features

1. Update `app.py` with new routes
2. Add migrations if schema changes needed
3. Test locally
4. Commit and push to Git
5. Redeploy: `databricks apps deploy ticket-service-app`

## 📄 License

This project is for educational/demonstration purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues or questions:
* Check the troubleshooting section above
* Review `validation_queries.sql` for data verification
* Check app logs: `databricks apps logs ticket-service-app`

---

**Built with ❤️ using Databricks Apps & Lakebase Postgres**
