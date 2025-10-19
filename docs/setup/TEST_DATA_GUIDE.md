# Test Data Setup Guide

This guide explains how to set up test data for the AI Video Processing Pipeline.

## Overview

The pipeline processes video files and generates transcripts, metadata, and web artifacts. Test videos are **not included in the repository** to keep it lightweight.

## Directory Structure

```
test_videos/
└── newsroom/
    └── 2024/
        └── [your test video files here]
```

## Setting Up Test Data

### Option 1: Use Your Own Videos

1. Create the test directory structure:
   ```powershell
   New-Item -ItemType Directory -Path "test_videos\newsroom\2024" -Force
   ```

2. Copy your test video files:
   - Supported formats: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`
   - Recommended: Short videos (1-5 minutes) for faster testing
   - Example naming: `newsroom-2024-episode001.mp4`

3. Update `config/system.yaml` or `config/pipeline.yaml` to point to your test directory

### Option 2: Download Sample Videos

For testing purposes, you can use:

1. **Creative Commons Videos:**
   - [Internet Archive](https://archive.org/details/movies)
   - [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Videos)
   - [Pexels Videos](https://www.pexels.com/videos/)

2. **Generate Test Content:**
   - Use screen recording software to create sample interview-style videos
   - Record short 2-3 minute conversations with multiple speakers

### Option 3: Sample News Content

If you're testing with news/interview content:

1. Download Creative Commons licensed news segments
2. Ensure proper attribution in your test documentation
3. Do not commit copyrighted content to the repository

## Verification

After setting up test data, verify with:

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run discovery script
python .\scripts\discover_videos.py

# Or run the full processing pipeline
python discover_now.py
```

## Expected Output

Once test videos are in place, the pipeline will generate:

- `data/audio/` - Extracted audio tracks
- `data/transcripts/` - VTT and TXT transcripts
- `data/enriched/` - AI-enriched metadata JSON
- `data/public/` - Web-ready HTML pages
- `logs/` - Processing audit trails

## Notes

- Test videos should have **clear audio** with distinguishable speakers for best diarization results
- Minimum recommended length: **30 seconds**
- Maximum recommended for testing: **5 minutes** (to avoid long processing times)
- Files with poor audio quality may produce less accurate transcripts

## Troubleshooting

If videos aren't being discovered:

1. Check file extensions match the configured patterns
2. Verify directory permissions
3. Review `config/system.yaml` or `config/pipeline.yaml` source paths
4. Check logs in `logs/` directory for errors

For more information, see:
- [N8N_TESTING_GUIDE.md](./N8N_TESTING_GUIDE.md)
- [N8N_FOLDER_SETUP_GUIDE.md](./N8N_FOLDER_SETUP_GUIDE.md)
