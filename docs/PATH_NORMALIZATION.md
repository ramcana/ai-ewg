# Path Normalization for n8n Integration

## Problem

When n8n runs in a Docker container and calls the backend API running on Windows host, path mismatches occur:

- **n8n (Docker)**: Uses Linux-style paths like `/data/test_videos/newsroom/2024/OSS096.mp4`
- **Backend (Windows)**: Expects Windows paths like `D:\n8n\ai-ewg\data\test_videos\newsroom\2024\OSS096.mp4`

This causes errors like:
```
WARNING - Source path does not exist: \data\test_videos\newsroom\2024
ProcessingError: Episode not found: unknown
```

## Solution Implemented

### Backend-Only Fix (Recommended)

The backend now handles path normalization automatically using **three-tier fallback strategy**:

#### 1. Path Normalization (`src/core/path_utils.py`)

New utility module that:
- Converts Linux paths to Windows paths automatically
- Maps Docker container paths (`/data`) to host paths (`D:\n8n\ai-ewg\data`)
- Handles mixed separators (`/` and `\`)
- Works cross-platform (Windows, Linux, macOS)

**Example:**
```python
from src.core.path_utils import normalize_path

# Automatically maps container path to host
path = normalize_path("/data/test_videos/newsroom/2024")
# Returns: WindowsPath('D:/n8n/ai-ewg/data/test_videos/newsroom/2024')
```

#### 2. Episode Discovery Enhancement

Updated `src/core/pipeline.py` to use path normalization:
```python
# Before
source_path = Path(source.path)  # Fails with Linux paths

# After
source_path = normalize_path(source.path)  # Handles any path format
```

#### 3. Filename-Based Fallback

Added `find_episode_by_filename()` to `src/core/registry.py`:
- When episode ID lookup fails, searches by filename
- Useful when n8n generates episode IDs differently than backend
- Case-insensitive matching on Windows

**Example:**
```python
# n8n sends: episode_id = "newsroom-2024-oss096"
# Backend extracts: "oss096" -> searches for "oss096.mp4"
# Finds episode even if stored with different ID format
```

## How It Works

### Discovery Flow

```
1. n8n calls: POST /episodes/discover
   ↓
2. Backend normalizes configured source paths
   D:\n8n\ai-ewg\data\test_videos\newsroom\2024
   ↓
3. Scans for .mp4 files
   ↓
4. Registers episodes with Windows paths in database
   ↓
5. Returns episode list to n8n
```

### Processing Flow

```
1. n8n calls: POST /episodes/process
   Body: { "episode_id": "newsroom-2024-oss096", ... }
   ↓
2. Backend tries to find episode:
   a) Direct ID lookup: "newsroom-2024-oss096"
   b) If not found, extract filename: "oss096"
   c) Search database for any path containing "oss096.mp4"
   ↓
3. Episode found! Process normally
```

## Configuration

### Backend Config (`config.yaml`)

```yaml
sources:
  - name: "Newsroom 2024"
    path: "D:\\n8n\\ai-ewg\\data\\test_videos\\newsroom\\2024"  # Windows path
    enabled: true
    include:
      - "**/*.mp4"
    exclude:
      - "**/*_temp*"
```

**Important:** Use Windows paths in backend config, not Docker paths.

### n8n Workflow

No changes needed! The workflow can continue using:
- Docker container paths (`/data/...`)
- Episode IDs generated from filenames
- No path mapping required

## Path Mapping Reference

| Docker Container Path | Windows Host Path |
|----------------------|-------------------|
| `/data` | `D:\n8n\ai-ewg\data` |
| `/data/test_videos` | `D:\n8n\ai-ewg\data\test_videos` |
| `/data/test_videos/newsroom/2024` | `D:\n8n\ai-ewg\data\test_videos\newsroom\2024` |

## Troubleshooting

### Issue: "Source path does not exist"

**Cause:** Backend config has wrong path or path doesn't exist on Windows host.

**Fix:**
1. Check `config.yaml` sources use Windows paths
2. Verify directory exists: `Test-Path "D:\n8n\ai-ewg\data\test_videos\newsroom\2024"`
3. Ensure n8n volume mount matches: `-v D:\n8n\ai-ewg\data:/data`

### Issue: "Episode not found: unknown"

**Cause:** n8n is passing `episode_id = "unknown"` to backend.

**Fix:**
1. Check n8n "Prepare Episodes" node generates correct episode_id
2. Verify episode was discovered: `GET /episodes/{episode_id}`
3. Check logs for filename-based fallback attempts

### Issue: "Multiple episodes found with filename"

**Cause:** Multiple episodes have same filename in different directories.

**Fix:**
1. Use more specific episode IDs (include full path components)
2. Ensure unique filenames across all source directories
3. Check database for duplicates: `SELECT * FROM episodes WHERE source_path LIKE '%filename%'`

## Testing

### Test Path Normalization

```powershell
# Start Python REPL
python

# Test normalization
from src.core.path_utils import normalize_path, paths_match

# Test container path
path1 = normalize_path("/data/test_videos/newsroom/2024")
print(path1)  # Should show Windows path

# Test path matching
match = paths_match(
    "/data/test_videos/OSS096.mp4",
    "D:\\n8n\\ai-ewg\\data\\test_videos\\OSS096.mp4"
)
print(match)  # Should be True
```

### Test Episode Discovery

```bash
# Call discovery endpoint
curl -X POST http://localhost:8000/episodes/discover

# Check discovered episodes
curl http://localhost:8000/episodes
```

## Alternative: n8n Path Mapping (Not Recommended)

If you need to send Windows paths from n8n:

```javascript
// In n8n Function node
const dockerPath = $json.full_path;  // "/data/test_videos/OSS096.mp4"

const windowsPath = dockerPath
  .replace('/data', 'D:\\n8n\\ai-ewg\\data')
  .replaceAll('/', '\\');

return [{
  json: {
    ...$json,
    windows_path: windowsPath
  }
}];
```

**Why not recommended:**
- Duplicates path logic in two places
- Harder to maintain
- n8n workflow becomes Windows-specific
- Backend fix is more robust and centralized

## Summary

✅ **What was fixed:**
- Backend now handles Linux/Windows path conversion automatically
- Episode lookup uses filename fallback for cross-platform compatibility
- No n8n workflow changes required

✅ **Benefits:**
- n8n workflow remains platform-agnostic
- Single source of truth for path configuration (backend)
- Robust fallback mechanisms
- Works with existing n8n workflows

✅ **Files modified:**
- `src/core/path_utils.py` (new)
- `src/core/pipeline.py` (path normalization)
- `src/core/registry.py` (filename-based lookup)
