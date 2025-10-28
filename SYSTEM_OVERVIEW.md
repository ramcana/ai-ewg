# AI-EWG System Overview

## Architecture Summary

### **Backend (FastAPI)**
- **API Server**: `src/api/server.py` - RESTful API on port 8000
- **Database**: SQLite with WAL mode (`data/pipeline.db`)
- **Processing Pipeline**: `src/core/pipeline.py` - Stage-based orchestration
- **Job Queue**: Async processing with threading for long-running tasks
- **Endpoints**:
  - `/episodes` - Episode management (list, get, process, delete)
  - `/async/episodes/{id}/process` - Background processing
  - `/clips` - Clip discovery and rendering
  - `/social` - Social media package generation
  - `/health` - Health checks

### **Frontend (Streamlit)**
- **Main Dashboard**: `dashboard.py` - Multi-page navigation
- **Video Processing**: `components/processing.py` - File selection, batch processing
- **Job Monitor**: `pages/job_monitor.py` - Real-time progress tracking
- **Social Publishing**: `components/social_generator.py` - Platform package creation
- **Features**:
  - ✅ File selection with checkboxes (single/multiple)
  - ✅ Progress tracking with ETA
  - ✅ Failed episode management (retry/delete)
  - ✅ Smart discovery (skips duplicate checking for selected files)

---

## Processing Pipeline

### **Stage 1: Discovery & Prep**
```
Video File → Discovery → Database Registration → Audio Extraction
```
- Scans organized input directories (see Input Structure below)
- Generates episode ID from filename and AI-extracted metadata
- Extracts audio for transcription

**Input Structure** (Organized by Show):
```
input_videos/
├── TheNewsForum/
│   ├── ForumDailyNews/      # Forum Daily News episodes
│   ├── BoomAndBust/          # Boom and Bust episodes
│   ├── CommunityProfile/     # Community Profile episodes
│   ├── EconomicPulse/        # Economic Pulse episodes
│   └── FreedomForum/         # Freedom Forum episodes
├── _uncategorized/           # Videos to be sorted later
└── data/temp/uploaded/       # Temporary uploads from Streamlit
```

**Output Structure** (Consistent with Input):
```
data/
├── clips/{episode_id}/clips/{clip_id}/    # Generated clips
├── transcripts/{episode_id}/              # Transcription files
├── enrichment/{episode_id}/               # AI analysis
├── html/{episode_id}/                     # Web pages
└── social_packages/{episode_id}/          # Platform packages
```

**Setup**: Run `.\setup_input_structure.ps1` to create input folders

### **Stage 2: Transcription (Whisper)**
```
Audio → Whisper AI → Transcript + Word Timestamps → VTT/SRT
```
- Uses OpenAI Whisper (large-v3 model)
- Word-level timestamps for precise clip generation
- Diarization support (speaker identification)
- Outputs: JSON transcript, VTT, SRT subtitles

### **Stage 3: AI Enrichment (Ollama)**
```
Transcript → Intelligence Chain → Metadata Extraction → Database
```

**Intelligence Chain Components** (`src/core/intelligence_chain_v2.py`):

1. **Entity Extraction**
   - Method: LLM (Ollama) or spaCy NLP
   - Extracts: People, organizations, locations, topics
   - Output: `entities.json`

2. **Disambiguation** (Wikidata API)
   - Resolves entities to Wikidata IDs
   - Enriches with: descriptions, images, URLs
   - Confidence scoring
   - Output: `enriched.json`

3. **Scoring & Ranking**
   - Proficiency scores for guests
   - Relevance ranking
   - Output: `scored.json`

4. **AI Analysis** (Ollama)
   - Show name, host name, episode number extraction
   - Executive summary generation
   - Key takeaways (bullet points)
   - Deep analysis
   - Topic extraction
   - Segment titles
   - Output: Stored in `episode.enrichment`

**Models Used**:
- LLM: `llama3.2:latest` (via Ollama)
- NLP: `en_core_web_lg` (spaCy)

---

## Social Media Generation

### **Platform Support**
- YouTube (16:9, 10 min max, chapter markers)
- Instagram Reels (9:16, 90 sec max)
- X/Twitter (16:9, 2:20 min max, 280 char)
- TikTok (9:16, 3 min max)
- Facebook (16:9, 4 min max)

### **Policy Engine** (`src/core/policy_engine.py`)
- Loads platform requirements from `config/platforms/*.yaml`
- Validates content against policies
- Transforms metadata (hashtags, descriptions, titles)
- Scoring system for policy compliance

### **Package Generator** (`src/core/package_generator.py`)
```
Episode → Policy Validation → Content Transformation → Package Files
```

**Output Structure**: `data/social_packages/{episode_id}/{platform}/`
- `video.mp4` (platform-specific naming)
- `title.txt` (optimized for platform)
- `caption.txt` (with hashtags)
- `description.txt` (full description)
- `hashtags.txt` (platform-specific tags)
- `metadata.json` (comprehensive metadata)
- `structured_data.jsonld` (Schema.org for SEO)

