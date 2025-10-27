# AI-EWG for n8n Developers - Getting Started

## 👋 Welcome!

This guide will get you up and running with AI-EWG (AI-Enhanced Web Generation) for n8n workflow automation in **under 10 minutes**.

---

## 🎯 What Does This System Do?

**Input**: Long-form video (podcast, webinar, interview)  
**Output**: 
- 📄 Interactive HTML page with synchronized video + transcript
- 🎬 5-10 short clips optimized for TikTok/Instagram/YouTube Shorts
- 📝 Full transcript with word-level timestamps
- 🤖 AI-generated titles, descriptions, hashtags
- 📊 Topic segmentation and key points

**Perfect for**: Content creators, marketing teams, media companies automating video repurposing.

---

## 🚀 Quick Start (5 Minutes)

### 1. Start the API Server

```powershell
# Navigate to project directory
cd d:\n8n\ai-ewg

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Start API server
python src/cli.py --config config/pipeline.yaml api --port 8000
```

**Expected output**:
```
Starting API server on 0.0.0.0:8000
API endpoints available at:
  - Health: http://0.0.0.0:8000/health
  ...
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 2. Verify It's Working

```powershell
# Test health endpoint
curl http://localhost:8000/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "active_episodes": 0,
  "queue_size": 0
}
```

### 3. Test with a Video

```powershell
# Discover videos
curl -X POST http://localhost:8000/episodes/discover

# Process a video (async)
curl -X POST http://localhost:8000/async/episodes/{episode_id}/process \
  -H "Content-Type: application/json" \
  -d '{"target_stage": "rendered"}'

# Check status
curl http://localhost:8000/async/jobs/{job_id}
```

✅ **You're ready to integrate with n8n!**

---

## 📚 Documentation Structure

We've created 4 documents for you:

### 1. **N8N_DEVELOPER_GUIDE.md** (Main Guide)
**Read this first!**
- Complete technical architecture
- Detailed API reference
- Processing pipeline explanation
- Integration patterns
- Troubleshooting guide

**Best for**: Understanding the full system

---

### 2. **API_QUICK_REFERENCE.md** (Cheat Sheet)
**Keep this open while building workflows!**
- All API endpoints in one page
- Request/response examples
- Typical durations
- Common errors

**Best for**: Quick lookups during development

---

### 3. **WORKFLOW_DIAGRAMS.md** (Visual Guide)
**Use this for planning!**
- System architecture diagrams
- Processing flow charts
- n8n workflow patterns (4 ready-to-use templates)
- Decision trees

**Best for**: Understanding data flow and designing workflows

---

### 4. **This Document** (Getting Started)
**You're reading it!**
- Quick start guide
- Essential concepts
- First workflow example

---

## 🎓 Essential Concepts

### Sync vs Async Endpoints

#### ❌ Sync Endpoints (Don't Use for Processing)
```http
POST /episodes/{id}/process
```
- Blocks until complete (5-15 minutes)
- Will timeout
- Only for quick operations

#### ✅ Async Endpoints (Use These!)
```http
POST /async/episodes/{id}/process  → Returns job_id immediately
GET /async/jobs/{job_id}            → Check progress
```
- Returns in <1 second
- Processing happens in background
- Poll for status updates

---

### Processing Stages

Every video goes through 5 stages:

| Stage | Duration | What Happens |
|-------|----------|--------------|
| `discovered` | 1s | Video found, hash computed |
| `prepared` | 1s | Validated, ready to process |
| `transcribed` | 5-8 min | Whisper speech-to-text |
| `enriched` | 2-5 min | Ollama AI metadata |
| `rendered` | 10s | HTML page generated |

**Total**: ~7-13 minutes for a 10-minute video

---

### Job Status Values

| Status | Meaning |
|--------|---------|
| `queued` | Waiting to start |
| `running` | Currently processing |
| `completed` | ✅ Success! |
| `failed` | ❌ Error occurred |

---

## 🔧 Your First n8n Workflow

### Goal: Process a video and get notified

**Nodes needed**: 4
1. HTTP Request (Discover)
2. HTTP Request (Submit Job)
3. HTTP Request (Check Status) - in a loop
4. Slack/Email (Notification)

### Step-by-Step

#### Node 1: Discover Episodes
```
Node Type: HTTP Request
Method: POST
URL: http://localhost:8000/episodes/discover
```

**Output**: Array of episodes with `episode_id`

---

#### Node 2: Submit Processing Job
```
Node Type: HTTP Request
Method: POST
URL: http://localhost:8000/async/episodes/{{ $json.episodes[0].episode_id }}/process
Headers: Content-Type: application/json
Body: {
  "target_stage": "rendered",
  "force_reprocess": false
}
```

**Output**: `{ "job_id": "abc-123-..." }`

---

#### Node 3: Poll Status (Loop)
```
Node Type: HTTP Request
Method: GET
URL: http://localhost:8000/async/jobs/{{ $json.job_id }}

