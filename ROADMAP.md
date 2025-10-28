# Video Processing Pipeline - Roadmap to Completion

**Status**: Core pipeline working! First successful end-to-end processing completed on Oct 19, 2025.
**What's Working**: Discovery → Prep → Transcription (Whisper) → Enrichment (placeholder) → Rendering (basic HTML)

---

## 🎯 Current State vs. Target

### ✅ What's Working (As of Oct 19, 2025)

1. **Infrastructure (95% Complete)**
   - ✅ Configuration system (YAML + env vars)
   - ✅ SQLite registry with stage tracking
   - ✅ Logging and monitoring
   - ✅ Resource management
   - ✅ n8n workflow integration
   - ✅ API server with endpoints

2. **Discovery & Preparation (100% Complete)**
   - ✅ Multi-source video scanning
   - ✅ File stability checking
   - ✅ Episode ID generation
   - ✅ Audio extraction (ffmpeg)
   - ✅ Media validation

3. **Transcription (100% Complete)**
   - ✅ Whisper integration (base model)
   - ✅ Plain text (.txt) generation
   - ✅ WebVTT (.vtt) captions with timestamps
   - ✅ 7+ minute processing time per video

4. **Enrichment (20% Complete)**
   - ⚠️ Placeholder JSON generation
   - ❌ No diarization
   - ❌ No entity extraction
   - ❌ No disambiguation
   - ❌ No guest scoring

5. **Rendering (40% Complete)**
   - ✅ Basic HTML generation
   - ✅ Metadata JSON export
   - ✅ Transcript file copying
   - ⚠️ Missing: AI-generated summaries, key takeaways, topics, guest profiles

### 🎨 AI-Enhanced HTML (from generate-html-ai.ps1) - Target Quality

Your existing PowerShell script shows what you want:

**AI Features (using Ollama)**:
1. ✨ Executive Summary (2-3 paragraphs)
2. ✨ Key Takeaways (5-7 bullet points)
3. ✨ Deep News Analysis (context, implications, impact)
4. ✨ Topics/Keywords extraction (8-10 tags)
5. ✨ Segment titles (AI-generated for each chunk)
6. ✨ Professional styling with badges and visual hierarchy

**Current Basic HTML Has**:
- Episode title, date, ID
- Raw transcript
- Download links
- Basic JSON-LD

**Missing from Current HTML**:
- Executive summary
- Key takeaways
- Analysis sections
- Visual hierarchy
- Guest credentials with badges
- Speaker-labeled transcript segments

---

## 📋 Priority Roadmap

### 🔥 **Phase 1: Intelligence Chain Integration** (CRITICAL - 2-3 days)

This is the biggest gap. Your plan calls for the "Four Utils Pipeline" but they're not implemented yet.

#### Task 1.1: Implement Ollama-Based Enrichment (HIGH PRIORITY)
**Goal**: Replace placeholder enrichment with real AI analysis (like generate-html-ai.ps1)

**What to Build**:
```python
# src/stages/enrichment_stage.py - Replace current placeholder

class EnrichmentStageProcessor:
    def __init__(self, ollama_model="llama3.1:latest"):
        self.model = ollama_model
    
    async def process(self, episode, audio_path, transcript_data):
        """
        Run Ollama AI analysis on transcript:
        1. Executive Summary (2-3 paragraphs)
        2. Key Takeaways (5-7 items)
        3. Deep Analysis (themes, implications, context)
        4. Topics/Keywords (8-10 tags)
        5. Segment Titles (for transcript chunks)
        """
```

**Implementation Steps**:
1. Install Ollama client: `pip install ollama`
2. Port the PowerShell Ollama prompts to Python
3. Call Ollama API for each analysis type
4. Store results in enrichment JSON
5. Handle timeouts (Ollama can be slow)

**Files to Create/Modify**:
- `src/stages/enrichment_stage.py` (rewrite)
- `src/utils/ollama_client.py` (new - wrap Ollama API)
- Add ollama to `requirements.txt`

**Expected Output** (`data/enriched/{episode_id}.json`):
```json
{
  "episode_id": "newsroom-2024-bb580",
  "ai_analysis": {
    "executive_summary": "2-3 paragraph summary from Ollama...",
    "key_takeaways": [
      "Takeaway 1...",
      "Takeaway 2...",
      "..."
    ],
    "deep_analysis": "Context, implications, impact...",
    "topics": ["AI", "Policy", "Energy", "..."],
    "segment_titles": [
      {"segment": 1, "title": "Opening Discussion on AI"},
      {"segment": 2, "title": "Energy Policy Implications"},
      "..."
    ]
  },
  "processing_time": 45.2
}
```

