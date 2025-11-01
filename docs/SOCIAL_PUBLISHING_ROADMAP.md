# Social Publishing System Roadmap

## Vision
Transform the AI-EWG pipeline into a full AI-aware, platform-intelligent publishing system that automatically generates, packages, and distributes optimized content across multiple social media platforms.

---

## Architecture Overview

### Three-Layer System Design

**Layer 1: Analysis & Enrichment**
- Builds base episode.jsonld
- Detects highlights, guests, sentiments, keywords
- Modules: metadata_enricher.py, clip_selector.py

**Layer 2: Packaging (Policy Engine)**
- Applies per-platform rules (title length, hashtags, aspect ratio)
- Modules: platforms/youtube.yaml, platforms/instagram.yaml

**Layer 3: Publishing Adapter**
- Knows how to push to each API or prepare upload folders for n8n
- Modules: publishers/youtube.py, publishers/x.py

---

## Current State (Baseline)

### What Works
- Episode processing pipeline (discovery → transcription → enrichment → clips)
- Streamlit GUI dashboard with episode management
- Async job queue system for background processing
- Basic social media package generation UI
- API endpoints for episode listing and status

### What's Missing
- Platform-specific policy engine
- Structured social package output folders
- Per-platform content transformations
- Job tracking database table
- Preview/review interface before publishing
- JSON-LD integration for clips

---

## Implementation Phases

### Phase 1: Policy Engine Foundation
**Timeline:** Next Sprint (4-6 hours)
**Priority:** HIGH

#### Deliverables
1. Platform Policy YAMLs (config/platforms/)
   - youtube.yaml
   - instagram.yaml
   - x.yaml
   - tiktok.yaml
   - facebook.yaml

2. Policy Engine Module (src/core/policy_engine.py)
   - load_policy(platform: str) -> dict
   - validate_content(content, policy) -> bool
   - apply_transformations(content, policy) -> dict

3. Package Generator (src/core/package_generator.py)
   - Creates structured output folders
   - Applies platform-specific transformations
   - Generates metadata files

#### Success Criteria
- All 5 platform YAMLs created with complete specifications
- Policy engine can load and validate policies
- Package generator creates correct folder structure
- Unit tests for policy validation

---

### Phase 2: Enhanced Social Package Generation
**Timeline:** Current Sprint Extension (2-3 hours)
**Priority:** HIGH

#### Deliverables
1. Structured Output Folders
   - /data/social_packages/{episode_id}/{platform}/
   - video file, title.txt, description.txt, tags.txt, thumbnail.jpg

2. Enhanced API Endpoint (/generate_social_packages)
   - Load platform policies
   - Apply transformations
   - Write to structured folders
   - Return job_id for tracking

3. Database Schema Update
   - social_packages table
   - Track status, paths, external IDs

#### Success Criteria
- Packages generated in correct folder structure
- All required files present per platform
- Database tracks package status
- API returns job_id immediately

---

### Phase 3: Job Tracking & Review Interface
**Timeline:** Next Sprint (4-5 hours)
**Priority:** MEDIUM

#### Deliverables
1. Job Tracking System
   - social_jobs table in database
   - Track generation progress per platform
   - Store logs and error messages

2. Streamlit UI Enhancements
   - Episode preview area
   - Smart platform defaults
   - Progress feedback
   - Review tab for editing

3. Preview Components
   - Video player for clips
   - Editable caption/title fields
   - Hashtag editor
   - Thumbnail selector

#### Success Criteria
- Real-time job progress tracking
- Users can preview all generated content
- Users can edit captions/titles inline
- Changes saved back to package files

---

### Phase 4: JSON-LD Deep Integration
**Timeline:** Future Sprint (6-8 hours)
**Priority:** LOW

#### Deliverables
1. Clip Metadata Integration
   - Each clip as @type: Clip with partOf relationship
   - Include startOffset, endOffset, thumbnailUrl
   - Add potentialAction (SeekToAction)

