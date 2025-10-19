# n8n Folder-Based Processing Setup Guide

This guide shows you how to set up folder-based video processing with n8n for your video files in `test_videos\newsroom\2024`.

## 🎯 What This Workflow Does

The folder-based workflow will:

1. **Scan your video folder** (`test_videos\newsroom\2024`)
2. **Generate episode IDs** for each video file (e.g., `newsroom-2024-bb580`)
3. **Process each video** through the complete pipeline:
   - **Discovery**: Register the video in the database
   - **Media Prep**: Extract audio, validate files
   - **Transcription**: Generate transcripts with Whisper
   - **Intelligence**: Speaker diarization, entity extraction, people scoring
   - **Editorial**: Generate summaries, key takeaways, topic tags
   - **Web Artifacts**: Create HTML pages, JSON metadata, search indices

## 📁 Your Video Files

Based on your folder, these episode IDs will be generated:

| Video File          | Generated Episode ID            |
| ------------------- | ------------------------------- |
| BB580.mp4           | `newsroom-2024-bb580`           |
| CI166.mp4           | `newsroom-2024-ci166`           |
| CJ335.mp4           | `newsroom-2024-cj335`           |
| CP557.mp4           | `newsroom-2024-cp557`           |
| EMP140.mp4          | `newsroom-2024-emp140`          |
| FD1307_10-16-25.mp4 | `newsroom-2024-fd1307-10-16-25` |
| FFCSFN2025_01.mp4   | `newsroom-2024-ffcsfn2025-01`   |
| MG096.mp4           | `newsroom-2024-mg096`           |
| OSS096.mp4          | `newsroom-2024-oss096`          |
| SL031.mp4           | `newsroom-2024-sl031`           |

## 🚀 Setup Steps

### Step 1: Import the Workflow

1. Go to n8n: `http://localhost:5678/home/workflows`
2. Click "Import from file"
3. Select `n8n_workflows/folder_based_processing.json`
4. Activate the workflow

### Step 2: Get the Webhook URL

After importing, you'll see a webhook node. The URL will be something like:

```
http://localhost:5678/webhook/process-folder
```

### Step 3: Test the Workflow

#### Option A: Use the Test Script

```bash
python test_folder_processing.py
```

#### Option B: Use curl

```bash
curl -X POST http://localhost:5678/webhook/process-folder \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "test_videos/newsroom/2024",
    "target_stage": "rendered",
    "process_all": true
  }'
```

#### Option C: Use PowerShell

```powershell
$body = @{
    folder_path = "test_videos/newsroom/2024"
    target_stage = "rendered"
    process_all = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5678/webhook/process-folder" -Method Post -Body $body -ContentType "application/json"
```

## 🎛️ Workflow Parameters

When triggering the workflow, you can customize these values:

### Required Parameters:

- **folder_path**: `"test_videos/newsroom/2024"` (your video folder)

### Optional Parameters:

- **target_stage**: Processing level (default: `"rendered"`)
  - `"discovered"` - Just register videos
  - `"prepped"` - Extract audio and validate
  - `"transcribed"` - Generate transcripts
  - `"enriched"` - Add AI intelligence (speakers, entities, etc.)
  - `"rendered"` - Complete processing with web artifacts
- **process_all**: `true` (process all videos in folder)

## 📊 Monitoring Progress

### n8n Interface

- Go to `http://localhost:5678`
- Click "Executions" to see workflow runs
- Watch real-time progress of each video

### API Endpoints

```bash
# Overall pipeline status
curl http://localhost:8000/status

# System health
curl http://localhost:8000/health

# List processed episodes
curl http://localhost:8000/episodes
```

### Expected Processing Time

- **Per video**: 1-3x the video duration
- **10 videos**: Expect 30-90 minutes total (depending on video length and system specs)

## 📂 Expected Outputs

After processing completes, you'll find:

### Transcripts

```
transcripts/
├── newsroom-2024-bb580.vtt
├── newsroom-2024-bb580.txt
├── newsroom-2024-ci166.vtt
└── ...
```

### Web Artifacts

```
web_artifacts/
├── newsroom-2024-bb580/
│   ├── index.html
│   ├── metadata.json
│   └── schema.json
├── newsroom-2024-ci166/
└── ...
```

### Processed Data

```
output/
├── newsroom-2024-bb580/
│   ├── diarization.json
│   ├── entities.json
│   ├── people_scores.json
│   └── editorial.json
└── ...
```

## 🔧 Troubleshooting

### Workflow Fails to Start

1. **Check n8n is running**: `http://localhost:5678`
2. **Check API server is running**: `http://localhost:8000/health`
3. **Verify webhook URL** in the workflow matches your test

### Processing Fails

1. **Check video files are accessible**
2. **Verify FFmpeg is installed** (for audio extraction)
3. **Check system resources** (CPU, memory, disk space)
4. **Look at n8n execution logs** for detailed errors

### No Output Generated

1. **Check processing stage** - use `"rendered"` for complete output
2. **Verify folder permissions** for writing output files
3. **Check API logs** in the terminal running the API server

## 🎉 Success Indicators

You'll know it's working when:

- ✅ n8n workflow executes without errors
- ✅ API status shows processed episodes
- ✅ Transcript files appear in `transcripts/` folder
- ✅ HTML pages appear in `web_artifacts/` folder
- ✅ Each video gets speaker identification and summaries

## 🔄 Re-processing Videos

To re-process videos (e.g., with different settings):

```json
{
  "folder_path": "test_videos/newsroom/2024",
  "target_stage": "rendered",
  "process_all": true,
  "force_reprocess": true
}
```

This will override existing processing and start fresh.