---

#### Task 1.2: Speaker Diarization (MEDIUM PRIORITY)
**Goal**: Identify who's speaking when (Host vs. Guests)

**What to Build**:
```python
# src/utils/diarize.py (from your plan - not yet implemented)

def diarize_audio(audio_path, transcript_text):
    """
    Use pyannote.audio or similar to:
    1. Detect speaker changes
    2. Label segments (Speaker 0, Speaker 1, etc.)
    3. Merge with transcript timing
    
    Returns: List of segments with speaker labels
    """
```

**Options**:
1. **pyannote.audio** (industry standard, requires Hugging Face token)
2. **Faster-Whisper with diarization** (newer, less setup)
3. **Simple heuristic** (split on silence, assume alternating speakers)

**Expected Output**:
```json
{
  "segments": [
    {"speaker": "SPEAKER_00", "start": 0.0, "end": 15.3, "text": "Welcome to the show..."},
    {"speaker": "SPEAKER_01", "start": 15.4, "end": 32.1, "text": "Thank you for having me..."},
    "..."
  ]
}
```

---

#### Task 1.3: Entity Extraction with Ollama (MEDIUM PRIORITY)
**Goal**: Extract people, organizations, locations from transcript

**What to Build**:
```python
# src/utils/extract_entities.py

async def extract_entities_ollama(transcript_text, model="llama3.1:latest"):
    """
    Ask Ollama to extract:
    - People (names, roles mentioned)
    - Organizations (companies, institutions)
    - Locations
    - Topics/Themes
    
    Returns: List of entities with types and context
    """
```

**Ollama Prompt Example**:
```
Extract all people mentioned in this transcript. For each person, provide:
- Full name
- Role/title if mentioned
- Organization if mentioned
- Context (why they're relevant)

Format as JSON array.

Transcript:
{transcript_text}
```

---

#### Task 1.4: Guest Disambiguation & Scoring (LOW PRIORITY)
**Goal**: Enrich identified people with Wikipedia/Wikidata links, credentials, badges

**What to Build**:
```python
# src/utils/disambiguate.py
# src/utils/score_people.py

def disambiguate_person(name, role, organization):
    """
    Look up person in:
    1. Wikidata API
    2. Wikipedia API
    3. Official org websites
    
    Returns: Bio, links, confidence score
    """

def score_credibility(person_data):
    """
    Assign badges based on:
    - "Verified Expert" (academic credentials)
    - "Industry Leader" (C-suite, gov officials)
    - "Academic Authority" (professor, researcher)
    
    Returns: Badge + reasoning
    """
```

**Note**: This is nice-to-have. Can be done later if time-constrained.

---

### 🎨 **Phase 2: Enhanced HTML Rendering** (CRITICAL - 1 day)

#### Task 2.1: Rewrite Rendering Stage with AI Data
**Goal**: Generate HTML like generate-html-ai.ps1 but using pipeline data

**What to Build**:
```python
# src/stages/rendering_stage.py (enhance existing)

class RenderingStageProcessor:
    def process(self, episode, transcript_data, enrichment_data):
        """
        Generate HTML with:
        1. AI-generated executive summary (from enrichment)
        2. Key takeaways section (from enrichment)
        3. Topics tags (from enrichment)
        4. Deep analysis box (from enrichment)
        5. Speaker-labeled transcript (from diarization)
        6. Guest credentials with badges (from scoring)
        """
```

**HTML Template to Add**:
- **AI Badge**: Show "AI ENHANCED" badge
- **Executive Summary Box**: Blue background, prominent
- **Key Takeaways List**: Green background, bullets
- **Deep Analysis Box**: Orange background
- **Topics Tags**: Pill-style tags
- **Speaker-Labeled Transcript**: "SPEAKER_00:", "SPEAKER_01:", etc.
- **Guest Cards**: Profile with badge, org, bio link

**Files to Modify**:
- `src/stages/rendering_stage.py` (enhance HTML generation)
- `src/templates/episode.html` (new - Jinja2 template)

---

### 🔗 **Phase 3: Indices & Navigation** (MEDIUM - 1 day)

From your PART1_PROCESSING_PLAN.md:

#### Task 3.1: Generate Per-Show Index
**Goal**: Create `data/public/series/{show-slug}/index.json`

```json
{
  "show": "Newsroom",
  "episodes": [
    {
      "id": "newsroom-2024-bb580",
      "title": "Episode Topic",
      "date": "2024-10-19",
      "tags": ["AI", "Policy"],
      "url": "/shows/newsroom/newsroom-2024-bb580/"
    }
  ]
}
```

#### Task 3.2: Generate Per-Host Index
**Goal**: Create `data/public/hosts/{host-slug}/index.json`

