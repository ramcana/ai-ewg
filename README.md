# TNF Video Library Processing Pipeline

Transform your existing video library into web-ready content with full metadata, transcription, and AI-enhanced enrichment. This is **Part 1** of a two-part system that processes videos from discovery through web artifact generation.

## 🚀 Quick Start

### Start API Server
```powershell
cd D:\n8n\ai-ewg
.\venv\Scripts\Activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### Run n8n Workflow
1. Import `n8n_workflows/video_processing_FIXED_v3.json`
2. Set folder path: `/data/test_videos/newsroom/2024`
3. Execute workflow

**📚 Documentation:**
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Complete setup guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Common commands
- **[docs/DEDUPLICATION_SYSTEM.md](docs/DEDUPLICATION_SYSTEM.md)** - Deduplication features

---

## Overview

This pipeline takes videos from multiple sources (local drives, NAS shares, external drives) and generates:

- High-quality transcripts with speaker identification
- AI-enriched guest profiles with proficiency scores and verification badges
- Web-ready HTML pages with embedded structured data (JSON-LD)
- Complete metadata for future publishing and distribution

## Key Features

✅ **Content-Based Deduplication** - SHA256 hashing prevents duplicate processing  
✅ **Auto-Discovery** - Scans configured folders for videos  
✅ **Automatic Backups** - Database backed up every 24 hours  
✅ **Resume Processing** - Continue from any stage  
✅ **n8n Integration** - Visual workflow automation  
✅ **Error Handling** - Graceful failure recovery

## Processing Stages

1. **Discovered** - Video file found and registered
2. **Prepped** - Audio extracted, file validated
3. **Transcribed** - Speech-to-text with Whisper
4. **Enriched** - AI analysis, entity extraction, speaker identification
5. **Rendered** - HTML pages and web artifacts generated

## Project Structure

```
├── config/
│   ├── system.yaml      # Main configuration
│   └── .env            # API keys and secrets
├── utils/              # Core AI processing utilities
│   ├── diarize.py      # Speaker identification
│   ├── extract_entities.py  # Entity extraction
│   ├── disambiguate.py # Guest enrichment via Wikidata/Wikipedia
│   └── score_people.py # Proficiency scoring and badge assignment
├── scripts/            # Pipeline orchestration
├── data/               # Generated during processing
│   ├── staging/        # Temporary file copies
│   ├── transcripts/    # TXT and VTT files
│   ├── public/         # Web-ready output
│   └── meta/           # Episode JSON metadata
└── PART1_PROCESSING_PLAN.md  # Detailed implementation plan
```

## Output Structure

Each processed episode generates:

**Web Page** (`data/public/shows/{show}/{episode}/index.html`)

- Episode title, date, and summary
- Host and guest profiles with verification badges
- Speaker-labeled transcript sections
- Video embed and download links
- Embedded JSON-LD structured data

**Metadata** (`data/meta/{episode_id}.json`)

- Complete episode object with all enrichment data
- Guest profiles with proficiency scores and reasoning
- Diarized transcript segments
- Topics, tags, and related content

**Transcripts** (`data/transcripts/`)

- Plain text transcripts
- VTT caption files with timestamps

## Configuration

Edit `config/pipeline.yaml`:

```yaml
sources:
  - path: "/data/test_videos/newsroom/2024"
    include: ["*.mp4", "*.mkv"]
    enabled: true

database:
  path: "data/pipeline.db"
  backup_enabled: true
  backup_interval_hours: 24
```

## API Documentation

When API server is running: http://localhost:8000/docs

## Development

```powershell
# Run tests
pytest

# Check code
pylint src/

# Format code
black src/
```

See `docs/architecture/` for system design details.
