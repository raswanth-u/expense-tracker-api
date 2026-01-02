# Development Environment - Expense Tracker API

This is the **development/staging** environment for the Expense Tracker application. It runs on port **8443** (HTTPS) to avoid conflicts with the production environment on the same server.

**Location**: `/home/life/projects/expense_tracker_app/expenses-app-v1`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Details](#environment-details)
3. [Multi-Environment Setup](#multi-environment-setup)
4. [Docker Configuration](#docker-configuration)
5. [Health Checks](#health-checks)
6. [Logs & Debugging](#logs--debugging)
7. [Database Operations](#database-operations)
8. [SSL Certificates](#ssl-certificates)
9. [Secrets Management](#secrets-management)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Production environment running in `/app/expense-tracker` (optional)

### Start Development Environment

```bash
# Navigate to dev environment directory
cd /home/life/projects/expense_tracker_app/expenses-app-v1

# Create environment file from example
cp .env.example .env

# Edit with your API keys and passwords
# IMPORTANT: Don't commit .env file!
nano .env

# Start all containers (db, api, nginx)
docker compose up -d

# Verify it's running
curl -k https://localhost:8443/health

# View logs
docker compose logs -f
```

### Access Development API

| Resource | URL |
|----------|-----|
| API Documentation | `https://localhost:8443/api/docs` |
| ReDoc API Docs | `https://localhost:8443/api/redoc` |
| Health Check | `https://localhost:8443/health` |
| Base API URL | `https://localhost:8443/api` |
| PostgreSQL | `localhost:5433` |

---

## Environment Details

### Port Configuration

**Why Different Ports?**

Both environments (dev & prod) run on the **same server**. Each service needs a unique host port:

```
DEV ENVIRONMENT                PROD ENVIRONMENT
┌──────────────────┐          ┌──────────────────┐
│ nginx: 8443      │          │ nginx: 443       │
│ http: 8081       │          │ http: 8080       │
│ db: 5433         │          │ db: 5432         │
└──────────────────┘          └──────────────────┘

If both used 443: ❌ PORT CONFLICT
With different ports: ✅ WORKS PERFECTLY
```

### Docker Services

```yaml
services:
  db:
    image: postgres:15-alpine
    ports:
      - "5433:5432"              # Host:Container
    environment:
      POSTGRES_USER: expense_admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: expenses_db
    volumes:
      - ./tracker-data:/var/lib/postgresql/data
  
  api:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://expense_admin:${DB_PASSWORD}@db:5432/expenses_db
  
  nginx:
    image: nginx:alpine
    ports:
      - "8081:80"                 # HTTP redirects to HTTPS
      - "8443:443"                # HTTPS (client-facing)
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
```

### Network Architecture

```
┌──────────────────────────────────────────────────┐
│  DOCKER NETWORK: expenses-app-v1_default         │
│  Subnet: 172.18.0.0/16                           │
│                                                   │
│  Container-to-Container (via service names):     │
│  ┌──────────┐     ┌──────┐     ┌─────────┐      │
│  │  nginx   │ ──> │ api  │ ──> │   db    │      │
│  │172.18.0.4│     │172.18│     │172.18.0.2      │
│  └──────────┘     └─0.3──┘     └─────────┘      │
│  :8443                                           │
│  (external)                                      │
│                                                   │
│  nginx.conf routing:                             │
│  Client :8443 -> nginx:443 -> upstream api:8000 │
└──────────────────────────────────────────────────┘
```

---

## Multi-Environment Setup

### Running Both Dev and Prod Simultaneously

```bash
# Terminal 1: Start PRODUCTION
cd /app/expense-tracker
docker compose up -d

# Terminal 2: Start DEVELOPMENT (this directory)
cd /home/life/projects/expense_tracker_app/expenses-app-v1
docker compose up -d

# Verify both are running
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
```

### Accessing Both Simultaneously

```bash
# Development
curl -k https://localhost:8443/health
expense --env dev user list

# Production
curl -k https://localhost/health
expense --env prod user list
```

### Port Allocation

| Purpose | Dev | Prod | Conflict? |
|---------|-----|------|-----------|
| PostgreSQL | 5433 | 5432 | ✅ No |
| HTTP | 8081 | 8080 | ✅ No |
| HTTPS | 8443 | 443 | ✅ No |

---

## Docker Configuration

### Environment File (.env)

Create `.env` from `.env.example`:

```bash
# .env (NEVER COMMIT - add to .gitignore!)

# ========== DATABASE ==========
POSTGRES_USER=expense_admin
POSTGRES_PASSWORD=secure_dev_password_change_me
POSTGRES_DB=expenses_db

# ========== API ==========
API_KEY=dev-api-key-abc123xyz789
DATABASE_URL=postgresql://expense_admin:secure_dev_password_change_me@db:5432/expenses_db

# ========== LOGGING ==========
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### Build & Deploy

```bash
# Build from Dockerfile
docker compose build api

# Start all services
docker compose up -d

# Monitor startup
docker compose logs -f
```

---

## Health Checks

### Quick Verification

```bash
# Check health endpoint
curl -k https://localhost:8443/health

# View container statuses
docker compose ps

# Check database
docker compose exec db pg_isready -U expense_admin
```

### Troubleshooting Health Issues

```bash
# Database not ready
docker compose restart db
docker compose logs db

# API can't start
docker compose logs api

# Nginx issues
docker compose logs nginx
docker compose exec nginx nginx -t
```

---

## Logs & Debugging

### View Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api
docker compose logs db
docker compose logs nginx

# Follow logs
docker compose logs -f api

# Last 50 lines
docker compose logs --tail=50 api
```

### Access Container

```bash
# Shell in API container
docker compose exec api /bin/bash

# Database connection
docker compose exec db psql -U expense_admin -d expenses_db

# Check Python version
docker compose exec api python --version
```

---

## Database Operations

### Backup & Restore

```bash
# Backup
docker compose exec db pg_dump -U expense_admin expenses_db > backup_dev_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U expense_admin expenses_db < backup_dev_20260102.sql
```

### Migrations

```bash
# If using Alembic
docker compose exec api alembic upgrade head
docker compose exec api alembic current

# Seed data
docker compose exec api python seed_database.py
```

### Check Data

```bash
# Connect to database
docker compose exec db psql -U expense_admin -d expenses_db

# List tables
\dt

# View users
SELECT * FROM users LIMIT 5;

# Exit
\q
```

---

## SSL Certificates

### Self-Signed Certificates

Pre-generated in `./nginx/ssl/`:
- `cert.pem` - Certificate
- `key.pem` - Private key

### Using Certificates

```bash
# Skip SSL verification (dev only!)
curl -k https://localhost:8443/health

# Or use certificate
curl --cacert ./nginx/ssl/cert.pem https://localhost:8443/health

# For Python
requests.get('https://localhost:8443/health', verify='./nginx/ssl/cert.pem')
```

### Regenerate Certificates

```bash
cd nginx/ssl

# Generate new certificate
openssl req -x509 -newkey rsa:2048 \
  -keyout key.pem \
  -out cert.pem \
  -days 365 -nodes \
  -subj "/CN=localhost/O=Development/C=US"

# Restart nginx
docker compose restart nginx
```

---

## Secrets Management

### Environment Variables

**⚠️ IMPORTANT**: Secrets go in `.env` file, NOT in code!

```bash
# ✅ GOOD: Secrets in .env (never committed)
.env
API_KEY=dev-api-key-123

# ❌ BAD: Secrets in config files (committed!)
config.toml
api_key = "dev-api-key-123"  # EXPOSED!
```

### Setup

```bash
# 1. Create .env from example
cp .env.example .env

# 2. Edit with real values
nano .env

# 3. Make readable only by you
chmod 600 .env

# 4. Check .gitignore
grep ".env" .gitignore
```

### Access in Code

```python
import os

API_KEY = os.getenv('API_KEY')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DATABASE_URL = os.getenv('DATABASE_URL')
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs api

# Full restart
docker compose down
docker compose up -d
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8443

# Kill process
kill -9 <PID>
```

### Database Connection Errors

```bash
# Check database is running
docker compose ps db

# Check if database is healthy
docker compose exec db pg_isready

# Verify DATABASE_URL
grep DATABASE_URL .env

# Check logs
docker compose logs db
```

### Nginx 502 Bad Gateway

```bash
# Check API is running
docker compose ps api

# Check API responds
docker compose exec api curl http://localhost:8000/health

# Test nginx config
docker compose exec nginx nginx -t

# Restart all
docker compose down
docker compose up -d
```

---

## Best Practices

### Do's ✅

- Use `.env` for secrets
- Keep dev and prod data separate
- Backup database regularly
- Check logs for debugging
- Use `--env dev` with CLI
- Monitor resource usage

### Don'ts ❌

- Don't commit `.env` files
- Don't use production credentials in dev
- Don't disable SSL in production
- Don't leave containers running indefinitely
- Don't share `.env` files via messaging
- Don't ignore container health checks

---

## Related Documentation

- [CLI README](../expense-cli/README.md)
- [Production Setup](../../app/expense-tracker/README.md)
- [System Architecture](../ARCHITECTURE.md)

**Last Updated**: January 2026
**Port**: 8443 (HTTPS)