```json
{
  "host": "Host Name",
  "appearances": [
    {
      "episode_id": "newsroom-2024-bb580",
      "show": "Newsroom",
      "date": "2024-10-19",
      "role": "host"
    }
  ]
}
```

#### Task 3.3: Generate Master Index
**Goal**: Create `data/public/index.json` with all shows, hosts, episodes

---

### ⚡ **Phase 4: Optimization & Polish** (LOW - 1-2 days)

#### Task 4.1: Increase n8n Timeout
**Status**: ✅ Known issue - documented in session
**Fix**: Set HTTP Request node timeout to 600000ms (10 min) or 900000ms (15 min)

#### Task 4.2: Whisper Model Optimization
**Options**:
- Use `base` model (current, ~2-5 min per video)
- Upgrade to `medium` for better accuracy (~5-10 min per video)
- Use `large-v3` for best quality (~10-20 min per video)
- Consider `faster-whisper` for 2-4x speedup

#### Task 4.3: Concurrent Processing
**Current**: Sequential processing (1 video at a time)
**Target**: Process 4 videos concurrently (your config says `max_concurrent_episodes: 4`)
**Fix**: Ensure resource limits don't block (already disabled in session)

#### Task 4.4: Add Progress Reporting
**Goal**: Real-time progress updates for n8n
**Implementation**: WebSocket or SSE endpoint for live progress

---

### 📊 **Phase 5: Testing & Quality** (ONGOING)

From tasks.md, several test tasks marked with `[ ]*`:

#### Tests Needed:
1. Media preparation tests (4.3)
2. Intelligence chain integration tests (6.6)
3. Editorial content tests (7.3)
4. Web artifact tests (8.4)
5. Index generation tests (9.3)
6. Reliability feature tests (10.4)
7. End-to-end pipeline tests (11.3)
8. n8n workflow automation (12.1, 12.2)

**Priority**: Low for now. Focus on functionality first, then add tests.

---

## 🎯 Definition of Done - Part 1 (From Your Plan)

### Current Status:

- [x] All videos discovered from every source path reliably
- [x] Files processed only when stable (unchanged for N minutes)
- [x] Idempotent reruns (unchanged files skipped)
- [x] `.txt` + `.vtt` transcripts generated
- [ ] ❌ Diarized segments with speaker labels
- [ ] ❌ Enriched & scored guests/hosts with badges
- [ ] ❌ Key Takeaway + Summary + tags generated
- [x] `index.html` created (basic version)
- [x] `meta/{episode_id}.json` with complete data (partial)
- [ ] ❌ Per-show episode index JSONs generated
- [ ] ❌ Per-host appearances index JSONs generated
- [x] Clean folder structure in `data/public/`
- [x] Comprehensive logging with success/failure reasons
- [x] Error handling with retries and backoff
- [x] Concurrency controls for resource protection
- [x] Processing stage tracking in SQLite
- [x] **Intelligent crop for clips** (feature/intelligent-crop branch)
  - Face detection and tracking
  - Motion-aware framing
  - Dynamic crop adjustment with smooth transitions
  - Multiple strategies (center, face, motion, hybrid)
  - Configurable via pipeline.yaml
  - Full test suite and documentation

**Overall Progress**: ~60% Complete

---

## 📅 Suggested Timeline

### Week 1 (Current Sprint)
**Focus**: Get AI-enhanced HTML working like generate-html-ai.ps1

**Days 1-2**: Ollama Integration
- Install ollama Python client
- Rewrite enrichment_stage.py with Ollama calls
- Test with one video
- Verify enrichment JSON output

**Day 3**: Enhanced HTML Rendering
- Update rendering_stage.py to use enrichment data
- Add CSS styling (copy from generate-html-ai.ps1)
- Generate one complete AI-enhanced HTML page

**Day 4**: End-to-End Testing
- Process 5-10 videos through full pipeline
- Review generated HTML pages
- Fix bugs, adjust prompts

**Day 5**: Polish & Documentation
- Add indices (show, host, master)
- Update README with examples
- Document Ollama setup

### Week 2 (Advanced Features)
**Focus**: Diarization, Guest Scoring, Optimization

**Days 1-2**: Speaker Diarization
- Choose library (pyannote or faster-whisper)
- Implement speaker segmentation
- Update HTML to show speaker labels

**Days 3-4**: Guest Enrichment
- Entity extraction with Ollama
- Wikipedia/Wikidata lookup
- Badge assignment
- Update HTML with guest cards

**Day 5**: Performance Optimization
- Concurrent processing (test 4 videos at once)
- Whisper model tuning
- Cache Ollama responses

