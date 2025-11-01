# Streamlit-API Communication Fix

## Problem Identified

The Streamlit dashboard was unable to discover episodes because of a **path mismatch** between where files were being copied and where the API was looking for them.

### Root Cause

1. **Streamlit copied files to**: `test_videos/newsroom/2024`
2. **API monitored path in config**: `data/test_videos/newsroom/2024`
3. **Result**: Files copied successfully, but API discovery found nothing

## Changes Made

### 1. Fixed Path in `components/processing.py`

**Line 760**: Changed monitored directory path
```python
# BEFORE (incorrect):
monitored_dir = Path("test_videos/newsroom/2024")

# AFTER (correct):
monitored_dir = Path("data/test_videos/newsroom/2024")
```

**Line 1491**: Updated manual copy command recommendation
```python
# BEFORE (incorrect):
target_dir = "test_videos/newsroom/2024"

# AFTER (correct):
target_dir = "data/test_videos/newsroom/2024"
```

### 2. Created Diagnostic Script

Created `diagnose_and_fix_discovery.py` to help identify API communication issues:
- Checks API server status
- Verifies configuration
- Lists video files in all monitored directories
- Tests API discovery endpoint
- Provides detailed recommendations

## How to Test the Fix

### Step 1: Ensure API Server is Running

```powershell
# Terminal 1: Start API Server
venv\Scripts\activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### Step 2: Run Diagnostic Script (Optional)

```powershell
# Terminal 2: Run diagnostics
venv\Scripts\activate.ps1
python diagnose_and_fix_discovery.py
```

This will show you:
- ✅ API server status
- 📁 Video files in monitored directories
- 🔍 Discovery results
- 💡 Recommendations if issues found

### Step 3: Start Streamlit Dashboard

```powershell
# Terminal 3: Start Streamlit
venv\Scripts\activate.ps1
streamlit run dashboard.py
```

### Step 4: Test Episode Discovery

1. Navigate to **Process Videos** page
2. Select your video file (e.g., `BB_test_10mins.mp4`)
3. Click **Start Processing**
4. The dashboard will now:
   - Copy file to `data/test_videos/newsroom/2024` (correct path)
   - Call API discovery
   - Find the episode successfully

## Expected Behavior After Fix

### Before Fix:
```
🔍 Discovering episodes via API...
⚠️ No episodes found via API discovery
📁 Attempting to register files with API...
✅ Copied 1 files to monitored directory
⚠️ Files copied but no episodes discovered by API
❌ Unable to register episodes with API
```

### After Fix:
```
🔍 Discovering episodes via API...
✅ Found 1 episodes from uploaded files!
📹 Discovered Episodes:
  - BB_test_10mins (data/test_videos/newsroom/2024/20241026_175100_BB_test_10mins.mp4)
🚀 Starting batch processing of 1 episodes...
```

## Configuration Reference

The API server monitors these directories (from `config/pipeline.yaml`):

```yaml
sources:
  - path: "data/test_videos/newsroom/2024"
    include: ["*.mp4", "*.mkv", "*.avi", "*.mov"]
    enabled: true
  
  - path: "data/temp/uploaded"
    include: ["*.mp4", "*.mkv", "*.avi", "*.mov", "*.webm", "*.flv"]
    enabled: true
```

**Important**: Streamlit must copy files to one of these monitored paths for API discovery to work.

## Troubleshooting

### Issue: API server not responding

**Solution**:
```powershell
# Check if server is running
curl http://localhost:8000/health

# If not running, start it:
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### Issue: Discovery still finds no episodes

**Checklist**:
1. ✅ API server running on port 8000
2. ✅ Video file exists in `data/test_videos/newsroom/2024`
3. ✅ File has valid video extension (.mp4, .mkv, etc.)
4. ✅ Source path is enabled in `config/pipeline.yaml`

**Run diagnostics**:
```powershell
python diagnose_and_fix_discovery.py
```

### Issue: File permissions error

**Solution**:
```powershell
# Ensure data directory exists and is writable
mkdir -p data/test_videos/newsroom/2024

# Check permissions
icacls data\test_videos\newsroom\2024
```

### Issue: Database locked errors

**Solution**: This is a known issue with SQLite. See `docs/SQLITE_LOCKING_FIXES.md` for comprehensive fixes. Quick fix:
- Ensure only 1 API server instance is running
- Restart API server if database gets locked

## Manual File Placement (Alternative)

If you prefer to manually place files instead of using Streamlit upload:

```powershell
# Copy your video file directly to monitored directory
copy "path\to\your\video.mp4" "data\test_videos\newsroom\2024\"

# Then in Streamlit, just click "Discover Episodes"
```

## Testing with Sample File

```powershell
# 1. Ensure directories exist
mkdir -p data/test_videos/newsroom/2024

# 2. Copy your test file
copy "BB_test_10mins.mp4" "data\test_videos\newsroom\2024\"

# 3. Test API discovery directly
python test_api_discovery.py

# Expected output:
# Discovery - Success: True
# Found 1 episodes in dict
# Episode 1: {'episode_id': 'newsroom-2024-bb_test_10mins', ...}
```

## Summary

The fix ensures that:
1. ✅ Streamlit copies files to the correct monitored directory
2. ✅ API discovery can find the copied files
3. ✅ Episode registration works properly
4. ✅ Processing can proceed normally

**Key Takeaway**: Always ensure file paths in Streamlit match the monitored paths in `config/pipeline.yaml`.
