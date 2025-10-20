# TNF Video Library Processing Pipeline

Transform your existing video library into web-ready content with full metadata, transcription, and AI-enhanced enrichment. This is **Part 1** of a two-part system that processes videos from discovery through web artifact generation.

## 🚀 New: CLI-Based Pipeline (v0.2.0)

The pipeline now features a **professional CLI** with SQLite state management, Windows-first design, and n8n integration.

### Quick Start (CLI)

```powershell
# 1. Setup
.\setup_cli.ps1

# 2. Discover videos
ai-ewg discover

# 3. Run pipeline
ai-ewg transcribe
ai-ewg diarize
ai-ewg enrich entities
ai-ewg web build

# 4. Check status
ai-ewg db status
```

**📚 Documentation:**
- **[UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md)** - What's new in v0.2.0
- **[docs/QUICKSTART_CLI.md](docs/QUICKSTART_CLI.md)** - Detailed CLI usage
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Migrate from scripts

---

## Overview

This pipeline takes videos from multiple sources (local drives, NAS shares, external drives) and generates:

- High-quality transcripts with speaker identification
- AI-enriched guest profiles with proficiency scores and verification badges
- Web-ready HTML pages with embedded structured data (JSON-LD)
- Complete metadata for future publishing and distribution

## Quick Start (Legacy Scripts)

1. **Setup Environment**

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Configure Sources**
   Edit `config/system.yaml` to specify your video sources:

   ```yaml
   source_paths:
     - "D:\\Videos\\Newsroom"
     - "E:\\Archive\\Shows"
   file_patterns:
     - "**/*.mp4"
     - "**/*.mkv"
   ```

3. **Run Processing Pipeline**
   ```powershell
   # Legacy approach
   python discover_now.py
   
   # Or use new CLI
   ai-ewg discover
   ```

## Processing Pipeline (10 Stages)

1. **Discovery & Config** - Find videos across all configured sources
2. **Episode Normalization** - Parse filenames into structured episode data
3. **Registry & Deduplication** - Track processing state, skip unchanged files
4. **Media Preparation** - Extract audio, validate files
5. **Transcription** - Generate text and VTT captions using Whisper
6. **Intelligence Chain** - 4-step AI enrichment process:
   - Speaker diarization (`utils/diarize.py`)
   - Entity extraction (`utils/extract_entities.py`)
   - Guest disambiguation (`utils/disambiguate.py`)
   - Proficiency scoring (`utils/score_people.py`)
7. **Editorial Layer** - Generate summaries, key takeaways, and tags
8. **Web Artifacts** - Create HTML pages with embedded JSON-LD
9. **Index Generation** - Build per-show and per-host indices
10. **Reliability & Logging** - Comprehensive error handling and progress tracking

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

## Key Features

**Multi-Source Discovery** - Process videos from local drives, network shares, external drives
**AI-Enhanced Guests** - Automatic guest identification, Wikipedia/Wikidata enrichment, proficiency scoring
**Verification Badges** - "Verified Expert", "Industry Leader", "Academic Authority" based on credentials
**Idempotent Processing** - Skip unchanged files, resume interrupted processing
**Web-Ready Output** - Complete HTML pages with structured data for SEO and accessibility

## Configuration

Key settings in `config/system.yaml`:

- Video source paths and file patterns
- Whisper model size and LLM selection
- Confidence thresholds for entity extraction
- Staging and output directory paths

## Next Steps

This is Part 1 of the system. Part 2 will handle:

- Publishing to live websites
- RSS feed and sitemap generation
- Platform integration (Google, Bing, Apple Podcasts, Perplexity)
- Content distribution and syndication

See `PART1_PROCESSING_PLAN.md` for detailed implementation specifications.
