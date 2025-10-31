# Cache Clearing Solution for AI-EWG Processing

## Problem

When a video processing workflow fails, old cached data remains in the system, causing issues when rerunning the same episode. This leads to:

- Stale metadata being used
- Failed processing states persisting
- Inconsistent behavior between runs
- Difficulty in debugging actual issues

## Solution Overview

Implemented comprehensive cache clearing mechanisms at multiple levels:

### 1. Processing Interface Cache Management

**Location**: `components/processing.py`

#### New Methods Added:

- `clear_all_caches(episode_id=None)` - Clear all or episode-specific caches
- `clear_failed_episode_cache(episode_id)` - Clear cache for failed episodes
- `cleanup_failed_episode_files(episode_id)` - Clean up temporary files

#### Automatic Cache Clearing:

- **On Failure**: Automatically clears cache when episode processing fails
- **On Retry**: Clears cache before retrying failed episodes
- **On Start**: Optional cache clearing when starting new processing (default: enabled)

#### Manual Cache Management:

- **Clear All Button**: Clears all caches and processing state
- **Deep Cleanup Button**: Clears caches + temporary files
- **Cache Stats Button**: Shows current cache statistics

### 2. API Client Cache Management

**Location**: `utils/api_client.py`

#### New Methods Added:

- `clear_all_cache()` - Clear all API response cache
- `clear_episode_cache(episode_id)` - Clear episode-specific API cache
- `clear_cache_by_type(cache_type)` - Clear cache by type (health, episodes, etc.)

### 3. Processing Options Enhancement

**Location**: `components/processing.py`

#### New Options:

- **Clear Cache on Start**: Checkbox option (default: enabled)
- **Force Reprocess**: Enhanced to include cache clearing
- **Retry Logic**: Automatically clears cache before retry

### 4. Command Line Support

**Location**: `process_episode.py`

#### New Command Line Options:

```bash
python process_episode.py                    # Normal processing
python process_episode.py --force            # Force reprocess
python process_episode.py --clear-cache      # Clear cache first
python process_episode.py --force --clear-cache  # Both options
```

## Cache Types Managed

### Session State Caches:

- `episodes_data` - Episode discovery results
- `processing_progress` - Current processing status
- `processing_results` - Final processing results
- `clip_metadata_*` - Clip discovery and metadata
- `discovered_clips_*` - Discovered clips data
- `file_cache` - File system operation cache
- `api_cache` - API response cache

### File System Caches:

- Temporary uploaded files
- Copied files in monitored directories
- Partial processing outputs
- Failed episode artifacts

## Usage Examples

### In Dashboard:

1. **Automatic**: Cache clearing happens automatically on failures and retries
2. **Manual**: Use "Clear All" or "Deep Cleanup" buttons in processing controls
3. **Selective**: Failed episode retry automatically clears only relevant caches

### Command Line:

```bash
# Clear cache and reprocess
python process_episode.py --clear-cache --force

# Normal processing (cache clearing on start is default in GUI)
python process_episode.py
```

### Programmatic:

```python
# In processing interface
interface = VideoProcessingInterface()

# Clear all caches
interface.clear_all_caches()

# Clear specific episode cache
interface.clear_failed_episode_cache("episode_123")

# Clear API cache
interface.api_client.clear_all_cache()
```

## Benefits

1. **Reliability**: Eliminates stale data issues causing processing failures
2. **Debugging**: Clean state makes it easier to identify real issues
3. **Consistency**: Each run starts with fresh data
4. **Recovery**: Failed episodes can be cleanly retried
5. **Performance**: Prevents cache bloat and memory issues

## Best Practices

1. **Always clear cache on retry** - Implemented automatically
2. **Clear cache when changing processing options** - Use "Clear All" button
3. **Use deep cleanup for persistent issues** - Clears files + cache
4. **Monitor cache statistics** - Use cache stats button to check cache size
5. **Enable "Clear Cache on Start"** - Default behavior for clean processing

## Implementation Notes

- Cache clearing is fail-safe - errors in cache clearing don't stop processing
- Automatic cache clearing happens before processing starts and after failures
- Manual cache clearing provides immediate feedback
- Command line options match GUI functionality
- All cache operations are logged for debugging

This solution ensures that cache-related issues don't interfere with video processing workflows, providing a more reliable and predictable system.
