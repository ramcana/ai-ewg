# AI Enrichment Utilities

**Python scripts for the guest enrichment pipeline**

---

## 📁 Scripts Overview

### Core Pipeline Scripts

1. **`diarize.py`** - Speaker diarization using pyannote.audio
2. **`extract_entities.py`** - Entity extraction using LLM or spaCy
3. **`disambiguate.py`** - Wikipedia/Wikidata disambiguation
4. **`score_people.py`** - Proficiency/credibility scoring

### Support Scripts

5. **`verify_enrichment_setup.py`** - Verify installation and configuration
6. **`test_enrichment_pipeline.py`** - Test pipeline with sample data
7. **`find_cudnn.py`** - GPU utility (existing)
8. **`verify-gpu.py`** - GPU verification (existing)

---

## 🚀 Quick Start

### 1. Verify Setup

```powershell
python utils/verify_enrichment_setup.py
```

### 2. Test Pipeline

```powershell
python utils/test_enrichment_pipeline.py
```

### 3. Run Full Pipeline

```powershell
# Step 1: Diarize audio
python utils/diarize.py `
    --audio "D:/newsroom/inbox/videos/video.mp4" `
    --segments_out "D:/newsroom/outputs/segments.json" `
    --num_speakers 2

# Step 2: Extract entities (requires transcript)
python utils/extract_entities.py `
    --transcript "D:/newsroom/outputs/transcript.txt" `
    --output "D:/newsroom/outputs/candidates.json"

# Step 3: Disambiguate
python utils/disambiguate.py `
    --candidates "D:/newsroom/outputs/candidates.json" `
    --output "D:/newsroom/outputs/enriched.json"

# Step 4: Score
python utils/score_people.py `
    --enriched "D:/newsroom/outputs/enriched.json" `
    --topics "economics inflation policy" `
    --output "D:/newsroom/outputs/scored.json"
```

---

## 📝 Script Details

### `diarize.py`

**Purpose:** Identify "who spoke when" in audio/video files

**Arguments:**
- `--audio` - Path to audio/video file (required)
- `--segments_out` - Output JSON path (required)
- `--hf_token` - Hugging Face token (or use HF_TOKEN env var)
- `--num_speakers` - Expected number of speakers (optional)
- `--device` - 'cuda' or 'cpu' (default: cuda)
- `--merge_gap` - Max gap to merge segments (default: 2.0s)

**Output:**
```json
{
  "audio_file": "path/to/file.mp4",
  "num_speakers": 2,
  "total_duration": 1847.3,
  "segments": [
    {
      "start": 0.5,
      "end": 12.8,
      "speaker": "SPEAKER_00",
      "duration": 12.3
    }
  ]
}
```

**Requirements:**
- Hugging Face token with pyannote access
- GPU recommended (20x faster than CPU)

---

### `extract_entities.py`

**Purpose:** Extract person names, roles, and organizations from transcript

