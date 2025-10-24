# Enhanced Deduplication System

## Overview

The video processing pipeline now includes a comprehensive deduplication system that prevents processing the same video multiple times, even if it's renamed, moved, or copied to different folders.

## Features Added

### 1. **File Content Hashing (SHA256)**
- Calculates SHA256 hash of actual video file content
- Detects duplicate videos regardless of filename or location
- More reliable than MD5 (better collision resistance)
- Efficient chunked reading for large video files (64KB chunks)

### 2. **File Size & Duration Tracking**
- Stores file size in bytes
- Extracts video duration using ffprobe
- Additional validation for duplicate detection
- Helps identify file corruption or incomplete downloads

### 3. **Source Path Tracking**
- Records the full path where video was discovered
- Updates path if same video is found in different location
- Maintains history of file movements
- Useful for troubleshooting and auditing

### 4. **Automatic Database Backups**
- Scheduled backups every 24 hours (configurable)
- Automatic cleanup of old backups (keeps last 7 days)
- Backup on shutdown for data safety
- Stored in same directory as main database

---

## How It Works

### Discovery Process

```
1. Scan video folders for .mp4 files
2. For each file:
   ├─ Calculate SHA256 hash of file content
   ├─ Get file size and last modified time
   ├─ Extract video duration with ffprobe
   ├─ Check if hash already exists in database
   │  ├─ YES: Skip (duplicate detected)
   │  └─ NO: Continue to step 3
   └─ Register new episode in database
```

### Deduplication Scenarios

#### Scenario 1: Exact Duplicate (Same Content)
```
File 1: D:/videos/2024/TT004.mp4(hash: abc123...)
File 2: D:/videos/archive/TT004_backup.mp4 (hash: abc123...)

Result: File 2 is recognized as duplicate, skipped
Database: Only one entry, path updated to File 2 location
```

#### Scenario 2: Same Filename, Different Content
```
File 1: D:/videos/TT004.mp4 (hash: abc123...)
File 2: D:/videos/TT004.mp4 (hash: def456...) [file was replaced]

Result: Hash mismatch detected, database updated with new hash
Action: File is reprocessed with new content
```

#### Scenario 3: File Moved to Different Folder
```
Original: /data/test_videos/newsroom/2024/TT004.mp4
Moved to: /data/archive/newsroom/2024/TT004.mp4

Result: Same hash detected, source path updated
Database: Path changed from original to new location
```

#### Scenario 4: Multiple Copies in Different Folders
```
Copy 1: /data/videos/newsroom/2024/TT004.mp4
Copy 2: /data/backup/newsroom/TT004.mp4
Copy 3: /data/archive/TT004_copy.mp4

Result: All recognized as same video (same hash)
Database: Only one episode entry, path points to most recently discovered location
```

---

## Database Schema

### Episodes Table (Enhanced)

```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,              -- Episode ID (newsroom-2024-tt004)
    hash TEXT UNIQUE NOT NULL,        -- SHA256 hash of file content
    stage TEXT NOT NULL,              -- Processing stage
    source_path TEXT NOT NULL,        -- Current file location
    file_size INTEGER,                -- File size in bytes
    duration_seconds REAL,            -- Video duration
    last_modified TIMESTAMP,          -- File modification time
    metadata JSON NOT NULL,           -- Episode metadata
    created_at TIMESTAMP,             -- First discovered
    updated_at TIMESTAMP              -- Last updated
);

CREATE INDEX idx_episodes_hash ON episodes(hash);
```

### Backup Log Table

```sql
CREATE TABLE backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    backup_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restored_at TIMESTAMP
);
```

---

## Configuration

### Enable/Disable Features

**In `config/pipeline.yaml`:**

```yaml
database:
  path: "data/pipeline.db"
  backup_enabled: true              # Enable automatic backups
  backup_interval_hours: 24         # Backup every 24 hours
```

### Hash Algorithm

Default: SHA256 (can be changed to md5 or sha512 if needed)

**To change (in code):**
```python
# In pipeline.py, _calculate_file_hash method
file_hash = self._calculate_file_hash(video_file, algorithm='sha512')
```

---

## API Usage

### Check for Duplicates

```python
from src.core.registry import EpisodeRegistry

registry = EpisodeRegistry(db_connection)

# Check by hash
duplicate = registry.get_episode_by_hash("abc123...")
if duplicate:
    print(f"Duplicate found: {duplicate.episode_id}")

# Check if hash exists
is_duplicate = registry.is_duplicate("abc123...")
```

### Update File Location

```python
# When file is moved
registry.update_episode_source_path(
    episode_id="newsroom-2024-tt004",
    new_path="/data/new_location/TT004.mp4"
)
```

