# n8n Integration Testing Guide

This guide provides step-by-step instructions for testing the Video Processing Pipeline with n8n workflows.

## Prerequisites

### 1. Install API Dependencies

```bash
pip install -r requirements-api.txt
```

### 2. Install n8n

```bash
npm install -g n8n
```

### 3. Prepare Test Environment

```bash
# Create test directories
mkdir -p test_videos/newsroom/2024
mkdir -p test_data
mkdir -p output

# Copy sample video files to test_videos/
# Structure: show-name/season/episode-date-topic.mp4
```

## Phase 1: API Server Setup

### 1. Start the Pipeline API Server

```bash
# Terminal 1: Start API server
python src/cli.py --config config/pipeline.yaml api --host 0.0.0.0 --port 8000

# Verify server is running
curl http://localhost:8000/health
```

### 2. Test API Endpoints Manually

```bash
# Check system health
curl http://localhost:8000/health

# Get pipeline status
curl http://localhost:8000/status

# List episodes
curl http://localhost:8000/episodes

# Get configuration
curl http://localhost:8000/config
```

### 3. Test Processing Endpoints

```bash
# Process single episode (replace with actual episode ID)
curl -X POST http://localhost:8000/episodes/process \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "your-episode-id",
    "target_stage": "rendered",
    "force_reprocess": false
  }'

# Test webhook endpoint
curl -X POST http://localhost:8000/webhooks/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "health_check",
    "data": {}
  }'
```

## Phase 2: n8n Workflow Setup

### 1. Start n8n

```bash
# Terminal 2: Start n8n
n8n start

# Access n8n interface at http://localhost:5678
```

### 2. Import Workflow Templates

#### Import Video Processing Trigger Workflow