### **Job Tracking** (`src/core/social_job_tracker.py`)
- Database: `social_jobs` table
- Real-time progress updates
- Per-platform error tracking
- Partial success support (some platforms succeed, others fail)

---

## Optimized Web Page + SEO

### **HTML Generation** (`src/stages/rendering_stage.py`)
```
Episode Data → Jinja2 Templates → Static HTML → data/html/{episode_id}/
```

**Generated Pages**:
- `episode.html` - Full episode page with player, transcript, guests
- `show_index.html` - Show listing page
- `person_profile.html` - Guest profile pages

**SEO Features**:

1. **JSON-LD Structured Data** (`src/core/jsonld_generator.py`)
   - Schema.org VideoObject
   - Person/Organization schemas
   - SeekToAction for Google Key Moments
   - Breadcrumbs navigation
   - Embedded in HTML `<head>`

2. **Metadata Optimization**
   - AI-generated titles and descriptions
   - Keyword-rich content from topics
   - Open Graph tags for social sharing
   - Twitter Card metadata

3. **Content Structure**
   - Semantic HTML5 markup
   - Heading hierarchy (H1-H6)
   - Accessible ARIA labels
   - Mobile-responsive design

4. **Rich Snippets**
   - Video duration, upload date
   - Guest information with credentials
   - Topic tags and categories
   - Transcript excerpts

**Output**: `data/html/{episode_id}/episode.html`

---

## Data Flow Summary

```
┌─────────────┐
│ Video File  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ BACKEND PIPELINE (FastAPI + SQLite)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Discovery → Episode Registration                    │
│  2. Prep → Audio Extraction                             │
│  3. Transcription → Whisper AI → Transcript + VTT       │
│  4. Enrichment → Ollama + Wikidata → Metadata           │
│  5. Rendering → Jinja2 → HTML + JSON-LD                 │
│  6. Clips → Discovery + Rendering → MP4 variants        │
│  7. Social → Policy Engine → Platform Packages          │
│                                                          │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ OUTPUTS                                                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📁 data/transcripts/{episode_id}/                      │
│     ├── transcript.json (full transcript)               │
│     ├── transcript.vtt (WebVTT subtitles)               │
│     └── transcript.srt (SRT subtitles)                  │
│                                                          │
│  📁 data/enrichment/{episode_id}/                       │
│     ├── entities.json (extracted entities)              │
│     ├── enriched.json (Wikidata enrichment)             │
│     └── scored.json (ranked guests)                     │
│                                                          │
│  📁 data/html/{episode_id}/                             │
│     └── episode.html (SEO-optimized page + JSON-LD)     │
│                                                          │
│  📁 data/clips/{episode_id}/clips/{clip_id}/            │
│     ├── 9x16_clean.mp4 (vertical, no subs)              │
│     ├── 9x16_subtitled.mp4 (vertical, with subs)        │
│     ├── 16x9_clean.mp4 (horizontal, no subs)            │
│     └── 16x9_subtitled.mp4 (horizontal, with subs)      │
│                                                          │
│  📁 data/social_packages/{episode_id}/                  │
│     ├── youtube/ (video + metadata + JSON-LD)           │
│     ├── instagram/ (9:16 video + caption + hashtags)    │
│     ├── twitter/ (video + 280 char + hashtags)          │
│     ├── tiktok/ (9:16 video + caption)                  │
│     └── facebook/ (video + description)                 │
│                                                          │
│  📁 data/pipeline.db (SQLite database)                  │
│     ├── episodes (all episode data)                     │
│     ├── clips (clip specifications)                     │
│     └── social_jobs (job tracking)                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ FRONTEND (Streamlit Dashboard)                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  🎬 Video Processing                                    │
│     ├── File selection (checkboxes)                     │
│     ├── Batch processing                                │
│     ├── Progress tracking                               │
│     └── Failed episode management                       │
│                                                          │
│  📊 Job Monitor                                         │
│     ├── Real-time status                                │
│     ├── Progress bars with ETA                          │
│     └── Output preview                                  │
│                                                          │
│  📱 Social Publishing                                   │
│     ├── Platform selection                              │
│     ├── Package generation                              │
│     └── Preview & download                              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Key Technologies

### **AI/ML**
- **Whisper** (OpenAI) - Speech-to-text transcription
- **Ollama** (Llama 3.2) - Metadata extraction, summarization
- **spaCy** (en_core_web_lg) - NLP entity extraction
- **Wikidata API** - Entity disambiguation and enrichment

### **Backend**
- **FastAPI** - REST API framework
- **SQLite** - Database (WAL mode for concurrency)
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **Threading** - Background job processing

### **Frontend**
- **Streamlit** - Dashboard UI
- **Pandas** - Data display
- **Plotly** - Charts (if used)

### **Media Processing**
- **FFmpeg** - Video/audio manipulation
- **PyAV** - Python FFmpeg bindings
- **Pillow** - Image processing

### **Web Generation**
- **Jinja2** - HTML templating
- **JSON-LD** - Structured data (Schema.org)
- **Markdown** - Content formatting

---

## Recent Improvements

### **File Selection Fix**
- ✅ Added checkboxes for individual file selection
- ✅ Select All / Deselect All buttons
- ✅ Only processes selected files (not all discovered)

### **Discovery Optimization**
- ✅ Skips full directory scan when files are selected
- ✅ Loads existing episodes from database first
- ✅ Only runs discovery for missing files
- ✅ No more "Duplicate file detected" spam

### **Failed Episode Management**
- ✅ Delete button for failed episodes
- ✅ Bulk delete with confirmation
- ✅ Individual retry/delete per episode
- ✅ Complete cleanup (database + files + cache)

### **Resume Capability**
- ✅ Processing state stored in database
- ✅ Automatically resumes from last completed stage
- ✅ No need to reprocess completed stages
- ✅ Force reprocess option available

---

## Configuration

### **Main Config**: `config/pipeline.yaml`
```yaml
# Organized input sources by show
sources:
  - path: "input_videos/TheNewsForum/ForumDailyNews"
    enabled: true
  - path: "input_videos/TheNewsForum/BoomAndBust"
    enabled: true
  - path: "input_videos/TheNewsForum/CommunityProfile"
    enabled: true
  - path: "input_videos/TheNewsForum/EconomicPulse"
    enabled: true
  - path: "input_videos/TheNewsForum/FreedomForum"
    enabled: true
  - path: "input_videos/_uncategorized"
    enabled: true
  - path: "data/temp/uploaded"
    enabled: true
  # Legacy folder (disabled)
  - path: "test_videos/newsroom/2024"
    enabled: false

