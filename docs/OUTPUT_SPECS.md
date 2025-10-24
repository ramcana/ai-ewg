# Output Specifications

This document defines the exact JSON shapes and output formats for all pipeline artifacts.

## Episode Metadata JSON

**Location:** `data/meta/{episode_id}.json`

```json
{
  "episode_id": "newsroom_2024_s01e042",
  "show_name": "The Newsroom",
  "season_number": 1,
  "episode_number": 42,
  "title": "Breaking News Coverage",
  "air_date": "2024-03-15",
  "duration_seconds": 3600.5,
  
  "source": {
    "path": "D:/newsroom/videos/2024/episode_042.mp4",
    "file_size": 1073741824,
    "last_modified": "2024-03-15T20:00:00Z",
    "content_hash": "sha256:abc123..."
  },
  
  "media": {
    "duration_seconds": 3600.5,
    "video_codec": "h264",
    "audio_codec": "aac",
    "resolution": "1920x1080",
    "fps": 29.97,
    "bitrate": 2500000
  },
  
  "transcription": {
    "language": "en",
    "confidence": 0.92,
    "word_count": 8500,
    "segments": [
      {
        "start": 0.0,
        "end": 5.5,
        "text": "Welcome to The Newsroom.",
        "speaker": "host",
        "confidence": 0.95
      }
    ]
  },
  
  "people": {
    "host": {
      "name": "John Smith",
      "role": "host",
      "wikidata_id": "Q12345",
      "wikipedia_url": "https://en.wikipedia.org/wiki/John_Smith",
      "bio": "Award-winning journalist...",
      "proficiency_score": 0.95,
      "badges": ["verified_expert", "industry_leader"],
      "credentials": [
        "Emmy Award Winner",
        "20+ years journalism"
      ]
    },
    "guests": [
      {
        "name": "Dr. Jane Doe",
        "role": "guest",
        "wikidata_id": "Q67890",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Jane_Doe",
        "bio": "Professor of Economics...",
        "proficiency_score": 0.88,
        "badges": ["academic_authority"],
        "credentials": [
          "PhD Economics, MIT",
          "Published 50+ papers"
        ],
        "topics": ["economics", "policy", "trade"]
      }
    ]
  },
  
  "editorial": {
    "summary": "In this episode, John Smith interviews Dr. Jane Doe about...",
    "key_takeaways": [
      "Economic indicators show...",
      "Policy changes will affect...",
      "Expert predictions for..."
    ],
    "topics": [
      {"name": "economics", "relevance": 0.95},
      {"name": "policy", "relevance": 0.82},
      {"name": "trade", "relevance": 0.76}
    ],
    "tags": ["economics", "interview", "expert-analysis"]
  },
  
  "processing": {
    "stage": "rendered",
    "created_at": "2024-03-15T21:00:00Z",
    "updated_at": "2024-03-15T22:30:00Z",
    "processing_time_seconds": 5400,
    "errors": null
  }
}
```

## JSON-LD Structured Data

**Embedded in:** `data/public/shows/{show}/{episode}/index.html`

```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "Breaking News Coverage",
  "description": "In this episode, John Smith interviews Dr. Jane Doe about...",
  "uploadDate": "2024-03-15T20:00:00Z",
  "duration": "PT1H0M0S",
  "contentUrl": "/videos/newsroom_2024_s01e042.mp4",
  "thumbnailUrl": "/images/newsroom_2024_s01e042_thumb.jpg",
  
  "partOfSeries": {
    "@type": "TVSeries",
    "name": "The Newsroom",
    "seasonNumber": 1,
    "episodeNumber": 42
  },
  
  "actor": [
    {
      "@type": "Person",
      "name": "John Smith",
      "jobTitle": "Host",
      "sameAs": "https://en.wikipedia.org/wiki/John_Smith",
      "description": "Award-winning journalist..."
    },
    {
      "@type": "Person",
      "name": "Dr. Jane Doe",
      "jobTitle": "Guest Expert",
      "sameAs": "https://en.wikipedia.org/wiki/Jane_Doe",
      "description": "Professor of Economics...",
      "affiliation": {
        "@type": "Organization",
        "name": "MIT"
      }
    }
  ],
  
  "keywords": "economics, interview, expert-analysis",
  
  "transcript": {
    "@type": "WebPageElement",
    "text": "Full transcript text...",
    "encodingFormat": "text/plain"
  },
  
  "interactionStatistic": {
    "@type": "InteractionCounter",
    "interactionType": "https://schema.org/WatchAction",
    "userInteractionCount": 0
  }
}
```

## VTT Caption File

**Location:** `data/transcripts/{episode_id}.vtt`

```vtt
WEBVTT

1
00:00:00.000 --> 00:00:05.500
Welcome to The Newsroom.

2
00:00:05.500 --> 00:00:12.300
Today we're joined by Dr. Jane Doe.

3
00:00:12.300 --> 00:00:18.750
Dr. Doe, thank you for being here.
```

## Plain Text Transcript

**Location:** `data/transcripts/{episode_id}.txt`

