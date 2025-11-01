# Resume & Recovery System for AI-EWG Pipeline

## Overview

The AI-EWG pipeline has a comprehensive multi-layer resume and recovery system designed to handle various failure scenarios and stuck processes. Here's how it works:

## 1. Automatic Recovery Mechanisms

### Process-Level Recovery

**Location**: `components/processing.py`

#### Retry Handler with Exponential Backoff

```python
process_response = RetryHandler.with_retry(
    process_operation,
    max_attempts=2,  # Configurable retry attempts
    delay_seconds=5.0,  # Delay between retries
    operation_name=f"Episode {episode_id} Processing",
    show_progress=False
)
```

**Features**:

- Automatic retry on transient failures
- Exponential backoff to avoid overwhelming the system
- Configurable retry attempts and delays
- Progress tracking during retries

#### Connection Recovery

- Automatic API connection retry with user feedback
- Health check validation before processing
- Graceful degradation when API is unavailable

### Episode-Level Recovery

#### Failed Episode Cleanup & Retry

```python
def retry_failed_episodes():
    # 1. Clear caches for failed episodes
    # 2. Reset processing stage to 'discovered'
    # 3. Clear error states
    # 4. Restart processing with force_reprocess=True
```

**Automatic Actions**:

- Cache clearing for failed episodes
- File system cleanup of partial artifacts
- Error state reset
- Fresh processing state initialization

## 2. Manual Recovery Controls

### Dashboard Controls

#### Processing Page Controls

- **🔄 Retry All Failed Episodes**: Comprehensive retry with cache clearing
- **🧹 Deep Clean**: Full system cleanup and state reset
- **⏹️ Stop Processing**: Graceful process termination
- **🗑️ Clear Results**: Reset processing state

#### Individual Episode Recovery

- **Retry Single Episode**: Target specific failed episodes
- **Force Reprocess**: Override existing processing state
- **Clear Episode Cache**: Remove stale data for specific episodes

### Clip-Level Recovery

**Location**: `components/clips.py`

#### Individual Clip Recovery

- **🔄 Retry Single Clip**: Re-render specific failed clips
- **🔄 Re-render Clip**: Force regeneration of existing clips
- **🗑️ Delete & Retry**: Remove corrupted files and retry

#### Bulk Clip Recovery

- **🔄 Retry All Failed**: Batch retry of all failed clips
- **🔄 Regenerate All**: Force regeneration of all clips
- **🧹 Clean & Retry**: Delete failed clips and retry generation

## 3. Stuck Process Detection & Recovery

### Timeout Mechanisms

#### API Request Timeouts

```python
timeout=3600  # 1 hour timeout for episode processing
```

#### Progress Monitoring

- Real-time progress tracking
- Stuck process detection via progress stagnation
- Automatic timeout handling

### Manual Intervention Options

#### Process Termination

- **Stop Processing Button**: Graceful termination
- **Force Stop**: Immediate process termination
- **System Reset**: Complete pipeline restart

#### State Recovery

- **Resume from Last Stage**: Continue from where it stopped
- **Reset to Discovered**: Start fresh processing
- **Selective Recovery**: Choose specific stages to retry

## 4. Stage-Based Recovery

### Processing Stage Recovery

The system supports recovery from any processing stage:

```python
PROCESSING_STAGES = [
    'discovered',    # Initial discovery
    'transcribed',   # Audio transcription
    'enriched',      # Content enrichment
    'editorial',     # Editorial processing
    'rendered'       # Final rendering
]
```

#### Stage-Specific Recovery

- **From Transcribed**: Skip discovery, resume from transcription
- **From Enriched**: Resume from enrichment stage
- **From Editorial**: Resume from editorial processing
- **Force Full Reprocess**: Start from discovery regardless of current stage

### Clip Generation Recovery

```python
CLIP_STAGES = [
    'discovered',    # Clip discovery
    'generated',     # Clip generation
    'rendered'       # Final clip rendering
]
```

## 5. Error Handling & Recovery

### Error Classification

#### Transient Errors (Auto-Retry)

- Network timeouts
- Temporary API unavailability
- Resource constraints
- File system locks

#### Persistent Errors (Manual Intervention)

- Configuration issues
- Missing dependencies
- Corrupted source files
- Insufficient disk space

### Recovery Strategies

#### Automatic Recovery