1. Open n8n interface (http://localhost:5678)
2. Click "Import from file"
3. Select `n8n_workflows/video_processing_trigger.json`
4. Activate the workflow

#### Import Batch Processing Workflow

1. Import `n8n_workflows/batch_processing.json`
2. Activate the workflow

#### Import Health Monitoring Workflow

1. Import `n8n_workflows/health_monitoring.json`
2. Activate the workflow

### 3. Configure Workflow URLs

Update all workflow nodes to use your API server URL:

- Replace `http://localhost:8000` with your actual API server address
- Ensure all endpoints are accessible from n8n

## Phase 3: End-to-End Testing

### 1. Test Video Discovery Trigger

#### Manual Webhook Test

```bash
# Trigger video processing via webhook
curl -X POST http://localhost:5678/webhook/video-discovered \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "test-episode-1",
    "video_path": "/path/to/video.mp4",
    "show_name": "Test Show"
  }'
```

#### Expected Flow:

1. n8n receives webhook
2. n8n calls pipeline API to process episode
3. Pipeline processes video through all stages
4. n8n receives success/failure notification
5. n8n logs results

### 2. Test Batch Processing

#### Scheduled Batch Test

1. Modify cron schedule in batch workflow to run every minute for testing
2. Ensure you have videos in "discovered" stage
3. Monitor n8n execution logs
4. Verify batch processing completes successfully

#### Manual Batch Trigger

```bash
# Trigger batch processing manually
curl -X POST http://localhost:8000/episodes/batch \
  -H "Content-Type: application/json" \
  -d '{
    "episode_ids": ["episode-1", "episode-2", "episode-3"],
    "target_stage": "rendered",
    "max_concurrent": 2
  }'
```

### 3. Test Health Monitoring

#### Monitor Health Alerts

1. Health monitoring workflow runs every 5 minutes
2. Check n8n execution history for health checks
3. Simulate high resource usage to trigger alerts
4. Verify alert notifications are sent

#### Manual Health Check

```bash
# Get current health status
curl http://localhost:8000/health

# Export metrics
curl http://localhost:8000/metrics/export?format_type=json
```

## Phase 4: Real Video Testing

### 1. Prepare Real Video Files

```bash
# Copy real video files to test directory
cp /path/to/real/videos/* test_videos/newsroom/2024/

# Verify file structure
ls -la test_videos/newsroom/2024/
```

### 2. Test Complete Pipeline Flow

#### Step 1: Discovery

```bash
# Check if videos are discovered
curl http://localhost:8000/episodes?stage=discovered
```

#### Step 2: Trigger Processing

```bash
# Use n8n webhook to trigger processing
curl -X POST http://localhost:5678/webhook/video-discovered \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "actual-episode-id",
    "trigger_source": "manual_test"
  }'
```

#### Step 3: Monitor Progress

```bash
# Monitor processing status
watch -n 5 'curl -s http://localhost:8000/status'

# Check specific episode status
curl http://localhost:8000/episodes/your-episode-id
```

#### Step 4: Verify Outputs

```bash
# Check generated files
ls -la output/
ls -la transcripts/
ls -la web_artifacts/

# Verify web artifacts
find web_artifacts/ -name "*.html" -o -name "*.json"
```

## Phase 5: Performance and Load Testing

### 1. Concurrent Processing Test

```bash
# Process multiple episodes simultaneously
for i in {1..5}; do
  curl -X POST http://localhost:5678/webhook/video-discovered \
    -H "Content-Type: application/json" \
    -d "{\"episode_id\": \"test-episode-$i\"}" &
done
wait
```

### 2. Resource Monitoring

```bash
# Monitor system resources during processing
watch -n 2 'curl -s http://localhost:8000/health | jq .'

# Monitor n8n execution queue
# Check n8n interface for workflow execution status
```

### 3. Error Recovery Testing

```bash
# Test error handling by processing invalid episode
curl -X POST http://localhost:8000/episodes/process \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "non-existent-episode",
    "target_stage": "rendered"
  }'

# Verify error is handled gracefully in n8n workflow
```

## Phase 6: Production Deployment

### 1. Environment Configuration

```yaml
# config/production.yaml
sources:
  - path: "/production/videos"
    include: ["*.mp4", "*.mkv", "*.avi"]
    enabled: true

processing:
  max_concurrent_episodes: 4
  max_retry_attempts: 3

database:
  path: "/production/data/pipeline.db"
  backup_enabled: true
```

### 2. Production API Server

```bash
# Start production API server
python src/cli.py --config config/production.yaml api \
  --host 0.0.0.0 --port 8000

# Or use systemd service, Docker, etc.
```

### 3. Production n8n Setup

1. Configure n8n with production database
2. Update workflow URLs to production API server
3. Set up proper authentication and security
4. Configure monitoring and alerting

## Expected Results

### Successful Test Criteria:

- ✅ API server starts without errors
- ✅ All API endpoints respond correctly
- ✅ n8n workflows import and activate successfully
- ✅ Webhook triggers work correctly
- ✅ Video processing completes all stages
- ✅ Output files are generated correctly
- ✅ Health monitoring detects issues
- ✅ Batch processing handles multiple videos
- ✅ Error recovery works properly

### Performance Benchmarks:

- **Processing Time**: < 2x video duration per episode
- **Memory Usage**: < 80% of available RAM
- **CPU Usage**: < 90% during processing
- **Success Rate**: > 95% for valid videos
- **API Response Time**: < 500ms for status endpoints

## Troubleshooting

### Common Issues:

#### API Server Won't Start

```bash
# Check dependencies
pip install -r requirements-api.txt

# Check port availability
netstat -an | grep 8000

# Check configuration
python src/cli.py --config config/pipeline.yaml validate
```

#### n8n Workflows Fail

1. Check API server is running and accessible
2. Verify webhook URLs are correct
3. Check n8n execution logs for detailed errors
4. Test API endpoints manually with curl

#### Processing Failures

1. Check video file formats and accessibility
2. Verify FFmpeg installation for media preparation
3. Check Whisper model availability
4. Monitor system resources during processing

#### Performance Issues

1. Reduce max_concurrent_episodes in configuration
2. Monitor system resources with health endpoint
3. Check for memory leaks in long-running processes
4. Optimize video file sizes and formats

This comprehensive testing approach ensures the pipeline works correctly with n8n integration for automated video processing workflows.
