# Quick Reference: ai-ewg Pipeline

Fast reference for common operations.

## Installation

```powershell
# Clone and setup
git clone <repo>
cd ai-ewg

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Setup environment
cp config\.env.template config\.env
# Edit config\.env with your API keys
```

## Configuration

**Main config:** `config/pipeline.yaml`  
**Environment:** `config/.env`  
**Validate:** `ai-ewg --config config/pipeline.yaml validate`

## CLI Commands

### Discovery & Database

```powershell
# Initialize database
ai-ewg db init

# Discover videos
ai-ewg discover

# Check database status
ai-ewg db status

# Run migrations
ai-ewg db migrate
```

### Processing Stages

```powershell
# Transcribe (Stage 3)
ai-ewg transcribe --model large-v3 --compute fp16 --device auto

# Transcribe specific episode
ai-ewg transcribe --episode newsroom_2024_s01e042

# Force re-transcription
ai-ewg transcribe --force

# Diarize (Stage 4)
ai-ewg diarize

# Enrich (Stage 5)
ai-ewg enrich entities
ai-ewg enrich disambiguate
ai-ewg enrich score

# Build web pages (Stage 9)
ai-ewg web build

# Build indices (Stage 10)
ai-ewg index build --kind all
```

### Options

```powershell
# Verbose output
ai-ewg --verbose discover

# Custom config
ai-ewg --config custom.yaml transcribe

# Help
ai-ewg --help
ai-ewg transcribe --help
```

## Testing

```powershell
# Fast mini tests (CI)
pytest -m mini

# All tests
pytest

# Specific test file
pytest tests/test_mini.py

# With coverage
pytest --cov=src --cov=utils

# Linting
ruff check .
ruff format .
```

## Output Locations

| Artifact | Location |
|----------|----------|
| Database | `data/pipeline.db` |
| Transcripts (TXT) | `data/transcripts/{episode_id}.txt` |
| Captions (VTT) | `data/transcripts/{episode_id}.vtt` |
| Metadata (JSON) | `data/meta/{episode_id}.json` |
| Web Pages | `data/public/shows/{show}/{episode}/index.html` |
| Logs (JSONL) | `logs/run_{timestamp}.jsonl` |
| Staging | `staging/` |

## n8n Integration

### Execute Command Node

```json
{
  "command": "ai-ewg transcribe --episode {{ $json.episode_id }}",
  "cwd": "D:/n8n/ai-ewg"
}
```

### Parse JSON Output

The last line of stdout is always a JSON summary:

```json
{
  "command": "transcribe",
  "episode_id": "newsroom_2024_s01e042",
  "success": true,
  "duration_seconds": 930.0,
  "stages": {
    "transcription": {
      "status": "completed",
      "duration_seconds": 925.5
    }
  },
  "errors": [],
  "error_count": 0
}
```

### n8n Workflow Example

1. **Watch Folder** → Trigger on new video
2. **Execute Command** → `ai-ewg discover`
3. **Parse JSON** → Extract episode_id
4. **Execute Command** → `ai-ewg transcribe --episode {{ $json.episode_id }}`
5. **Parse JSON** → Check success
6. **Conditional** → If success, continue
7. **Execute Command** → `ai-ewg web build --episode {{ $json.episode_id }}`

## Environment Variables

```bash
# Required
HF_TOKEN=hf_...                    # HuggingFace token for diarization

# Optional
WHISPER_MODEL=large-v3             # Whisper model size
WHISPER_DEVICE=auto                # auto, cuda, cpu
WHISPER_COMPUTE_TYPE=float16       # int8, float16, float32
DIARIZE_DEVICE=cuda                # cuda, cpu
OLLAMA_URL=http://localhost:11434  # Ollama server
MAX_CONCURRENT_EPISODES=4          # Parallel processing limit
LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
```

## Common Issues

### "No videos discovered"
- Check `config/pipeline.yaml` sources paths
- Verify paths exist and are accessible
- Check file patterns match your videos

### "CUDA out of memory"
- Reduce `MAX_GPU_CONCURRENT` to 1
- Use smaller Whisper model: `--model base`
- Use int8 compute: `--compute int8`
- Set `WHISPER_DEVICE=cpu` to force CPU