```python
if error_type == 'transient':
    # Automatic retry with exponential backoff
    retry_with_backoff(operation, max_attempts=3)
elif error_type == 'cache_related':
    # Clear cache and retry
    clear_episode_cache(episode_id)
    retry_operation(operation)
```

#### Manual Recovery

```python
if error_type == 'persistent':
    # Provide user with recovery options
    show_recovery_options(error_details)
    # Allow manual intervention
    wait_for_user_action()
```

## 6. Recovery User Interface

### Visual Recovery Indicators

#### Progress Tracking

- Real-time progress bars
- Stage completion indicators
- Error state visualization
- Recovery action buttons

#### Error Details

- Detailed error messages
- Recovery suggestions
- Manual intervention options
- System health indicators

### Recovery Workflows

#### Failed Episode Recovery Workflow

1. **Identify Failed Episodes**: Show failed episodes with error details
2. **Provide Recovery Options**:
   - Retry with cache clearing
   - Force reprocess from beginning
   - Skip to next stage
   - Manual intervention
3. **Execute Recovery**: Run selected recovery action
4. **Monitor Progress**: Track recovery progress
5. **Verify Success**: Confirm successful recovery

#### Stuck Process Recovery Workflow

1. **Detect Stuck Process**: Monitor for progress stagnation
2. **Offer Intervention Options**:
   - Wait longer (extend timeout)
   - Terminate and retry
   - Skip current operation
   - Manual debugging
3. **Execute Intervention**: Perform selected action
4. **Resume Processing**: Continue from appropriate stage

## 7. Configuration & Customization

### Timeout Configuration

```python
TIMEOUTS = {
    'episode_processing': 3600,  # 1 hour
    'clip_generation': 1800,     # 30 minutes
    'api_requests': 300,         # 5 minutes
    'file_operations': 120       # 2 minutes
}
```

### Retry Configuration

```python
RETRY_CONFIG = {
    'max_attempts': 3,
    'base_delay': 5.0,
    'max_delay': 60.0,
    'exponential_base': 2.0
}
```

### Recovery Policies

```python
RECOVERY_POLICIES = {
    'auto_retry_transient': True,
    'auto_clear_cache_on_retry': True,
    'auto_cleanup_failed_files': True,
    'manual_intervention_required': ['config_error', 'missing_dependency']
}
```

## 8. Monitoring & Logging

### Recovery Metrics

- Recovery success rate
- Time to recovery
- Most common failure points
- Recovery action effectiveness

### Logging

- Detailed recovery operation logs
- Error classification and handling
- Recovery decision tracking
- Performance impact analysis

## 9. Best Practices for Users

### When Process Gets Stuck

#### Immediate Actions

1. **Check Progress**: Look for progress indicators
2. **Wait Appropriately**: Allow reasonable time for completion
3. **Check System Resources**: Verify CPU, memory, disk space
4. **Review Logs**: Check for error messages

#### Recovery Actions

1. **Soft Recovery**: Use "Retry" buttons for transient issues
2. **Cache Clearing**: Use "Deep Clean" for persistent issues
3. **Force Reprocess**: Use when data corruption is suspected
4. **Manual Intervention**: Check system configuration and dependencies

### Prevention Strategies

1. **Regular Cleanup**: Use automatic cache clearing
2. **Monitor Resources**: Ensure adequate system resources
3. **Validate Inputs**: Check source files before processing
4. **Update Dependencies**: Keep system components updated

## 10. Advanced Recovery Features

### Checkpoint System

- Save processing state at key stages
- Resume from last successful checkpoint
- Rollback to previous stable state

### Distributed Recovery

- Handle failures in multi-instance deployments
- Coordinate recovery across multiple workers
- Maintain consistency during recovery

### Predictive Recovery

- Detect potential failures before they occur
- Proactive resource management
- Early warning systems

## Summary

The AI-EWG pipeline has a comprehensive recovery system that handles:

- **Automatic Recovery**: Transient failures, network issues, resource constraints
- **Manual Recovery**: Persistent errors, configuration issues, user intervention
- **Stage-Based Recovery**: Resume from any processing stage
- **Granular Recovery**: Individual episodes, clips, or operations
- **Preventive Measures**: Cache management, resource monitoring, validation

This multi-layered approach ensures that processes can recover from various failure scenarios and provides users with appropriate tools to handle stuck or failed processes effectively.
