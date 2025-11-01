# Comprehensive Cleanup Mechanism for AI-EWG Pipeline

## Problem Statement

When video processing fails, old cached data remains in multiple places and causes issues when rerunning:

1. **Streamlit session state cache** - Old episode data, progress, and file cache remains
2. **File system cache** - Partial files from failed processing remain
3. **API/Database state** - Episode registry may have stale state
4. **No proper cleanup on failure** - When processing fails, cleanup doesn't happen

## Solution Overview

Implemented a comprehensive cleanup mechanism that addresses all caching layers:

### 1. Deep Cache Clearing (`clear_all_caches_and_state()`)

**Location**: `components/processing.py`

Clears all Streamlit session state caches:

- Processing state: `processing_active`, `processing_episodes`, `processing_progress`, `processing_results`
- Data caches: `episodes_data`, `last_refresh`, `file_cache`, `file_cache_timestamps`
- API caches: `api_cache`, `cache_timestamps`
- Temporary files: `copied_files_for_cleanup`
- Episode-specific caches: `clip_metadata_*`, `discovered_clips_*`, `episode_*`

### 2. Failed Episode File Cleanup (`cleanup_failed_episode_files()`)

**Location**: `components/processing.py`

Uses the file manager's `cleanup_episode_files()` method to remove:

- Clips directory
- Outputs directory
- Social packages directory
- Transcripts (optional)

### 3. Automatic Cleanup on Failure

**Location**: `process_episode_workflow()` exception handler

When episode processing fails:

1. Automatically calls `cleanup_failed_episode_files()`
2. Updates progress state with cleanup status
3. Logs cleanup success/failure

### 4. Force Reprocess Enhancement

**Location**: `process_episode_workflow()`

When `force_reprocess=True`:

1. Cleans up existing episode files before processing
2. Clears API-side errors for the episode
3. Ensures fresh start for processing

### 5. User Interface Controls

#### Processing Page Controls

- **Deep Clean Button**: Comprehensive cleanup of all caches and temporary files
- **Clear Cache on Start**: Default enabled option to prevent stale data
- **Force Reprocess Warning**: Shows warning about file cleanup when enabled
- **Retry with Cleanup**: Failed episode retry includes automatic cleanup

#### Dashboard Sidebar

- **Deep Clean Button**: Global cleanup accessible from any page

### 6. Retry Mechanism Enhancement

**Location**: `render_processing_results()`

When retrying failed episodes:

1. Automatically cleans up failed episode files
2. Resets progress state
3. Shows cleanup status to user
4. Forces reprocessing with clean state

## Usage Instructions

### For Users

1. **Automatic Cleanup** (Recommended):

   - Keep "Clear Cache on Start" enabled (default)
   - This prevents most stale data issues

2. **Force Reprocess**:

   - Check "Force Reprocess" for problematic episodes
   - This will clean up all existing files and caches

3. **Manual Deep Clean**:

   - Use "Deep Clean" button when experiencing persistent issues
   - Available in processing page and dashboard sidebar

4. **Retry Failed Episodes**:
   - Use "Retry All Failed Episodes" button
   - Automatically includes cleanup of failed files

### For Developers

```python
# Clear all caches and state
interface = VideoProcessingInterface()
interface.clear_all_caches_and_state()

# Clean up specific failed episode
interface.cleanup_failed_episode_files("episode_id")

# Deep cleanup from dashboard
from dashboard import deep_cleanup_all_state
deep_cleanup_all_state()
```

## Technical Details

### Cache Layers Addressed

1. **Streamlit Session State**

   - Episode processing state
   - File operation caches
   - API response caches
   - UI component state

2. **File System**

   - Partial episode outputs
   - Failed clip renders
   - Incomplete social packages
   - Temporary uploaded files

3. **API/Database State**
   - Episode error states
   - Processing stage inconsistencies

### Error Handling

- All cleanup operations include comprehensive error handling
- Failed cleanup is logged but doesn't prevent processing
- User is informed of cleanup success/failure status
- Graceful degradation when cleanup partially fails

### Performance Considerations

- Cleanup operations are fast (< 1 second typically)
- File operations use efficient batch deletion
- Cache clearing is selective to preserve authentication state
- Background cleanup doesn't block UI

## Testing

The cleanup mechanism has been tested with:

- Failed episode processing scenarios
- Large file uploads with failures
- Multiple retry attempts
- Cache corruption scenarios
- Partial file system cleanup

## Future Enhancements

1. **Scheduled Cleanup**: Automatic cleanup of old temporary files
2. **Selective Cleanup**: Clean only specific episode data
3. **Cleanup Metrics**: Track cleanup effectiveness
4. **Recovery Verification**: Verify cleanup success before retry
