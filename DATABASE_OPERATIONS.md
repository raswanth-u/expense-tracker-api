# Database Operations Guide

## Overview

This guide covers all database operations for the Expense Tracker application, including backup, restore, migration, and merge strategies used in production environments.

---

## Table of Contents

1. [Database Architecture](#database-architecture)
2. [Environment Configuration](#environment-configuration)
3. [Backup Operations](#backup-operations)
4. [Restore Operations](#restore-operations)
5. [Migration Strategies](#migration-strategies)
6. [Schema Changes Guide](#schema-changes-guide)
7. [Production Update Procedures](#production-update-procedures)
8. [Emergency Recovery](#emergency-recovery)
9. [Automated Backups](#automated-backups)
10. [Best Practices](#best-practices)

---

## 1. Database Architecture

### Environments

```
┌─────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT                              │
│  Location: /home/life/projects/expense_tracker_app/         │
│            expenses-app-v1/tracker-data                     │
│  Port: 5433                                                 │
│  Purpose: Testing, development, new features                │
└─────────────────────────────────────────────────────────────┘
                          ↓ (After testing)
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION                               │
│  Location: /app/expense-tracker/tracker-data                │
│  Port: 5432                                                 │
│  Purpose: Live data, real users                             │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- Core tables (as of 2026-01-04)
users           -- User accounts
expenses        -- Individual expenses
accounts        -- Bank accounts, wallets
assets          -- Physical/digital assets
budgets         -- Budget tracking
credit_cards    -- Credit card management
savings_goals   -- Savings targets
recurring       -- Recurring transactions
alembic_version -- Migration tracking
```

---

## 2. Environment Configuration

### Development Environment

```bash
# .env file in expenses-app-v1/
POSTGRES_USER=expense_admin
POSTGRES_PASSWORD=dev_password_dev
POSTGRES_DB=expenses_db
DATABASE_URL=postgresql://expense_admin:dev_password_dev@db:5432/expenses_db

# For db_manager.py (when running outside Docker)
DEV_DB_HOST=localhost
DEV_DB_PORT=5433
DEV_DB_NAME=expenses_db
DEV_DB_USER=expense_admin
DEV_DB_PASSWORD=dev_password_dev
```

### Production Environment

```bash
# .env.prod file in /app/expense-tracker/
POSTGRES_USER=expense_admin
POSTGRES_PASSWORD=<strong-production-password>
POSTGRES_DB=expenses_db
DATABASE_URL=postgresql://expense_admin:<password>@db:5432/expenses_db

# For db_manager.py (when running outside Docker)
PROD_DB_HOST=localhost
PROD_DB_PORT=5432
PROD_DB_NAME=expenses_db
PROD_DB_USER=expense_admin
PROD_DB_PASSWORD=<production-password>
```

---

## 3. Backup Operations

### Quick Reference

```bash
# Full backup (recommended for production)
python db_manager.py backup --env prod

# Custom format backup (compressed, supports parallel restore)
python db_manager.py backup --env prod --format custom

# Data only backup (useful for data migration)
python db_manager.py backup --env prod --data-only

# Schema only backup (useful for comparison)
python db_manager.py backup --env prod --schema-only

# Backup specific table
python db_manager.py backup --env prod --table users

# List all backups
python db_manager.py list-backups
```

### Backup Types Explained

| Type | Command | Use Case | File Size |
|------|---------|----------|-----------|
| **Full (Plain)** | `backup --env prod` | General purpose, human-readable | Large |
| **Full (Custom)** | `backup --format custom` | Faster restore, compression | Small |
| **Data Only** | `backup --data-only` | Migrate data to new schema | Medium |
| **Schema Only** | `backup --schema-only` | Compare schemas, documentation | Very Small |
| **Single Table** | `backup --table users` | Partial recovery | Varies |

### Manual Backup (Docker)

```bash
# Development database
docker-compose exec db pg_dump -U expense_admin -d expenses_db > backup_dev_$(date +%Y%m%d).sql

# Production database
docker-compose -f docker-compose.prod.yaml exec db pg_dump -U expense_admin -d expenses_db > backup_prod_$(date +%Y%m%d).sql

# Compressed backup
docker-compose exec db pg_dump -U expense_admin -d expenses_db | gzip > backup_prod_$(date +%Y%m%d).sql.gz
```

### Backup File Naming Convention

```
backup_<env>_<timestamp>.sql          # Full plain backup
backup_<env>_<timestamp>.dump         # Custom format backup
backup_<env>_<table>_<timestamp>.sql  # Table-specific backup
backup_<env>_data_<timestamp>.sql     # Data only backup
backup_<env>_schema_<timestamp>.sql   # Schema only backup
```

### Backup Verification

```bash
# Check backup file integrity
sha256sum backup_prod_20260104.sql

# Compare with checksum file
cat backup_prod_20260104.sql.sha256

# Test restore to temp database
createdb expenses_db_test
psql -d expenses_db_test -f backup_prod_20260104.sql
dropdb expenses_db_test
```

---

## 4. Restore Operations

### Quick Reference

```bash
# Restore from backup
python db_manager.py restore --env prod --file backups/backup_prod_20260104.sql

# Restore with drop existing (destructive!)
python db_manager.py restore --env prod --file backup.sql --drop
```

### Manual Restore (Docker)

```bash
# Stop API service first
docker-compose stop api

# Restore to development
cat backup_dev_20260104.sql | docker-compose exec -T db psql -U expense_admin -d expenses_db

# Restore to production (DANGEROUS!)
cat backup_prod_20260104.sql | docker-compose -f docker-compose.prod.yaml exec -T db psql -U expense_admin -d expenses_db

# Restore from compressed backup
gunzip -c backup_prod_20260104.sql.gz | docker-compose exec -T db psql -U expense_admin -d expenses_db

# Restart API
docker-compose start api
```

### Partial Restore (Single Table)

```bash
# Restore specific table from full backup
pg_restore --table=users --dbname=expenses_db backup_prod.dump

# Or using SQL file
grep -A 1000 "CREATE TABLE users" backup.sql | grep -B 1000 "CREATE TABLE expenses" > users_only.sql
psql -d expenses_db -f users_only.sql
```

---

## 5. Migration Strategies

### Using Alembic

```bash
# Check current migration version
python db_manager.py info --env prod

# Run all pending migrations
python db_manager.py migrate --env prod

# Run to specific revision
python db_manager.py migrate --env prod --revision abc123

# Rollback one migration
python db_manager.py rollback --env prod --steps 1

# Rollback multiple migrations
python db_manager.py rollback --env prod --steps 3
```

### Creating New Migrations

```bash
# Auto-generate migration from model changes
cd expenses-app-v1
alembic revision --autogenerate -m "add_new_column_to_users"

# Create empty migration (for manual SQL)
alembic revision -m "custom_migration"

# Edit the generated file
nano migrations/versions/xxxx_add_new_column_to_users.py
```

### Migration File Structure

```python
"""add_new_column_to_users

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-01-04 12:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add new column
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))

def downgrade() -> None:
    # Remove column (rollback)
    op.drop_column('users', 'phone')
```

---

## 6. Schema Changes Guide

### Adding New Table

**Risk Level: LOW**

```python
# Migration
def upgrade():
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )

def downgrade():
    op.drop_table('notifications')
```

**Procedure:**
1. ✅ Add model to `models.py`
2. ✅ Generate migration
3. ✅ Test in development
4. ✅ Apply to production

---

### Adding Nullable Column

**Risk Level: LOW**

```python
def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))

def downgrade():
    op.drop_column('users', 'phone')
```

**Procedure:**
1. ✅ Add field to model
2. ✅ Generate migration
3. ✅ Test in development
4. ✅ Apply to production (no data loss)

---

### Adding Non-Nullable Column

**Risk Level: MEDIUM**

```python
def upgrade():
    # Step 1: Add as nullable
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    
    # Step 2: Set default value for existing rows
    op.execute("UPDATE users SET email = 'unknown@example.com' WHERE email IS NULL")
    
    # Step 3: Make non-nullable
    op.alter_column('users', 'email', nullable=False)

def downgrade():
    op.drop_column('users', 'email')
```

**Procedure:**
1. ⚠️ Backup production first
2. ⚠️ Determine default value for existing rows
3. ✅ Generate multi-step migration
4. ✅ Test in development
5. ✅ Apply to production

---

### Modifying Column Type

**Risk Level: HIGH**

```python
def upgrade():
    # Option 1: Direct change (if compatible)
    op.alter_column('expenses', 'amount',
        type_=sa.Numeric(12, 2),
        existing_type=sa.Float()
    )

def downgrade():
    op.alter_column('expenses', 'amount',
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 2)
    )
```

**For incompatible types:**

```python
def upgrade():
    # Step 1: Add new column
    op.add_column('users', sa.Column('age_int', sa.Integer(), nullable=True))
    
    # Step 2: Migrate data
    op.execute("UPDATE users SET age_int = CAST(age AS INTEGER)")
    
    # Step 3: Drop old column
    op.drop_column('users', 'age')
    
    # Step 4: Rename new column
    op.alter_column('users', 'age_int', new_column_name='age')

def downgrade():
    # Reverse the process
    op.add_column('users', sa.Column('age_str', sa.String(10), nullable=True))
    op.execute("UPDATE users SET age_str = CAST(age AS VARCHAR)")
    op.drop_column('users', 'age')
    op.alter_column('users', 'age_str', new_column_name='age')
```

**Procedure:**
1. 🔴 FULL BACKUP before proceeding
2. ⚠️ Test data conversion in development
3. ⚠️ Check for data loss during conversion
4. ✅ Apply to production during low-traffic period

---

### Renaming Column

**Risk Level: HIGH**

```python
def upgrade():
    op.alter_column('users', 'username', new_column_name='user_name')

def downgrade():
    op.alter_column('users', 'user_name', new_column_name='username')
```

**Procedure:**
1. 🔴 Update ALL code references first
2. 🔴 Full backup
3. ✅ Apply migration
4. ⚠️ Test all API endpoints

---

### Adding Foreign Key

**Risk Level: MEDIUM**

```python
def upgrade():
    # Step 1: Add column
    op.add_column('expenses', 
        sa.Column('category_id', sa.Integer(), nullable=True)
    )
    
    # Step 2: Add foreign key constraint
    op.create_foreign_key(
        'fk_expenses_category',
        'expenses', 'categories',
        ['category_id'], ['id']
    )

def downgrade():
    op.drop_constraint('fk_expenses_category', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'category_id')
```

**Procedure:**
1. ⚠️ Ensure referenced table exists
2. ⚠️ Ensure all foreign key values are valid
3. ✅ Generate migration
4. ✅ Test in development

---

### Adding Unique Constraint

**Risk Level: HIGH**

```python
def upgrade():
    # Check for duplicates first!
    op.create_unique_constraint('uq_users_email', 'users', ['email'])

def downgrade():
    op.drop_constraint('uq_users_email', 'users', type_='unique')
```

**Pre-migration check:**

```sql
-- Find duplicates
SELECT email, COUNT(*) 
FROM users 
GROUP BY email 
HAVING COUNT(*) > 1;

-- Fix duplicates before migration
UPDATE users SET email = email || '_dup_' || id WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) as rn
        FROM users
    ) t WHERE rn > 1
);
```

---

### Deleting Column

**Risk Level: MEDIUM**

```python
def upgrade():
    op.drop_column('users', 'obsolete_field')

def downgrade():
    op.add_column('users', sa.Column('obsolete_field', sa.String(100)))
```

**Procedure:**
1. 🔴 FULL BACKUP (column data will be lost!)
2. ⚠️ Verify no code references the column
3. ✅ Apply migration
4. ⚠️ Note: Cannot fully recover data in downgrade

---

### Deleting Table

**Risk Level: VERY HIGH**

```python
def upgrade():
    op.drop_table('old_table')

def downgrade():
    # Recreate table structure (data is lost!)
    op.create_table('old_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        # ... all columns
    )
```

**Procedure:**
1. 🔴 FULL BACKUP with data export
2. 🔴 Export table data separately: `pg_dump --table=old_table ...`
3. 🔴 Verify no foreign key references
4. ✅ Apply migration

---

## 7. Production Update Procedures

### Standard Update Workflow

```bash
# Step 1: Backup production
python db_manager.py backup --env prod

# Step 2: Compare schemas
python db_manager.py compare --source dev --target prod

# Step 3: Review differences (JSON output)
# Make sure all changes are expected

# Step 4: Run safe production update (interactive)
python db_manager.py update-prod

# Step 5: Validate
python db_manager.py validate --env prod
```

### Automated Production Update Script

```bash
#!/bin/bash
# production_update.sh

set -e

echo "🔄 Starting production update..."

# 1. Backup
echo "📦 Creating backup..."
BACKUP_FILE=$(python db_manager.py backup --env prod | grep "Backup created" | awk '{print $NF}')
echo "Backup: $BACKUP_FILE"

# 2. Compare
echo "🔍 Comparing schemas..."
python db_manager.py compare --source dev --target prod > /tmp/schema_diff.json

# 3. Run migrations
echo "🚀 Running migrations..."
if ! docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic upgrade head"; then
    echo "❌ Migration failed! Restoring backup..."
    python db_manager.py restore --env prod --file "$BACKUP_FILE"
    exit 1
fi

# 4. Validate
echo "✅ Validating..."
python db_manager.py validate --env prod

# 5. Restart API
echo "🔄 Restarting API..."
docker-compose -f docker-compose.prod.yaml restart api

echo "✅ Production update complete!"
```

### Manual Step-by-Step (Docker)

```bash
# 1. Navigate to production
cd /app/expense-tracker

# 2. Backup database
docker-compose -f docker-compose.prod.yaml exec db pg_dump -U expense_admin -d expenses_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Stop API (prevent data changes during migration)
docker-compose -f docker-compose.prod.yaml stop api

# 4. Run migrations
docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic upgrade head"

# 5. Verify migration success
docker-compose -f docker-compose.prod.yaml exec db psql -U expense_admin -d expenses_db -c "SELECT * FROM alembic_version;"

# 6. Start API
docker-compose -f docker-compose.prod.yaml up -d api

# 7. Verify health
curl -k https://localhost/health
```

---

## 8. Emergency Recovery

### Scenario 1: Migration Failed Mid-Way

```bash
# 1. Check current state
docker-compose -f docker-compose.prod.yaml logs api

# 2. Check alembic version
docker-compose -f docker-compose.prod.yaml exec db psql -U expense_admin -d expenses_db -c "SELECT * FROM alembic_version;"

# 3. Try to rollback
docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic downgrade -1"

# 4. If rollback fails, restore from backup
docker-compose -f docker-compose.prod.yaml stop api
cat backup_prod_latest.sql | docker-compose -f docker-compose.prod.yaml exec -T db psql -U expense_admin -d expenses_db
docker-compose -f docker-compose.prod.yaml up -d api
```

### Scenario 2: Database Corrupted

```bash
# 1. Stop all services
docker-compose -f docker-compose.prod.yaml down

# 2. Remove corrupted data
rm -rf tracker-data/*

# 3. Start fresh database
docker-compose -f docker-compose.prod.yaml up -d db
sleep 10

# 4. Restore from backup
cat backup_prod_latest.sql | docker-compose -f docker-compose.prod.yaml exec -T db psql -U expense_admin -d expenses_db

# 5. Start API
docker-compose -f docker-compose.prod.yaml up -d api nginx
```

### Scenario 3: Need to Merge Data from Dev to Prod

```bash
# 1. Export specific data from dev
docker-compose exec db pg_dump -U expense_admin -d expenses_db --data-only --table=users > users_data.sql

# 2. Review and edit the data (remove duplicates, etc.)
nano users_data.sql

# 3. Import to prod (careful with IDs!)
cat users_data.sql | docker-compose -f docker-compose.prod.yaml exec -T db psql -U expense_admin -d expenses_db
```

### Scenario 4: Point-in-Time Recovery

If you have continuous archiving enabled (not default):

```bash
# 1. Restore to specific time
pg_restore --target-time="2026-01-04 10:30:00" --target-action=promote ...

# For our setup, use most recent backup before the incident
python db_manager.py list-backups
python db_manager.py restore --env prod --file backups/backup_prod_20260104_103000.sql
```

---

## 9. Automated Backups

### Cron Job Setup

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * cd /app/expense-tracker && /usr/bin/python3 db_manager.py backup --env prod >> /var/log/db_backup.log 2>&1

# Weekly full backup on Sunday at 3 AM
0 3 * * 0 cd /app/expense-tracker && /usr/bin/python3 db_manager.py backup --env prod --format custom >> /var/log/db_backup.log 2>&1

# Monthly cleanup of old backups
0 4 1 * * cd /app/expense-tracker && /usr/bin/python3 db_manager.py cleanup --days 90 >> /var/log/db_backup.log 2>&1
```

### Docker-Based Backup

Create `backup.sh`:

```bash
#!/bin/bash
# /app/expense-tracker/backup.sh

BACKUP_DIR="/app/expense-tracker/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_prod_$TIMESTAMP.sql"

# Create backup
docker-compose -f docker-compose.prod.yaml exec -T db pg_dump -U expense_admin -d expenses_db > "$BACKUP_FILE"

# Compress
gzip "$BACKUP_FILE"

# Create checksum
sha256sum "$BACKUP_FILE.gz" > "$BACKUP_FILE.gz.sha256"

# Remove backups older than 30 days
find "$BACKUP_DIR" -name "backup_*.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "backup_*.sha256" -mtime +30 -delete

echo "Backup complete: $BACKUP_FILE.gz"
```

---

## 10. Best Practices

### Pre-Deployment Checklist

- [ ] Backup production database
- [ ] Test migrations in development
- [ ] Review migration SQL (alembic upgrade --sql)
- [ ] Check for breaking changes in API
- [ ] Update API code to handle new schema
- [ ] Plan rollback strategy
- [ ] Schedule during low-traffic period
- [ ] Notify team of deployment

### Migration Guidelines

| Do | Don't |
|----|-------|
| ✅ Use nullable columns first | ❌ Add non-nullable without default |
| ✅ Test migrations locally | ❌ Apply untested migrations |
| ✅ Keep migrations small | ❌ Combine many changes in one |
| ✅ Write downgrade functions | ❌ Skip rollback capability |
| ✅ Backup before migrate | ❌ Migrate without backup |
| ✅ Use transactions | ❌ Partial migrations |

### Backup Guidelines

| Do | Don't |
|----|-------|
| ✅ Daily automated backups | ❌ Manual-only backups |
| ✅ Verify backup integrity | ❌ Assume backups work |
| ✅ Store backups off-site | ❌ Keep only local copies |
| ✅ Test restore periodically | ❌ Wait until emergency |
| ✅ Encrypt sensitive backups | ❌ Store plain text |

### Security

```bash
# Set proper permissions on backup files
chmod 600 backups/*.sql
chmod 600 .env.prod

# Use environment variables for passwords
export PROD_DB_PASSWORD="your-password"

# Never commit passwords to Git
echo ".env.prod" >> .gitignore
echo "backups/" >> .gitignore
```

---

## Quick Reference Card

```bash
# === BACKUP ===
python db_manager.py backup --env prod              # Full backup
python db_manager.py backup --env prod --data-only  # Data only
python db_manager.py list-backups                   # List backups

# === RESTORE ===
python db_manager.py restore --env prod --file backup.sql

# === MIGRATE ===
python db_manager.py migrate --env prod             # Apply migrations
python db_manager.py rollback --env prod --steps 1  # Rollback

# === COMPARE ===
python db_manager.py compare --source dev --target prod

# === VALIDATE ===
python db_manager.py validate --env prod
python db_manager.py info --env prod

# === SAFE UPDATE ===
python db_manager.py update-prod                    # Interactive guide

# === CLEANUP ===
python db_manager.py cleanup --days 30              # Remove old backups
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `pg_dump: command not found` | Install PostgreSQL client: `apt install postgresql-client` |
| `connection refused` | Check Docker is running, ports are correct |
| `permission denied` | Check database user permissions |
| `relation does not exist` | Migration order issue, check dependencies |
| `duplicate key value` | Data conflict, check unique constraints |
| `foreign key violation` | Referenced data doesn't exist |

---

## Contact

For database emergencies, contact the DevOps team immediately.

**Created:** 2026-01-04  
**Last Updated:** 2026-01-04  
**Author:** Expense Tracker Team
