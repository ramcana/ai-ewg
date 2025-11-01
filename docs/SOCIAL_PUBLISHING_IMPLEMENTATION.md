# Social Media Publishing System - Implementation Guide

## Overview

The AI-EWG pipeline now includes a comprehensive multi-platform social media publishing system with AI-powered content generation, policy-based transformations, and job tracking.

## Architecture

### Three-Layer System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Analysis & Enrichment            │
│  • Episode metadata extraction                               │
│  • AI-generated summaries, topics, guests                    │
│  • Clip discovery and highlight scoring                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: Policy Engine                    │
│  • Platform-specific rules (YAML configs)                    │
│  • Content validation and transformation                     │
│  • Metadata template application                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: Package Generator                │
│  • Structured output folders                                 │
│  • Video transcoding (aspect ratio, resolution)              │
│  • Metadata file generation                                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Platform Policy Files

**Location:** `config/platforms/*.yaml`

Each platform has a YAML configuration defining:
- Video specifications (aspect ratio, duration, codec, resolution)
- Metadata requirements (title, caption, hashtags)
- Content guidelines and restrictions
- Platform-specific features
- Transformation rules
- AI enhancement settings

**Available Platforms:**
- `youtube.yaml` - 16:9, up to 10 minutes, chapter markers
- `instagram.yaml` - 9:16 vertical Reels, up to 90 seconds
- `x.yaml` - 16:9, up to 2:20 minutes, 280 char tweets
- `tiktok.yaml` - 9:16 vertical, up to 3 minutes
- `facebook.yaml` - 16:9, up to 4 minutes

### 2. Policy Engine

**File:** `src/core/policy_engine.py`

**Key Classes:**
- `PlatformPolicyEngine` - Loads and applies platform policies
- `ValidationResult` - Content validation results
- `TransformationResult` - Applied transformations

**Features:**
- Load platform policies from YAML
- Validate content against platform requirements
- Apply metadata transformations (templates, hashtag formatting)
- Generate platform-specific requirements summary

**Example Usage:**
```python
from src.core.policy_engine import PlatformPolicyEngine

engine = PlatformPolicyEngine()

# Validate content
validation = engine.validate_content('youtube', {
    'video': {'duration_seconds': 300, 'aspect_ratio': '16:9'},
    'metadata': {'title': 'My Video', 'hashtags': ['#AI', '#Tech']}
})

# Apply transformations
transformation = engine.apply_transformations('instagram', content)
```

### 3. Package Generator

**File:** `src/core/package_generator.py`

**Key Classes:**
- `SocialMediaPackageGenerator` - Creates platform-specific packages
- `PackageMetadata` - Package metadata structure
- `PackageResult` - Generation results

**Output Structure:**
```
data/social_packages/
  {episode_id}/
    youtube/
      video_16x9.mp4
      title.txt
      description.txt
      tags.txt
      thumbnail.jpg
      metadata.json
    instagram/
      reel_9x16.mp4
      caption.txt
      hashtags.txt
      thumbnail_square.jpg
      metadata.json
    x/
      clip_720p.mp4
      tweet.txt
      hashtags.txt
      thumbnail.jpg
      metadata.json
```

**Features:**
- Platform-specific folder structure
- Video file handling (copy/transcode)
- Metadata file generation (title, caption, hashtags, description)
- Thumbnail generation (placeholder)
- Package listing and deletion

### 4. Job Tracking System

**File:** `src/core/social_job_tracker.py`

**Database Schema:**
```sql
CREATE TABLE social_jobs (
    job_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    platforms TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    progress REAL DEFAULT 0.0,
    packages_generated TEXT,
    errors TEXT,
    warnings TEXT,
    metadata TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
);
```

**Job Statuses:**
- `pending` - Job created, waiting to start
- `processing` - Job in progress
- `completed` - Job finished successfully
- `failed` - Job failed with errors
- `cancelled` - Job cancelled by user

**Features:**
- Create and track jobs
- Update progress and status
- Store package paths and errors
- List jobs with filters
- Job statistics

### 5. API Endpoints

**File:** `src/api/social_endpoints.py`

**Endpoints:**

#### POST `/social/generate`
Generate social media packages for an episode.

**Request:**
```json
{
  "episode_id": "episode_123",
  "platforms": ["youtube", "instagram", "x"],
  "clip_id": null,
  "metadata_overrides": {
    "title": "Custom Title"
  }
}
```

