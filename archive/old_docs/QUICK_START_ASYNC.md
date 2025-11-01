# Quick Start: Async Processing

## 🚀 Get Started in 5 Minutes

### Step 1: Restart API Server
```powershell
# Stop current server (Ctrl+C if running)

# Start with async support
venv\Scripts\activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

**You should see:**
```
INFO - Async processing endpoints registered
INFO - Starting API server on 0.0.0.0:8000
```

### Step 2: Test Async Endpoints
```powershell
# In a new terminal
venv\Scripts\activate.ps1
python test_async_api.py
```

**This will:**
- ✅ Check API health
- ✅ Discover episodes
- ✅ Submit async processing job
- ✅ Poll job status with progress updates
- ✅ Show queue statistics

### Step 3: Process Your Video

**Option A: Using the Test Script**
```powershell
python test_async_api.py
# Follow the prompts
```

**Option B: Using curl/PowerShell**
```powershell
# 1. Discover episodes
curl -X POST http://localhost:8000/episodes/discover

# 2. Start async processing
curl -X POST http://localhost:8000/async/episodes/YOUR-EPISODE-ID/process `
  -H "Content-Type: application/json" `
  -d '{
    "episode_id": "YOUR-EPISODE-ID",
    "target_stage": "rendered",
    "force_reprocess": false
  }'

# Response: {"job_id": "abc-123", "status": "queued", ...}

# 3. Check status (repeat every 30s)
curl http://localhost:8000/async/jobs/abc-123
```

**Option C: Using Python**
```python
import requests
import time

# Submit job
response = requests.post(
    "http://localhost:8000/async/episodes/my-episode/process",
    json={"episode_id": "my-episode", "target_stage": "rendered"}
)
job_id = response.json()["job_id"]

# Poll status
while True:
    status = requests.get(f"http://localhost:8000/async/jobs/{job_id}").json()
    print(f"{status['progress']}% - {status['message']}")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(30)
```

---

## 📊 Understanding the Output

### Job Status Response
```json
{
  "job_id": "abc-123",
  "job_type": "process_episode",
  "status": "running",           // queued, running, completed, failed
  "progress": 45.0,               // 0-100%
  "current_stage": "transcribing", // discovered, transcribing, enriched, rendered
  "message": "Processing audio segment 3/7",
  "eta_seconds": 180,             // Estimated time remaining
  "result": null                  // Populated when completed
}
```

### Progress Stages
1. **queued** (0%) - Waiting for worker
2. **starting** (5%) - Initializing
3. **transcribing** (10-40%) - Whisper AI processing
4. **enriching** (40-80%) - Ollama LLM analysis
5. **rendering** (80-95%) - Generating HTML
6. **completed** (100%) - Done!

---

## 🎯 Real-World Example

### Processing a 10-Minute Video

```powershell
# Start processing
curl -X POST http://localhost:8000/async/episodes/newsroom-2024-bb_test_10mins/process `
  -H "Content-Type: application/json" `
  -d '{"episode_id":"newsroom-2024-bb_test_10mins","target_stage":"rendered"}'

# Response
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "queued",
  "message": "Episode processing queued. Poll /async/jobs/f47ac10b... for status."
}

# Poll status (every 30s)
curl http://localhost:8000/async/jobs/f47ac10b-58cc-4372-a567-0e02b2c3d479

# Progress updates:
# [14:30:00] Status: running | Progress: 5.0% | Stage: starting
# [14:30:30] Status: running | Progress: 15.0% | Stage: transcribing | ETA: 240s
# [14:31:00] Status: running | Progress: 25.0% | Stage: transcribing | ETA: 180s
# [14:31:30] Status: running | Progress: 35.0% | Stage: transcribing | ETA: 120s
# [14:32:00] Status: running | Progress: 50.0% | Stage: enriching | ETA: 180s
# [14:32:30] Status: running | Progress: 65.0% | Stage: enriching | ETA: 120s
# [14:33:00] Status: running | Progress: 80.0% | Stage: enriching | ETA: 60s
# [14:33:30] Status: running | Progress: 90.0% | Stage: rendering | ETA: 30s
# [14:34:00] Status: completed | Progress: 100.0% | Stage: completed

# Total time: ~4 minutes for 10-minute video
```

---

## 🔧 Common Use Cases

### Use Case 1: Batch Processing Overnight
```python
# Process multiple videos
episodes = ["ep1", "ep2", "ep3", "ep4", "ep5"]
job_ids = []

for episode_id in episodes:
    response = requests.post(
        f"http://localhost:8000/async/episodes/{episode_id}/process",
        json={"episode_id": episode_id, "target_stage": "rendered"}
    )
    job_ids.append(response.json()["job_id"])
    print(f"Submitted {episode_id}: {job_ids[-1]}")

# Check all jobs in the morning
for job_id in job_ids:
    status = requests.get(f"http://localhost:8000/async/jobs/{job_id}").json()
    print(f"{job_id}: {status['status']}")
```

