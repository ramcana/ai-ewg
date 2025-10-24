# SQLite Locking Fixes - Quick Summary

## ✅ What Was Fixed

### 1. **Database Configuration** (`src/core/config.py`)
- ✅ WAL journal mode (better concurrency)
- ✅ 10-second busy timeout (10000ms)
- ✅ NORMAL synchronous mode (safe with WAL)
- ✅ 64MB cache size

### 2. **Connection Management** (`src/core/database.py`)
- ✅ NullPool-like behavior (close connections immediately)
- ✅ `check_same_thread=False` (thread-safe)
- ✅ Aggressive connection cleanup on errors
- ✅ Enhanced retry logic (5 attempts, exponential backoff)

### 3. **API Server** (`src/api/server.py`)
- ✅ Single-worker mode enforced (`workers=1`)
- ✅ Startup configuration verification
- ✅ Logs SQLite settings on startup

### 4. **Startup Script** (`start-api-server.ps1`)
- ✅ Displays optimization info
- ✅ Warns about operational guardrails
- ✅ Clear instructions for users

## 🎯 Quick Start

```powershell
# Start the API server (already optimized)
.\start-api-server.ps1
```

You should see:
```
🔧 SQLite Optimizations Active:
   • Single-worker mode (prevents multi-process locks)
   • WAL journal mode (better concurrency)
   • 10-second busy timeout with exponential backoff
   • NullPool behavior (aggressive connection closing)
```

## ⚙️ n8n Configuration

**Workflow Settings:**
```
Concurrency: 1-2 (start low)
Timeout: 300 seconds
```

**HTTP Request Node:**
```
Retry on Fail: Yes
Max Retries: 3
Retry Wait Time: 500ms (exponential)
```

**Batch Processing Pattern:**
```
[Split In Batches (5)] → [HTTP Request] → [Wait 500ms] → [Loop]
```

## ✅ DO's

- ✅ Let n8n **only** call the API (no direct DB access)
- ✅ Keep `pipeline.db` on local NTFS
- ✅ Exclude `data/` folder from Windows Defender
- ✅ Use Split in Batches + Wait nodes
- ✅ Add Retry on Error to HTTP nodes

## ❌ DON'Ts

- ❌ Access `pipeline.db` from multiple processes
- ❌ Mount the same DB into multiple containers
- ❌ Run with `--workers > 1`
- ❌ Run VACUUM during processing
- ❌ Edit DB while API is running

## 🧪 Test Your Setup

```powershell
# 1. Start API
.\start-api-server.ps1

# 2. Test concurrent requests (should work without errors)
1..10 | ForEach-Object -Parallel {
    Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
}

# 3. Check WAL mode is active
Get-ChildItem data\pipeline.db*
# Should see: pipeline.db, pipeline.db-wal, pipeline.db-shm
```

## 🚨 Troubleshooting

### Still getting "database is locked"?

**1. Check for multiple processes:**
```powershell
Get-Process | Where-Object {$_.Path -like "*python*"}
```

**2. Add Windows Defender exclusion:**
```powershell
Add-MpPreference -ExclusionPath "D:\n8n\ai-ewg\data"
```

**3. Verify WAL mode:**
```powershell
sqlite3 data\pipeline.db "PRAGMA journal_mode;"
# Should output: wal
```

**4. Reduce n8n concurrency to 1**

**5. Add more Wait nodes between requests**

## 📈 When to Migrate to PostgreSQL

Consider PostgreSQL if:
- ❌ Still experiencing lock errors after fixes
- ❌ Need n8n concurrency > 3
- ❌ Processing > 20 episodes concurrently
- ❌ Want to run multiple API workers
- ❌ Need production-grade scalability

See: `docs/POSTGRES_MIGRATION.md`

## 📚 Full Documentation

- **Detailed fixes:** `docs/SQLITE_LOCKING_FIXES.md`
- **PostgreSQL migration:** `docs/POSTGRES_MIGRATION.md`

## 🎉 Expected Results

**Before fixes:**
```
❌ "database is locked" errors
❌ n8n workflows failing randomly
❌ Retry storms
```

**After fixes:**
```
✅ No lock errors with concurrency 1-2
✅ Stable n8n workflow execution
✅ Predictable performance
✅ Clear path to PostgreSQL if needed
```

## 🔧 Configuration Files Changed

1. `src/core/config.py` - Database settings
2. `src/core/database.py` - Connection management
3. `src/api/server.py` - Single-worker enforcement
4. `start-api-server.ps1` - Startup script

**No changes needed to:**
- n8n workflows (just configure retry)
- Existing data (fully backward compatible)
- Other pipeline components

## 📊 Performance Expectations

**SQLite (Optimized):**
- Max concurrent writes: 1
- Max n8n concurrency: 1-3
- Latency: 50-200ms
- Lock errors: Rare (with proper config)

**PostgreSQL (Future):**
- Max concurrent writes: 5-10
- Max n8n concurrency: 10-20
- Latency: 10-50ms
- Lock errors: None

---

**Last Updated:** 2025-10-22  
**Status:** ✅ All fixes applied and tested
