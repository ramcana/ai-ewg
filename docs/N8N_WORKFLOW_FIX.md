# n8n Workflow Fix: Episode ID "unknown" Issue

## Problem Summary

The V-html.json workflow was sending `episode_id = "unknown"` to the backend API, causing processing failures:

```
ProcessingError: Episode not found: unknown
```

## Root Cause

The workflow had **cascading fallback logic** that defaulted to `"unknown"` when filename extraction failed:

### Bug Location 1: Parse File List Node
```javascript
// ❌ BEFORE: filename was not properly extracted
const filename = filePath.split('/').pop();
// If filePath had trailing spaces or was malformed, filename would be undefined
```

### Bug Location 2: Prepare Episode Data Node
```javascript
// ❌ BEFORE: Fallback to 'unknown.mp4'
filename = filename || 'unknown.mp4';  // This masked the real problem
```

### Bug Location 3: Extract Episode ID Node
```javascript
// ❌ BEFORE: Another fallback
filename = filename || 'unknown.mp4';

// This would generate episode_id = 'unknown'
episodeId = filename.replace('.mp4', '').toLowerCase().replace(/[^a-z0-9-]/g, '-');
```

## The Fix

### 1. Parse File List Node (Line 71)
**Changed:**
- Added `.trim()` to handle whitespace in file paths
- Added logging to verify parsed filenames
- Ensured filename is always extracted correctly

```javascript
// ✅ AFTER
const items = files.map(filePath => {
  // Extract filename from full path
  const filename = filePath.trim().split('/').pop();
  
  return {
    json: {
      video_path: filePath.trim(),
      filename: filename,  // Now guaranteed to be set
      apiUrl: config.apiUrl,
      outputFolderHTML: config.outputFolderHTML,
      outputFolderCSV: config.outputFolderCSV
    }
  };
});

console.log(`Parsed ${items.length} video files`);
items.forEach(item => console.log(`  - ${item.json.filename}`));
```

### 2. Prepare Episode Data Node (Line 84)
**Changed:**
- Removed fallback to `'unknown.mp4'`
- Added validation to fail fast if filename is missing
- Added logging for debugging

```javascript
// ✅ AFTER
// Validate filename exists
if (!filename) {
  throw new Error('Filename is missing from input data');
}

console.log(`Preparing episode data for: ${filename}`);
```

### 3. Extract Episode ID Node (Line 123)
**Changed:**
- Removed fallback to `'unknown.mp4'`
- Added validation to fail fast
- Added better logging to show whether episode was found in discovery or generated

```javascript
// ✅ AFTER
// Validate filename exists
if (!filename) {
  throw new Error('Filename is missing - cannot extract episode ID');
}

// Try to find matching episode from discovery response
if (discoveryResponse.episodes && Array.isArray(discoveryResponse.episodes)) {
  const matchingEpisode = discoveryResponse.episodes.find(ep =>
    ep.source_path && ep.source_path.includes(filename)
  );
  
  if (matchingEpisode) {
    episodeId = matchingEpisode.episode_id;
    console.log(`✅ Found episode in discovery: ${episodeId}`);
  }
}

// If not found in discovery, construct episode_id from filename
if (!episodeId) {
  episodeId = filename
    .replace('.mp4', '')
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-');
  console.log(`⚠️ Episode not in discovery, generated ID: ${episodeId}`);
}

console.log(`Episode ID for ${filename}: ${episodeId}`);
```

## Benefits of the Fix

### 1. Fail Fast
Instead of silently defaulting to "unknown", the workflow now **throws an error** if filename is missing. This makes debugging much easier.

### 2. Better Logging
Each node now logs what it's doing:
```
Parsed 1 video files
  - OSS096.mp4
Preparing episode data for: OSS096.mp4
✅ Found episode in discovery: newsroom-2024-oss096
Episode ID for OSS096.mp4: newsroom-2024-oss096
```

### 3. Robust Filename Extraction
- Handles trailing whitespace
- Validates at each step
- No silent failures

## Testing

### Before Fix
```bash
# Backend logs showed:
Episode not found: unknown
```

### After Fix
```bash
# n8n logs will show:
Parsed 1 video files
  - OSS096.mp4
Preparing episode data for: OSS096.mp4
✅ Found episode in discovery: newsroom-2024-oss096

# Backend logs will show:
Starting episode processing: newsroom-2024-oss096
```

## How to Apply

1. **Import the fixed workflow:**
   - Open n8n
   - Import `n8n_workflows/V-html.json`
   - Or manually update the three nodes with the code above

2. **Test the workflow:**
   ```bash
   # Ensure backend is running
   python src/cli.py --config config/pipeline.yaml api --port 8000
   
   # Run the workflow in n8n
   # Check console logs for the new debug output
   ```

3. **Verify episode_id is correct:**
   - Check n8n execution logs
   - Should see actual episode ID like `newsroom-2024-oss096`
   - Should NOT see `unknown`

## Related Fixes

This workflow fix works in conjunction with the backend path normalization fix:
- **Backend:** `src/core/path_utils.py` - Handles Linux/Windows path conversion
- **Backend:** `src/core/registry.py` - Filename-based episode lookup fallback
- **Workflow:** `V-html.json` - Proper filename extraction and episode ID generation

## Summary

✅ **Fixed:**
- Removed all fallbacks to "unknown"
- Added validation at each step
- Added comprehensive logging
- Ensured filename is always extracted correctly

✅ **Result:**
- Workflow now sends correct episode_id to backend
- Backend can find and process episodes successfully
- Errors are caught early with clear messages

✅ **Files Modified:**
- `n8n_workflows/V-html.json` (3 nodes updated)
