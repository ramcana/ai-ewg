# AI-EWG System Overview

**Last Updated:** October 30, 2025

## 📋 Table of Contents

- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Naming & Organization System](#naming--organization-system)
- [UI Components](#ui-components)
- [Recent Enhancements](#recent-enhancements)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)

---

## 🏗️ System Architecture

### **High-Level Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit Dashboard                         │
│  (Process Videos | View Outputs | Clip Management | Social Gen) │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                              │
│  (Episode Endpoints | Clip Endpoints | Social Endpoints)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline                           │
│  Discovery → Transcription → Enrichment → Rendering → Clips     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    NamingService (Central Authority)             │
│  Show Mapping | Episode ID Generation | Path Generation         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SQLite Database                               │
│  Episodes | Clips | Assets | Social Jobs | Corrections          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    File System                                   │
│  data/outputs/{show}/{year}/{episode}/                          │
│    ├── clips/                                                    │
│    ├── html/                                                     │
│    └── social/                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Core Components

### **1. Pipeline Orchestrator** (`src/core/pipeline.py`)

**Purpose:** Main processing engine that coordinates all stages

**Key Methods:**
- `discover_episodes()` - Find and catalog video files
- `process_episode()` - Run episode through all stages
- `_process_transcription_stage()` - Whisper transcription
- `_process_enrichment_stage()` - AI metadata extraction
- `_process_rendering_stage()` - HTML generation
- `_process_clips_discovery_stage()` - Intelligent clip detection

**Features:**
- ✅ Force reprocess support
- ✅ Stage-by-stage processing
- ✅ Skip existing data (unless forced)
- ✅ Error handling and recovery
- ✅ Progress tracking

---

### **2. NamingService** (`src/core/naming_service.py`)

**Purpose:** Single source of truth for all naming and path generation

**Key Methods:**
- `map_show_name(show_name)` - Convert AI names to canonical folder names
- `generate_episode_id(...)` - Create unique episode IDs
- `get_episode_folder_path(...)` - Generate consistent folder paths

**Configuration:**
- Loads from `config/show_mappings.json` (user-defined)
- Falls back to hardcoded defaults
- Supports slugification for unknown shows

**Ensures Consistency:**
- All components use same naming service
- Database stores canonical names
- All paths generated consistently

---

### **3. Registry** (`src/core/registry.py`)

**Purpose:** Database management for episodes and metadata

**Key Methods:**
- `register_episode()` - Add new episode to database
- `get_episode()` - Retrieve episode by ID
- `list_episodes()` - Get all episodes with filters
- `update_episode_data()` - Update episode metadata
- `delete_episode()` - Remove episode and handle foreign keys

**Database Tables:**
- `episodes` - Episode metadata and processing state
- `clips` - Discovered clips with timestamps
- `clip_assets` - Rendered clip files
- `social_jobs` - Social media package jobs
- `corrections` - Self-learning transcript corrections

---

### **4. Clip System**

#### **Clip Discovery** (`src/core/clip_discovery.py`)
- Topic segmentation using embeddings
- Semantic boundary detection
- Scoring based on multiple factors
- GPU-accelerated processing

#### **Clip Export** (`src/core/clip_export.py`)
- FFmpeg-based video rendering
- Multiple aspect ratios (16:9, 9:16, 1:1)
- Subtitle variants (clean, subtitled)
- Intelligent cropping support

#### **Clip Registry** (`src/core/clip_registry.py`)
- Clip metadata storage
- Asset tracking
- Status management

---

### **5. Social Media System**

#### **Package Generator** (`src/core/package_generator.py`)
- Platform-specific content generation
- Metadata transformation
- File organization

#### **Policy Engine** (`src/core/policy_engine.py`)
- Platform requirements validation
- Content compliance checking
- Template-based transformations

#### **Job Tracker** (`src/core/social_job_tracker.py`)
- Background job processing
- Progress tracking
- Error handling

---

## 🔄 Data Flow

### **Complete Processing Flow**

```
1. VIDEO UPLOAD/DISCOVERY
   ├─ User uploads file → data/temp/uploaded/
   ├─ Or: Files in input_videos/{show}/
   └─ Discovery scans all sources

2. EPISODE REGISTRATION
   ├─ Extract show name from filename/folder
   ├─ NamingService.map_show_name() → Canonical name
   ├─ NamingService.generate_episode_id() → Unique ID
   ├─ Calculate file hash for deduplication
   └─ Registry.register_episode() → Database

3. TRANSCRIPTION STAGE
   ├─ Check if transcription exists (skip if present)
   ├─ Extract audio from video
   ├─ Whisper transcription (GPU accelerated)
   ├─ Generate VTT/SRT files
   └─ Save to episode.transcription → Database

4. ENRICHMENT STAGE
   ├─ Check if enrichment exists (skip if present)
   ├─ AI analysis (Ollama/LLM)
   ├─ Extract: show_name, host_name, episode_number
   ├─ Generate: summaries, topics, key_takeaways
   ├─ Update episode.enrichment → Database
   └─ Update episode.show and episode.title

5. RENDERING STAGE
   ├─ NamingService.get_episode_folder_path()
   ├─ Generate HTML with synchronized video/transcript
   ├─ Create index pages and feeds
   ├─ Save to: data/outputs/{show}/{year}/{episode}/
   └─ Update episode.stage = 'rendered'

6. CLIP DISCOVERY (Optional)
   ├─ Topic segmentation (GPU accelerated)
   ├─ Semantic boundary detection
   ├─ Clip scoring and ranking
   ├─ Save to clips table
   └─ Update episode.stage = 'clips_discovered'

7. CLIP RENDERING (On Demand)
   ├─ Get episode folder path
   ├─ For each clip and variant:
   │  ├─ FFmpeg rendering
   │  ├─ Intelligent cropping (if enabled)
   │  └─ Save to: {episode_folder}/clips/{clip_id}/
   └─ Update clip_assets table

8. SOCIAL PACKAGES (On Demand)
   ├─ Get episode folder path
   ├─ For each platform:
   │  ├─ Validate content against policies
   │  ├─ Transform metadata
   │  ├─ Generate platform-specific files
   │  └─ Save to: {episode_folder}/social/{platform}/
   └─ Update social_jobs table
```

---

## 📁 Naming & Organization System

### **Episode ID Format**

```
{show_folder}_ep{episode_number}_{date}
```

**Examples:**
- `ForumDailyNews_ep140_2024-10-27`
- `ForumDailyWeek_ep001_2025-10-30`
- `MyGeneration_ep025_2024-11-15`

### **Folder Structure**

```
data/outputs/
├── ForumDailyNews/
│   └── 2025/
│       └── ForumDailyNews_ep140_2024-10-27/
│           ├── index.html
│           ├── clips/
│           │   └── clip_abc123/
│           │       ├── 9x16_clean.mp4
│           │       ├── 9x16_subtitled.mp4
│           │       ├── 16x9_clean.mp4
│           │       └── 16x9_subtitled.mp4
│           └── social/
│               ├── youtube/
│               ├── instagram/
│               └── tiktok/
├── ForumDailyWeek/
│   └── 2025/
└── MyGeneration/
    └── 2024/
```

### **Show Name Mapping**

| AI Extracted | Filename Prefix | Canonical Folder |
|--------------|----------------|------------------|
| "Forum Daily News" | FD | ForumDailyNews |
| "Forum Daily Week" | FDW | ForumDailyWeek |
| "My Generation" | MG | MyGeneration |
| "Boom and Bust" | BB | BoomAndBust |
| "Community Profile" | CP | CommunityProfile |

**Configuration:** `config/show_mappings.json`

---

## 🖥️ UI Components

### **1. Process Videos Page** (`components/processing.py`)

**Features:**
- ✅ Previously Processed Videos section with reprocessing
- ✅ Persistent uploaded files management
- ✅ Episode selection dropdown
- ✅ Force reprocess option (auto-enabled for reprocessing)
- ✅ Processing options configuration
- ✅ Real-time progress monitoring
- ✅ Bulk delete for failed episodes

**Recent Enhancements:**
- Uploaded files persist across sessions
- One-click reprocessing from history
- Visual file management (use/delete)
- Smart priority system for folder selection

---

### **2. View Outputs Page** (`components/outputs.py`)

**Features:**
- ✅ Episode list with filtering
- ✅ Episode details view
- ✅ Delete episode button with confirmation
- ✅ HTML preview
- ✅ Metadata display
- ✅ File cleanup on deletion

---

### **3. Clip Management Page** (`components/clips.py`)

**Features:**
- ✅ Previously Processed Episodes section
- ✅ Episode metrics dashboard
- ✅ Clip parameter configuration
- ✅ Intelligent crop settings (Beta)
- ✅ Clip discovery preview
- ✅ Bulk rendering controls
- ✅ Clip generation monitoring

**Intelligent Crop Options:**
- Strategy: hybrid, face_tracking, motion_aware, center
- Face detection toggle
- Motion detection toggle
- Smooth transitions toggle

**Recent Enhancements:**
- Episode table with status icons
- Quick navigation buttons
- Intelligent crop params passed to API

---

### **4. Social Generator Page** (`components/social_generator.py`)

**Features:**
- ✅ Episode selection
- ✅ Platform selection (YouTube, Instagram, TikTok, X, Facebook)
- ✅ Package generation
- ✅ Job monitoring with progress bars
- ✅ Statistics dashboard

---

### **5. Show Configuration Page** (`components/show_config.py`)

**Features:**
- ✅ Current show mappings view
- ✅ Add new show with aliases
- ✅ Bulk edit mappings (JSON)
- ✅ Folder path preview
- ✅ Example output paths
- ✅ Delete mappings

**Recent Enhancements:**
- Real-time folder path preview
- Visual confirmation of output structure
- Alias management

---

### **6. Corrections Page** (`components/corrections.py`)

**Features:**
- ✅ Self-learning correction engine
- ✅ Correction rules management
- ✅ Pattern-based replacements
- ✅ Statistics and analytics

---

## 🆕 Recent Enhancements (October 2025)

### **1. Episode Deletion System**
- DELETE API endpoint with file cleanup
- Registry method with foreign key handling
- UI delete buttons with confirmation
- Bulk delete for failed episodes

### **2. Episode Reprocessing**
- Select from previously processed list
- Auto-enable force reprocess
- One-click reprocessing workflow
- Clear visual feedback

### **3. Persistent Upload Management**
- Uploaded files persist across sessions
- Visual file list with actions
- Per-file use/delete buttons
- Bulk process all uploads
- Smart priority system

### **4. Show Configuration**
- User-defined show mappings
- Config file support (show_mappings.json)
- Folder path previews
- Alias management
- Default mappings fallback

### **5. Filename Prefix Extraction**
- Auto-extract show from filename (FDW, FD, MG, etc.)
- Prefix mapping to show names
- Handles uploaded files without folder structure

### **6. Clip Management Improvements**
- Previously Processed Episodes section
- Episode metrics dashboard
- Intelligent crop integration
- Status-based filtering

### **7. Naming System Consistency**
- NamingService as single source of truth
- All components use same naming logic
- Database stores canonical names
- Config file synchronization

---

## 🔌 API Endpoints

### **Episode Endpoints** (`/episodes`)

```
GET    /episodes                    # List all episodes
GET    /episodes/{id}               # Get episode details
POST   /episodes/discover           # Discover new episodes
POST   /episodes/{id}/process       # Process episode
DELETE /episodes/{id}               # Delete episode
GET    /episodes/{id}/status        # Get processing status
```

### **Clip Endpoints** (`/episodes/{id}/clips`)

```
POST   /episodes/{id}/discover_clips    # Discover clips
POST   /episodes/{id}/render_clips      # Render all clips
GET    /clips/{clip_id}                 # Get clip details
POST   /clips/{clip_id}/render          # Render single clip
```

### **Social Endpoints** (`/social`)

```
POST   /social/generate                 # Generate packages
GET    /social/jobs/{job_id}            # Get job status
GET    /social/jobs                     # List all jobs
GET    /social/platforms                # List platforms
GET    /social/packages/{episode_id}    # List packages
DELETE /social/packages/{episode_id}/{platform}  # Delete package
```

### **Async Endpoints** (`/async`)

```
POST   /async/episodes/{id}/process     # Async processing
GET    /async/jobs/{job_id}             # Get job status
```

---

## ⚙️ Configuration

### **Main Config** (`config/pipeline.yaml`)

```yaml
organization:
  folder_structure: "{show_folder}/{year}"
  episode_template: "{show_folder}_ep{episode_number}_{date}"
  date_format: "%Y-%m-%d"

models:
  whisper: "large-v3"
  llm: "llama3.1:latest"

transcription:
  language: "auto"
  translate_to_english: false
  supported_languages: ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]

sources:
  - path: "input_videos/TheNewsForum/ForumDailyNews"
    enabled: true
  - path: "input_videos/_uncategorized"
    enabled: true
  - path: "data/temp/uploaded"
    enabled: true
```

### **Show Mappings** (`config/show_mappings.json`)

```json
{
  "forum daily news": "ForumDailyNews",
  "forum daily week": "ForumDailyWeek",
  "fdw": "ForumDailyWeek",
  "my generation": "MyGeneration",
  "boom and bust": "BoomAndBust"
}
```

### **Platform Configs** (`config/platforms/*.yaml`)

```yaml
# youtube.yaml
name: "YouTube"
aspect_ratio: "16:9"
max_duration: 600
requirements:
  - "Chapter markers for long videos"
  - "Thumbnail required"
```

---

## 📊 Database Schema

### **Episodes Table**

```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    source_path TEXT NOT NULL,
    content_hash TEXT UNIQUE,
    metadata TEXT,  -- JSON: show_name, title, date, etc.
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### **Clips Table**

```sql
CREATE TABLE clips (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    score REAL NOT NULL,
    status TEXT NOT NULL,
    metadata TEXT,  -- JSON: title, description, topics
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
)
```

### **Clip Assets Table**

```sql
CREATE TABLE clip_assets (
    id TEXT PRIMARY KEY,
    clip_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL,
    output_path TEXT NOT NULL,
    file_size INTEGER,
    status TEXT NOT NULL,
    FOREIGN KEY (clip_id) REFERENCES clips(id) ON DELETE CASCADE
)
```

---

## 🚀 Performance Optimizations

### **GPU Acceleration**
- ✅ Whisper transcription (FP16)
- ✅ Topic segmentation (CUDA)
- ✅ Embedding generation (sentence-transformers)

### **Caching**
- ✅ Skip existing transcriptions
- ✅ Skip existing enrichment
- ✅ Content hash deduplication

### **Background Processing**
- ✅ Async API endpoints
- ✅ Job queue system
- ✅ Progress tracking

### **Resource Management**
- ✅ Memory limits for FFmpeg
- ✅ Concurrent processing limits
- ✅ Cleanup on failure

---

## 🔐 Security

### **API Security**
- Token-based authentication (optional)
- Rate limiting
- CORS configuration

### **File System**
- Sandboxed file operations
- Path validation
- Size limits

### **Database**
- Foreign key constraints
- Transaction support
- Backup mechanisms

---

## 📚 Additional Documentation

- **[GETTING_STARTED.md](../GETTING_STARTED.md)** - Quick start guide
- **[MULTILINGUAL_SUPPORT.md](MULTILINGUAL_SUPPORT.md)** - Language support
- **[NAMING_SYSTEM.md](NAMING_SYSTEM.md)** - Naming conventions
- **[CLEANUP_MECHANISM.md](CLEANUP_MECHANISM.md)** - Data cleanup
- **[INTELLIGENT_CROP.md](INTELLIGENT_CROP.md)** - Intelligent cropping
- **[SOCIAL_PUBLISHING_IMPLEMENTATION.md](SOCIAL_PUBLISHING_IMPLEMENTATION.md)** - Social media
- **[HYBRID_WORKFLOW_IMPLEMENTATION.md](HYBRID_WORKFLOW_IMPLEMENTATION.md)** - Async workflows

---

## 🎯 Key Takeaways

1. **NamingService is the single source of truth** for all naming
2. **All components use the same naming logic** ensuring consistency
3. **Database stores canonical names** for reliable retrieval
4. **Folder structure is consistent** across all output types
5. **Force reprocess regenerates all files** when needed
6. **Uploaded files persist** across sessions
7. **Episode reprocessing is one-click** from history
8. **Show configuration is user-customizable** via UI and config files

---

**System Version:** 2.0  
**Last Major Update:** October 30, 2025  
**Status:** Production Ready ✅