```
Welcome to The Newsroom. Today we're joined by Dr. Jane Doe. Dr. Doe, thank you for being here.
```

## HTML Web Page

**Location:** `data/public/shows/{show}/{episode}/index.html`

### Required Elements

1. **Head Section:**
   - Title: `{episode_title} - {show_name}`
   - Meta description: First 160 chars of summary
   - JSON-LD script tag
   - Open Graph tags
   - Twitter Card tags

2. **Body Structure:**
   - Header with show branding
   - Episode title and metadata (date, duration)
   - Host and guest profiles with badges
   - Video player embed
   - Transcript with speaker labels
   - Key takeaways list
   - Related episodes
   - Footer with navigation

3. **CSS Classes:**
   - `.episode-header`
   - `.person-card` (with `.host` or `.guest`)
   - `.badge` (with `.verified-expert`, `.industry-leader`, `.academic-authority`)
   - `.transcript-segment` (with `.speaker-{name}`)
   - `.key-takeaway`

## JSONL Log Format

**Location:** `logs/run_{timestamp}.jsonl`

Each line is a JSON object:

```json
{"event": "run_started", "command": "transcribe", "episode_id": "newsroom_2024_s01e042", "timestamp": "2024-03-15T21:00:00.000Z", "level": "info"}
{"event": "stage_started", "stage": "transcription", "episode_id": "newsroom_2024_s01e042", "timestamp": "2024-03-15T21:00:05.123Z", "level": "info"}
{"event": "metric", "metric": "transcription_confidence", "value": 0.92, "episode_id": "newsroom_2024_s01e042", "timestamp": "2024-03-15T21:15:30.456Z", "level": "info"}
{"event": "stage_completed", "stage": "transcription", "episode_id": "newsroom_2024_s01e042", "duration_seconds": 925.5, "timestamp": "2024-03-15T21:15:30.678Z", "level": "info"}
{"event": "run_completed", "command": "transcribe", "episode_id": "newsroom_2024_s01e042", "duration_seconds": 930.0, "success": true, "stages_completed": 1, "error_count": 0, "timestamp": "2024-03-15T21:15:35.000Z", "level": "info"}
```

## n8n Summary JSON

**Output to:** `stdout` (for n8n to capture)

```json
{
  "command": "transcribe",
  "episode_id": "newsroom_2024_s01e042",
  "success": true,
  "duration_seconds": 930.0,
  "start_time": "2024-03-15T21:00:00Z",
  "end_time": "2024-03-15T21:15:30Z",
  "stages": {
    "transcription": {
      "status": "completed",
      "duration_seconds": 925.5,
      "timestamp": "2024-03-15T21:15:30Z"
    }
  },
  "errors": [],
  "error_count": 0,
  "stages_completed": 1,
  "stages_failed": 0
}
```

## Batch Processing Summary

```json
{
  "command": "transcribe",
  "success": true,
  "total_items": 10,
  "processed": 10,
  "failed": 0,
  "success_rate": 1.0,
  "duration_seconds": 9300.0,
  "items_per_second": 0.001,
  "start_time": "2024-03-15T21:00:00Z",
  "end_time": "2024-03-15T23:35:00Z"
}
```

## Registry Database Schema

### Episodes Table

```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    hash TEXT UNIQUE NOT NULL,
    stage TEXT NOT NULL,
    source_path TEXT NOT NULL,
    metadata TEXT NOT NULL,  -- JSON
    file_size INTEGER,
    duration_seconds REAL,
    last_modified TEXT,
    errors TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Processing Log Table

```sql
CREATE TABLE processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'started', 'completed', 'failed'
    duration_seconds REAL,
    error_message TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);
```

### Artifacts Table

```sql
CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,  -- 'transcript', 'vtt', 'html', 'json'
    file_path TEXT NOT NULL,
    file_size INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);
```

## Processing Stages

Valid stage values (in order):

1. `new` - Newly discovered
2. `staged` - Copied to staging area
3. `transcribed` - Audio transcribed
4. `diarized` - Speakers identified
5. `entities_extracted` - Named entities extracted
6. `disambiguated` - Entities matched to knowledge bases
7. `scored` - Proficiency scores calculated
8. `enriched` - Editorial content generated
9. `rendered` - HTML pages built
10. `indexed` - Added to indices

## File Naming Conventions

- Episode ID: `{show_slug}_{year}_s{season:02d}e{episode:03d}`
- Metadata: `{episode_id}.json`
- Transcript: `{episode_id}.txt`
- VTT: `{episode_id}.vtt`
- HTML: `{show_slug}/{episode_id}/index.html`
- Logs: `run_{timestamp}.jsonl`

## Validation Rules

1. **Episode ID:** Must be unique, alphanumeric + underscores
2. **Content Hash:** SHA-256 of source file
3. **Confidence Scores:** Float 0.0-1.0
4. **Timestamps:** ISO 8601 format
5. **Durations:** Seconds as float
6. **URLs:** Must be valid HTTP/HTTPS
7. **Wikidata IDs:** Format `Q[0-9]+`
