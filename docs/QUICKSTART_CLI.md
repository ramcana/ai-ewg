# Quick Start: CLI Usage

The new `ai-ewg` CLI provides a streamlined interface for running the video processing pipeline.

## Installation

```powershell
# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt

# Verify installation
ai-ewg version
```

## Basic Usage

### 1. Initialize the Registry Database

```powershell
ai-ewg db init
```

This creates the SQLite registry at `data/registry.db` with all necessary tables.

### 2. Discover Videos

```powershell
# Discover all videos from configured sources
ai-ewg discover

# Discover from specific directory
ai-ewg discover --source "D:\Videos\Newsroom" --pattern "**/*.mp4"

# Dry run (preview without registering)
ai-ewg discover --dry-run
```

### 3. Process Videos Through Pipeline Stages

```powershell
# Stage 2: Normalize metadata
ai-ewg normalize

# Stage 3: Transcribe audio
ai-ewg transcribe --model large-v3 --compute fp16

# Stage 4: Diarize speakers
ai-ewg diarize

# Stage 5: Extract and enrich entities
ai-ewg enrich entities
ai-ewg enrich disambiguate
ai-ewg enrich score

# Stage 9: Build web pages
ai-ewg web build

# Stage 10: Build indices and feeds
ai-ewg index build
```

### 4. Process Specific Episode

```powershell
# Process just one episode through a stage
ai-ewg transcribe --episode newsroom-2024-bb580
ai-ewg web build --episode newsroom-2024-bb580
```

### 5. Check Database Status

```powershell
ai-ewg db status
```

## Configuration

### Using config/system.yaml

Create `config/system.yaml`:

```yaml
# Project paths
project_root: D:\n8n\ai-ewg
data_dir: D:\n8n\ai-ewg\data
config_dir: D:\n8n\ai-ewg\config

# Source discovery
source_paths:
  - D:\Videos\Newsroom
  - E:\Archive\Shows
file_patterns:
  - "**/*.mp4"
  - "**/*.mkv"
exclude_patterns:
  - "**/.*"
  - "**/__*"

# Registry database
registry_db_path: D:\n8n\ai-ewg\data\registry.db

# Logging
log_dir: D:\n8n\ai-ewg\data\logs
log_level: INFO
log_format: json

# Transcription settings
transcription:
  model: large-v3
  compute_type: fp16
  device: auto
  beam_size: 5
  vad_filter: true
  max_concurrent: 1

# Diarization settings
diarization:
  model: pyannote/speaker-diarization-3.1
  min_speakers: null
  max_speakers: null
  hf_token: ${HF_TOKEN}  # Set in .env

# Enrichment settings
enrichment:
  spacy_model: en_core_web_lg
  use_llm: false
  wikidata_enabled: true
  wikipedia_enabled: true
  cache_ttl_days: 30
  requests_per_second: 1.0
  max_retries: 3

# Web generation
web:
  template_dir: templates
  output_dir: data/public
  site_name: AI-EWG
  site_url: https://example.com
  site_description: Educational video archive
  enable_search: true
  enable_rss: true
  enable_sitemap: true

# Performance
max_workers: 4
chunk_size: 1000
```

### Using Environment Variables

Create `.env`:

```env
# Override any setting with AIEWG_ prefix
AIEWG_LOG_LEVEL=DEBUG
AIEWG_TRANSCRIPTION__MODEL=large-v3
AIEWG_DIARIZATION__HF_TOKEN=hf_xxxxxxxxxxxxx
AIEWG_WEB__SITE_URL=https://mysite.com
```

### Using CLI Flags

```powershell
# Specify config file
ai-ewg --config custom-config.yaml discover

# Enable verbose logging
ai-ewg --verbose transcribe
```

## n8n Integration

Each CLI command outputs JSON to stdout for n8n to capture:

```json
{"stage": "discover", "success": true, "count": 42}
```

### Example n8n Workflow Node

**Execute Command** node:

```
Command: ai-ewg
Arguments: transcribe --episode {{ $json.episode_id }}
Working Directory: D:\n8n\ai-ewg
```

Parse the JSON output in the next node to check success and get counts.

## Common Workflows

### Full Pipeline for New Videos

```powershell
ai-ewg discover
ai-ewg normalize
ai-ewg transcribe
ai-ewg diarize
ai-ewg enrich entities
ai-ewg enrich disambiguate
ai-ewg enrich score
ai-ewg web build
ai-ewg index build
```

### Re-process with Force Flag

```powershell
# Force re-transcription of all episodes
ai-ewg transcribe --force

# Force rebuild of web pages
ai-ewg web build --force
```

### Check What Needs Processing

```powershell
# View database stats
ai-ewg db status

# This shows counts by state:
# - NEW: needs normalization
# - NORMALIZED: needs transcription
# - TRANSCRIBED: needs diarization
# - DIARIZED: needs enrichment
# - ENRICHED: needs web rendering
# - RENDERED: complete
```

## Troubleshooting

### Database Locked

If you see "database is locked" errors:

```powershell
# Check for stale connections
ai-ewg db status

# The registry uses WAL mode for better concurrency
# Ensure no other processes are holding locks
```

### Missing Dependencies

```powershell
# Install all dependencies
pip install -r requirements.txt

# For development/testing
pip install -r requirements-dev.txt
```

### Path Issues on Windows

- Always use absolute paths in `config/system.yaml`
- The CLI normalizes paths automatically
- Internal IDs are URL-safe slugs, not raw paths

## Next Steps

- See [ARCHITECTURE.md](./architecture/N8N_ARCHITECTURE_EXPLAINED.md) for pipeline details
- See [N8N_TESTING_GUIDE.md](./setup/N8N_TESTING_GUIDE.md) for testing strategies
- Check `templates/` for customizing HTML output