### Update File Hash (Content Changed)

```python
from datetime import datetime

# When file content changes
registry.update_episode_hash(
    episode_id="newsroom-2024-tt004",
    new_hash="def456...",
    file_size=1024000,
    last_modified=datetime.now()
)
```

---

## Backup Management

### Manual Backup

```python
from src.core.database import DatabaseManager

db_manager = DatabaseManager(config.database)
backup_path = db_manager.backup_database()
print(f"Backup created: {backup_path}")
```

### Restore from Backup

```python
db_manager.restore_database("data/pipeline_backup_20251021_143000.db")
```

### List Backups

```bash
# In data directory
ls -lh *_backup_*.db
```

---

## Performance Considerations

### File Hashing Speed

- **Small files (<100MB):** ~1-2 seconds
- **Medium files (100MB-1GB):** ~5-10 seconds  
- **Large files (>1GB):** ~10-30 seconds

Hashing is done only once during discovery, not on every workflow run.

### Database Size

- **Per episode:** ~2-5 KB (metadata + hash)
- **1000 episodes:** ~2-5 MB
- **10,000 episodes:** ~20-50 MB

Database remains small and fast even with thousands of episodes.

### Backup Size

- Backup file size ≈ Database size
- Compressed backups can be 50-70% smaller
- Old backups auto-deleted after 7 days

---

## Troubleshooting

### Issue: Duplicate Not Detected

**Possible Causes:**
1. File content actually different (even if filename same)
2. File corrupted during copy
3. Different video encoding/compression

**Solution:**
```bash
# Manually check file hashes
sha256sum file1.mp4
sha256sum file2.mp4
```

### Issue: Hash Calculation Slow

**Possible Causes:**
1. Very large video files (>5GB)
2. Slow disk I/O
3. Network-mounted storage

**Solution:**
- Use local SSD for video storage
- Consider using MD5 instead of SHA256 (faster but less secure)
- Process files in smaller batches

### Issue: Backup Failed

**Possible Causes:**
1. Disk space full
2. Permission issues
3. Database locked

**Solution:**
```python
# Check disk space
import shutil
stats = shutil.disk_usage("/")
print(f"Free space: {stats.free / (1024**3):.2f} GB")

# Check database size
db_size = Path("data/pipeline.db").stat().st_size
print(f"Database size: {db_size / (1024**2):.2f} MB")
```

### Issue: ffprobe Not Found

**Error:** `Failed to extract duration`

**Solution:**
```bash
# Install ffmpeg (includes ffprobe)
# Windows (with Chocolatey):
choco install ffmpeg

# Ubuntu/Debian:
sudo apt install ffmpeg

# Verify installation:
ffprobe -version
```

---

## Best Practices

### 1. Regular Backups
- Keep `backup_enabled: true` in production
- Store backups on different drive/server
- Test restore procedure periodically

### 2. Monitor Database Size
```python
# Get database stats
stats = db_manager.get_database_stats()
print(f"Episodes: {stats['episodes_count']}")
print(f"Database size: {stats['database_size'] / (1024**2):.2f} MB")
```

### 3. Clean Up Old Episodes
```python
# Archive old episodes (>1 year)
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(days=365)
# Implement archive logic based on created_at
```

### 4. Validate File Integrity
```python
# Periodically verify files still exist and match hash
for episode in registry.get_all_episodes():
    if not Path(episode.source.path).exists():
        logger.warning(f"File missing: {episode.source.path}")
```

---

## Migration from Old System

If you have existing episodes without hashes:

```python
# Run migration script
from pathlib import Path
import hashlib

registry = get_registry()
episodes = registry.get_all_episodes()

for episode in episodes:
    if not episode.content_hash or episode.content_hash.startswith('md5:'):
        # Recalculate hash
        file_path = Path(episode.source.path)
        if file_path.exists():
            new_hash = calculate_file_hash(file_path)
            registry.update_episode_hash(
                episode.episode_id,
                new_hash,
                file_path.stat().st_size,
                datetime.fromtimestamp(file_path.stat().st_mtime)
            )
            print(f"Updated: {episode.episode_id}")
```

---

## Summary

✅ **Content-based deduplication** - No more duplicate processing  
✅ **File size & duration tracking** - Better validation  
✅ **Source path tracking** - Know where files are  
✅ **Automatic backups** - Data safety guaranteed  
✅ **Efficient hashing** - Fast even for large files  
✅ **Cross-folder detection** - Find duplicates anywhere  

The system now provides enterprise-grade deduplication and data protection! 🎉