2. Schema.org Compliance
   - Validate JSON-LD against schema.org
   - Enable Google Key Moments
   - Deep-linking support

#### Success Criteria
- Valid JSON-LD for all clips
- Google Search Console validates structured data
- Key Moments appear in search results

---

### Phase 5: Publishing Automation
**Timeline:** Future Sprint (8-10 hours)
**Priority:** MEDIUM

#### Deliverables
1. n8n Integration
   - File watcher workflow
   - Per-platform upload nodes
   - Error handling and retry logic

2. Publishing Adapters (src/publishers/)
   - youtube.py, x.py, instagram.py, tiktok.py, facebook.py

3. Distribution Tracking
   - Update social_packages with external IDs
   - Track view counts and engagement
   - Store published URLs

#### Success Criteria
- n8n automatically uploads new packages
- All platforms supported
- External IDs stored in database
- Failed uploads retry automatically

---

## Platform Policy Specifications

### YouTube (youtube.yaml)
- Aspect ratio: 16:9
- Max duration: 600s (10 min)
- Title max: 100 chars
- Description max: 5000 chars
- Tags: 15 max from topics/guests
- Features: chapter markers, end screen

### Instagram (instagram.yaml)
- Aspect ratio: 9:16
- Max duration: 90s
- Caption max: 2200 chars
- Hashtags: 30 max
- Features: watermark, burn-in captions

### X/Twitter (x.yaml)
- Aspect ratio: 16:9
- Max duration: 140s
- Tweet max: 280 chars
- Hashtags: 2 max
- Max file size: 512MB

### TikTok (tiktok.yaml)
- Aspect ratio: 9:16
- Max duration: 180s
- Caption max: 150 chars
- Hashtags: 5 max
- Features: auto-captions, duet enabled

### Facebook (facebook.yaml)
- Aspect ratio: 16:9
- Max duration: 240s
- Title max: 255 chars
- Description max: 5000 chars
- Hashtags: 10 max

---

## Database Schema Changes

### social_packages table
```sql
CREATE TABLE social_packages (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    status TEXT NOT NULL,
    package_path TEXT,
    metadata JSON,
    created_at TIMESTAMP,
    published_at TIMESTAMP,
    external_id TEXT,
    external_url TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);
```

### social_jobs table
```sql
CREATE TABLE social_jobs (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    platforms JSON NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    current_step TEXT,
    log_path TEXT,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);
```

---

## File Structure

### New Directories
```
config/platforms/          # Platform policy YAMLs
src/core/policy_engine.py  # Load and apply policies
src/core/package_generator.py  # Generate output folders
src/publishers/            # Platform upload adapters
data/social_packages/      # Generated packages
```

---

## API Endpoints

### POST /social/generate
Generate social media packages for an episode.

Request:
- episode_id
- platforms (array)
- options (optional)

Response:
- job_id
- status
- created_at

### GET /social/jobs/{job_id}
Get status of generation job.

Response:
- job_id
- status
- progress (0-100)
- current_step
- packages (array)

### GET /social/packages/{episode_id}
List all packages for an episode.

Response:
- episode_id
- packages (array with status, external_id, url)

### PATCH /social/packages/{package_id}
Update package metadata (edit captions/titles).

---

## Streamlit UI Enhancements

### New Components
1. Episode Preview Panel
   - Thumbnail, duration, metadata
   - AI-suggested clip moments
   - Transcript summary

2. Platform Selector
   - Smart defaults
   - Visual cards with icons
   - Policy constraints display

3. Generation Progress
   - Real-time progress bar
   - Current step indicator
   - Platform-by-platform status

4. Review Interface
   - Video preview
   - Editable caption fields
   - Hashtag editor
   - Thumbnail selector

---

## Testing Strategy

### Unit Tests
- Policy engine loads YAMLs correctly
- Policy validation catches invalid content
- Package generator creates correct structure
- Transformations apply correctly

