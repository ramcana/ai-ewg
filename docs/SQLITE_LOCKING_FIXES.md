# SQLite Locking Fixes & Concurrency Guide

## Overview

This document describes the fixes applied to prevent "database is locked" errors when running the AI-EWG pipeline with n8n workflows. These errors occur when multiple processes attempt to write to SQLite simultaneously.

## Problem

SQLite uses file-level locking, which causes conflicts when:
- Multiple n8n workflow executions run in parallel
- FastAPI runs with multiple workers
- Windows/Docker file sharing adds locking friction
- Connections are held open too long

## Applied Fixes (Current State)

### ✅ 1. Optimal SQLite Configuration

**File:** `src/core/config.py`

```yaml
database:
  journal_mode: WAL          # Write-Ahead Logging for better concurrency
  synchronous: NORMAL        # Safe with WAL, reduces filesystem thrashing
  busy_timeout: 10000        # Wait 10 seconds if database is locked (10000ms)
  connection_timeout: 10     # SQLite connection timeout (seconds)
```

**What this does:**
- **WAL mode**: Allows readers and one writer to operate concurrently
- **NORMAL synchronous**: Reduces fsync calls while maintaining safety with WAL
- **10s busy timeout**: SQLite waits up to 10 seconds before throwing "locked" error
- **Additional PRAGMAs**: 64MB cache, temp_store in memory

### ✅ 2. NullPool-Like Connection Management

**File:** `src/core/database.py`

**Changes:**
- Connections close immediately after each transaction (prevents stale file handles)
- `check_same_thread=False` allows connection sharing across threads
- `isolation_level=None` for explicit transaction management
- Aggressive connection cleanup on errors

**Key behavior:**
```python
# After successful transaction
if self._use_nullpool:
    self.close_connection()  # Close immediately

# On any error
self.close_connection()  # Always close stale connections
```

### ✅ 3. Enhanced Transaction Retry Logic

**File:** `src/core/database.py`

**Features:**
- Default to `BEGIN IMMEDIATE` (exclusive lock from start)
- 5 retry attempts with exponential backoff (0.5s → 1s → 2s → 4s → 8s)
- Automatic connection cleanup on lock failures
- Detailed logging of retry attempts

### ✅ 4. Single-Worker FastAPI Mode

**File:** `src/api/server.py`

**Critical change:**
```python
uvicorn.run(
    app,
    host=host,
    port=port,
    workers=1,  # CRITICAL: Single worker only for SQLite
    log_level="info"
)
```

**Why:** Multiple uvicorn workers = multiple processes = guaranteed SQLite locks

### ✅ 5. Startup Configuration Verification

**File:** `src/api/server.py`

On startup, the API server now:
- Verifies WAL mode is active
- Checks busy_timeout is ≥5000ms
- Logs warnings if configuration is suboptimal

## Operational Guardrails

### ✅ DO:
- ✅ Let n8n **only** call the API via HTTP nodes
- ✅ Run the API with the provided `start-api-server.ps1` script
- ✅ Keep `pipeline.db` on local NTFS (not network share)
- ✅ Exclude the `data/` folder from Windows Defender real-time scanning
- ✅ Use n8n's **Split in Batches** + **Wait** nodes to throttle requests
- ✅ Add **Retry on Error** to HTTP nodes (3 retries, exponential backoff)

### ❌ DON'T:
- ❌ Access `pipeline.db` from multiple containers simultaneously
- ❌ Mount the same DB file into both n8n and API containers
- ❌ Edit the DB from the host while containers are running
- ❌ Run VACUUM during active processing
- ❌ Use multiple uvicorn workers (`--workers > 1`)
- ❌ Run the API with gunicorn in multi-worker mode

## n8n Workflow Configuration

### Recommended Settings

**Workflow Settings:**
```
Concurrency: 1-2 (start low, increase gradually)
Timeout: 300 seconds
```

**HTTP Request Node (calling API):**
```
Retry on Fail: Yes
Max Retries: 3
Retry Wait Time: 500ms (exponential backoff)
```

**Example Throttled Batch Processing:**
```
1. Split In Batches (batch size: 5)
2. HTTP Request (process episode)
3. Wait (500ms)
4. Loop back to next batch
```

## Testing Your Setup

### 1. Verify SQLite Configuration

Start the API server and check logs:
```powershell
.\start-api-server.ps1
```

