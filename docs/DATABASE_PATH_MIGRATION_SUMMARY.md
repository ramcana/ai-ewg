# Database Path Migration - Complete ✅

## Summary

All hardcoded D: drive paths have been removed from the codebase AND the database is now configured to store relative paths for portability.

## Changes Made

### 1. Configuration (`config/pipeline.yaml`)
- Removed all D: drive paths
- Using relative paths: `test_videos/newsroom/2024`, `data/temp/uploaded`

### 2. Code Updates

#### `src/core/models.py` - Added Path Resolution
**New method in `SourceInfo` class:**
```python
def get_absolute_path(self) -> Path:
    """Get absolute path to source file, resolving relative paths from project root"""
    path_obj = Path(self.path)
    if path_obj.is_absolute():
        return path_obj
    project_root = Path(__file__).parent.parent.parent.resolve()
    return (project_root / path_obj).resolve()
```

#### `src/core/pipeline.py` - Store Relative Paths
**Lines 748-756:** Discovery now stores relative paths in database
```python
# Store relative path from project root to make database portable
try:
    project_root = Path(__file__).parent.parent.parent.resolve()
    relative_path = video_file.relative_to(project_root)
    source_path = str(relative_path).replace('\\', '/')
except ValueError:
    # File is outside project root, store absolute path
    source_path = str(video_file).replace('\\', '/')
```

#### Updated File Access Points
- `src/stages/prep_stage.py`: Use `episode.source.get_absolute_path()`
- `src/api/clip_endpoints.py`: Use `episode.source.get_absolute_path()` (2 locations)

### 3. Path Utilities (`src/core/path_utils.py`)
- Removed hardcoded `D:/n8n/ai-ewg` paths
- Now uses dynamic project root resolution
- Supports relative path resolution from project root

### 4. Tests (`tests/test_mini.py`)
- Updated test paths from `D:/test/...` to `test/...`

## Database Migration

### For Existing Databases

If you have an existing database with absolute D: paths, run the migration script:

```powershell
# Dry run to see what would change
python migrate_database_paths.py --dry-run

# Apply migration (creates backup automatically)
python migrate_database_paths.py

# Skip backup if you're confident
python migrate_database_paths.py --no-backup
```

### What the Migration Does

1. **Backs up database** (unless `--no-backup`)
2. **Converts paths**:
   - `D:/n8n/ai-ewg/test_videos/...` → `test_videos/...`
   - `D:/n8n/ai-ewg/data/...` → `data/...`
3. **Verifies** no D: paths remain
4. **Updates** all episode records

## Benefits

### ✅ Portability
- Database can be moved to any drive/location
- Works on different machines without path updates
- No hardcoded drive letters

### ✅ Compatibility
- Works with relative paths (stored in DB)
- Works with absolute paths (legacy support)
- Automatically resolves paths when accessing files

### ✅ Backward Compatible
- Old absolute paths still work
- `get_absolute_path()` handles both cases
- No breaking changes to existing code

## How It Works

### Storage (Database)
```
Stored in DB: "test_videos/newsroom/2024/video.mp4"
```

### Runtime (File Access)
```python
# Code calls:
source_path = episode.source.get_absolute_path()

# Returns:
# D:/n8n/ai-ewg/test_videos/newsroom/2024/video.mp4  (on Windows)
# /home/user/ai-ewg/test_videos/newsroom/2024/video.mp4  (on Linux)
```

### Project Root Detection
```python
# Automatically detected from code location:
# src/core/models.py → ../../ → project root
project_root = Path(__file__).parent.parent.parent.resolve()
```

## Testing

### 1. Restart API Server (REQUIRED)
```powershell
# Stop current server (Ctrl+C)
# Restart:
venv\Scripts\activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### 2. Test Discovery
```powershell
python test_api_discovery.py
```

**Expected:** Episodes discovered with relative paths like `test_videos/newsroom/2024/video.mp4`

### 3. Test File Access
```powershell
# Start Streamlit
streamlit run dashboard.py

# Process a video - should work normally
# File access automatically resolves relative → absolute
```

### 4. Verify Database
```powershell
# Check database paths
sqlite3 data/pipeline.db "SELECT id, source_path FROM episodes LIMIT 5;"
```

**Expected:** No `D:` prefixes in source_path column

## Troubleshooting

### Issue: "Source file not found"

**Cause:** Path resolution failing

**Solution:**
```python
# Check what path is being resolved:
episode = registry.get_episode(episode_id)
print(f"Stored path: {episode.source.path}")
print(f"Resolved path: {episode.source.get_absolute_path()}")
print(f"Exists: {episode.source.get_absolute_path().exists()}")
```

### Issue: Old episodes still have D: paths

**Solution:** Run migration script
```powershell
python migrate_database_paths.py
```

### Issue: Files outside project root

**Behavior:** Absolute paths are stored as-is (fallback)

**Example:**
- File at: `E:/external/video.mp4`
- Stored as: `E:/external/video.mp4` (absolute)
- This is intentional for external files

## Next Steps

1. ✅ Restart API server
2. ✅ Run migration script (if you have existing data)
3. ✅ Test discovery and processing
4. ✅ Verify paths in database are relative
5. ✅ Test Streamlit dashboard

## Files Modified

- `config/pipeline.yaml` - Relative paths only
- `src/core/models.py` - Added `get_absolute_path()` method
- `src/core/pipeline.py` - Store relative paths on discovery
- `src/core/path_utils.py` - Dynamic project root
- `src/stages/prep_stage.py` - Use `get_absolute_path()`
- `src/api/clip_endpoints.py` - Use `get_absolute_path()` (2x)
- `tests/test_mini.py` - Relative test paths
- `components/processing.py` - Relative monitored paths

## Files Created

- `migrate_database_paths.py` - Database migration script
- `DATABASE_PATH_MIGRATION_SUMMARY.md` - This document
