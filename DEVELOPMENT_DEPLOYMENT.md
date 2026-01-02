# Development Deployment Guide

## Quick Start (3 commands)

```bash
cd /home/life/projects/expense_tracker_app/expenses-app-v1

# Start all services (db, api, nginx)
docker-compose up -d

# Check if everything started successfully
docker-compose ps

# View logs to see migrations running
docker-compose logs api
```

That's it! Migrations run automatically in development.

---

## What Happens Automatically

```
1. Docker-Compose starts services in order:
   ├── Database starts first
   ├── Waits for database to be healthy
   ├── Starts API with RUN_MIGRATIONS=true
   │   ├── Entrypoint script runs
   │   ├── Alembic runs migrations
   │   ├── FastAPI starts
   │   └── API ready on port 8000
   └── Nginx starts and routes to API

2. Access your application:
   - API directly: http://localhost:8000
   - Via Nginx: https://localhost:8443
   - Health check: https://localhost:8443/health
```

---

## Common Development Tasks

### **View Logs**

```bash
# Watch API logs in real-time
docker-compose logs -f api

# Watch database logs
docker-compose logs -f db

# View all service logs
docker-compose logs -f
```

### **Restart Services**

```bash
# Restart just the API (keep database running)
docker-compose restart api

# Restart everything
docker-compose restart

# Full restart (hard stop/start)
docker-compose down
docker-compose up -d
```

### **Database Shell**

```bash
# Access PostgreSQL CLI
docker-compose exec db psql -U expense_admin -d expenses_db

# List tables
\dt

# Exit
\q
```

### **Python Shell in Container**

```bash
# Run Python REPL with app context
docker-compose exec api python

# Or run Python script
docker-compose exec api python script.py
```

### **View Running Logs**

```bash
# Last 100 lines of API logs
docker-compose logs --tail=100 api

# With timestamps
docker-compose logs --timestamps api
```

---

## Debugging

### **Migration Failed?**

```bash
# Check the error
docker-compose logs api

# Typical issues:
# 1. Migration file syntax error
#    Fix: Edit alembic/versions/*.py
#    Then: docker-compose restart api

# 2. Database constraint violation
#    Fix: Check existing data in database
#    Then: Update migration or migration strategy

# 3. Missing dependency
#    Fix: Ensure earlier migrations succeeded
#    Check: docker-compose exec db psql -U expense_admin -d expenses_db -c "SELECT * FROM alembic_version;"
```

### **API Not Starting?**

```bash
# Check logs for errors
docker-compose logs api

# Common issues:
# 1. Port 8000 already in use
#    Fix: Change port in docker-compose.yaml or kill other process

# 2. Import error in Python code
#    Fix: Check syntax in main.py and models.py

# 3. Database connection error
#    Fix: Verify .env file exists and DATABASE_URL is correct
```

### **Database Connection Issues?**

```bash
# Check if database is healthy
docker-compose ps db
# Should show: Up (healthy)

# Try connecting directly
docker-compose exec db psql -U expense_admin -d expenses_db -c "SELECT 1"

# If fails, check database logs
docker-compose logs db
```

---

## Reset Database (Development Only)

⚠️ **WARNING: This deletes all data!**

```bash
# Stop all services
docker-compose down

# Remove database volume (data will be deleted)
docker-compose down -v

# Start fresh
docker-compose up -d

# Migrations will automatically run again
```

---

## Code Changes & Hot Reload

### **Python Code Changes**

```bash
# If you modify Python files:
# - main.py
# - models.py
# - routes/

# Docker-compose mounts your code, so changes are visible immediately

# Restart API to apply changes
docker-compose restart api

# OR watch logs to see auto-reload if you have watchdog installed
docker-compose logs -f api
```

### **Model/Migration Changes**

```bash
# If you add new models to models.py:

# 1. Create new migration
docker-compose exec api alembic revision --autogenerate -m "description of change"

# 2. Check the generated migration file
cat alembic/versions/*_description_of_change.py

# 3. Restart API to run the new migration
docker-compose restart api

# 4. Verify tables were created
docker-compose exec db psql -U expense_admin -d expenses_db -c "\dt"
```

---

## Environment Variables

Development uses `.env` file. Example:

```bash
# Database config
POSTGRES_USER=expense_admin
POSTGRES_PASSWORD=dev_password_dev
POSTGRES_DB=expenses_db
DATABASE_URL=postgresql://expense_admin:dev_password_dev@db:5432/expenses_db

# API config
DEBUG=True
LOG_LEVEL=DEBUG

# Email config (optional)
SMTP_SERVER=localhost
SMTP_PORT=1025
```

---

## Testing

### **Run Tests in Container**

```bash
# Run all tests
docker-compose exec api python -m pytest

# Run specific test file
docker-compose exec api python -m pytest tests/test_users.py

# Run with coverage
docker-compose exec api python -m pytest --cov=src
```

### **Database Tests**

```bash
# Pytest automatically uses test database if configured
# Check conftest.py for test database setup

docker-compose exec api python -m pytest tests/ -v
```

---

## Performance Monitoring

### **Check Container Resource Usage**

```bash
# View real-time stats
docker stats

# Watch specific container
docker stats expense_api_dev
```

### **Check Database Performance**

```bash
# Connect to database
docker-compose exec db psql -U expense_admin -d expenses_db

# List table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema') 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# List slow queries
SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

---

## Quick Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Remove all data
docker-compose down -v

# View status
docker-compose ps

# View logs
docker-compose logs -f api

# Access database
docker-compose exec db psql -U expense_admin -d expenses_db

# Restart service
docker-compose restart api

# Rebuild image
docker-compose build api

# SSH into container
docker-compose exec api bash

# Run command in container
docker-compose exec api python -c "print('hello')"
```

---

## Next Steps

- Check [API Documentation](../README.md)
- Read [Alembic Migration Guide](../ALEMBIC.md)
- Review [Architecture](../ARCHITECTURE.md)