**Response:**
```json
{
  "job_id": "social_episode_123_abc123",
  "episode_id": "episode_123",
  "platforms": ["youtube", "instagram", "x"],
  "status": "pending",
  "message": "Package generation started..."
}
```

#### GET `/social/jobs/{job_id}`
Get job status and results.

**Response:**
```json
{
  "job_id": "social_episode_123_abc123",
  "episode_id": "episode_123",
  "platforms": ["youtube", "instagram", "x"],
  "status": "completed",
  "progress": 100.0,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:05:00",
  "completed_at": "2024-01-01T12:05:00",
  "packages_generated": {
    "youtube": "data/social_packages/episode_123/youtube",
    "instagram": "data/social_packages/episode_123/instagram"
  },
  "errors": {},
  "warnings": []
}
```

#### GET `/social/jobs`
List all jobs with optional filters.

**Query Parameters:**
- `episode_id` - Filter by episode
- `status` - Filter by status
- `limit` - Maximum results (default: 50)

#### GET `/social/platforms`
List available platforms.

**Response:**
```json
["youtube", "instagram", "x", "tiktok", "facebook"]
```

#### GET `/social/platforms/{platform}`
Get platform requirements.

**Response:**
```json
{
  "platform": "youtube",
  "display_name": "YouTube",
  "icon": "🎥",
  "video": {
    "aspect_ratio": "16:9",
    "max_duration": "10:00",
    "min_duration": "1:00",
    "resolution": "1920x1080"
  },
  "metadata": {
    "title_max_length": 100,
    "caption_max_length": null,
    "hashtags_max_count": 15
  },
  "features": {
    "chapter_markers": true,
    "burn_in_captions": false
  }
}
```

#### GET `/social/packages/{episode_id}`
List generated packages for an episode.

#### DELETE `/social/packages/{episode_id}/{platform}`
Delete a generated package.

#### GET `/social/stats`
Get job statistics.

### 6. Streamlit UI

**File:** `components/social_generator.py`

**Features:**
- **Generate Packages Tab:**
  - Episode selection dropdown
  - Platform checkboxes with tooltips
  - Generate button (submits job to API)
  - Preview button (shows captions/hashtags)
  
- **Job Monitor Tab:**
  - Real-time job status display
  - Progress bars for active jobs
  - Package paths and errors
  - Auto-refresh toggle
  - Job statistics dashboard

**UI Flow:**
1. User selects episode and platforms
2. Clicks "Generate Social Packages"
3. Job submitted to API, returns job_id
4. User switches to "Job Monitor" tab
5. Sees real-time progress updates
6. Views generated package paths when complete

## Usage

### 1. Start API Server

```powershell
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### 2. Start Streamlit Dashboard

```powershell
streamlit run dashboard.py
```

### 3. Generate Packages

**Via UI:**
1. Navigate to "Social Publishing" page
2. Select episode and platforms
3. Click "Generate Social Packages"
4. Monitor progress in "Job Monitor" tab

**Via API:**
```python
import requests

response = requests.post(
    "http://localhost:8000/social/generate",
    json={
        "episode_id": "episode_123",
        "platforms": ["youtube", "instagram", "x"]
    }
)

job_id = response.json()['job_id']

# Poll for status
status_response = requests.get(f"http://localhost:8000/social/jobs/{job_id}")
print(status_response.json())
```

### 4. Access Generated Packages

Packages are saved to: `data/social_packages/{episode_id}/{platform}/`

Each package contains:
- Video file (platform-specific naming)
- Metadata files (title.txt, caption.txt, hashtags.txt, etc.)
- metadata.json (comprehensive metadata)
- thumbnail (placeholder)

## Integration with n8n

### Workflow Setup

1. **Trigger:** Schedule or webhook
2. **HTTP Request:** POST to `/social/generate`
3. **Wait Node:** 5 seconds
4. **Loop:** Poll `/social/jobs/{job_id}` until completed
5. **Conditional:** Check status
6. **Upload Nodes:** Upload to each platform using package files

### Example n8n Workflow

```json
{
  "nodes": [
    {
      "name": "Generate Packages",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://localhost:8000/social/generate",
        "method": "POST",
        "jsonParameters": true,
        "bodyParametersJson": {
          "episode_id": "{{$json.episode_id}}",
          "platforms": ["youtube", "instagram", "x"]
        }
      }
    },
    {
      "name": "Poll Job Status",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://localhost:8000/social/jobs/{{$json.job_id}}",
        "method": "GET"
      }
    },
    {
      "name": "Check Completion",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.status}}",
              "operation": "equals",
              "value2": "completed"
            }
          ]
        }
      }
    }
  ]
}
```

## Customization

### Adding a New Platform

1. **Create Policy File:** `config/platforms/newplatform.yaml`
```yaml
platform: newplatform
display_name: New Platform
icon: 🆕
video:
  aspect_ratio: 16:9
  max_duration: 300
  min_duration: 30