Look for:
```
SQLite configuration verified journal_mode=wal busy_timeout_ms=10000
```

### 2. Test Concurrent Requests

From PowerShell, simulate parallel n8n executions:
```powershell
1..10 | ForEach-Object -Parallel {
    Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
}
```

Should complete without "database is locked" errors.

### 3. Monitor Database Locks

While running workflows:
```powershell
# Check for WAL files (indicates WAL mode is active)
Get-ChildItem data\pipeline.db*
# Should see: pipeline.db, pipeline.db-wal, pipeline.db-shm
```

## Performance Tuning

### Current Limits (SQLite)
- **Max concurrent writes:** 1 (SQLite limitation)
- **Max concurrent reads:** Unlimited (with WAL)
- **Recommended n8n concurrency:** 1-3
- **Recommended batch size:** 5-10 episodes

### If You Hit Limits
- Increase `busy_timeout` to 15000-20000ms
- Reduce n8n workflow concurrency to 1
- Add more Wait nodes between batches
- **Consider migrating to PostgreSQL** (see below)

## Troubleshooting

### Still Getting "database is locked"?

**1. Check for multiple processes:**
```powershell
# Find processes accessing the DB
Get-Process | Where-Object {$_.Path -like "*python*"} | Select-Object Id, Path
```

**2. Check Windows Defender:**
```powershell
# Add exclusion
Add-MpPreference -ExclusionPath "D:\n8n\ai-ewg\data"
```

**3. Verify WAL mode:**
```powershell
sqlite3 data\pipeline.db "PRAGMA journal_mode;"
# Should output: wal
```

**4. Check for stale locks:**
```powershell
# Stop all processes, then delete WAL files
Remove-Item data\pipeline.db-wal, data\pipeline.db-shm -ErrorAction SilentlyContinue
```

**5. Enable debug logging:**
```yaml
# config/pipeline.yaml
logging:
  level: DEBUG
```

## Migration to PostgreSQL (Recommended for Production)

### Why Migrate?
- ✅ True multi-process concurrency
- ✅ No file locking issues
- ✅ Better performance under load
- ✅ Connection pooling
- ✅ Can scale to multiple API instances

### Quick Migration Guide

**1. Add PostgreSQL container:**
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: pipeline
      POSTGRES_USER: pipeline_user
      POSTGRES_PASSWORD: your_secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

**2. Install PostgreSQL driver:**
```powershell
pip install psycopg2-binary sqlalchemy
```

**3. Update configuration:**
```yaml
# config/pipeline.yaml
database:
  type: postgresql  # Change from sqlite
  host: localhost
  port: 5432
  database: pipeline
  user: pipeline_user
  password: your_secure_password
  pool_size: 5
  max_overflow: 10
```

**4. Update database.py:**
```python
# Use SQLAlchemy for PostgreSQL
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "postgresql+psycopg2://user:pass@localhost:5432/pipeline",
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)
```

**5. Migrate data:**
```powershell
# Export from SQLite
sqlite3 data\pipeline.db .dump > backup.sql

# Import to PostgreSQL (after schema conversion)
psql -U pipeline_user -d pipeline -f backup_converted.sql
```

**6. Remove worker limit:**
```python
# Can now use multiple workers
uvicorn.run(app, workers=4)  # Safe with PostgreSQL
```

## Checklist: Quick Fixes Applied

- [x] WAL mode enabled
- [x] busy_timeout set to 10 seconds
- [x] NullPool-like connection management
- [x] Single-worker uvicorn mode enforced
- [x] Transaction retry with exponential backoff
- [x] Startup configuration verification
- [x] Updated start script with warnings
- [x] Documentation created

## Checklist: Operational Best Practices

- [ ] n8n only calls API (no direct DB access)
- [ ] Database on local NTFS (not network share)
- [ ] Windows Defender exclusion added
- [ ] n8n concurrency set to 1-2
- [ ] HTTP nodes have retry configured
- [ ] Split in Batches + Wait nodes used
- [ ] Monitoring for lock errors in logs

## Support

If you continue to experience locking issues after applying these fixes:

1. Review the troubleshooting section above
2. Check logs for specific error patterns
3. Consider PostgreSQL migration for production workloads
4. Reduce n8n concurrency to 1 as a temporary measure

## References

- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Locking](https://www.sqlite.org/lockingv3.html)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [n8n Workflow Settings](https://docs.n8n.io/workflows/settings/)
