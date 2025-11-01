# n8n Developer Guide - AI-EWG Pipeline Integration

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Technical Architecture](#technical-architecture)
3. [Processing Pipeline Stages](#processing-pipeline-stages)
4. [API Reference](#api-reference)
5. [Integration Patterns](#integration-patterns)
6. [Workflow Examples](#workflow-examples)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 System Overview

### What is AI-EWG?
AI-EWG (AI-Enhanced Web Generation) is an automated video processing pipeline that transforms long-form video content into:
- **AI-enriched transcripts** with speaker diarization
- **Interactive HTML presentations** with synchronized video/text
- **Intelligent short-form clips** optimized for social media
- **SEO-optimized metadata** (titles, descriptions, hashtags)

### Use Cases
- **Content Repurposing**: Convert podcasts/webinars into blog posts + clips
- **Social Media Automation**: Generate TikTok/YouTube Shorts from long videos
- **Knowledge Management**: Create searchable video libraries with AI summaries
- **Accessibility**: Auto-generate captions and transcripts

---

## 🏗️ Technical Architecture

### Technology Stack

#### **Core Pipeline**
- **Language**: Python 3.11+
- **Framework**: FastAPI (async REST API)
- **Database**: SQLite with WAL mode (portable, single-file)
- **Processing**: Async job queue with threading

#### **AI/ML Components**
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Transcription** | OpenAI Whisper (large-v3) | Speech-to-text with word-level timestamps |
| **LLM Enrichment** | Ollama (llama3.2) | Summarization, topic extraction, SEO metadata |
| **Embeddings** | sentence-transformers | Semantic similarity for clip selection |
| **Topic Segmentation** | ruptures + spaCy | Detect topic boundaries in transcripts |
| **Speaker Diarization** | pyannote.audio | Identify different speakers |

#### **Output Formats**
- **HTML**: Interactive web pages with video player + transcript
- **VTT/SRT**: Subtitle files for video players
- **JSON**: Structured metadata for programmatic access
- **MP4**: Rendered video clips with burned-in subtitles

### Episode Naming & Organization

**Episode ID Format**: `{show_folder}_ep{number}_{date}`

**Examples**:
- `ForumDailyNews_ep140_2024-10-27`
- `BoomAndBust_ep580_2024-10-27`
- `CanadianJustice_ep335_2024-10-27`

**Folder Structure**:
```
data/outputs/{show_folder}/{year}/{episode_id}/
```

**Show Mappings** (AI-extracted name → folder):
- "Forum Daily News" → `ForumDailyNews`
- "Boom and Bust" → `BoomAndBust`
- "Canadian Justice" → `CanadianJustice`
- "Counterpoint" → `Counterpoint`
- "The LeDrew Show" → `TheLeDrewShow`
- And more...

**Configuration**: See `config/pipeline.yaml` → `organization` section

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         n8n Workflow                         │
│  (Scheduling, Orchestration, Notifications)                  │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP REST API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server (Port 8000)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Sync Endpoints│  │Async Endpoints│  │Job Queue Mgr │      │
│  │ (Quick ops)  │  │(Long-running) │  │(Background)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Pipeline Orchestrator                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Stage 1: Discovery  → Find videos, compute hashes   │   │
│  │  Stage 2: Prep       → Validate, extract metadata    │   │
│  │  Stage 3: Transcribe → Whisper + diarization         │   │
│  │  Stage 4: Enrich     → Ollama LLM processing         │   │
│  │  Stage 5: Render     → Generate HTML + assets        │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│  - Episodes (metadata, processing state)                     │
│  - Processing logs (audit trail)                             │
│  - Clips (specifications, render status)                     │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    File System Storage                       │
│  data/                                                       │
│  ├── transcripts/     (TXT, JSON, VTT)                      │
│  ├── outputs/         (HTML, CSS, JS)                       │
│  ├── clips/           (MP4 video files)                     │
│  └── temp/            (Processing artifacts)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Processing Pipeline Stages

### Stage 1: Discovery (`discovered`)
**Purpose**: Find and catalog video files

**Process**:
1. Scan configured directories for video files (MP4, MOV, AVI, MKV)
2. Compute SHA-256 hash for deduplication
3. Extract basic metadata (duration, file size, resolution)
4. Create episode record in database

**Output**: Episode ID, source path, content hash

**API Endpoint**: `POST /episodes/discover`

**Duration**: ~1-2 seconds per video

---

### Stage 2: Preparation (`prepared`)
**Purpose**: Validate and prepare for processing

**Process**:
1. Verify source file exists and is readable
2. Validate video codec compatibility
3. Extract detailed media info (codec, bitrate, framerate)
4. Check available disk space

**Output**: Validated episode ready for transcription

**API Endpoint**: Automatic (part of processing pipeline)

**Duration**: <1 second

---

### Stage 3: Transcription (`transcribed`)
**Purpose**: Convert speech to text with timestamps

**Process**:
1. **Whisper Transcription**:
   - Model: `large-v3` (best accuracy)
   - Word-level timestamps enabled
   - Language auto-detection
   - Hallucination filtering

2. **Speaker Diarization** (optional):
   - Identify different speakers
   - Assign speaker labels to segments
   - Merge overlapping segments

3. **Output Generation**:
   - Plain text transcript
   - JSON with word timestamps
   - VTT subtitle file
   - SRT subtitle file

**Output Files**:
```
data/transcripts/
├── txt/{episode_id}.txt      # Plain text
├── json/{episode_id}.json    # Structured data
└── vtt/{episode_id}.vtt      # WebVTT subtitles
```

**API Endpoint**: Part of `POST /async/episodes/{id}/process`

**Duration**: ~0.5x video length (10 min video = 5 min processing)

**GPU Acceleration**: Supported (CUDA/ROCm)

---

### Stage 4: AI Enrichment (`enriched`)
**Purpose**: Add AI-generated metadata and insights

**Process**:
1. **Show & Host Extraction** (NEW):
   - AI extracts show name from content
   - Identifies host/presenter name
   - Detects episode number if mentioned

2. **Topic Extraction**:
   - Identify main topics discussed
   - Extract key themes
   - Generate topic timeline

3. **Summarization**:
   - Executive summary (2-3 paragraphs)
   - Key takeaways (bullet points)
   - Deep analysis of main themes

4. **SEO Optimization**:
   - Generate compelling title
   - Write meta description
   - Create relevant hashtags (#AI, #Tech, etc.)
   - Suggest keywords

5. **Guest Intelligence** (Intelligence Chain V2):
   - Extract guest names and roles
   - Calculate proficiency scores
   - Identify areas of expertise

**LLM Configuration**:
```json
{
  "model": "llama3.2",
  "temperature": 0.7,
  "max_tokens": 2000,
  "system_prompt": "You are an expert content analyst..."
}
```

**Output Structure** (saved to database):
```json
{
  "enrichment": {
    "show_name": "Boom and Bust",
    "host_name": "Tony Clement",
    "episode_number": "Episode 42",
    "executive_summary": "This episode discusses...",
    "key_takeaways": ["Point 1", "Point 2"],
    "topics": ["AI", "Technology", "Politics"],
    "segment_titles": ["Intro", "Discussion", "Conclusion"],
    "tags": ["#AI", "#Tech"],
    "enriched_guests": {
      "guest_name": {
        "proficiency_score": 0.85,
        "expertise": ["AI", "ML"]
      }
    }
  }
}
```

**API Endpoint**: Part of `POST /async/episodes/{id}/process`

**Duration**: ~2-5 minutes (depends on transcript length)

**Access Enrichment Data**:
- `GET /episodes/{id}` - Returns full enrichment object
- Dashboard "Episodes" tab - Visual display
- HTML output - Embedded in generated pages

---

### Stage 5: HTML Rendering (`rendered`)
**Purpose**: Generate interactive web presentation

**Process**:
1. **Template Selection**: Choose layout based on content type
2. **Asset Generation**:
   - Responsive HTML5 page
   - CSS styling (mobile-first)
   - JavaScript for video sync
   - Thumbnail images

3. **Features**:
   - Click transcript to jump to video timestamp
   - Search within transcript
   - Speaker highlighting
   - Topic navigation
   - Social sharing buttons

**Output Files**:
```
data/outputs/{show_folder}/{year}/{episode_id}/
├── html/
│   ├── index.html          # Main page
│   ├── styles.css          # Styling
│   └── script.js           # Interactivity
├── thumbnail.jpg           # Preview image
└── metadata.json           # Structured data
```

**API Endpoint**: Part of `POST /async/episodes/{id}/process`

**Duration**: ~5-10 seconds

**Live Demo**: Open `index.html` in any browser

---

## 🎬 Intelligent Clip Segmentation

### Overview
The clip discovery system uses AI to identify the most engaging segments for social media.

### Algorithm Pipeline

```
Transcript → Topic Segmentation → Sentence Scoring → Clip Selection → Rendering
```

### Step 1: Topic Segmentation
**Technology**: ruptures (change point detection) + sentence-transformers

**Process**:
1. Generate embeddings for each sentence
2. Detect topic boundaries using Pelt algorithm
3. Merge short segments (min 20s)
4. Split long segments (max 2 min)

**Parameters**:
```python
{
  "model": "Binseg",           # Binary segmentation
  "min_size": 10,              # Min sentences per segment
  "jump": 5,                   # Search jump size
  "penalty": 3                 # Sensitivity (lower = more breaks)
}
```

### Step 2: Sentence Scoring
**Criteria** (weighted):
- **Semantic Coherence** (30%): How well sentences flow together
- **Information Density** (25%): Keywords, entities, technical terms
- **Engagement Signals** (20%): Questions, exclamations, emphasis
- **Quotability** (15%): Standalone value, shareability
- **Duration** (10%): Optimal length for platform (20-60s)

**Scoring Formula**:
```python
score = (
    0.30 * coherence_score +
    0.25 * information_density +
    0.20 * engagement_score +
    0.15 * quotability_score +
    0.10 * duration_score
)
```

### Step 3: Clip Selection
**Strategy**: Greedy selection with diversity

**Process**:
1. Sort segments by score (descending)
2. Select top segment
3. For each remaining segment:
   - Check temporal overlap (skip if <30s gap)
   - Check semantic similarity (skip if >0.8 similarity)
   - Add to selection if diverse enough
4. Stop at max_clips limit

**Parameters**:
```json
{
  "max_clips": 5,
  "min_duration_ms": 20000,    // 20 seconds
  "max_duration_ms": 120000,   // 2 minutes
  "min_gap_seconds": 30,       // Between clips
  "similarity_threshold": 0.8   // Diversity filter
}
```

### Step 4: Clip Rendering
**Output Variants**:
- **Clean**: Video only, no overlays
- **Subtitled**: Burned-in captions
- **Branded**: Logo + lower third

**Aspect Ratios**:
- **16:9**: YouTube, Twitter
- **9:16**: TikTok, Instagram Reels, YouTube Shorts
- **1:1**: Instagram Feed, Facebook

**Rendering Stack**:
- **FFmpeg**: Video processing
- **ImageMagick**: Thumbnail generation
- **Pillow**: Text rendering for subtitles

**Output Structure**:
```
data/outputs/{show_folder}/{year}/{episode_id}/clips/
├── {clip_id}/
│   ├── 16x9_clean.mp4
│   ├── 9x16_clean.mp4
│   ├── 16x9_subtitled.mp4
├── {clip_id}_subtitled_9x16.mp4
└── metadata.json
```

---

## 🔌 API Reference

### Base URL
```
http://localhost:8000
```

### Authentication
Currently: None (local deployment)
Production: Add API key authentication

---

### 📍 Core Endpoints

#### 1. Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "disk_percent": 38.5,
  "active_episodes": 2,
  "queue_size": 1
}
```

---

#### 2. Discover Episodes
```http
POST /episodes/discover
```

**Description**: Scan configured directories for new videos

**Response**:
```json
{
  "discovered": 3,
  "duplicates": 1,
  "episodes": [
    {
      "episode_id": "newsroom-2024-episode-01",
      "title": "Episode 01",
      "duration": 1847.5,
      "source_path": "test_videos/newsroom/2024/episode_01.mp4",
      "stage": "discovered"
    }
  ]
}
```

**Duration**: 1-5 seconds

---

#### 3. Get Episode Details
```http
GET /episodes/{episode_id}
```

**Response**:
```json
{
  "episode_id": "newsroom-2024-episode-01",
  "title": "Episode 01",
  "show": "newsroom",
  "stage": "enriched",
  "duration": 1847.5,
  "transcription": {
    "text": "Full transcript...",
    "word_count": 2847,
    "language": "en"
  },
  "enrichment": {
    "summary": "This episode discusses...",
    "topics": ["AI", "Technology", "Future"],
    "hashtags": ["#AI", "#Tech", "#Innovation"]
  }
}
```

---

### 🔄 Async Processing Endpoints

#### 4. Submit Processing Job (Async)
```http
POST /async/episodes/{episode_id}/process
```

**Description**: Start background processing (returns immediately)

**Request Body**:
```json
{
  "target_stage": "rendered",
  "force_reprocess": false,
  "webhook_url": "https://your-n8n-instance.com/webhook/job-complete"
}
```

**Response** (immediate):
```json
{
  "job_id": "b373f3b4-4381-4ed8-8f5d-3c0d6bbb7f06",
  "status": "queued",
  "message": "Episode processing queued. Poll /async/jobs/{job_id} for status."
}
```

**Duration**: <1 second

---

#### 5. Get Job Status
```http
GET /async/jobs/{job_id}
```

**Response**:
```json
{
  "job_id": "b373f3b4-4381-4ed8-8f5d-3c0d6bbb7f06",
  "job_type": "process_episode",
  "status": "running",
  "progress": 45.5,
  "current_stage": "transcribing",
  "message": "Transcribing audio with Whisper...",
  "eta_seconds": 180,
  "created_at": "2025-10-26T18:31:29.591498",
  "started_at": "2025-10-26T18:31:29.593004",
  "completed_at": null
}
```

**Status Values**:
- `queued`: Job submitted, waiting to start
- `running`: Currently processing
- `completed`: Successfully finished
- `failed`: Error occurred
- `cancelled`: Manually stopped

---

#### 6. List Jobs
```http
GET /async/jobs?status=running&limit=20
```

**Query Parameters**:
- `status`: Filter by status (optional)
- `limit`: Max results (default: 50)

**Response**:
```json
[
  {
    "job_id": "...",
    "status": "running",
    "progress": 45.5,
    ...
  }
]
```

---

#### 7. Queue Statistics
```http
GET /async/stats
```

**Response**:
```json
{
  "queued": 2,
  "running": 1,
  "completed": 15,
  "failed": 0,
  "total_jobs": 18,
  "avg_duration_seconds": 342.5
}
```

---

### 🎬 Clip Endpoints

#### 8. Discover Clips
```http
POST /episodes/{episode_id}/discover_clips
```

**Description**: Analyze transcript and identify best clips

**Request Body**:
```json
{
  "max_clips": 5,
  "min_duration_ms": 20000,
  "max_duration_ms": 120000,
  "target_platforms": ["tiktok", "youtube_shorts"]
}
```

**Response**:
```json
{
  "clips_discovered": 5,
  "clips": [
    {
      "id": "clip_001",
      "title": "Key Insight About AI",
      "start_ms": 45000,
      "end_ms": 75000,
      "duration_ms": 30000,
      "score": 0.87,
      "caption": "This is the most important thing about AI...",
      "hashtags": ["#AI", "#Tech", "#Innovation"]
    }
  ]
}
```

**Duration**: 10-30 seconds

---

#### 9. Render Clips (Async)
```http
POST /async/episodes/{episode_id}/render_clips
```

**Description**: Generate video files for discovered clips

**Request Body**:
```json
{
  "clip_ids": ["clip_001", "clip_002"],
  "variants": ["clean", "subtitled"],
  "aspect_ratios": ["16:9", "9:16"],
  "force_rerender": false,
  "webhook_url": "https://your-n8n-instance.com/webhook/clips-ready"
}
```

**Response**:
```json
{
  "job_id": "render_job_123",
  "status": "queued",
  "message": "Clip rendering queued. Poll /async/jobs/{job_id} for status."
}
```

**Duration**: 2-5 minutes per clip (background)

---

#### 10. Get Rendered Clips
```http
GET /episodes/{episode_id}/clips
```

**Response**:
```json
{
  "episode_id": "newsroom-2024-episode-01",
  "clips": [
    {
      "id": "clip_001",
      "status": "rendered",
      "files": [
        {
          "variant": "clean",
          "aspect_ratio": "16:9",
          "path": "data/clips/newsroom-2024-episode-01/clip_001_clean_16x9.mp4",
          "size_bytes": 2458624,
          "duration_ms": 30000
        }
      ]
    }
  ]
}
```

---

## 🔗 Integration Patterns

### Pattern 1: Simple Polling (Recommended for n8n)

**Use Case**: Process videos and wait for completion

**Workflow**:
```
1. Discover episodes
2. Submit async processing job
3. Poll job status every 30 seconds
4. When complete, fetch results
5. Send notification
```

**n8n Nodes**:
```
HTTP Request (Discover)
  ↓
HTTP Request (Submit Job)
  ↓
Wait (30 seconds)
  ↓
HTTP Request (Check Status) ←┐
  ↓                          │
IF (status == "completed")   │
  ↓ NO ─────────────────────┘
  ↓ YES
HTTP Request (Get Episode)
  ↓
Slack/Email Notification
```

**Example n8n HTTP Request Node** (Submit Job):
```json
{
  "method": "POST",
  "url": "http://localhost:8000/async/episodes/{{ $json.episode_id }}/process",
  "body": {
    "target_stage": "rendered",
    "force_reprocess": false
  },
  "options": {
    "timeout": 30000
  }
}
```

---

### Pattern 2: Webhook Notification

**Use Case**: Get notified when job completes (no polling)

**Workflow**:
```
1. Create n8n webhook endpoint
2. Submit job with webhook_url
3. n8n waits for webhook callback
4. Process results when notified
```

**n8n Nodes**:
```
Webhook (Listen)
  ↓
HTTP Request (Submit Job with webhook_url)
  ↓
Wait for Webhook
  ↓
HTTP Request (Get Episode)
  ↓
Process Results
```

**Webhook Payload** (sent by AI-EWG):
```json
{
  "job_id": "b373f3b4-4381-4ed8-8f5d-3c0d6bbb7f06",
  "status": "completed",
  "job_type": "process_episode",
  "result": {
    "episode_id": "newsroom-2024-episode-01",
    "stage": "rendered",
    "duration": 342.5
  }
}
```

---

### Pattern 3: Scheduled Batch Processing

**Use Case**: Process all new videos daily at 2 AM

**Workflow**:
```
Schedule Trigger (Daily 2 AM)
  ↓
HTTP Request (Discover)
  ↓
Split in Batches (5 at a time)
  ↓
HTTP Request (Submit Job)
  ↓
Wait (30 seconds)
  ↓
Loop until all complete
  ↓
Aggregate Results
  ↓
Send Summary Email
```

**Benefits**:
- Runs during off-hours
- Processes multiple videos in parallel
- Automatic retry on failure
- Daily summary report

---

## 📝 Workflow Examples

### Example 1: Basic Video Processing

**Goal**: Process a single video end-to-end

```javascript
// n8n Code Node - Submit Processing
const episodeId = $input.first().json.episode_id;

const response = await $http.request({
  method: 'POST',
  url: `http://localhost:8000/async/episodes/${episodeId}/process`,
  body: {
    target_stage: 'rendered',
    force_reprocess: false
  }
});

return { job_id: response.job_id };
```

```javascript
// n8n Code Node - Check Status
const jobId = $input.first().json.job_id;

const response = await $http.request({
  method: 'GET',
  url: `http://localhost:8000/async/jobs/${jobId}`
});

// Return status for IF node
return {
  status: response.status,
  progress: response.progress,
  is_complete: response.status === 'completed',
  is_failed: response.status === 'failed'
};
```

---

### Example 2: Clip Generation Pipeline

**Goal**: Generate social media clips from processed video

```javascript
// Step 1: Discover Clips
const episodeId = 'newsroom-2024-episode-01';

const discoverResponse = await $http.request({
  method: 'POST',
  url: `http://localhost:8000/episodes/${episodeId}/discover_clips`,
  body: {
    max_clips: 5,
    min_duration_ms: 20000,
    max_duration_ms: 60000
  }
});

const clipIds = discoverResponse.clips.map(c => c.id);

// Step 2: Render Clips
const renderResponse = await $http.request({
  method: 'POST',
  url: `http://localhost:8000/async/episodes/${episodeId}/render_clips`,
  body: {
    clip_ids: clipIds,
    variants: ['subtitled'],
    aspect_ratios: ['9:16'],  // TikTok/Reels format
    webhook_url: 'https://your-n8n.com/webhook/clips-ready'
  }
});

return { job_id: renderResponse.job_id };
```

---

### Example 3: Automated Content Publishing

**Goal**: Process video → Generate clips → Post to social media

```
Schedule Trigger (Daily 9 AM)
  ↓
HTTP Request (Discover Episodes)
  ↓
Filter (Only new episodes)
  ↓
HTTP Request (Process Episode)
  ↓
Wait & Poll (Until complete)
  ↓
HTTP Request (Discover Clips)
  ↓
HTTP Request (Render Clips - 9:16)
  ↓
Wait & Poll (Until clips ready)
  ↓
HTTP Request (Get Clip Files)
  ↓
Split in Batches
  ↓
TikTok API (Upload Video)
  ↓
Instagram API (Upload Reel)
  ↓
Slack (Send Summary)
```

---

## 📊 Monitoring & Dashboard

### Job Monitor Dashboard

**Access**: `streamlit run dashboard.py` → Navigate to "Job Monitor" page

**Purpose**: Visual interface for monitoring processing jobs and reviewing generated content

#### Features:

**1. Active Jobs Tab** 🔄
- Real-time progress bars with percentage
- ETA calculations (time remaining)
- Current processing stage
- Episode information

**2. Completed Jobs Tab** ✅
- Processing history with show name and episode title
- Processing duration and timestamps
- Direct links to view HTML output
- **Note**: Job history is in-memory and cleared on API restart

**3. Episodes Tab** 📹
- All processed episodes grouped by show
- **Displays AI-extracted metadata**:
  - Show name (e.g., "Boom and Bust")
  - Episode title
  - Duration and file size
  - Executive summary preview
  - Processing stage with status emoji
- Actions:
  - Open HTML in browser
  - View full transcript
  - See enrichment details

**4. Clips Tab** 🎬
- Generated clips by episode
- Clip metadata (title, caption, hashtags, score)
- Rendered file variants
- Discover new clips button

#### Top Metrics Bar

Shows at-a-glance statistics:
```
📚 Total Episodes: 5
🔍 Discovered: 1
📝 Transcribed: 1  
🤖 Enriched: 1
✅ Rendered: 2
```

#### Key Differences: Jobs vs Episodes

| Feature | Jobs (In-Memory) | Episodes (Database) |
|---------|------------------|---------------------|
| **Persistence** | ❌ Cleared on restart | ✅ Survives restarts |
| **Purpose** | Track active processing | Store final results |
| **Data** | Progress, ETA, status | Full metadata, enrichment |
| **Access** | Completed Jobs tab | Episodes tab |

**Best Practice**: Use **Episodes tab** to view processed content, especially after server restarts.

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. Timeout Errors
**Symptom**: `Read timed out` when calling API

**Solution**: Use async endpoints (`/async/*`) instead of sync endpoints

**Correct**:
```javascript
// ✅ Returns immediately
POST /async/episodes/{id}/process
```

**Incorrect**:
```javascript
// ❌ Blocks for entire processing time
POST /episodes/{id}/process
```

---

#### 2. Job Stuck in "Running"
**Symptom**: Job progress stops updating

**Diagnosis**:
```bash
# Check API server logs
tail -f logs/api.log

# Check system resources
curl http://localhost:8000/health
```

**Common Causes**:
- Out of memory (Whisper model requires 8GB+ RAM)
- GPU driver issues
- Ollama service not running

**Solutions**:
- Restart API server
- Check Ollama: `ollama list`
- Monitor resources: Task Manager / htop

---

#### 3. Clips Not Generating
**Symptom**: `discover_clips` returns 0 clips

**Diagnosis**:
```bash
# Check if episode is transcribed
curl http://localhost:8000/episodes/{episode_id}
# Look for "stage": "transcribed" or higher
```

**Common Causes**:
- Episode not transcribed yet
- Transcript too short (<2 minutes)
- All segments below quality threshold

**Solutions**:
- Wait for transcription to complete
- Lower `min_duration_ms` parameter
- Check transcript quality manually

---

#### 4. Webhook Not Firing
**Symptom**: n8n workflow doesn't receive webhook callback

**Diagnosis**:
```bash
# Check job completed
curl http://localhost:8000/async/jobs/{job_id}

# Check API logs for webhook attempts
grep "webhook" logs/api.log
```

**Common Causes**:
- Webhook URL not accessible from API server
- Firewall blocking outbound requests
- n8n webhook node not active

**Solutions**:
- Test webhook URL with curl
- Use ngrok for local n8n testing
- Check n8n webhook node is "listening"

---

### Performance Optimization

#### Processing Speed
| Stage | Duration (10 min video) | Optimization |
|-------|------------------------|--------------|
| Discovery | 1-2s | N/A |
| Transcription | 5-8 min | Use GPU (3-5 min) |
| Enrichment | 2-5 min | Use local Ollama |
| Rendering | 5-10s | N/A |
| **Total** | **7-13 min** | **With GPU: 5-10 min** |

#### GPU Acceleration
```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"

# Enable GPU in config
# config/pipeline.yaml
transcription:
  device: cuda  # or 'cpu'
```

#### Concurrent Processing
```yaml
# config/pipeline.yaml
job_queue:
  max_workers: 2  # Process 2 videos simultaneously
  
# Note: Each job requires 8GB+ RAM
# 2 workers = 16GB+ RAM recommended
```

---

## 📚 Additional Resources

### Configuration Files
- `config/pipeline.yaml` - Main configuration
- `config/llm_prompts.yaml` - AI prompt templates
- `config/clip_templates.yaml` - Clip rendering settings

### Documentation
- `README.md` - Quick start guide
- `HYBRID_WORKFLOW_IMPLEMENTATION.md` - Architecture details
- `QUICK_START_ASYNC.md` - Async API tutorial

### Monitoring
- Streamlit Dashboard: `streamlit run dashboard.py`
- Job Monitor: Navigate to "Job Monitor" page
- API Logs: `logs/api.log`

### Support
- GitHub Issues: [Report bugs/feature requests]
- API Health: `GET /health`
- System Status: `GET /status`

---

## 🚀 Quick Start Checklist

- [ ] API server running on port 8000
- [ ] Ollama service running (`ollama list`)
- [ ] Test video files in `test_videos/` directory
- [ ] n8n instance accessible
- [ ] Webhook endpoint created (if using webhooks)
- [ ] Test discovery: `POST /episodes/discover`
- [ ] Test async processing: `POST /async/episodes/{id}/process`
- [ ] Monitor job: `GET /async/jobs/{job_id}`
- [ ] Verify outputs in `data/outputs/` directory

---

## 📞 Contact & Support

For technical questions or integration support:
- Check logs: `logs/api.log`
- Review documentation: `docs/`
- Test with Streamlit dashboard first
- Use async endpoints for production workflows

**Happy Automating! 🎉**