### Integration Tests
- End-to-end package generation
- Database tracking updates
- API endpoints return expected responses
- n8n workflow triggers

### Manual Testing
- Generate packages for test episode
- Verify all files present
- Preview in Streamlit UI
- Edit captions and save
- Upload to test accounts

---

## Success Metrics

### Phase 1
- All 5 platform YAMLs complete
- Policy engine unit tests pass
- Package structure validated

### Phase 2
- Packages generated in under 30s per platform
- 100% of required files present
- Database tracking accurate

### Phase 3
- Users can preview before publishing
- Caption edits save successfully
- Job progress updates in real-time

### Phase 4
- Valid JSON-LD for all clips
- Google validates structured data
- Key Moments appear in search

### Phase 5
- 95%+ successful upload rate
- Failed uploads retry automatically
- External IDs tracked correctly

---

## Risk Mitigation

### Technical Risks
1. Platform API Changes
   - Mitigation: Abstract publishers, version policies

2. Video Transcoding Performance
   - Mitigation: GPU acceleration, job queue

3. Database Locking
   - Mitigation: WAL mode, consider PostgreSQL

### Operational Risks
1. API Rate Limits
   - Mitigation: Exponential backoff, queue management

2. Storage Growth
   - Mitigation: Cleanup old packages, compression

3. Content Policy Violations
   - Mitigation: Pre-upload validation, manual review

---

## Future Enhancements

### Analytics Dashboard
- View counts per platform
- Engagement metrics
- Best performing clips
- Optimal posting times

### A/B Testing
- Multiple caption variations
- Thumbnail options
- Hashtag combinations

### Automated Scheduling
- Platform-specific optimal times
- Staggered releases
- Timezone awareness

### Content Recommendations
- AI suggests best clips per platform
- Trending topic integration
- Audience preference learning

---

## Dependencies

### Python Packages
- streamlit>=1.28.0
- pyyaml>=6.0
- pillow>=10.0
- moviepy>=1.0.3
- google-api-python-client>=2.0
- tweepy>=4.14.0
- facebook-sdk>=3.1.0

### External Services
- YouTube Data API v3
- Twitter/X API v2
- Instagram Graph API
- TikTok API
- Facebook Graph API

### Infrastructure
- FFmpeg (video transcoding)
- GPU (optional, faster processing)
- n8n (workflow automation)

---

## Timeline Summary

| Phase | Duration | Priority | Status |
|-------|----------|----------|--------|
| Phase 1: Policy Engine | 4-6 hours | HIGH | Not Started |
| Phase 2: Package Generation | 2-3 hours | HIGH | Not Started |
| Phase 3: Job Tracking & UI | 4-5 hours | MEDIUM | Not Started |
| Phase 4: JSON-LD Integration | 6-8 hours | LOW | Not Started |
| Phase 5: Publishing Automation | 8-10 hours | MEDIUM | Not Started |

**Total Estimated Time:** 24-32 hours

---

## Immediate Next Steps

1. Create platform policy YAMLs (30 min)
2. Build policy engine module (2 hours)
3. Update social package generator (1 hour)
4. Add database tables (30 min)
5. Update Streamlit UI with preview (1 hour)

**Next Session Focus:** Phase 1 + Phase 2 (6-9 hours total)

---

## Questions to Resolve

1. Clip Selection: Copy clips to packages or reference existing?
   - Recommendation: Copy for self-contained packages

2. n8n Integration: Folder watch, API poll, or webhook?
   - Recommendation: Folder watch for MVP, webhook for production

3. Database: Continue SQLite or migrate to PostgreSQL?
   - Recommendation: SQLite for now, PostgreSQL when scaling

4. Caption Editing: In-app or external editor?
   - Recommendation: In-app with live preview

5. Thumbnail Generation: Auto or manual selection?
   - Recommendation: Auto-generate with manual override

---

*Last Updated: October 26, 2025*
*Branch: feature/gui-control-panel*
*Status: Planning Phase*
