# Synchronous Video Processing Workflow

## Overview

This n8n workflow provides a **synchronous, sequential** approach to video processing. It discovers `.mp4` files from a folder, processes each one through your AI pipeline, and saves the results (HTML + metadata CSV).

## Features

✅ **Synchronous Processing** - Waits for each video to complete before moving to the next  
✅ **Automatic Discovery** - Finds all `.mp4` files in configured folder  
✅ **Full Pipeline Integration** - Uses `/episodes/discover` and `/episodes/process` APIs  
✅ **HTML Output** - Saves rendered HTML for each episode  
✅ **CSV Metadata** - Appends processing results to a CSV file  
✅ **Error Handling** - Captures and logs processing errors  
✅ **PowerShell Compatible** - Uses PowerShell commands for Windows environments

## Workflow Structure

```
Manual Trigger
    ↓
Set Folder Config (Define paths)
    ↓
List MP4 Files (PowerShell)
    ↓
Parse File List (Code)
    ↓
Prepare Episode Data (Code)
    ↓
Discover Episodes (POST /episodes/discover)
    ↓
Extract Episode ID (Code)
    ↓
Process Episode (POST /episodes/process) [WAITS FOR COMPLETION]
    ↓
Get Episode Details (GET /episodes/{id})
    ↓
Parse Result & Extract Metadata (Code)
    ↓
Check if HTML Available (IF)
    ↓
├─→ Write HTML to Disk (PowerShell)
    ↓
Format CSV Data (Code)
    ↓
Append to CSV (PowerShell)
    ↓
Create Summary (Code)
```

## Configuration

### Required Settings (Set in "Set Folder Config" node)

| Variable | Description | Example |
|----------|-------------|---------|
| `input_folder` | Folder containing `.mp4` files to process | `D:\Videos\ToProcess` |
| `api_base_url` | Your API server URL | `http://localhost:8000` |
| `output_folder_html` | Where to save rendered HTML files | `D:\Videos\Processed\HTML` |
| `output_csv` | Path to metadata CSV file | `D:\Videos\Processed\metadata.csv` |

### API Endpoints Used

1. **POST /episodes/discover** - Discovers video files and creates episode entries
2. **POST /episodes/process** - Processes episode through full pipeline (transcription → entities → disambiguation → rendering)
3. **GET /episodes/{episode_id}** - Retrieves episode details and rendered output

## Installation

### 1. Import Workflow

1. Open n8n
2. Click **"Import from File"**
3. Select `synchronous_video_processing.json`
4. Click **"Import"**

### 2. Configure Paths

1. Open the **"Set Folder Config"** node
2. Update the four path variables to match your environment:
   - `input_folder` - Where your `.mp4` files are located
   - `api_base_url` - Your API server URL (default: `http://localhost:8000`)
   - `output_folder_html` - Where to save HTML output
   - `output_csv` - Full path to CSV file for metadata

### 3. Ensure API Server is Running

Make sure your FastAPI server is running:

