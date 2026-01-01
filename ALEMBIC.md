# Alembic Migrations Guide

## Quick Start

### 1. Generate Migration
```bash
alembic revision --autogenerate -m "description of changes"
```

### 2. Review Generated File
```bash
cat migrations/versions/abc123_*.py
```

### 3. Test Locally
```bash
alembic upgrade head
pytest tests/
```

### 4. Commit
```bash
git add models.py migrations/versions/abc123_*.py
git commit -m "Add migration: description"
```

### 5. Deploy with Docker
```bash
docker-compose up -d --build
```
Migrations run automatically on startup.

---

## Common Commands

```bash
# Check current migration
alembic current

# View history
alembic history

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# In Docker container
docker-compose exec api alembic <command>
```

---

## How It Works

1. **models.py** → Your source of truth
2. **alembic revision --autogenerate** → Generates migration SQL
3. **migrations/versions/*.py** → Git-tracked migration files
4. **docker-compose up --build** → Docker runs `alembic upgrade head`
5. **PostgreSQL** → Schema updated automatically

---

## Volume Mounts

The api service mounts volumes to avoid copying code:

- `.:/code` → Mount entire project
- `./migrations:/code/migrations` → Mount migrations folder

This ensures changes persist after `docker-compose down`.

---

## Dockerfile

Only `requirements.txt` and `alembic.ini` are copied. Everything else is mounted as volume (development setup).

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY alembic.ini .
# Code/migrations mounted via docker-compose volumes
```

---

## .env Required

```bash
DATABASE_URL=postgresql://expense_admin:password@db:5432/expenses_db
API_KEY=your-api-key
```

Use `db:5432` (not localhost) for Docker.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "alembic: command not found" | `pip install alembic` |
| Migration fails | Check logs: `docker-compose logs api` |
| Database locked | `docker-compose restart db` |
| Need fresh DB | `docker-compose down -v && docker-compose up --build` |

See [Alembic Docs](https://alembic.sqlalchemy.org/) for more.