### "HuggingFace token required"
- Get token: https://huggingface.co/settings/tokens
- Add to `config/.env`: `HF_TOKEN=hf_...`
- Or set environment: `$env:HF_TOKEN="hf_..."`

### "Database locked"
- Close other processes using the database
- Check `data/pipeline.db-wal` and `data/pipeline.db-shm`
- Restart if needed

## Performance Tips

### GPU Optimization
- Use `large-v3` model with RTX 4080
- Use `float16` compute type
- Keep `MAX_GPU_CONCURRENT=1` to avoid OOM
- Process multiple episodes sequentially

### CPU Fallback
- Use `base` or `small` model
- Use `int8` compute type
- Increase `MAX_CONCURRENT_EPISODES` to 4-8

### Network Drives
- Enable staging: `staging.enabled: true`
- Increase `discovery.stability_minutes` to 10
- Use absolute paths in config

## File Structure

```
ai-ewg/
├── config/
│   ├── pipeline.yaml          # Main configuration
│   ├── .env                   # Secrets (gitignored)
│   └── .env.template          # Template
├── data/
│   ├── pipeline.db            # SQLite registry
│   ├── transcripts/           # TXT and VTT files
│   ├── meta/                  # Episode JSON
│   └── public/                # Web artifacts
├── logs/
│   └── run_*.jsonl            # Structured logs
├── src/
│   ├── ai_ewg/
│   │   └── cli.py             # CLI entry point
│   └── core/
│       ├── settings.py        # Pydantic config
│       ├── registry.py        # SQLite registry
│       ├── transcription_engine.py  # Faster-Whisper
│       └── structured_logging.py    # JSONL logging
├── tests/
│   ├── test_mini.py           # Fast CI tests
│   └── data/mini/             # Test fixtures
├── pyproject.toml             # Package config
├── requirements.txt           # Dependencies
└── README.md                  # Documentation
```

## Processing Stages

| Stage | Command | Input | Output |
|-------|---------|-------|--------|
| 1. Discovery | `discover` | Video files | Registry entries |
| 2. Normalize | `normalize` | Registry | Metadata |
| 3. Transcribe | `transcribe` | Video/audio | TXT, VTT |
| 4. Diarize | `diarize` | Audio | Speaker labels |
| 5a. Extract | `enrich entities` | Transcript | Named entities |
| 5b. Disambiguate | `enrich disambiguate` | Entities | Wikidata links |
| 5c. Score | `enrich score` | Entities | Proficiency scores |
| 6. Editorial | (future) | All data | Summary, takeaways |
| 9. Web | `web build` | All data | HTML pages |
| 10. Index | `index build` | HTML pages | Indices, sitemap |

## Registry States

Episodes progress through these states:

1. `new` → Discovered
2. `staged` → Copied to staging
3. `transcribed` → Audio transcribed
4. `diarized` → Speakers identified
5. `entities_extracted` → Named entities found
6. `disambiguated` → Entities matched to knowledge bases
7. `scored` → Proficiency scores calculated
8. `enriched` → Editorial content generated
9. `rendered` → HTML pages built
10. `indexed` → Added to indices

Query by state:
```sql
SELECT * FROM episodes WHERE stage = 'transcribed';
```

## Logs and Debugging

### Console Logs
- Colored output with Rich
- Progress bars and status
- Error messages with context

### JSONL Logs
- Location: `logs/run_{timestamp}.jsonl`
- One JSON object per line
- Parse with: `jq` or Python

### Example: Find errors
```powershell
# PowerShell
Get-Content logs\run_*.jsonl | ConvertFrom-Json | Where-Object { $_.level -eq "error" }

# Bash
cat logs/run_*.jsonl | jq 'select(.level == "error")'
```

## Support

- **Documentation:** `docs/`
- **Issues:** GitHub Issues
- **Architecture:** `docs/architecture/N8N_ARCHITECTURE_EXPLAINED.md`
- **Output Specs:** `docs/OUTPUT_SPECS.md`
- **Implementation:** `IMPLEMENTATION_SUMMARY.md`
