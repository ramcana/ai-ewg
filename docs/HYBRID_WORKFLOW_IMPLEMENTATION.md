# Hybrid Workflow Implementation - Phase 1 Complete ✅

## What's Been Implemented

### 1. ✅ Job Queue System (`src/core/job_queue.py`)
- **In-memory job queue** (no Redis/Celery required for now)
- Thread-safe concurrent job processing
- Configurable max workers (default: 2)
- Job status tracking (queued, running, completed, failed)
- Progress updates with ETA calculation
- Webhook notifications on completion
- Automatic cleanup of old jobs

**Key Features:**
```python
# Submit a job
job_id = job_queue.submit_job(
    job_type="process_episode",
    parameters={"episode_id": "...", "target_stage": "rendered"},
    webhook_url="http://n8n.yourdomain.com/webhook/complete"
)

# Check status
status = job_queue.get_job_status(job_id)
# Returns: status, progress, stage, message, eta_seconds

# Update progress (from worker)
job_queue.update_job_progress(job_id, 45.0, "transcribing", "Processing audio...")
```

### 2. ✅ Async API Endpoints (`src/api/async_endpoints.py`)

#### New Endpoints:

**POST `/async/episodes/{episode_id}/process`**
- Submit episode for async processing
- Returns immediately with `job_id`
- Supports webhook notifications
```json
{
  "episode_id": "newsroom-2024-video",
  "target_stage": "rendered",
  "force_reprocess": false,
  "webhook_url": "http://n8n.yourdomain.com/webhook/episode-complete"
}
```

**POST `/async/episodes/{episode_id}/render_clips`**
- Submit clips for async rendering
- Returns immediately with `job_id`
```json
{
  "episode_id": "newsroom-2024-video",
  "clip_ids": null,
  "variants": ["clean", "subtitled"],
  "aspect_ratios": ["9x16", "16x9"],
  "webhook_url": "http://n8n.yourdomain.com/webhook/clips-complete"
}
```

**GET `/async/jobs/{job_id}`**
- Poll job status and progress
- Returns: status, progress %, current stage, ETA
```json
{
  "job_id": "abc-123",
  "status": "running",
  "progress": 45.0,
  "current_stage": "transcribing",
  "message": "Processing audio segment 3/7",
  "eta_seconds": 120
}
```

**GET `/async/jobs`**
- List all jobs with filtering
- Query params: `?status=running&limit=50`

**DELETE `/async/jobs/{job_id}`**
- Cancel a queued job

**GET `/async/stats`**
- Get queue statistics
```json
{
  "queued": 2,
  "running": 1,
  "completed": 15,
  "failed": 1,
  "total": 19,
  "max_workers": 2
}
```

### 3. ✅ n8n Workflow Template (`n8n_workflows/async_processing_workflow.json`)

**Workflow Flow:**
```
Schedule (Daily 2 AM)
    ↓
Discover Episodes
    ↓
Has Episodes? → No → End
    ↓ Yes
Split in Batches
    ↓
For Each Episode:
    ├─ Start Async Processing (returns job_id)
    ├─ Wait 30s
    ├─ Check Job Status
    ├─ Is Complete? → No → Loop back to Wait
    │   ↓ Yes
    │   ├─ Discover Clips
    │   ├─ Start Clip Rendering
    │   └─ Notify Success (Slack)
    └─ Is Failed? → Yes → Notify Failure (Slack)
```

**Features:**
- ✅ Scheduled execution (cron)
- ✅ Batch processing with concurrency control
- ✅ Status polling with 30s intervals
- ✅ Automatic clip generation after processing
- ✅ Slack notifications (success/failure)
- ✅ Error handling and retries

### 4. ✅ Server Integration
- Async endpoints registered in API server
- Compatible with existing sync endpoints
- No breaking changes to current functionality

---

## How to Use

### Option A: Manual Mode (Streamlit)
**Use for:** Quick testing, single videos, review before publishing

```powershell
# Start API server
venv\Scripts\activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000

# Start Streamlit dashboard
streamlit run dashboard.py
```

**In Dashboard:**
1. Upload video
2. Click "Start Processing"
3. Monitor progress in real-time
4. Review outputs when complete

### Option B: Async Mode (API)
**Use for:** Long-running videos, batch processing, automation

```python
import requests

# Submit job
response = requests.post(
    "http://localhost:8000/async/episodes/my-episode-id/process",
    json={
        "episode_id": "my-episode-id",
        "target_stage": "rendered",
        "webhook_url": "http://myserver.com/webhook"
    }
)
job_id = response.json()["job_id"]

# Poll status
while True:
    status = requests.get(f"http://localhost:8000/async/jobs/{job_id}").json()
    print(f"Progress: {status['progress']}% - {status['message']}")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(30)
```

### Option C: n8n Automation
**Use for:** Production, scheduled runs, full automation

1. **Import workflow:**
   - Open n8n
   - Import `n8n_workflows/async_processing_workflow.json`

2. **Configure:**
   - Update API URL if not localhost
   - Configure Slack credentials
   - Set schedule (default: 2 AM daily)

3. **Activate:**
   - Enable workflow
   - Runs automatically on schedule

---

## Testing the Implementation

### Step 1: Start API Server
```powershell
venv\Scripts\activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### Step 2: Test Async Processing
```powershell
# Test with curl or PowerShell
curl -X POST http://localhost:8000/async/episodes/test-episode/process `
  -H "Content-Type: application/json" `
  -d '{"episode_id":"test-episode","target_stage":"rendered"}'

# Response:
# {"job_id":"abc-123","status":"queued","message":"Episode processing queued..."}

# Check status
curl http://localhost:8000/async/jobs/abc-123

# Response:
# {"job_id":"abc-123","status":"running","progress":45.0,"current_stage":"transcribing",...}
```