**Arguments:**
- `--transcript` - Path to transcript file (required)
- `--output` - Output JSON path (required)
- `--model` - Ollama model name (default: mistral)
- `--ollama_url` - Ollama API URL (default: http://localhost:11434)
- `--method` - 'llm' or 'spacy' (default: llm)

**Output:**
```json
{
  "candidates": [
    {
      "name": "Dr. Jane Smith",
      "role_guess": "Chief Economist",
      "org_guess": "Bank of Canada",
      "quotes": ["Dr. Jane Smith from the Bank..."],
      "confidence": 0.85
    }
  ],
  "topics": ["inflation", "monetary policy"]
}
```

**Requirements:**
- **LLM method:** Ollama running with a model installed
- **spaCy method:** spaCy + en_core_web_lg model

---

### `disambiguate.py`

**Purpose:** Match candidates to Wikipedia/Wikidata entities

**Arguments:**
- `--candidates` - Path to candidates JSON (required)
- `--output` - Output JSON path (required)
- `--min_confidence` - Minimum confidence threshold (default: 0.6)

**Output:**
```json
{
  "enriched_people": [
    {
      "wikidata_id": "Q12345",
      "name": "Jane Smith",
      "description": "Canadian economist",
      "job_title": "Chief Economist",
      "affiliation": "Bank of Canada",
      "knows_about": ["monetary policy", "inflation"],
      "wikipedia_url": "https://en.wikipedia.org/wiki/Jane_Smith",
      "same_as": ["https://www.wikidata.org/wiki/Q12345"],
      "confidence": 0.85
    }
  ],
  "topics": ["inflation", "monetary policy"],
  "summary": {
    "total_candidates": 3,
    "enriched_count": 2,
    "success_rate": 0.67
  }
}
```

**Requirements:**
- Internet connection for Wikipedia/Wikidata API
- Rate limited to ~2 requests/second

---

### `score_people.py`

**Purpose:** Calculate credibility scores and assign badges

**Arguments:**
- `--enriched` - Path to enriched people JSON (required)
- `--topics` - Episode topics as space-separated words (optional)
- `--output` - Output JSON path (required)

**Output:**
```json
{
  "scored_people": [
    {
      "name": "Jane Smith",
      "proficiencyScore": 0.86,
      "credibilityBadge": "Verified Expert",
      "reasoning": "Strong role-topic match; authoritative affiliation; well-documented",
      "scoreBreakdown": {
        "roleMatch": 0.30,
        "authorityDomain": 0.25,
        "knowledgeBase": 0.15,
        "publications": 0.10,
        "recency": 0.10,
        "ambiguityPenalty": 0.00
      }
    }
  ],
  "summary": {
    "total_people": 2,
    "avg_score": 0.78,
    "verified_experts": 1,
    "identified_contributors": 1
  }
}
```

**Badge Levels:**
- **0.75-1.00:** ✅ Verified Expert
- **0.60-0.74:** ⚠️ Identified Contributor
- **0.40-0.59:** ℹ️ Guest
- **0.00-0.39:** ❓ Unverified

---

## 🔧 Environment Variables

Create `config/.env`:

```env
# Required
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx

# Optional
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral
DIARIZE_DEVICE=cuda
NEWSROOM_PATH=D:/newsroom
API_RATE_LIMIT_DELAY=0.5
MIN_PUBLISH_SCORE=0.60
MIN_EXPERT_SCORE=0.75
```

Load variables:
```powershell
Get-Content config/.env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
```

---

## 🐛 Troubleshooting

### Issue: ModuleNotFoundError

```powershell
# Install dependencies
pip install -r config/requirements.txt

# Download spaCy model
python -m spacy download en_core_web_lg
```

### Issue: Hugging Face token error

```powershell
# Set token
$env:HF_TOKEN = "hf_xxxxx"

# Verify
python utils/verify_enrichment_setup.py
```

### Issue: Ollama not accessible

```powershell
# Check if running
Get-Process ollama

# Test endpoint
curl http://localhost:11434/api/tags

# Pull model if needed
ollama pull mistral
```

### Issue: CUDA out of memory

```powershell
# Use CPU instead
python utils/diarize.py --audio <file> --segments_out <output> --device cpu
```

---

## 📊 Performance Tips

1. **Use GPU for diarization** - 20x faster than CPU
2. **Use spaCy for extraction if Ollama is slow** - Faster but less accurate
3. **Batch process multiple videos** - Amortize model loading time
4. **Cache guest registry** - Avoid re-enriching known guests

---

## 🔗 Related Documentation

- [ENRICHMENT_SUMMARY.md](../ENRICHMENT_SUMMARY.md) - System overview
- [SETUP_ENRICHMENT.md](../SETUP_ENRICHMENT.md) - Installation guide
- [docs/SPEAKER_DIARIZATION.md](../docs/SPEAKER_DIARIZATION.md) - Diarization details
- [docs/ENTITY_EXTRACTION.md](../docs/ENTITY_EXTRACTION.md) - Extraction methods
- [docs/PROFICIENCY_SCORING.md](../docs/PROFICIENCY_SCORING.md) - Scoring system

---

**Version:** 1.0  
**Last Updated:** October 18, 2025
