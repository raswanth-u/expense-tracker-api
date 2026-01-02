# Migration Strategy Summary

## 🎯 Problem Solved

**Old Approach (Problematic):**
```dockerfile
ENTRYPOINT ["sh", "-c", "alembic upgrade head && uvicorn main:app ..."]
```
Issues:
- ❌ Runs migrations on EVERY container restart
- ❌ Race conditions if multiple containers start simultaneously
- ❌ Failed migrations lock the database
- ❌ 4 containers for 3 services (migrate + api were duplicates)

**New Approach (Optimized):**
- ✅ Single entrypoint script with conditional migration
- ✅ Dev: Automatic migrations (RUN_MIGRATIONS=true)
- ✅ Prod: Manual migrations only (RUN_MIGRATIONS=false)
- ✅ 3 containers for 3 services (no duplicates)
- ✅ Explicit control over when migrations run

---

## 📋 Architecture

### **Development (Automatic)**

```
docker-compose up -d
    ↓
1. Start DB container
2. Wait for DB health check
3. Start API container with RUN_MIGRATIONS=true
   ├── Entrypoint script runs
   ├── Alembic runs migrations
   ├── FastAPI starts
4. Start Nginx
    ↓
All services running, migrations done
```

**Usage:**
```bash
docker-compose up -d
docker-compose logs api  # See migrations running
curl https://localhost:8443/health  # Test
```

### **Production (Manual)**

```
1. Start DB only
   docker-compose -f docker-compose.prod.yaml up -d db

2. Wait for DB ready
   sleep 10

3. Run migrations manually
   docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic upgrade head"

4. Start API & Nginx
   docker-compose -f docker-compose.prod.yaml up -d api nginx

5. Test health
   curl https://localhost/health
```

---

## 🔄 How It Works

### **Entrypoint Script Logic**

```bash
#!/bin/bash

if [ "$RUN_MIGRATIONS" = "true" ]; then
    # Dev mode: Run migrations
    alembic upgrade head
else
    # Prod mode: Skip migrations (run manually)
    echo "Skipping migrations (RUN_MIGRATIONS=false)"
fi

# Start FastAPI
uvicorn main:app --host 0.0.0.0 --port 8000
```

### **Environment Variables**

| Variable | Dev | Prod | Purpose |
|----------|-----|------|---------|
| `RUN_MIGRATIONS` | `true` | `false` | Control migration behavior |
| `DATABASE_URL` | `.env` | `.env.prod` | Database connection |
| `POSTGRES_USER` | `expense_admin` | `expense_admin` | Database user |
| `POSTGRES_PASSWORD` | `dev_password_dev` | From `.env.prod` | Database password |

---

## 📁 Files Changed/Created

### **Modified Files**

1. **Dockerfile** - Updated to use entrypoint script
2. **docker-compose.yaml** (dev) - Added `RUN_MIGRATIONS=true`, added port 8000 mapping

### **New Files**

1. **entrypoint.sh** - Smart migration/startup script
2. **docker-compose.prod.yaml** - Production-safe configuration with `RUN_MIGRATIONS=false`
3. **PRODUCTION_DEPLOYMENT.md** - Step-by-step production deployment guide
4. **DEVELOPMENT_DEPLOYMENT.md** - Development quick-start guide

---

## ✅ Key Benefits

| Aspect | Old | New |
|--------|-----|-----|
| **Containers** | 4 (db, migrate, api, nginx) | 3 (db, api, nginx) |
| **Duplicate Services** | Yes (migrate = api) | No |
| **Dev Migration** | Manual | Automatic |
| **Prod Migration** | Auto on restart ❌ | Manual only ✅ |
| **Control** | Implicit | Explicit |
| **Race Conditions** | Possible | Prevented |

---

## 🚀 Quick Reference

### **Development**

```bash
# Start (migrations run automatically)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down

# Reset database
docker-compose down -v && docker-compose up -d
```

### **Production**

```bash
# Step 1: Start database
docker-compose -f docker-compose.prod.yaml up -d db

# Step 2: Run migrations (one-time)
sleep 10
docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic upgrade head"

# Step 3: Start API & Nginx
docker-compose -f docker-compose.prod.yaml up -d api nginx

# Verify
curl -k https://localhost/health
```

---

## ⚠️ Migration Failure Recovery

If migration fails in production:

```bash
# 1. Check logs
docker-compose -f docker-compose.prod.yaml logs api

# 2. Fix the issue (e.g., update migration file)

# 3. Retry migration
docker-compose -f docker-compose.prod.yaml run --rm api sh -c "alembic upgrade head"

# 4. Verify it worked
docker-compose -f docker-compose.prod.yaml ps

# 5. Start API & Nginx
docker-compose -f docker-compose.prod.yaml up -d api nginx
```

---

## 📚 Documentation

- **DEVELOPMENT_DEPLOYMENT.md** - Dev quick-start & common tasks
- **PRODUCTION_DEPLOYMENT.md** - Prod deployment procedures & troubleshooting

---

## 🎯 Why This Approach is Better

1. **Simpler** - 3 containers instead of 4, no duplicate services
2. **Safer** - Migrations don't auto-run, reducing production incidents
3. **Flexible** - Same codebase works for both dev (auto) and prod (manual)
4. **Explicit** - Clear when migrations happen
5. **Debuggable** - Easy to see what went wrong and retry
6. **Industry Standard** - Matches how major projects handle migrations