### Step 3: Test with Streamlit
```powershell
streamlit run dashboard.py
```
- Dashboard will continue to work as before
- Behind the scenes, it can use async mode for long videos

### Step 4: Test n8n Workflow
1. Start n8n: `n8n start`
2. Import workflow
3. Trigger manually or wait for schedule
4. Monitor execution in n8n UI

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACES                       │
├─────────────────────────────────────────────────────────┤
│  Streamlit Dashboard  │  n8n Workflows  │  Direct API   │
└────────────┬──────────┴────────┬────────┴───────┬───────┘
             │                   │                 │
             └───────────────────┼─────────────────┘
                                 ↓
                    ┌────────────────────────┐
                    │   FastAPI Server       │
                    │   (localhost:8000)     │
                    └────────────┬───────────┘
                                 │
                    ┌────────────┴───────────┐
                    │                        │
         ┌──────────▼─────────┐   ┌─────────▼──────────┐
         │  Sync Endpoints    │   │  Async Endpoints   │
         │  /episodes/process │   │  /async/episodes/  │
         │  (blocks until     │   │  (returns job_id)  │
         │   complete)        │   │                    │
         └──────────┬─────────┘   └─────────┬──────────┘
                    │                        │
                    │             ┌──────────▼──────────┐
                    │             │   Job Queue         │
                    │             │   (in-memory)       │
                    │             │   - Track status    │
                    │             │   - Progress updates│
                    │             │   - Webhooks        │
                    │             └──────────┬──────────┘
                    │                        │
                    └────────────┬───────────┘
                                 ↓
                    ┌────────────────────────┐
                    │  Processing Pipeline   │
                    │  1. Discovery          │
                    │  2. Transcription      │
                    │  3. AI Enrichment      │
                    │  4. Rendering          │
                    │  5. Clip Generation    │
                    └────────────┬───────────┘
                                 ↓
                    ┌────────────────────────┐
                    │   SQLite Database      │
                    │   + File Storage       │
                    └────────────────────────┘
```

---

## Configuration

### Job Queue Settings
Edit `src/core/job_queue.py` to adjust:
```python
# Maximum concurrent jobs
job_queue = JobQueue(max_workers=2)  # Increase for more parallelism

# Job cleanup
job_queue.cleanup_old_jobs(max_age_hours=24)  # Keep jobs for 24 hours
```

### Webhook Configuration
When submitting jobs, provide webhook URL:
```json
{
  "webhook_url": "http://n8n.yourdomain.com/webhook/episode-complete"
}
```

**Webhook Payload:**
```json
{
  "job_id": "abc-123",
  "job_type": "process_episode",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "episode_id": "...",
    "stage": "rendered",
    "duration": 347.2
  }
}
```

---

## Next Steps

### Phase 2: Enhanced Monitoring (Optional)
- [ ] Add real-time progress updates via WebSocket
- [ ] Create monitoring dashboard in Streamlit
- [ ] Add email notifications
- [ ] Implement job priority queue

### Phase 3: Production Readiness (Recommended)
- [ ] Migrate to Celery + Redis for distributed processing
- [ ] Add job persistence (survive server restarts)
- [ ] Implement rate limiting
- [ ] Add authentication to async endpoints
- [ ] Set up monitoring/alerting (Prometheus/Grafana)

### Phase 4: Advanced Features
- [ ] Parallel processing of multiple episodes
- [ ] Automatic retry with exponential backoff
- [ ] Job dependencies (clip rendering after processing)
- [ ] Scheduled maintenance windows
- [ ] Resource usage optimization

---

## Troubleshooting

### Issue: Jobs stuck in "queued" status
**Cause:** No workers available or max_workers reached

**Solution:**
```python
# Check queue stats
GET /async/stats

# Increase workers if needed
job_queue = JobQueue(max_workers=4)
```

### Issue: Webhook not triggering
**Cause:** Invalid webhook URL or network issue

**Solution:**
- Verify webhook URL is accessible
- Check n8n webhook is active
- Review API server logs for webhook errors

### Issue: Job progress not updating
**Cause:** Background task not calling update_job_progress

**Solution:**
- Check that processing code calls `job_queue.update_job_progress()`
- Verify job_id is correct
- Review logs for errors

---

## Performance Considerations

### Current Setup (In-Memory Queue)
- ✅ Simple, no dependencies
- ✅ Fast for small workloads
- ❌ Jobs lost on server restart
- ❌ Limited to single server
- **Good for:** Development, small teams, <10 videos/day

### Future: Celery + Redis
- ✅ Distributed processing
- ✅ Job persistence
- ✅ Horizontal scaling
- ✅ Advanced features (retries, scheduling)
- **Good for:** Production, large teams, >10 videos/day

---

## Summary

✅ **Implemented:**
- Async processing endpoints
- Job queue system
- Status polling
- Webhook notifications
- n8n workflow template
- Backward compatible with existing code

✅ **Benefits:**
- No more timeouts on long videos
- Can process videos overnight
- Batch processing support
- Real-time progress tracking
- Automation ready

✅ **Ready to Use:**
- Restart API server
- Test async endpoints
- Import n8n workflow
- Start automating!

🎯 **Recommended Next:** Test with your 10-minute video using async mode!