### Week 3+ (Part 2 - Publishing)
From PART1_PROCESSING_PLAN.md:
- RSS feed generation
- Sitemap creation
- Platform integration (Google, Bing, Apple, Perplexity)
- Live site publishing

---

## 🚀 Quick Wins (Do These First)

### 1. **Add Ollama to Enrichment** (Highest Impact)
**Why**: This gets you from basic HTML to professional AI-enhanced pages
**Time**: 1 day
**Effort**: Medium
**Files**: `src/stages/enrichment_stage.py`, `src/utils/ollama_client.py`

### 2. **Update HTML Template** (Visual Impact)
**Why**: Makes output look professional immediately
**Time**: 4 hours
**Effort**: Low (copy from generate-html-ai.ps1)
**Files**: `src/stages/rendering_stage.py`

### 3. **Fix n8n Timeout** (Practical Fix)
**Why**: Prevents workflow errors on long videos
**Time**: 5 minutes
**Effort**: Trivial
**Files**: n8n workflow (UI change)

### 4. **Generate Indices** (Usability)
**Why**: Enables navigation and discovery
**Time**: 4 hours
**Effort**: Medium
**Files**: `src/stages/rendering_stage.py` or new `src/stages/indexing_stage.py`

---

## 📚 Resources & Next Steps

### Documentation to Update:
1. **README.md**: Add "Getting Started" with Ollama setup
2. **ARCHITECTURE.md**: Document new enrichment pipeline
3. **API.md**: Document endpoints for n8n

### Dependencies to Add:
```txt
# Add to requirements.txt
ollama>=0.1.0              # Ollama Python client
pyannote.audio>=3.0.0      # Speaker diarization (optional)
jinja2>=3.1.0              # HTML templating
```

### Configuration to Add:
```yaml
# Add to config/pipeline.yaml
models:
  whisper: "base"
  ollama: "llama3.1:latest"  # NEW
  
enrichment:
  ollama_enabled: true        # NEW
  ollama_host: "localhost"    # NEW
  ollama_port: 11434          # NEW
  summary_max_tokens: 500     # NEW
  takeaways_count: 7          # NEW
```

---

## 🎉 Success Metrics

**Phase 1 Complete When**:
- [ ] AI-enhanced HTML matches quality of generate-html-ai.ps1
- [ ] Executive summary, key takeaways, analysis all auto-generated
- [ ] Processing 10 videos produces 10 professional HTML pages
- [ ] No manual intervention needed

**Phase 2 Complete When**:
- [ ] Speaker diarization working (transcript shows "HOST:", "GUEST:")
- [ ] Guests auto-identified with credentials and badges
- [ ] Indices generated (show, host, master)

**Phase 3 Complete When**:
- [ ] Can process 100+ video backlog overnight
- [ ] All HTML pages ready for publishing
- [ ] Ready to move to Part 2 (RSS, sitemaps, distribution)

---

## 🤝 Let's Get Started!

**Recommended First Task**: 
Implement Ollama-based enrichment (Task 1.1) - this will have the biggest impact on output quality and gets you closest to the generate-html-ai.ps1 quality you already have.

**Want to pair program on it?** I can help you:
1. Set up Ollama client in Python
2. Port the PowerShell prompts
3. Update enrichment_stage.py
4. Test with one video end-to-end

Let me know which task you want to tackle first! 🚀

---

## ✅ Recent Completions

### Intelligent Crop System (Oct 28, 2025)
**Branch**: `feature/intelligent-crop`  
**Status**: Complete - Ready for Testing

Implemented intelligent video cropping for clip generation:
- **Face Detection & Tracking** - OpenCV Haar Cascades for face detection
- **Motion-Aware Framing** - Frame differencing for motion tracking
- **Dynamic Crop Adjustment** - Smooth transitions with exponential moving average
- **Multiple Strategies** - Center, face tracking, motion aware, speaker tracking, hybrid
- **Configuration** - Full YAML config in pipeline.yaml
- **Testing** - Complete test suite in tests/test_intelligent_crop.py
- **Documentation** - Comprehensive guide in docs/INTELLIGENT_CROP.md

**Files Created:**
- `src/core/intelligent_crop.py` (850+ lines)
- `tests/test_intelligent_crop.py` (300+ lines)
- `docs/INTELLIGENT_CROP.md` (500+ lines)

**Files Modified:**
- `src/core/clip_export.py` (integrated intelligent crop)
- `config/pipeline.yaml` (added intelligent_crop section)

**Next Steps:**
- Test with sample videos
- Enable in production (set `intelligent_crop.enabled: true`)
- Monitor performance and accuracy
- Consider deep learning face detection for better accuracy
