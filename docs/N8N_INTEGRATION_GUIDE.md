# n8n Integration Guide - AI-EWG Video Processing Pipeline

**Version:** 1.0  
**Last Updated:** October 23, 2025  
**Target Audience:** n8n Workflow Engineers

---

## Table of Contents
1. [System Overview](#system-overview)
2. [API Architecture](#api-architecture)
3. [Available Endpoints](#available-endpoints)
4. [Processing Pipeline Stages](#processing-pipeline-stages)
5. [Intelligence Features Status](#intelligence-features-status)
6. [n8n Workflow Patterns](#n8n-workflow-patterns)
7. [Error Handling & Retry Logic](#error-handling--retry-logic)
8. [Performance & Concurrency](#performance--concurrency)
9. [Output Artifacts](#output-artifacts)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

### What is AI-EWG?
AI-EWG (AI-Enhanced Web Generator) is a video processing pipeline that:
- Transcribes video/audio files using Whisper
- Enriches content with AI analysis (Ollama)
- Performs speaker diarization
- Generates SEO-optimized HTML pages
- **[Phase 2]** Entity extraction, disambiguation, and guest proficiency scoring

### Technology Stack
- **Backend:** Python 3.11+ with FastAPI
- **Database:** SQLite (WAL mode) with connection pooling
- **AI Models:** 
  - Whisper (transcription)
  - Ollama (LLM analysis)
  - PyAnnote (diarization)
- **API Server:** Uvicorn with single-worker mode
- **Output:** Static HTML + JSON metadata

---

## API Architecture

### Base Configuration
```
Protocol: HTTP
Default Host: http://localhost:8000
Content-Type: application/json
Authentication: None (internal network only)
```

### Server Startup
```powershell
# Start API server
.\start-api-server.ps1

# Or manually
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --workers 1
```

**⚠️ CRITICAL:** Server MUST run with `--workers 1` due to SQLite locking constraints.

---

## Available Endpoints

### 1. Health & Status Endpoints

#### `GET /health`
Check if API server is running and healthy.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-23T17:00:00",
  "database_connected": true,
  "orchestrator_ready": true
}
```

**n8n Node:** HTTP Request
- Method: GET
- URL: `{{ $json.apiUrl }}/health`
- Response: JSON

---

#### `GET /status`
Get pipeline processing statistics.

**Response:**
```json
{
  "total_episodes": 150,
  "by_stage": {
    "discovered": 10,
    "transcribed": 5,
    "enriched": 3,
    "rendered": 132
  },
  "processing_active": true,
  "last_updated": "2025-10-23T17:00:00"
}
```

---

### 2. Episode Discovery

#### `POST /episodes/discover`
Scan configured directories for new video files.

**Request:** No body required

**Response:**
```json
{
  "discovered": 5,
  "episodes": [
    {
      "episode_id": "newsroom-2024-oss096",
      "video_path": "data/videos/newsroom/OSS096.mp4",
      "show_name": "newsroom",
      "status": "discovered"
    }
  ]
}
```

**n8n Usage:**
```
Trigger: Schedule (daily at 2 AM)
→ HTTP Request: POST /episodes/discover
→ Split In Batches (batch size: 1)
→ Process each episode
```

---

### 3. Episode Processing (PRIMARY ENDPOINT)

#### `POST /episodes/process`
Process a single episode through the entire pipeline.

**Request Body:**
```json
{
  "episode_id": "newsroom-2024-oss096",
  "force_reprocess": false,
  "stages": ["transcription", "enrichment", "rendering"]
}
```

**Parameters:**
- `episode_id` (required): Episode identifier
- `force_reprocess` (optional, default: false): Reprocess even if already completed
- `stages` (optional): Array of stages to run. If omitted, runs all stages.

**Response (Success):**
```json
{
  "success": true,
  "episode_id": "newsroom-2024-oss096",
  "stage": "rendered",
  "message": "Episode processed successfully",
  "outputs": {
    "rendered_html": "<!DOCTYPE html>...",
    "html_path": "data/public/shows/newsroom/newsroom-2024-oss096/index.html",
    "transcript_path": "data/transcripts/newsroom-2024-oss096.txt",
    "vtt_path": "data/transcripts/newsroom-2024-oss096.vtt"
  },
  "processing_time_seconds": 245.3,
  "timestamp": "2025-10-23T17:00:00"
}
```

**Response (Error):**
```json
{
  "success": false,
  "episode_id": "newsroom-2024-oss096",
  "stage": "transcription",
  "error": "Audio file not found",
  "timestamp": "2025-10-23T17:00:00"
}
```

**n8n Implementation:**
```javascript
// HTTP Request Node Configuration
Method: POST
URL: {{ $json.apiUrl }}/episodes/process
Body: JSON
{
  "episode_id": "{{ $json.episode_id }}",
  "force_reprocess": false
}

// Response Handling
Success: outputs.rendered_html contains full HTML
Error: Check success field, log error message
```

---

#### `POST /episodes/process-async`
Process episode asynchronously (returns immediately with job ID).

**Request Body:** Same as `/episodes/process`

**Response:**
```json
{
  "job_id": "job-abc123",
  "episode_id": "newsroom-2024-oss096",
  "status": "queued",
  "created_at": "2025-10-23T17:00:00"
}
```

**Poll Status:**
```
GET /jobs/{job_id}
```

---

#### `POST /episodes/batch`
Process multiple episodes in batch.

**Request Body:**
```json
{
  "episode_ids": ["newsroom-2024-oss096", "newsroom-2024-ci166"],
  "force_reprocess": false,
  "concurrency": 1
}
```

**⚠️ WARNING:** Keep `concurrency: 1` to avoid SQLite locking issues.

---

### 4. Episode Status

#### `GET /episodes/{episode_id}`
Get current status of an episode.

**Response:**
```json
{
  "episode_id": "newsroom-2024-oss096",
  "stage": "rendered",
  "status": "completed",
  "metadata": {
    "title": "OSS096",
    "show_name": "Second Street",
    "duration_seconds": 1313
  },
  "last_updated": "2025-10-23T17:00:00"
}
```

---

#### `GET /episodes`
List all episodes with optional filtering.

**Query Parameters:**
- `stage` (optional): Filter by stage (discovered, transcribed, enriched, rendered)
- `limit` (optional, default: 20): Max results

**Response:**
```json
{
  "episodes": [
    {
      "episode_id": "newsroom-2024-oss096",
      "stage": "rendered",
      "status": "completed"
    }
  ],
  "total": 150,
  "returned": 20
}
```

---

## Processing Pipeline Stages

### Stage Flow
```
1. DISCOVERED → 2. TRANSCRIBED → 3. ENRICHED → 4. RENDERED
```

### Stage Details

#### 1. **DISCOVERED**
- Video file detected in source directory
- Metadata extracted (filename, duration, size)
- Episode ID generated
- **Duration:** Instant

#### 2. **TRANSCRIBED**
- Audio extracted from video
- Whisper transcription (word-level timestamps)
- VTT caption file generated
- **Duration:** ~2-5 minutes per hour of video
- **Output:** `data/transcripts/{episode_id}.txt`, `.vtt`

#### 3. **ENRICHED**
- AI analysis via Ollama:
  - Executive summary (2-3 paragraphs)
  - Key takeaways (5-7 bullet points)
  - Deep analysis (themes, implications)
  - Topics/keywords (8-10 tags)
- Speaker diarization (who spoke when)
- **[Phase 2]** Entity extraction, disambiguation, proficiency scoring
- **Duration:** ~30-60 seconds
- **Output:** `data/enriched/{episode_id}.json`

#### 4. **RENDERED**
- HTML page generation with AI enhancements
- SEO meta tags + JSON-LD schema
- Responsive CSS styling
- **Duration:** <1 second
- **Output:** `data/public/shows/{show}/{episode_id}/index.html`

---

## Intelligence Features Status

### ✅ Fully Implemented (Phase 1 + Phase 2)

#### Phase 1: AI Analysis & Diarization
1. **AI Analysis** (Ollama)
   - Executive summaries
   - Key takeaways
   - Deep analysis
   - Topic extraction
   - Show name extraction
   - Host name extraction

2. **Speaker Diarization** (PyAnnote)
   - Speaker identification
   - Timestamp segments
   - Quality validation

3. **HTML Rendering**
   - AI Enhanced badge
   - Executive summary section
   - Key takeaways list
   - Topics covered tags
   - Deep analysis section
   - SEO optimization
   - JSON-LD schema

#### Phase 2: Intelligence Chain (NOW INTEGRATED ✅)
1. **Entity Extraction**
   - People identification from transcript
   - Organization extraction
   - Confidence scoring
   - Journalistic relevance assessment

2. **Disambiguation**
   - Wikidata matching
   - Authority verification
   - Biographical data retrieval
   - Multiple candidate evaluation

3. **Guest Proficiency Scoring**
   - Credibility badges (Verified Expert, Identified Contributor, Guest)
   - Job titles and affiliations
   - Authority scoring (high/medium/low)
   - Detailed score breakdown
   - Editorial reasoning

**Status:** ✅ **FULLY INTEGRATED** - Intelligence chain v2 now runs automatically during enrichment stage.

**Output:** HTML now includes populated "Guest Credentials" section with:
```json
"proficiency_scores": {
  "scored_people": [
    {
      "name": "Peter Copeland",
      "credibilityBadge": "Verified Expert",
      "job_title": "Deputy Director of Domestic Policy",
      "affiliation": "Macdonald Laurier Institute",
      "proficiencyScore": 0.85,
      "authorityLevel": "high",
      "reasoning": "..."
    }
  ]
}
```

---

## n8n Workflow Patterns

### Pattern 1: Manual Folder Selection with CSV Output (RECOMMENDED)
**Use Case:** Process videos from a specific folder, check for HTML generation, save results to CSV

```
Manual Trigger
→ Set Folder Config (configure paths)
   - inputFolder: /data/test_videos/newsroom/2024
   - apiUrl: http://localhost:8000
   - outputFolderHTML: /data/public
   - outputFolderCSV: /data/metadata.csv
→ HTTP: POST /episodes/discover (scan for episodes)
→ Execute Command: List MP4 Files (find *.mp4 in folder)
→ Code: Parse Files & Match Episodes (assign IDs)
→ Split In Batches (size: 1, concurrency: 1)
   → HTTP: POST /episodes/process (process each episode)
   → Code: Parse Result & Extract Metadata
   → IF: HTML Available?
      TRUE:
         → Write Binary File (save HTML to disk)
         → Code: Format CSV Data
         → Append to CSV
      FALSE:
         → Code: Format CSV Data (without HTML path)
         → Append to CSV
   → Code: Create Summary (log results)
```

**Key Features:**
- Manual folder selection via Set node
- Automatic episode ID assignment
- HTML generation check
- CSV output with metadata
- Error handling with retry logic
- Detailed logging

**Implementation:** See `n8n_workflows/V-html-corrected_workflow.json`

---

### Pattern 2: Simple Sequential Processing
```
Trigger (Manual/Schedule)
→ HTTP: POST /episodes/discover
→ Split In Batches (size: 1)
→ HTTP: POST /episodes/process
→ Code: Extract HTML from response
→ Write Binary File (HTML to disk)
```

### Pattern 3: Async Processing with Polling
```
Trigger
→ HTTP: POST /episodes/process-async
→ Wait 30 seconds
→ HTTP: GET /jobs/{job_id}
→ IF: status == "completed"
   → Extract outputs
   ELSE: Loop back to Wait
```

### Pattern 4: Batch Processing with Error Handling
```
Trigger
→ HTTP: POST /episodes/discover
→ Split In Batches (size: 1, concurrency: 1)
→ HTTP: POST /episodes/process
   → Retry on Error (3 attempts, exponential backoff)
→ IF: success == true
   → Write HTML
   → Send success notification
   ELSE:
   → Log error
   → Send failure notification
```

### Pattern 5: Status Monitoring
```
Schedule Trigger (every 5 minutes)
→ HTTP: GET /status
→ Store in variable
→ Compare with previous status
→ IF: changes detected
   → Send notification
```

---

## Detailed Workflow Implementation Guide

### Your Workflow Requirements

**Objective:** 
1. Manually choose a folder
2. Scan for episodes and assign IDs
3. Check if HTML has been generated
4. Save results as CSV

### Step-by-Step Implementation

#### Node 1: Manual Trigger
```
Type: Manual Trigger
Purpose: Start workflow on demand
```

#### Node 2: Set Folder Config
```
Type: Set (Edit Fields)
Purpose: Configure all paths in one place

Assignments:
- inputFolder: "/data/test_videos/newsroom/2024"
  (Change this to your target folder)
- apiUrl: "http://localhost:8000"
  (Or http://host.docker.internal:8000 if in Docker)
- outputFolderHTML: "/data/public"
  (Where HTML files will be saved)
- outputFolderCSV: "/data/metadata.csv"
  (CSV file path for results)
```

**To Change Folder:** Simply edit the `inputFolder` value before running.

#### Node 3: Discover Episodes
```
Type: HTTP Request
Method: POST
URL: {{ $json.apiUrl }}/episodes/discover
Headers: Content-Type: application/json
Timeout: 60000ms

Purpose: Tell the API to scan configured directories
```

#### Node 4: List MP4 Files
```
Type: Execute Command
Command: find {{ $('Set Folder Config').first().json.inputFolder }} -maxdepth 1 -name '*.mp4' -type f 2>/dev/null | sort || echo ""

Purpose: Get actual list of .mp4 files in the chosen folder
```

#### Node 5: Parse Files & Match Episodes
```
Type: Code (JavaScript)
Purpose: 
- Parse file list from shell output
- Generate episode IDs from filenames
- Match with discovered episodes
- Create items for batch processing

Output per file:
{
  video_path: "/data/test_videos/newsroom/2024/OSS096.mp4",
  filename: "OSS096.mp4",
  episode_id: "newsroom-2024-oss096",
  show_hint: "newsroom",
  discovered: true,
  apiUrl: "http://localhost:8000",
  outputFolderHTML: "/data/public",
  outputFolderCSV: "/data/metadata.csv"
}
```

**Episode ID Generation:**
- Filename: `OSS096.mp4`
- Converted to: `oss096` (lowercase, special chars to hyphens)
- Combined with show: `newsroom-2024-oss096`

#### Node 6: Split In Batches
```
Type: Split In Batches
Batch Size: 1
Options:
  - Reset: false

Purpose: Process one episode at a time (prevents SQLite locking)
```

#### Node 7: Process Episode
```
Type: HTTP Request
Method: POST
URL: {{ $json.apiUrl }}/episodes/process
Headers: Content-Type: application/json
Body (JSON):
{
  "episode_id": "{{ $json.episode_id }}",
  "target_stage": "rendered",
  "force_reprocess": false
}

Options:
  - Timeout: 3600000ms (1 hour)
  - Retry: 2 attempts, 5000ms interval

Purpose: Run full pipeline (transcription → enrichment → rendering)
```

**Response includes:**
- `success`: true/false
- `stage`: Current stage (rendered if complete)
- `outputs.rendered_html`: Full HTML content
- `metadata`: Episode metadata (title, show, host, etc.)
- `duration`: Processing time in seconds

#### Node 8: Merge Process Result
```
Type: Set (Edit Fields)
Purpose: Preserve original episode data + API response

Preserves:
- episode_id
- filename
- video_path
- apiUrl
- outputFolderHTML
- outputFolderCSV
- processResult (full API response)
```

#### Node 9: Parse Result & Extract Metadata
```
Type: Code (JavaScript)
Purpose: 
- Extract metadata from API response
- Convert HTML text to binary data
- Prepare for file writing and CSV export

Key Logic:
1. Extract metadata from response.metadata
2. Check if HTML exists in response.outputs.rendered_html
3. Convert HTML to base64 binary for Write Binary File node
4. Build complete output object

Output:
{
  filename: "OSS096.mp4",
  episode_id: "newsroom-2024-oss096",
  success: true,
  stage: "rendered",
  show_name: "Second Street",
  title: "OSS096",
  host: "Unknown",
  html_output_path: "/data/public/newsroom-2024-oss096.html",
  rendered_html_content: "<!DOCTYPE html>...",
  processed_at: "2025-10-23T17:00:00Z"
}

Binary:
{
  html_binary: {
    data: "base64_encoded_html",
    mimeType: "text/html",
    fileName: "newsroom-2024-oss096.html"
  }
}
```

#### Node 10: Check if HTML Available
```
Type: IF (Conditional)
Conditions (AND):
  1. html_output_path is not empty
  2. rendered_html_content is not empty

TRUE branch → Write HTML to Disk
FALSE branch → Skip to CSV (HTML not generated)
```

#### Node 11: Write HTML to Disk (TRUE branch)
```
Type: Write Binary File
Operation: write
File Name: {{ $json.html_output_path }}
Binary Data: true
Binary Property Name: html_binary
Options:
  - Make Directories: true

Purpose: Save HTML file to disk
```

#### Node 12: Format CSV Data (Both branches)
```
Type: Code (JavaScript)
Purpose: Format episode data as CSV row

CSV Columns:
- filename
- episode_id
- show_name
- title
- host
- topic
- stage
- duration
- success
- processed_at
- html_output_path
- error

Output:
{
  csv_header: "filename,episode_id,show_name,...",
  csv_row: "OSS096.mp4,newsroom-2024-oss096,Second Street,..."
}
```

#### Node 13: Append to CSV
```
Type: Read/Write Files from Disk
Operation: append
Mode: fileContent
File Path: {{ $json.outputFolderCSV }}
File Content: {{ $json.csv_row }}\n
Options:
  - Create Folders: true
  - Continue On Fail: true

Purpose: Append CSV row to metadata file
```

**CSV Output Example:**
```csv
filename,episode_id,show_name,title,host,topic,stage,duration,success,processed_at,html_output_path,error
OSS096.mp4,newsroom-2024-oss096,Second Street,OSS096,Unknown,crime severity index,rendered,245,true,2025-10-23T17:00:00,/data/public/newsroom-2024-oss096.html,
CI166.mp4,newsroom-2024-ci166,Second Street,CI166,Unknown,Unknown,rendered,198,true,2025-10-23T17:05:00,/data/public/newsroom-2024-ci166.html,
```

#### Node 14: Create Summary
```
Type: Code (JavaScript)
Purpose: Log processing results to console

Output:
============================================================
Processing Complete: OSS096.mp4
============================================================
Status: ✅ SUCCESS
Episode ID: newsroom-2024-oss096
Show: Second Street
Title: OSS096
Stage: rendered
Duration: 245s
HTML: Yes
============================================================
```

### How to Use This Workflow

#### 1. Initial Setup
```powershell
# Start API server
.\start-api-server.ps1

# Verify it's running
curl http://localhost:8000/health
```

#### 2. Configure Folder
- Open n8n workflow
- Click on "Set Folder Config" node
- Edit `inputFolder` to your target folder path
- Example: `/data/test_videos/newsroom/2024`

#### 3. Run Workflow
- Click "Execute Workflow" button
- Watch progress in execution log
- Check CSV file for results

#### 4. Verify Results
```powershell
# Check CSV output
cat /data/metadata.csv

# Check HTML files
ls /data/public/*.html

# Check specific episode
cat /data/public/newsroom-2024-oss096.html
```

### Workflow Behavior

**If HTML is Generated:**
1. Episode processed successfully
2. HTML saved to disk at `outputFolderHTML/{episode_id}.html`
3. CSV row includes `html_output_path`
4. Success status in CSV

**If HTML is NOT Generated:**
1. Episode may have failed at some stage
2. No HTML file written
3. CSV row has empty `html_output_path`
4. Error message in CSV (if available)

**Episode ID Assignment:**
- Automatically generated from filename
- Format: `{show}-{year}-{identifier}`
- Example: `newsroom-2024-oss096` from `OSS096.mp4`
- Matched with discovered episodes if already in database

### Customization Options

#### Change Folder Per Run
Edit the `inputFolder` value in "Set Folder Config" node before each run.

#### Process Specific Files
Modify the "List MP4 Files" command to filter:
```bash
# Only files starting with "OSS"
find ... -name 'OSS*.mp4' ...

# Only files from specific date
find ... -name '*2024*.mp4' ...
```

#### Change CSV Columns
Edit the "Format CSV Data" node to add/remove columns:
```javascript
const csvRow = [
  metadata.filename,
  metadata.episode_id,
  // Add your custom fields here
  metadata.custom_field,
].join(',');
```

#### Force Reprocessing
Change `force_reprocess: false` to `true` in "Process Episode" node to reprocess already-completed episodes.

---

## Error Handling & Retry Logic

### Common Errors

#### 1. **Database Locked**
```json
{
  "detail": "database is locked"
}
```
**Cause:** Multiple concurrent requests  
**Solution:** 
- Use `concurrency: 1` in n8n Split In Batches
- Add Wait nodes between requests (2-5 seconds)
- Enable Retry on Error (3 attempts, exponential backoff)

#### 2. **Episode Not Found**
```json
{
  "detail": "Episode not found: newsroom-2024-xyz"
}
```
**Cause:** Invalid episode_id  
**Solution:** Run `/episodes/discover` first

#### 3. **Processing Failed**
```json
{
  "success": false,
  "error": "Transcription failed: Audio file corrupt"
}
```
**Cause:** Corrupt media file or missing dependencies  
**Solution:** Check logs, verify file integrity

### n8n Retry Configuration
```javascript
// HTTP Request Node Settings
Retry On Fail: true
Max Tries: 3
Wait Between Tries: 2000ms (exponential)
```

---

## Performance & Concurrency

### SQLite Constraints
- **Max Concurrency:** 1 writer at a time
- **Journal Mode:** WAL (Write-Ahead Logging)
- **Busy Timeout:** 10 seconds
- **Connection Pool:** NullPool (no pooling)

### n8n Best Practices
1. **Use Split In Batches** with `batchSize: 1`
2. **Add Wait Nodes** (2-5 seconds) between API calls
3. **Enable Retry Logic** (3 attempts, exponential backoff)
4. **Monitor Queue Depth** - don't queue >10 episodes
5. **Avoid Parallel Execution** - use sequential workflows

### Processing Times (Approximate)
- Discovery: <1 second per episode
- Transcription: 2-5 minutes per hour of video
- Enrichment (Phase 1 + Phase 2): 2-4 minutes
  - Ollama AI analysis: 30-60 seconds
  - Intelligence Chain V2: 1-3 minutes (entity extraction, disambiguation, scoring)
- Rendering: <1 second
- **Total:** ~5-10 minutes per 1-hour episode (with full intelligence features)

---

## Output Artifacts

### File Structure
```
data/
├── audio/
│   └── {episode_id}.wav          # Extracted audio
├── transcripts/
│   ├── {episode_id}.txt          # Plain text transcript
│   └── {episode_id}.vtt          # WebVTT captions
├── enriched/
│   └── {episode_id}.json         # AI analysis + diarization
├── public/
│   └── shows/
│       └── {show_slug}/
│           └── {episode_id}/
│               └── index.html    # Final HTML page
└── meta/
    └── {episode_id}.json         # Episode metadata
```

### HTML Output Structure
The rendered HTML includes:
- **Header:** Show name, episode title, host name (if extracted)
- **AI Enhanced Badge:** Visual indicator
- **Executive Summary:** 2-3 paragraph overview
- **Key Takeaways:** Bulleted list (5-7 items)
- **Topics Covered:** Tag cloud
- **Deep Analysis:** Detailed analysis section
- **Guest Credentials:** [Empty in Phase 1] - Will show verified experts
- **Video Section:** Placeholder + download links
- **Transcript:** [Optional] Full transcript with timestamps
- **Footer:** Generation timestamp

### Accessing HTML in n8n
```javascript
// From /episodes/process response
const html = $json.outputs.rendered_html;
const htmlPath = $json.outputs.html_path;

// Convert to binary for Write Binary File node
const binary = {
  html_binary: {
    data: Buffer.from(html, 'utf8').toString('base64'),
    mimeType: 'text/html',
    fileName: `${$json.episode_id}.html`
  }
};

return [{ json: $json, binary: binary }];
```

---

## Troubleshooting

### Issue: "Database is locked"
**Symptoms:** 500 errors, timeout errors  
**Solutions:**
1. Verify server running with `--workers 1`
2. Add Wait nodes in workflow (2-5 seconds)
3. Reduce concurrency to 1
4. Check Windows Defender exclusions for `data/` folder
5. Verify database is on local NTFS (not network share)

### Issue: "Episode not found"
**Symptoms:** 404 errors  
**Solutions:**
1. Run `/episodes/discover` first
2. Verify episode_id format: `{show}-{year}-{identifier}`
3. Check video files exist in source directories

### Issue: "Transcription failed"
**Symptoms:** Processing stops at transcription stage  
**Solutions:**
1. Verify Whisper model installed
2. Check audio file is valid (not corrupt)
3. Ensure sufficient disk space
4. Check logs: `logs/pipeline.log`

### Issue: "Ollama connection refused"
**Symptoms:** Enrichment stage fails  
**Solutions:**
1. Start Ollama: `ollama serve`
2. Verify model pulled: `ollama pull llama3.1:latest`
3. Check Ollama URL in config: `http://localhost:11434`

### Issue: "HTML missing guest credentials"
**Symptoms:** Guest section empty in HTML  
**Solutions:**
1. Verify Intelligence Chain V2 is enabled in enrichment stage
2. Check logs for "Intelligence Chain V2 completed successfully"
3. Verify utility scripts exist: `utils/extract_entities.py`, `utils/disambiguate.py`, `utils/score_people.py`
4. Check enrichment JSON has `proficiency_scores.scored_people` populated
5. Ensure Ollama is running for entity extraction (LLM method)
6. If using spaCy fallback, verify spaCy model installed: `python -m spacy download en_core_web_lg`

**Note:** As of latest version, Phase 2 is fully integrated and should populate guest credentials automatically.

---

## Configuration Reference

### Environment Variables
```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1  # MUST be 1

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest

# Whisper
WHISPER_MODEL=base
WHISPER_DEVICE=cuda  # or cpu

# Diarization
DIARIZATION_DEVICE=cuda  # or cpu
NUM_SPEAKERS=2  # or 0 for auto-detect
HF_TOKEN=your_huggingface_token
```

### Config File
Location: `config/pipeline_config.yaml`

```yaml
models:
  whisper: "base"
  llm: "llama3.1:latest"
  diarization_device: "cuda"
  num_speakers: 2

ollama_url: "http://localhost:11434"

thresholds:
  confidence_min: 0.7
  entity_confidence: 0.6
  expert_score: 0.7
  publish_score: 0.5

output:
  transcripts: "data/transcripts"
  enriched: "data/enriched"
  web_artifacts: "data/public"
```

---

## Quick Start Checklist

### Prerequisites
- [ ] Python 3.11+ installed
- [ ] Ollama installed and running (`ollama serve`)
- [ ] Whisper model downloaded
- [ ] HuggingFace token configured (for diarization)
- [ ] Video files in source directories

### Server Setup
- [ ] Start API server: `.\start-api-server.ps1`
- [ ] Verify health: `GET http://localhost:8000/health`
- [ ] Check status: `GET http://localhost:8000/status`

### n8n Workflow Setup (Using V-html-corrected_workflow.json)
- [ ] Import workflow: `n8n_workflows/V-html-corrected_workflow.json`
- [ ] Open "Set Folder Config" node
- [ ] Edit `inputFolder` to your video folder path
- [ ] Edit `apiUrl` if not using `http://localhost:8000`
- [ ] Edit `outputFolderHTML` for HTML output location
- [ ] Edit `outputFolderCSV` for CSV output file path
- [ ] Save workflow

### Testing
- [ ] Click "Execute Workflow" in n8n
- [ ] Watch execution progress in n8n UI
- [ ] Check console logs for "Processing Complete" messages
- [ ] Verify CSV file created: `cat /data/metadata.csv`
- [ ] Verify HTML files created: `ls /data/public/*.html`
- [ ] Open HTML in browser to validate rendering
- [ ] Check for AI enhancements (summary, takeaways, topics)

### Workflow Validation
```powershell
# 1. Check API is running
curl http://localhost:8000/health

# 2. Check video folder has files
ls /data/test_videos/newsroom/2024/*.mp4

# 3. Run workflow in n8n (click Execute)

# 4. Verify outputs
cat /data/metadata.csv
ls /data/public/*.html

# 5. Check specific episode
cat /data/public/newsroom-2024-oss096.html | grep "AI ENHANCED"
```

---

## Support & Resources

### Documentation
- Main README: `README.md`
- SQLite Locking Fixes: `docs/SQLITE_LOCKING_FIXES.md`
- PostgreSQL Migration: `docs/POSTGRES_MIGRATION.md`

### Logs
- API Server: `logs/api.log`
- Pipeline: `logs/pipeline.log`
- Errors: `logs/errors.log`

### Contact
For issues or questions, check logs first, then review this guide.

---

**Document Version:** 1.0  
**Last Updated:** October 23, 2025  
**Status:** Phase 1 Complete, Phase 2 Pending Integration
