# Stuck Process Detection & Recovery System

## Overview

The AI-EWG pipeline now includes comprehensive stuck process detection and recovery mechanisms to handle processes that get stuck at any stage.

## 1. Automatic Stuck Process Detection

### Detection Criteria

The system automatically detects stuck processes based on:

- **Time-based Detection**: No progress updates for configurable time periods
- **Stage-specific Timeouts**: Different timeout thresholds for different processing stages
- **Progress Stagnation**: Same progress percentage for extended periods

### Timeout Thresholds

```python
STAGE_TIMEOUTS = {
    'processing': 1800,    # 30 minutes for main processing
    'clips': 900,          # 15 minutes for clip generation
    'social': 300,         # 5 minutes for social packages
    'transcribed': 1200,   # 20 minutes for transcription
    'enriched': 600,       # 10 minutes for enrichment
    'editorial': 300,      # 5 minutes for editorial
    'default': 600         # 10 minutes default
}
```

### Real-time Monitoring

- **Progress Timestamps**: Every progress update includes timestamp
- **Health Indicators**: Visual status indicators in processing controls
- **Resource Monitoring**: CPU and memory usage tracking
- **Automatic Alerts**: Warning messages for stuck processes

## 2. Recovery Options

### Individual Episode Recovery

When a process gets stuck, users have several options:

#### 🔄 Retry

- Clears episode cache
- Resets progress to 'discovered' stage
- Restarts processing with clean state
- Maintains processing history

#### ⏹️ Skip

- Marks episode as failed
- Continues with other episodes
- Preserves error information
- Allows manual review later

### Bulk Recovery Actions

#### 🔄 Retry All Stuck

- Applies retry logic to all stuck episodes
- Batch cache clearing
- Parallel retry execution
- Progress tracking for all retries

#### ⏹️ Skip All Stuck

- Marks all stuck episodes as failed
- Continues processing remaining episodes
- Bulk error logging
- Summary reporting

#### 🧹 Deep Clean & Retry

- Comprehensive cache clearing
- File system cleanup
- State reset
- Fresh processing attempt

## 3. User Interface

### Stuck Process Alerts

When stuck processes are detected:

```
⚠️ Detected 2 potentially stuck episode(s)

🔧 Stuck Process Recovery Options
┌─────────────────────────────────────────────────────────┐
│ Episode: newsroom-2024-bb_test_10mins                   │
│ Stage: processing, Last update: 2025-10-26 17:30:00    │
│ [🔄 Retry] [⏹️ Skip]                                    │
└─────────────────────────────────────────────────────────┘

Bulk Actions: [🔄 Retry All] [⏹️ Skip All] [🧹 Deep Clean & Retry]
```

### Health Monitoring Dashboard

The processing controls now show:

```
🔄 Processing is active | ✅ All healthy | 🟢 Resources: 45% CPU, 60% RAM
```

Or when issues are detected:

```
🔄 Processing is active | ⚠️ 2 stuck | 🟡 Resources: 75% CPU, 80% RAM
```

## 4. Recovery Strategies

### Automatic Recovery

1. **Transient Issues**: Automatic retry with exponential backoff
2. **Resource Constraints**: Wait for resources and retry
3. **Network Issues**: Connection retry with timeout extension

### Manual Recovery

1. **Configuration Issues**: User intervention required
2. **File Corruption**: Manual file validation and replacement
3. **System Errors**: Deep cleanup and restart

### Progressive Recovery

1. **Soft Recovery**: Simple retry without cleanup
2. **Medium Recovery**: Cache clearing and retry
3. **Hard Recovery**: Full cleanup, state reset, and retry
4. **Emergency Recovery**: Process termination and manual restart

## 5. Prevention Mechanisms

### Proactive Monitoring

- **Resource Thresholds**: Alert when system resources are high
- **Progress Validation**: Ensure progress updates are meaningful
- **Health Checks**: Regular API and system health validation

### Early Warning System

- **Slow Progress Detection**: Identify processes that are slowing down
- **Resource Trend Analysis**: Predict resource exhaustion
- **Error Pattern Recognition**: Identify recurring failure patterns

## 6. Configuration Options

### Timeout Configuration

Users can adjust timeout thresholds based on their system:

```python
# For slower systems
EXTENDED_TIMEOUTS = {
    'processing': 3600,    # 1 hour
    'clips': 1800,         # 30 minutes
    'transcribed': 2400,   # 40 minutes
}

# For faster systems
REDUCED_TIMEOUTS = {
    'processing': 900,     # 15 minutes
    'clips': 450,          # 7.5 minutes
    'transcribed': 600,    # 10 minutes
}
```

### Recovery Policies

```python
RECOVERY_POLICIES = {
    'auto_retry_stuck': True,           # Automatically retry stuck processes
    'max_auto_retries': 2,              # Maximum automatic retries
    'require_user_confirmation': False,  # Require user confirmation for recovery
    'deep_clean_on_multiple_failures': True  # Deep clean after multiple failures
}
```

## 7. Logging & Monitoring

### Recovery Logs

All recovery actions are logged with:

- **Timestamp**: When recovery was initiated
- **Episode ID**: Which episode was affected
- **Recovery Action**: What action was taken
- **Success Status**: Whether recovery was successful
- **Duration**: How long recovery took

### Metrics Tracking

- **Stuck Process Rate**: Percentage of processes that get stuck
- **Recovery Success Rate**: Percentage of successful recoveries
- **Time to Recovery**: Average time from detection to resolution
- **Most Common Stuck Stages**: Which stages get stuck most often

## 8. Best Practices

### For Users

1. **Monitor Regularly**: Check processing status periodically
2. **Act Quickly**: Address stuck processes promptly
3. **Use Progressive Recovery**: Start with soft recovery, escalate as needed
4. **Check Resources**: Ensure adequate system resources
5. **Review Logs**: Check logs for patterns and root causes

### For System Administrators

1. **Tune Timeouts**: Adjust timeouts based on system performance
2. **Monitor Resources**: Ensure adequate CPU, memory, and disk space
3. **Regular Maintenance**: Perform regular system cleanup
4. **Update Dependencies**: Keep system components updated
5. **Backup Configurations**: Maintain backup of working configurations

## 9. Troubleshooting Guide

### Common Stuck Scenarios

#### Transcription Stage Stuck

- **Cause**: Large video files, insufficient memory
- **Recovery**: Increase timeout, check memory usage, retry with smaller batch

#### Clip Generation Stuck

- **Cause**: Complex video processing, GPU issues
- **Recovery**: Check GPU availability, reduce clip complexity, retry

#### Social Package Creation Stuck

- **Cause**: API rate limits, network issues
- **Recovery**: Check network connectivity, wait for rate limit reset, retry

### Emergency Recovery

If all recovery options fail:

1. **Stop Processing**: Use stop button to halt all processing
2. **Deep Clean**: Use deep clean to reset all state
3. **Check System**: Verify system health and resources
4. **Restart API**: Restart the API server if needed
5. **Manual Intervention**: Check logs and fix underlying issues

## Summary

The stuck process detection and recovery system provides:

- **Automatic Detection**: Identifies stuck processes based on time and progress
- **Multiple Recovery Options**: From simple retry to deep cleanup
- **User-Friendly Interface**: Clear alerts and recovery controls
- **Comprehensive Logging**: Detailed tracking of all recovery actions
- **Preventive Measures**: Early warning and resource monitoring

This ensures that users can effectively handle stuck processes and maintain reliable pipeline operation.
