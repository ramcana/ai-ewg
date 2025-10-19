# Part 1: Video Library Processing Pipeline

## Overview

Transform existing video library into web-ready content with full metadata, transcription, and enrichment. No distribution/publishing - just generate all content and format for web consumption.

## 1. Inputs & Configuration

### Config Structure (`config/system.yaml`)

```yaml
sources:
  - path: "C:\\Videos"
    include: ["*.mp4", "*.mkv", "*.avi"]
    exclude: ["*temp*", "*draft*"]
  - path: "\\\\NAS\\Shows"
    include: ["*.mp4"]
    exclude: []
  - path: "E:\\Archive"
    include: ["*.mp4", "*.mov"]
    exclude: []

staging:
  enabled: true
  path: "data/staging"

discovery:
  stability_minutes: 5 # File must be unchanged for N minutes to be "ready"

models:
  whisper: "base" # tiny, base, small, medium, large
  llm: "gpt-3.5-turbo"

thresholds:
  confidence_min: 0.7
  entity_confidence: 0.6
```

### Discovery Rules

- Treat file as "ready" only if size & mtime unchanged for N minutes
- Support local drives, UNC shares, external drives
- Shadow copy option: copy large files to `data/staging/` before processing

**Done When:** One job finds all candidates across all drives without touching partial copies.

## 2. Episode Normalization

### Filename/Folder Parser

Extract best-effort fields from paths:

- Show name
- Season number
- Episode number
- Date
- Topic/title

### Stable ID Generation

Format: `{show-slug}-s{season}e{episode}-{date}-{topic-slug}`
Example: `counterpoint-s03e12-2024-11-02-ai-and-energy`

### Episode Object Structure

```json
{
  "episode_id": "counterpoint-s03e12-2024-11-02-ai-and-energy",
  "source": {
    "path": "\\\\NAS\\Shows\\Counterpoint\\S03\\E12.mp4"
  },
  "media": {
    "videoPath": "data/staging/counterpoint-s03e12-2024-11-02-ai-and-energy.mp4",
    "audioPath": "data/audio/counterpoint-s03e12-2024-11-02-ai-and-energy.wav"
  },
  "metadata": {
    "show": "Counterpoint",
    "season": 3,
    "episode": 12,
    "date": "2024-11-02",
    "topic": "AI and Energy"
  }
}
```

**Done When:** Re-running on same file yields same episode_id.

## 3. Registry & Deduplication

### SQLite Schema

```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    hash TEXT UNIQUE,
    stage TEXT,  -- discovered, prepped, transcribed, enriched, rendered
    errors TEXT,
    updated_at TIMESTAMP
);
```

### Hash Computation

Combine: file size + path + duration for unique identification

**Done When:** Repeated runs only process new/changed items.

## 4. Media Preparation

### Audio Extraction

- Extract audio to `.wav` for stable transcription
- Store in `data/audio/{episode_id}.wav`

### Health Checks

- Verify duration
- Confirm file readability
- Validate audio quality

**Done When:** `media.audioPath` exists and is valid.

## 5. Transcription

### Whisper Processing

- Generate `.txt` (plain text)
- Generate `.vtt` (captions with timestamps)
- Store in `data/transcripts/{txt,vtt}/{episode_id}.*`

### Output Structure

```
data/transcripts/
├── txt/
│   └── counterpoint-s03e12-2024-11-02-ai-and-energy.txt
└── vtt/
    └── counterpoint-s03e12-2024-11-02-ai-and-energy.vtt
```

**Done When:** Both transcript files exist; paths recorded on episode.

## 6. Intelligence Chain (Four Utils Pipeline)

### 6.1 Speaker Diarization (`utils/diarize.py`)

- Input: Audio file + transcript
- Output: Transcript segments with speaker labels
- Result: `transcript.segments` with speaker turns

### 6.2 Entity Extraction (`utils/extract_entities.py`)

- Input: Diarized transcript
- Output: Candidate people, organizations, topics
- Method: LLM extraction with spaCy fallback

### 6.3 Disambiguation (`utils/disambiguate.py`)

- Input: Extracted entities
- Output: Enriched people via Wikidata/Wikipedia/official bios
- Fields: sameAs links, affiliation, confidence scores

### 6.4 Proficiency Scoring (`utils/score_people.py`)

- Input: Disambiguated entities
- Output: Proficiency scores + badges + reasoning
- Badges: "Verified Expert", "Industry Leader", "Academic Authority"

### Expected Guest/Host Object

```json
{
  "name": "Jane Doe",
  "jobTitle": "Senior Economist",
  "affiliation": {
    "name": "Bank of Canada",
    "url": "https://www.bankofcanada.ca"
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Q12345",
    "https://en.wikipedia.org/wiki/Jane_Doe"
  ],
  "score": 0.83,
  "badge": "Verified Expert",
  "confidence": 0.88,
  "reasoning": "Senior economist with 15+ years at central bank, published researcher"
}
```

**Done When:** Each episode has complete host/guest objects with scores and badges.

## 7. Editorial Layer

### Content Generation

- **Key Takeaway:** Single compelling sentence
- **Summary:** 2-3 line episode overview
- **Topics/Tags:** Top 5-10 relevant keywords
- **Related Links:** Same-show or same-topic matches

### Quality Standards

- Concise and readable
- Factually accurate
- SEO-friendly
- Engaging for readers

**Done When:** All editorial fields exist and meet quality standards.

