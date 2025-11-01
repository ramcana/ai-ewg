# Comprehensive Cleanup Solution for AI-EWG Pipeline

## Problem Statement

When a process fails in the AI-EWG pipeline, old cached data and intermediate files remain, causing issues when rerunning the process. This leads to:

1. **Stale Cache Issues**: Old API responses, file metadata, and processing state persist
2. **Incomplete File Cleanup**: Failed episodes leave partial files that interfere with reprocessing
3. **Session State Pollution**: Streamlit session state accumulates stale data across runs
4. **Inconsistent Retry Behavior**: Retries may use cached data instead of fresh processing

## Solution Overview

I've implemented a comprehensive cleanup mechanism with multiple layers:

### 1. Automatic Cache Clearing

**Location**: `components/processing.py`

- **On Process Start**: Automatically clears caches when "Clear Cache on Start" is enabled (default: True)
- **On Force Reprocess**: Deep cleanup when force reprocess is enabled
- **On Failure**: Automatic cleanup of failed episodes to prevent stale data

### 2. Manual Cleanup Controls

**Processing Page Controls**:

- **🧹 Deep Clean Button**: Comprehensive cleanup of all caches and temporary files
- **🗑️ Clear Results Button**: Clears processing results and progress
- **Clear Cache on Start Checkbox**: Default enabled option to prevent stale data

### 3. Comprehensive Cleanup Methods

#### `clear_all_caches_and_state(episode_ids=None)`

Clears multiple types of cached data:

```python
# Streamlit session state caches
- clip_metadata_{episode_id}
- discovered_clips_{episode_id}
- episode_status_{episode_id}
- episode_outputs_{episode_id}
- social_packages_{episode_id}
- processing_progress

# File manager caches
- file_cache
- file_cache_timestamps

# API client caches
- api_cache
- cache_timestamps

# Error states
- Processing errors via error_reporter
```

#### `cleanup_episode_files_on_failure(episode_ids, keep_transcripts=True)`

Cleans up file system artifacts for failed episodes:

```python
# Removes directories:
- clips/{episode_id}/
- outputs/{episode_id}/
- social/{episode_id}/
- transcripts/{episode_id}.* (optional)
```

### 4. Enhanced Processing Workflow

#### Force Reprocess Behavior

When `force_reprocess=True`:

1. **Cache Clearing**: All episode-related caches are cleared
2. **File Cleanup**: Intermediate files are removed
3. **State Reset**: Processing stage is reset to "discovered"
4. **Error Clearing**: Previous errors are cleared

#### Failure Recovery

When episodes fail:

1. **Immediate Cleanup**: Failed episode files are cleaned up
2. **Cache Invalidation**: Related caches are cleared
3. **State Marking**: Episode is marked as failed with error details
4. **Retry Preparation**: Clean state for potential retry

### 5. API Integration

#### Enhanced API Client

**Location**: `utils/api_client.py`

The API client now supports:

- `force_reprocess` parameter in process_episode calls
- Automatic cache clearing on force reprocess
- Better error handling and retry logic

#### CLI Integration

**Location**: `src/cli.py`

The CLI supports:

- `--force` flag for force reprocessing
- `--clear-errors` flag for error clearing
- Recovery operations with cleanup

### 6. User Interface Improvements

#### Processing Options

- **Force Reprocess**: Checkbox with clear explanation of cleanup behavior
- **Clear Cache on Start**: Default enabled to prevent stale data issues
- **Debug Info**: Shows current cache state and processing options

#### Visual Feedback

- **Cleanup Progress**: Spinner and progress indicators during cleanup
- **Success Messages**: Clear confirmation of cleanup completion
- **Error Details**: Detailed error information with cleanup suggestions

## Usage Guide

### 1. Automatic Cleanup (Recommended)

**Default Behavior**:

- Keep "Clear Cache on Start" enabled (default)
- Use "Force Reprocess" when encountering stale data issues

### 2. Manual Cleanup

**When to Use**:

- Persistent processing issues
- Suspected cache corruption
- After system errors or crashes

**How to Use**:

1. Navigate to "Process Videos" page
2. Click "🧹 Deep Clean" button
3. Wait for cleanup completion
4. Retry processing

### 3. Troubleshooting Failed Episodes

**Automatic Recovery**:

1. Failed episodes are automatically cleaned up
2. Retry buttons clear relevant caches
3. Force reprocess ensures fresh processing

**Manual Recovery**:

1. Use "🧹 Deep Clean" for comprehensive cleanup
2. Enable "Force Reprocess" for problematic episodes
3. Check debug info to verify cache state

## Technical Implementation Details

### Cache Key Patterns

The system recognizes and clears these cache key patterns:

```python
CACHE_PATTERNS = [
    'clip_metadata_',
    'discovered_clips_',
    'episode_status_',
    'episode_outputs_',
    'social_packages_',
    'processing_progress'
]
```

### File System Cleanup

The system cleans up these directory structures:

```
data/
├── clips/{episode_id}/          # Clip files and metadata
├── outputs/{episode_id}/        # Generated HTML and assets
├── social/{episode_id}/         # Social media packages
└── transcripts/{episode_id}.*   # Transcript files (optional)
```

### Error Handling

The cleanup system includes comprehensive error handling:

- **Non-blocking**: Cleanup errors don't prevent processing
- **Logging**: All cleanup operations are logged
- **Graceful Degradation**: Partial cleanup is better than no cleanup
- **User Feedback**: Clear messages about cleanup status

## Benefits

1. **Reliability**: Eliminates stale data issues that cause processing failures
2. **Consistency**: Ensures fresh processing on retries
3. **User Experience**: Clear controls and feedback for cleanup operations
4. **Maintainability**: Centralized cleanup logic that's easy to extend
5. **Performance**: Prevents cache bloat and memory issues

## Future Enhancements

1. **Selective Cleanup**: More granular control over what gets cleaned
2. **Cache Statistics**: Dashboard showing cache usage and hit rates
3. **Automated Maintenance**: Scheduled cleanup of old cache entries
4. **Cache Warming**: Pre-populate caches with frequently used data
5. **Distributed Cleanup**: Cleanup coordination across multiple instances

## Testing

The cleanup mechanism has been tested with:

- ✅ Failed episode processing scenarios
- ✅ Force reprocess workflows
- ✅ Manual cleanup operations
- ✅ Cache invalidation edge cases
- ✅ File system cleanup operations
- ✅ Session state management

## Monitoring

Monitor cleanup effectiveness through:

- **Log Messages**: Cleanup operations are logged with details
- **User Feedback**: Success/error messages in the UI
- **Cache Statistics**: Available through debug info
- **File System**: Check for orphaned files in data directories

This comprehensive cleanup solution addresses the core issue of stale cache and state data interfering with processing retries, providing both automatic and manual cleanup mechanisms for reliable operation.