→ Connect to Wait node (30 seconds)
→ Connect to IF node (check if status == "completed")
→ If NO: Loop back to this node
→ If YES: Continue to notification
```

---

#### Node 4: Send Notification
```
Node Type: Slack/Email
Message: "✅ Video processed!
Episode: {{ $json.result.episode_id }}
Duration: {{ $json.result.duration }}s
View: http://localhost:8000/episodes/{{ $json.result.episode_id }}"
```

---

## 🎬 Bonus: Generate Clips

Add these nodes after the main workflow:

```
HTTP Request: POST /episodes/{id}/discover_clips
  ↓
HTTP Request: POST /async/episodes/{id}/render_clips
  ↓
Poll until complete
  ↓
HTTP Request: GET /episodes/{id}/clips
  ↓
Upload to TikTok/Instagram
```

**See WORKFLOW_DIAGRAMS.md for complete examples!**

---

## 🔍 Monitoring & Debugging

### Option 1: Streamlit Dashboard (Visual)
```powershell
streamlit run dashboard.py
```
- Navigate to "Job Monitor" page
- See real-time progress
- View outputs (HTML, transcripts, clips)

### Option 2: API Endpoints (Programmatic)
```bash
# Check queue status
curl http://localhost:8000/async/stats

# Get job details
curl http://localhost:8000/async/jobs/{job_id}

# List all running jobs
curl http://localhost:8000/async/jobs?status=running
```

### Option 3: Logs (Debugging)
```powershell
# View API logs
Get-Content logs/api.log -Tail 50 -Wait
```

---

## 🚨 Common Issues & Solutions

### Issue: "Read timed out"
**Solution**: You're using sync endpoints. Switch to `/async/*` endpoints.

### Issue: "Episode not found"
**Solution**: Run discovery first: `POST /episodes/discover`

### Issue: "No clips discovered"
**Solution**: Episode must be transcribed first. Check stage: `GET /episodes/{id}`

### Issue: Job stuck at 5%
**Solution**: Check Ollama is running: `curl http://localhost:11434/api/tags`

---

## 📊 Performance Tips

### For Faster Processing
1. **Use GPU**: Edit `config/pipeline.yaml`, set `device: cuda`
2. **Parallel Processing**: Set `max_workers: 2` (requires 16GB+ RAM)
3. **Smaller Model**: Use `medium` instead of `large-v3` Whisper model

### For Better Clips
1. **Adjust duration**: `min_duration_ms: 15000` for shorter clips
2. **More clips**: `max_clips: 10` instead of 5
3. **Platform-specific**: Use `target_platforms: ["tiktok"]` for optimization

---

## 🎯 Next Steps

1. ✅ **Read N8N_DEVELOPER_GUIDE.md** - Understand the full system
2. ✅ **Try the example workflow** - Get hands-on experience
3. ✅ **Check WORKFLOW_DIAGRAMS.md** - See 4 ready-to-use patterns
4. ✅ **Bookmark API_QUICK_REFERENCE.md** - For quick lookups

---

## 💡 Use Case Examples

### Content Creator
**Goal**: Turn weekly podcast into blog post + 5 TikTok clips

**Workflow**:
1. Upload podcast to `test_videos/` folder
2. n8n discovers and processes (overnight)
3. Morning: HTML blog post ready
4. n8n generates 5 clips (9:16 format)
5. Auto-post to TikTok with AI-generated captions

**Time saved**: 4-6 hours per episode

---

### Marketing Team
**Goal**: Repurpose webinar into multiple content pieces

**Workflow**:
1. Process webinar video
2. Extract key moments as clips
3. Generate SEO-optimized blog post
4. Create social media posts with hashtags
5. Schedule posts across platforms

**Output**: 1 video → 10+ content pieces

---

### Media Company
**Goal**: Process 50 videos per day automatically

**Workflow**:
1. Videos uploaded to network share
2. n8n scans every hour
3. Batch processing (5 at a time)
4. Clips auto-generated
5. Metadata exported to CMS
6. Daily summary report

**Capacity**: 50 videos/day with 2 workers

---

## 📞 Support & Resources

### Health Check
```bash
curl http://localhost:8000/health
```

### System Status
```bash
curl http://localhost:8000/status
```

### Queue Statistics
```bash
curl http://localhost:8000/async/stats
```

### Logs
```bash
# API logs
Get-Content logs/api.log -Tail 100

# Processing logs
Get-Content logs/pipeline.log -Tail 100
```

---

## 🎉 You're Ready!

You now have everything you need to:
- ✅ Understand the AI-EWG system
- ✅ Build n8n workflows
- ✅ Process videos automatically
- ✅ Generate clips for social media
- ✅ Monitor and debug issues

**Start with the example workflow above, then explore the other patterns in WORKFLOW_DIAGRAMS.md!**

---

**Happy Automating! 🚀**

*Questions? Check the troubleshooting section in N8N_DEVELOPER_GUIDE.md*
