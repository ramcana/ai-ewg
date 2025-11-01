# AI-EWG API Quick Reference

## 🎯 Base URL
```
http://localhost:8000
```

---

## 📍 Essential Endpoints

### Discover Videos
```http
POST /episodes/discover
```
**Returns**: List of found videos  
**Duration**: 1-5s

---

### Process Video (Async)
```http
POST /async/episodes/{episode_id}/process
Content-Type: application/json

{
  "target_stage": "rendered",
  "force_reprocess": false,
  "webhook_url": "https://optional-webhook.com"
}
```
**Returns**: `job_id` immediately  
**Duration**: <1s (actual processing runs in background)

---

### Check Job Status
```http
GET /async/jobs/{job_id}
```
**Returns**: Progress, ETA, status  
**Poll every**: 30 seconds

---

### Get Episode Details
```http
GET /episodes/{episode_id}
```
**Returns**: Full episode data including:
- Basic info: episode_id, title, show, duration
- Processing stage and timestamps
- Transcription: full text, word timestamps, VTT captions
- **Enrichment**: AI-extracted show name, host name, topics, summaries
- Metadata: file size, source path, content hash

---

### Discover Clips
```http
POST /episodes/{episode_id}/discover_clips
Content-Type: application/json

{
  "max_clips": 5,
  "min_duration_ms": 20000,
  "max_duration_ms": 120000
}
```
**Returns**: List of identified clips  
**Duration**: 10-30s

---

### Render Clips (Async)
```http
POST /async/episodes/{episode_id}/render_clips
Content-Type: application/json

{
  "clip_ids": ["clip_001", "clip_002"],
  "variants": ["clean", "subtitled"],
  "aspect_ratios": ["16:9", "9:16"],
  "webhook_url": "https://optional-webhook.com"
}
```
**Returns**: `job_id` immediately  
**Duration**: 2-5 min per clip (background)

---

### Get Clips
```http
GET /episodes/{episode_id}/clips
```
**Returns**: List of rendered clips with file paths

---

### Queue Stats
```http
GET /async/stats
```
**Returns**: Queue statistics (queued, running, completed, failed)

---

## 🔄 Processing Stages

| Stage | Value | Description | Data Generated |
|-------|-------|-------------|----------------|
| Discovered | `discovered` | Video found, not processed | episode_id, content_hash |
| Prepared | `prepared` | Validated, ready to process | media info, duration |
| Transcribed | `transcribed` | Speech-to-text complete | full transcript, word timestamps, VTT |
| Enriched | `enriched` | AI metadata added | **show_name, host_name, topics, summaries** |
| Rendered | `rendered` | HTML output generated | interactive web page |

---

## 📊 Job Status Values

| Status | Description |
|--------|-------------|
| `queued` | Waiting to start |
| `running` | Currently processing |
| `completed` | Successfully finished |
| `failed` | Error occurred |
| `cancelled` | Manually stopped |

---

## ⏱️ Typical Durations (10 min video)

| Operation | Duration |
|-----------|----------|
| Discovery | 1-2s |
| Transcription | 5-8 min (CPU), 3-5 min (GPU) |
| AI Enrichment | 2-5 min |
| HTML Rendering | 5-10s |
| Clip Discovery | 10-30s |
| Clip Rendering | 2-5 min per clip |

---

## 🎬 Clip Variants

| Variant | Description |
|---------|-------------|
| `clean` | Video only, no overlays |
| `subtitled` | Burned-in captions |
| `branded` | Logo + lower third |

---

## 📐 Aspect Ratios

| Ratio | Platforms |
|-------|-----------|
| `16:9` | YouTube, Twitter |
| `9:16` | TikTok, Instagram Reels, YouTube Shorts |
| `1:1` | Instagram Feed, Facebook |

---

## 🔗 n8n Integration Pattern