```powershell
# Start the API server
.\start-api-server.ps1

# Or manually:
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## Usage

### Manual Execution

1. Click **"Execute Workflow"** button in n8n
2. The workflow will:
   - List all `.mp4` files in `input_folder`
   - Process each file sequentially
   - Save HTML and metadata for each completed episode
3. Check the execution log for results

### Scheduled Execution

To run automatically on a schedule:

1. Replace **"Manual Trigger"** node with **"Cron"** or **"Schedule Trigger"**
2. Configure schedule (e.g., daily at 2 AM)
3. Activate the workflow

## Output Files

### HTML Files

Location: `{output_folder_html}\{episode_id}.html`

Example: `D:\Videos\Processed\HTML\newsroom-2024-show-ep1.html`

Contains the fully rendered episode page with:
- Transcript with speaker diarization
- Extracted entities (people, organizations, topics)
- Proficiency scores
- Metadata

### CSV Metadata File

Location: `{output_csv}`

Example: `D:\Videos\Processed\metadata.csv`

**CSV Columns:**
```csv
filename,episode_id,show_name,title,host,topic,stage,duration,success,processed_at,html_output_path,error
show_ep1.mp4,newsroom-2024-show-ep1,The Newsroom,Tech Trends,Alice Doe,Technology,rendered,1234,true,2025-10-22T21:30:00Z,D:\Videos\Processed\HTML\newsroom-2024-show-ep1.html,
```

## Processing Stages

The workflow processes videos through these stages:

1. **DISCOVERED** - Video file found and registered
2. **TRANSCRIBED** - Audio transcribed to text
3. **DIARIZED** - Speakers identified and separated
4. **ENTITIES_EXTRACTED** - Named entities extracted (people, orgs, topics)
5. **DISAMBIGUATED** - Entities linked to knowledge base
6. **PROFICIENCY_SCORED** - Speaker proficiency calculated
7. **RENDERED** - Final HTML output generated

## Timeout Settings

- **Discovery**: 30 seconds
- **Processing**: 1 hour (3,600,000 ms)
- **Episode Details**: 10 seconds

Adjust these in the HTTP Request nodes if needed for longer videos.

## Error Handling

If a video fails to process:
- Error is captured in the `error` field
- `success` field set to `false`
- Processing continues with next video
- Check CSV for error details

## Troubleshooting

### "Pipeline orchestrator not available"

**Solution:** Ensure API server is running and accessible

```powershell
# Test API
curl http://localhost:8000/health
```

### "No .mp4 files found"

**Solution:** Check `input_folder` path and ensure it contains `.mp4` files

```powershell
# List files
Get-ChildItem -Path "D:\Videos\ToProcess" -Filter *.mp4
```

### "Permission denied writing HTML/CSV"

**Solution:** Ensure output directories exist and have write permissions

```powershell
# Create directories
New-Item -ItemType Directory -Path "D:\Videos\Processed\HTML" -Force
New-Item -ItemType Directory -Path "D:\Videos\Processed" -Force
```

### Processing takes too long

**Solution:** 
- Check API logs for bottlenecks
- Consider using the async workflow for large batches
- Verify GPU/CPU resources for transcription

## Performance Considerations

### Synchronous Processing

**Pros:**
- Simple and predictable
- Easy to debug
- Immediate feedback per video
- Good for small batches (1-10 videos)

**Cons:**
- Slower for large batches
- No parallelization
- Blocks on each video

### When to Use Async Workflow

Consider the async workflow (`configurable_processing_v2.json`) if:
- Processing 10+ videos at once
- Want parallel processing
- Need background job queue
- Can tolerate delayed results

## Integration with Other Tools

### Google Sheets

Replace **"Append to CSV"** node with **"Google Sheets"** node:

1. Add **Google Sheets** node after **"Format CSV Data"**
2. Configure authentication
3. Select spreadsheet and sheet
4. Map fields from `$json` to columns

### Notion

Replace **"Append to CSV"** node with **"Notion"** node:

1. Add **Notion** node after **"Format CSV Data"**
2. Configure Notion API credentials
3. Select database
4. Map fields to Notion properties

### Slack Notifications

Add **Slack** node after **"Create Summary"**:

1. Add **Slack** node
2. Configure webhook or OAuth
3. Send summary message:
   ```
   {{ $json.status }} - {{ $json.filename }}
   Show: {{ $json.show_name }}
   Duration: {{ $json.duration_seconds }}s
   ```

## Advanced Customization

### Filter by File Pattern

Modify **"List MP4 Files"** PowerShell command:

```powershell
# Only process files matching pattern
Get-ChildItem -Path "{{ $json.input_folder }}" -Filter "show_*.mp4" -File | ...
```

### Process to Different Stage

Modify **"Process Episode"** node body parameter:

```json
{
  "episode_id": "={{ $json.episode_id }}",
  "target_stage": "transcribed",  // Change to: transcribed, diarized, entities_extracted, etc.
  "force_reprocess": false
}
```

### Add Email Notifications

Add **Email** node after **"Create Summary"**:

1. Add **Send Email** node
2. Configure SMTP settings
3. Send processing report

## Workflow Maintenance

### Regular Cleanup

Periodically clean up old files:

```powershell
# Delete HTML files older than 30 days
Get-ChildItem -Path "D:\Videos\Processed\HTML" -Filter *.html | 
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
  Remove-Item
```

### Archive CSV

Rotate CSV file monthly:

```powershell
# Archive current CSV
$date = Get-Date -Format "yyyy-MM"
Move-Item "D:\Videos\Processed\metadata.csv" "D:\Videos\Processed\metadata_$date.csv"
```

## Related Workflows

- **configurable_processing_v2.json** - Async batch processing with job queue
- **video_processing_FIXED_v3.json** - Original async workflow
- **configurable_processing.json** - Legacy configurable workflow

## Support

For issues or questions:
1. Check API logs: `logs/api.log`
2. Check n8n execution logs
3. Review `docs/N8N_TESTING_GUIDE.md`
4. Review `docs/ASYNC_WORKFLOW_GUIDE.md`

## Version History

- **v1.0** (2025-10-22) - Initial synchronous workflow release