models:
  whisper_model: large-v3
  llm: llama3.2:latest
  spacy_model: en_core_web_lg

clip_generation:
  enabled: true
  min_duration: 30
  max_duration: 180

# Episode naming and organization
organization:
  folder_structure: "{show_folder}/{year}"
  episode_template: "{show_folder}_ep{episode_number}_{date}"
```

### **Platform Configs**: `config/platforms/*.yaml`
- `youtube.yaml` - YouTube requirements
- `instagram.yaml` - Instagram Reels specs
- `tiktok.yaml` - TikTok requirements
- `twitter.yaml` - X/Twitter specs
- `facebook.yaml` - Facebook requirements

---

## Startup Commands

### **Start Backend API**
```powershell
.\start-api-server.ps1
# Runs on http://localhost:8000
```

### **Start Frontend Dashboard**
```powershell
streamlit run dashboard.py
# Runs on http://localhost:8501
```

### **Check Health**
```powershell
curl http://localhost:8000/health
```

---

## API Endpoints Quick Reference

### **Episodes**
- `GET /episodes` - List all episodes
- `GET /episodes/{id}` - Get episode details
- `POST /episodes/discover` - Discover new episodes
- `POST /episodes/{id}/process` - Process episode (sync)
- `DELETE /episodes/{id}` - Delete episode

### **Async Processing**
- `POST /async/episodes/{id}/process` - Start background job
- `GET /async/jobs/{id}` - Get job status
- `GET /async/jobs` - List all jobs

### **Clips**
- `POST /clips/discover/{episode_id}` - Discover clips
- `POST /clips/render/{episode_id}` - Render clips
- `GET /clips/{episode_id}` - List episode clips

### **Social Media**
- `POST /social/generate` - Generate packages (returns job_id)
- `GET /social/jobs/{job_id}` - Get generation status
- `GET /social/platforms` - List supported platforms
- `GET /social/packages/{episode_id}` - List packages

---

## Performance Characteristics

### **Processing Times** (10-minute video)
- Discovery: ~1 second
- Audio Extraction: ~5 seconds
- Transcription (Whisper): ~2-3 minutes
- Enrichment (AI): ~30-60 seconds
- HTML Generation: ~2 seconds
- Clip Discovery: ~10-15 seconds
- Social Packages: ~5-10 seconds per platform

### **Resource Usage**
- CPU: High during transcription (Whisper)
- GPU: Used if available (RTX 4080 detected)
- RAM: ~4-8 GB during processing
- Disk: ~500 MB per 10-minute episode (all outputs)

### **Scalability**
- Single-worker mode (SQLite limitation)
- Sequential processing (one episode at a time)
- Background jobs for long operations
- PostgreSQL migration available for production

---

## Next Steps / Future Enhancements

### **Planned**
- [ ] Direct platform publishing (YouTube, Instagram APIs)
- [ ] Video transcoding for platform requirements
- [ ] Thumbnail generation with AI
- [ ] Analytics and performance tracking
- [ ] Multi-language support
- [ ] PostgreSQL migration for production

### **In Progress**
- [x] File selection UI
- [x] Discovery optimization
- [x] Failed episode management
- [x] Resume capability

---

**Last Updated**: October 27, 2025  
**Version**: 1.0  
**Status**: Production-Ready