```
1. POST /episodes/discover
   ↓
2. POST /async/episodes/{id}/process
   ↓ (returns job_id immediately)
3. Wait 30 seconds
   ↓
4. GET /async/jobs/{job_id}
   ↓
5. IF status != "completed" → Go to step 3
   ↓
6. GET /episodes/{id}
   ↓
7. POST /episodes/{id}/discover_clips
   ↓
8. POST /async/episodes/{id}/render_clips
   ↓
9. Poll until clips ready
   ↓
10. GET /episodes/{id}/clips
```

---

## 🚨 Common Errors

| Error | Solution |
|-------|----------|
| `Read timed out` | Use `/async/*` endpoints |
| `Episode not found` | Run `/episodes/discover` first |
| `Job not found` | Check job_id is correct |
| `No clips discovered` | Ensure episode is transcribed |
| `503 Service Unavailable` | Check API server is running |

---

## 🛠️ Health Check

```bash
# Check API is running
curl http://localhost:8000/health

# Check Ollama is running
curl http://localhost:11434/api/tags

# Check queue status
curl http://localhost:8000/async/stats
```

---

## 📁 Output Locations

```
data/
├── transcripts/
│   ├── txt/{episode_id}.txt
│   ├── json/{episode_id}.json
│   └── vtt/{episode_id}.vtt
│
├── outputs/
│   └── {show_folder}/{year}/{episode_id}/
│       ├── clips/
│       │   └── {clip_id}/
│       │       └── {aspect_ratio}_{variant}.mp4
│       ├── html/
│       │   └── index.html
│       └── meta/
│
└── social_packages/
    └── {show_folder}/{year}/{episode_id}/
        └── {platform}/
            ├── video.mp4
            ├── title.txt
            ├── caption.txt
            └── metadata.json
```

**Note**: Episode IDs now follow format: `{show_folder}_ep{number}_{date}`
Example: `ForumDailyNews_ep140_2024-10-27`

---

## 🔧 Configuration

**Main config**: `config/pipeline.yaml`

**Key settings**:
```yaml
transcription:
  model: large-v3
  device: cuda  # or 'cpu'

llm:
  provider: ollama
  model: llama3.2
  base_url: http://localhost:11434

job_queue:
  max_workers: 2
```

---

## 🤖 AI-Extracted Enrichment Data

After the **enriched** stage, episodes contain AI-generated metadata:

```json
{
  "enrichment": {
    "show_name": "Boom and Bust",
    "host_name": "Tony Clement",
    "episode_number": "Episode 42",
    "executive_summary": "This episode discusses...",
    "key_takeaways": [
      "Main point 1",
      "Main point 2"
    ],
    "topics": ["AI", "Technology", "Politics"],
    "segment_titles": ["Introduction", "Main Discussion", "Conclusion"],
    "tags": ["#AI", "#Tech", "#Innovation"],
    "enriched_guests": {
      "John Doe": {
        "proficiency_score": 0.85,
        "expertise": ["AI", "Machine Learning"]
      }
    }
  }
}
```

**Access via:**
- `GET /episodes/{id}` - Full enrichment object
- Dashboard "Episodes" tab - Visual display
- HTML output - Embedded in generated pages

---

## 📊 Job Monitor Dashboard

**Access**: `streamlit run dashboard.py` → "Job Monitor" page

**Features:**
- **Active Jobs**: Real-time progress, ETA, current stage
- **Completed Jobs**: Processing history (cleared on restart)
- **Episodes**: All processed videos with show name, summaries, topics
- **Clips**: Generated clips with metadata

**Note**: Job history is in-memory (cleared on restart). Episodes persist in database.

---

## 📞 Quick Support

1. **Check logs**: `logs/api.log`
2. **Test with dashboard**: `streamlit run dashboard.py`
3. **Verify health**: `GET /health`
4. **Check queue**: `GET /async/stats`
5. **View episodes**: `GET /episodes` or Dashboard "Episodes" tab

---

**Last Updated**: 2025-10-26 (Added enrichment data structure and Job Monitor info)