metadata:
  title:
    max_length: 100
    template: "{title} | {show}"
```

2. **Update UI:** Add checkbox in `components/social_generator.py`

3. **Test:** Generate packages and verify output

### Customizing Templates

Edit platform YAML files to customize metadata templates:

```yaml
metadata:
  title:
    template: "{title} - {show_name}"
  description:
    template: |
      {summary}
      
      🎯 Topics: {topics}
      👥 Guests: {guests}
      
      🔗 Full episode: {canonical_url}
```

### Adding Video Transcoding

Implement in `src/core/package_generator.py`:

```python
def _generate_video_file(self, package_dir, platform, content):
    # Add FFmpeg transcoding logic
    import subprocess
    
    source_path = content['video']['source_path']
    policy = self.policy_engine.get_policy(platform)
    
    # Get target specs
    aspect_ratio = policy['video']['aspect_ratio']
    resolution = policy['video']['resolution']['preferred']
    
    # Transcode with FFmpeg
    output_path = package_dir / "video.mp4"
    subprocess.run([
        'ffmpeg', '-i', source_path,
        '-vf', f'scale={resolution}',
        '-aspect', aspect_ratio,
        str(output_path)
    ])
    
    return output_path
```

## Best Practices

1. **Database Management:**
   - API runs in single-worker mode (SQLite limitation)
   - Job tracking uses same database as episodes
   - Regular cleanup of old jobs recommended

2. **File Management:**
   - Packages stored in `data/social_packages/`
   - Consider cleanup strategy for old packages
   - Implement retention policy (e.g., 30 days)

3. **Error Handling:**
   - Jobs track per-platform errors
   - Partial success supported (some platforms succeed)
   - Review warnings for optimization opportunities

4. **Performance:**
   - Background processing prevents UI blocking
   - Multiple platforms processed sequentially
   - Consider parallel processing for production

5. **Content Quality:**
   - Preview packages before generation
   - Review AI-generated captions and hashtags
   - Use metadata overrides for customization

## Troubleshooting

### Job Stuck in "Processing"

Check API logs for errors:
```powershell
# View recent logs
Get-Content logs/api.log -Tail 50
```

### Package Generation Fails

1. Verify episode has required metadata (enrichment)
2. Check source video file exists
3. Review platform policy validation errors
4. Check disk space in `data/social_packages/`

### Database Locked Errors

Ensure API runs with single worker:
```python
uvicorn.run(app, workers=1)  # Critical for SQLite
```

## Future Enhancements

1. **Video Transcoding:**
   - FFmpeg integration for aspect ratio conversion
   - Resolution upscaling/downscaling
   - Compression optimization

2. **Thumbnail Generation:**
   - Extract frame from video
   - Add text overlays
   - Platform-specific sizing

3. **Direct Publishing:**
   - YouTube API integration
   - Instagram Graph API
   - Twitter/X API v2
   - TikTok API

4. **JSON-LD Integration:**
   - Clip metadata with `@type: Clip`
   - `partOf` relationship to episode
   - `startOffset` and `endOffset` timestamps
   - Google Key Moments support

5. **Analytics:**
   - Track package performance
   - A/B testing for captions
   - Optimal posting time recommendations

6. **Scheduling:**
   - Queue packages for future posting
   - Platform-specific best times
   - Content calendar integration

## Summary

The social media publishing system provides:

✅ **Policy-Based Generation** - Platform-specific rules and transformations
✅ **Job Tracking** - Real-time progress monitoring and status updates
✅ **Structured Output** - Predictable folder structure for automation
✅ **API Integration** - RESTful endpoints for n8n workflows
✅ **UI Dashboard** - User-friendly interface with job monitoring
✅ **Extensible Design** - Easy to add new platforms and features

The system is production-ready for generating social media packages and can be extended with direct publishing capabilities as needed.