### Use Case 2: With Webhook Notifications
```python
# Submit with webhook
response = requests.post(
    "http://localhost:8000/async/episodes/my-episode/process",
    json={
        "episode_id": "my-episode",
        "target_stage": "rendered",
        "webhook_url": "http://myserver.com/webhook/complete"
    }
)

# When complete, your webhook receives:
# POST http://myserver.com/webhook/complete
# {
#   "job_id": "...",
#   "status": "completed",
#   "result": {
#     "episode_id": "my-episode",
#     "stage": "rendered",
#     "duration": 347.2
#   }
# }
```

### Use Case 3: Monitoring Dashboard
```python
# Get queue stats
stats = requests.get("http://localhost:8000/async/stats").json()
print(f"Queue: {stats['queued']} | Running: {stats['running']} | Completed: {stats['completed']}")

# List recent jobs
jobs = requests.get("http://localhost:8000/async/jobs?limit=10").json()
for job in jobs:
    print(f"{job['job_id']}: {job['status']} ({job['progress']}%)")
```

---

## 🎬 n8n Automation

### Import Workflow
1. Open n8n (http://localhost:5678)
2. Click **Workflows** → **Import from File**
3. Select `n8n_workflows/async_processing_workflow.json`
4. Click **Import**

### Configure Workflow
1. **Schedule Node**: Set your preferred schedule (default: 2 AM daily)
2. **HTTP Nodes**: Update URL if not using localhost
3. **Slack Nodes**: Add your Slack credentials
4. **Activate**: Toggle workflow to active

### Test Workflow
1. Click **Execute Workflow** (manual trigger)
2. Watch execution in real-time
3. Check Slack for notifications

---

## 📈 Performance Expectations

| Video Length | Transcription | AI Enrichment | Rendering | Total |
|--------------|---------------|---------------|-----------|-------|
| 5 minutes    | ~1-2 min      | ~1-2 min      | ~30s      | ~3-5 min |
| 10 minutes   | ~2-3 min      | ~2-3 min      | ~1 min    | ~5-8 min |
| 30 minutes   | ~5-8 min      | ~5-8 min      | ~2 min    | ~12-18 min |
| 60 minutes   | ~10-15 min    | ~10-15 min    | ~3 min    | ~25-35 min |

**Factors:**
- GPU: RTX 4080 speeds up transcription significantly
- CPU: Threadripper PRO 5995WX handles AI enrichment well
- Disk: NVMe SSD recommended for fast I/O

---

## ❓ Troubleshooting

### Issue: "Job stuck in queued status"
**Cause:** Max workers reached (default: 2)

**Solution:**
```python
# Check queue stats
GET /async/stats
# If "running" = "max_workers", wait for jobs to complete

# Or increase workers (requires code change in job_queue.py)
job_queue = JobQueue(max_workers=4)
```

### Issue: "Job failed immediately"
**Cause:** Episode not found or invalid

**Solution:**
```powershell
# Verify episode exists
curl http://localhost:8000/episodes

# Check episode ID is correct
curl http://localhost:8000/episodes/YOUR-EPISODE-ID
```

### Issue: "Timeout on status polling"
**Cause:** Very long video or slow processing

**Solution:**
- Increase poll interval (30s → 60s)
- Check API server logs for actual progress
- Verify GPU is being used (check logs for CUDA)

### Issue: "No progress updates"
**Cause:** Background task not calling update_job_progress

**Solution:**
- Check API server logs for errors
- Verify job_id is correct
- Restart API server if needed

---

## 🎯 Next Steps

✅ **You've completed Phase 1!**

**Now you can:**
1. ✅ Process long videos without timeouts
2. ✅ Run batch processing overnight
3. ✅ Monitor progress in real-time
4. ✅ Automate with n8n workflows
5. ✅ Get webhook notifications

**Optional enhancements:**
- Add email notifications
- Create monitoring dashboard
- Set up scheduled processing
- Integrate with social media APIs

**For production:**
- Migrate to Celery + Redis (see Phase 3)
- Add authentication to endpoints
- Set up monitoring/alerting
- Implement rate limiting

---

## 📚 Additional Resources

- **Full Documentation**: `HYBRID_WORKFLOW_IMPLEMENTATION.md`
- **n8n Workflow**: `n8n_workflows/async_processing_workflow.json`
- **Test Script**: `test_async_api.py`
- **API Docs**: http://localhost:8000/docs (when server running)

---

## 💬 Support

If you encounter issues:
1. Check API server logs
2. Run `python test_async_api.py` for diagnostics
3. Review `HYBRID_WORKFLOW_IMPLEMENTATION.md` troubleshooting section
4. Check that all paths are relative (no D: drive references)

**Happy automating! 🚀**