## 8. Web-Ready Artifacts

### Folder Structure

```
data/public/
├── shows/
│   └── {show-slug}/
│       └── {episode_id}/
│           └── index.html
├── assets/
│   └── transcripts/
│       ├── {episode_id}.txt
│       └── {episode_id}.vtt
└── meta/
    └── {episode_id}.json
```

### Episode JSON (`meta/{episode_id}.json`)

Complete episode object including:

- All inputs and outputs
- Guest scores and badges
- Diarized segments
- Summary and tags
- Transcript paths

### HTML Page (`index.html`)

- Episode title and date
- Key Takeaway + Summary
- Host & Guest chips with badges + links
- Speaker-labeled transcript sections
- Video embed (placeholder URL)
- Transcript download links
- Embedded JSON-LD

### JSON-LD Schema

```json
{
  "@context": "https://schema.org",
  "@type": "TVEpisode",
  "name": "AI and Energy — Counterpoint",
  "datePublished": "2024-11-02",
  "partOfSeries": {
    "@type": "TVSeries",
    "name": "Counterpoint",
    "url": "https://thenewsforum.ca/series/counterpoint"
  },
  "video": {
    "@type": "VideoObject",
    "url": "https://.../player.mp4",
    "thumbnailUrl": "https://.../thumb.jpg"
  },
  "about": ["AI", "energy", "policy", "Canada"],
  "actor": [
    {
      "@type": "Person",
      "name": "Host Name",
      "sameAs": ["https://..."]
    },
    {
      "@type": "Person",
      "name": "Jane Doe",
      "jobTitle": "Senior Economist",
      "affiliation": {
        "@type": "Organization",
        "name": "Bank of Canada",
        "url": "https://www.bankofcanada.ca"
      },
      "sameAs": ["https://www.wikidata.org/wiki/Q12345"]
    }
  ]
}
```

**Done When:** Opening `index.html` shows complete episode page; `meta/{episode_id}.json` mirrors data.

## 9. Indices for Future Use

### Per-Show Index (`series/{show-slug}/index.json`)

```json
{
  "show": "Counterpoint",
  "episodes": [
    {
      "id": "counterpoint-s03e12-2024-11-02-ai-and-energy",
      "title": "AI and Energy",
      "url": "/shows/counterpoint/counterpoint-s03e12-2024-11-02-ai-and-energy/",
      "date": "2024-11-02",
      "tags": ["AI", "energy", "policy"]
    }
  ]
}
```

### Per-Host Index (`hosts/{host-slug}/index.json`)

```json
{
  "host": "John Smith",
  "appearances": [
    {
      "episode_id": "counterpoint-s03e12-2024-11-02-ai-and-energy",
      "show": "Counterpoint",
      "date": "2024-11-02",
      "role": "host"
    }
  ]
}
```

**Done When:** Index JSONs exist for all shows and hosts.

## 10. Reliability & Performance

### Processing Stages

1. **discovered** - File found and normalized
2. **prepped** - Media extracted and validated
3. **transcribed** - Whisper processing complete
4. **enriched** - Intelligence chain complete
5. **rendered** - Web artifacts generated

### Reliability Features

- Retries with exponential backoff
- Skip processing on unchanged hash
- Concurrency limits for Whisper/enrichment
- Comprehensive error logging

### Logging Structure

```json
{
  "episode_id": "counterpoint-s03e12-2024-11-02-ai-and-energy",
  "stage": "enriched",
  "timings": {
    "transcription": "45.2s",
    "diarization": "12.1s",
    "entity_extraction": "8.7s",
    "disambiguation": "23.4s",
    "scoring": "5.2s"
  },
  "errors": [],
  "scores": {
    "guest_confidence": 0.88,
    "entity_count": 12,
    "proficiency_scores": [0.83, 0.76]
  }
}
```

**Done When:** Large backfill (hundreds of files) runs end-to-end without manual intervention.

## Definition of Done - Part 1

### ✅ Discovery & Processing

- [ ] All videos discovered from every source path reliably
- [ ] Files processed only when stable (unchanged for N minutes)
- [ ] Idempotent reruns (unchanged files skipped)

### ✅ Per Episode Outputs

- [ ] `.txt` + `.vtt` transcripts generated
- [ ] Diarized segments with speaker labels
- [ ] Enriched & scored guests/hosts with badges
- [ ] Key Takeaway + Summary + tags generated
- [ ] `index.html` with embedded JSON-LD created
- [ ] `meta/{episode_id}.json` with complete data

### ✅ Indices & Organization

- [ ] Per-show episode index JSONs generated
- [ ] Per-host appearances index JSONs generated
- [ ] Clean folder structure in `data/public/`

### ✅ System Reliability

- [ ] Comprehensive logging with success/failure reasons
- [ ] Error handling with retries and backoff
- [ ] Concurrency controls for resource protection
- [ ] Processing stage tracking in SQLite

### 🎯 Success Criteria

When Part 1 is complete:

1. Any video file can be dropped into source folders and automatically processed
2. Opening any `index.html` shows a complete, professional episode page
3. All metadata is structured and ready for Part 2 (publishing/distribution)
4. System handles hundreds of files without manual intervention
5. Logs provide clear visibility into processing status and any issues

---

**Next:** Part 2 will handle publishing to live site, RSS/sitemaps generation, and platform integration (Google/Bing/Apple/Perplexity).
