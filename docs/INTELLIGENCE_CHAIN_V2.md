# Intelligence Chain V2 - Architecture & Usage

## Overview

Intelligence Chain V2 is a rock-solid, cacheable, and auditable upgrade to the AI processing pipeline. It implements the four-stage enrichment flow (diarization → entity extraction → disambiguation → proficiency scoring) with enterprise-grade reliability features.

## Key Improvements

### 1. **Typed I/O with Schema Versioning**

All data structures use **pydantic models** with immutable schemas:

```python
from core.intelligence_models import DiarizationResult, EntitiesResult

# Every artifact includes schema_version: "ic-1.0.0"
result = DiarizationResult(
    schema_version="ic-1.0.0",
    audio_file="path/to/audio.mp4",
    num_speakers=2,
    segments=[...]
)
```

**Benefits:**
- Prevents "silent" shape drift between releases
- Enables schema migration strategies
- Type-safe interfaces between steps

### 2. **Content-Addressed Caching**

Deterministic caching using `video_hash + config_hash`:

```
data/cache/{step_name}/{video_hash}-{config_hash}-{step_version}.json
data/cache/{step_name}/{video_hash}-{config_hash}-{step_version}.provenance.json
```

**Cache Key Components:**
- `video_hash`: SHA256 of audio track (first 10MB + last 10MB + file size)
- `config_hash`: SHA256 of configuration affecting the step
- `step_version`: Semantic version of step implementation

**Provenance Metadata:**
```json
{
  "cache_key": "diarization-abc123...-def456...-1.0.0",
  "created_at": "2025-10-21T22:30:00Z",
  "duration_ms": 45230,
  "input_hash": "...",
  "output_hash": "..."
}
```

### 3. **DAG-Based Execution**

Steps are registered with explicit dependencies:

```python
registry.register(StepDefinition(
    name="disambiguate",
    executor=disambiguate_func,
    result_type=ResolutionResult,
    requires=["extract_entities"],  # Dependency
    version="1.0.0"
))
```

**Execution Features:**
- Topological sort ensures correct order
- `--from-step` resumes from middle (uses cached earlier steps)
- `--until-step` stops early for partial runs
- Parallel fan-out ready (future enhancement)

### 4. **Provenance & Explainability**

Every job produces three artifacts:

**`meta/{job_id}.json`** - Execution metadata:
```json
{
  "job_id": "episode-123-abc",
  "video_hash": "...",
  "started_at": "...",
  "total_duration_ms": 67890,
  "steps_completed": ["diarization", "extract_entities", ...],
  "steps_cached": ["diarization"],
  "cache_hits": 1,
  "cache_misses": 3,
  "metrics": [
    {
      "step_name": "diarization",
      "duration_ms": 45230,
      "cache_hit": false,
      "output_hash": "..."
    }
  ],
  "warnings": []
}
```

**`meta/{job_id}.explain.json`** - Explainability payload:
```json
{
  "job_id": "episode-123-abc",
  "schema_version": "ic-1.0.0",
  "diarization_explain": {
    "num_speakers": 2,
    "validation": {...},
    "consistency": {...}
  },
  "disambiguation_explain": {
    "decisions": [
      {
        "name": "Jane Smith",
        "confidence": 0.87,
        "authority_level": "high",
        "decision_rule": "Overlap(name) + Context(topic)=0.78 > 0.65",
        "candidates_considered": 3
      }
    ]
  },
  "decision_traces": [...]
}
```

**`meta/{job_id}.quality.json`** - Quality assessment:
```json
{
  "overall_quality": "good",
  "steps": {
    "diarization": {
      "passed": true,
      "quality_level": "excellent",
      "issues": []
    },
    "extract_entities": {
      "passed": true,
      "quality_level": "good",
      "issues": ["Few topics extracted (2)"]
    }
  },
  "recommendations": []
}
```

### 5. **Quality Gates (Fail-Soft)**

Each step has quality validation that **warns but doesn't block**:

| Step | Quality Checks | Fail-Soft Behavior |
|------|----------------|-------------------|
| **Diarization** | Min segments, speaker count, consistency | Continue with mono-speaker fallback |
| **Entities** | Min candidates, confidence distribution | Continue with low-confidence entities marked |
| **Disambiguation** | Success rate, authority verification | Continue with partial enrichment |
| **Proficiency** | Score distribution, verified experts | Continue (scoring is informational) |

**Quality Levels:**
- `excellent` - No issues
- `good` - Minor issues (1-2)
- `acceptable` - Some issues (3-4)
- `degraded` - Many issues but usable
- `failed` - Unusable output

### 6. **Strong Provenance for Entities**

Every resolved entity includes:

```python
EntityResolution(
    original_name="Jane Smith",
    wikidata_id="Q12345",
    confidence=0.87,
    
    # Evidence trail
    evidence=[
        EntityEvidence(
            source="NER",
            text="Jane Smith, economist at...",
            timestamp_range=(45.2, 52.8),
            score=0.9
        )
    ],
    
    # Candidates considered
    candidates_considered=[
        DisambiguationCandidate(
            qid="Q12345",
            label="Jane Smith (economist)",
            score=0.87
        ),
        DisambiguationCandidate(
            qid="Q67890",
            label="Jane Smith (politician)",
            score=0.43
        )
    ],
    
    # Decision rule
    decision_rule="Overlap(name) + Context(topic)=0.78 > 0.65"
)
```

## Usage

### CLI Tool

```bash
# Basic run
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt

# Force rerun (ignore cache)
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt \
  --force

# Resume from middle step
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt \
  --from-step disambiguate

# Partial run (stop early)
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt \
  --until-step extract_entities

# Cache management
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt \
  --show-cache-stats \
  --clear-cache

# Clear specific step cache
python scripts/run_intelligence_chain.py \
  --audio path/to/video.mp4 \
  --transcript path/to/transcript.txt \
  --clear-step-cache diarization
```

### Programmatic API

```python
from core.intelligence_chain_v2 import IntelligenceChainOrchestratorV2
from core.config import PipelineConfig

# Initialize
config = PipelineConfig(...)
orchestrator = IntelligenceChainOrchestratorV2(config)

# Run chain
result = await orchestrator.process_episode(
    episode=episode_obj,
    audio_path="path/to/audio.mp4",
    transcript_text="Full transcript...",
    force_rerun=False,
    start_from_step=None,
    stop_at_step=None
)

# Check results
if result.success:
    print(f"Diarization: {result.diarization.num_speakers} speakers")
    print(f"Entities: {len(result.entities.candidates)} candidates")
    print(f"Enriched: {len(result.resolution.enriched_people)} people")
    print(f"Scored: {len(result.proficiency.scored_people)} people")
    
    # Access metadata
    print(f"Cache hits: {result.metadata.cache_hits}")
    print(f"Duration: {result.metadata.total_duration_ms}ms")
else:
    print(f"Failed at: {result.error_step}")
    print(f"Error: {result.error}")
```

## Cache Management

### View Cache Stats

```python
stats = orchestrator.get_cache_stats()
# {
#   'total_files': 42,
#   'total_size_bytes': 15728640,
#   'steps': {
#     'diarization': {'files': 10, 'size_bytes': 5242880},
#     'extract_entities': {'files': 12, 'size_bytes': 4194304},
#     ...
#   }
# }
```

### Clear Cache

```python
# Clear all cache
count = orchestrator.clear_cache()

# Clear specific step
count = orchestrator.clear_cache('diarization')
```

### Cache Invalidation

Cache automatically invalidates when:
- Video file changes (different hash)
- Configuration changes (different config_hash)
- Step version changes (code update)
- `--force` flag is used

## Quality Assessment

### Reading Quality Reports

```python
import json

with open(f'data/meta/{job_id}.quality.json') as f:
    quality = json.load(f)

overall = quality['overall_quality']  # excellent, good, acceptable, degraded, failed

for step_name, step_quality in quality['steps'].items():
    print(f"{step_name}: {step_quality['quality_level']}")
    for issue in step_quality['issues']:
        print(f"  - {issue}")
```

### Recommendations

Quality reports include actionable recommendations:

```json
{
  "recommendations": [
    {
      "step": "diarization",
      "strategy": "Continue but flag for manual review"
    }
  ]
}
```

## Explainability & Debugging

### Decision Traces

Every disambiguation decision is logged:

```python
with open(f'data/meta/{job_id}.explain.json') as f:
    explain = json.load(f)

for decision in explain['disambiguation_explain']['decisions']:
    print(f"{decision['name']}: {decision['confidence']:.2f}")
    print(f"  Rule: {decision['decision_rule']}")
    print(f"  Candidates: {decision['candidates_considered']}")
```

### Score Breakdowns

Proficiency scores include detailed breakdowns:

```python
for person in explain['proficiency_explain']['score_details']:
    print(f"{person['name']}: {person['score']:.2f}")
    print(f"  Badge: {person['badge']}")
    print(f"  Breakdown:")
    for criterion, score in person['breakdown'].items():
        print(f"    {criterion}: {score:.3f}")
    print(f"  Reasoning: {person['reasoning']}")
```

## Integration with Existing Pipeline

### Drop-in Replacement

V2 orchestrator is designed as a drop-in replacement:

```python
# Old
from core.intelligence_chain import IntelligenceChainOrchestrator
orchestrator = IntelligenceChainOrchestrator(config)

# New
from core.intelligence_chain_v2 import IntelligenceChainOrchestratorV2
orchestrator = IntelligenceChainOrchestratorV2(config)

# Same interface
result = await orchestrator.process_episode(episode, audio_path, transcript_text)
```

### Backward Compatibility

V2 uses adapters to convert legacy JSON outputs to typed models, so existing utility scripts (`diarize.py`, `extract_entities.py`, etc.) work without modification.

## Golden Test Set

Create a golden set for regression testing:

```bash
# Run on golden episodes
for episode in golden_set/*.mp4; do
    python scripts/run_intelligence_chain.py \
        --audio "$episode" \
        --transcript "${episode%.mp4}.txt" \
        --output-dir golden_results
done

# Compare outputs
python scripts/compare_golden_results.py \
    --expected golden_expected/ \
    --actual golden_results/
```

## Performance Characteristics

| Step | Typical Duration | Cache Hit Speed |
|------|-----------------|----------------|
| Diarization | 30-60s | <100ms |
| Entity Extraction (LLM) | 10-30s | <50ms |
| Entity Extraction (spaCy) | 2-5s | <50ms |
| Disambiguation | 5-15s | <50ms |
| Proficiency Scoring | 1-3s | <50ms |

**Cache Hit Rate:** Typically 70-90% on reruns with same config.

## Troubleshooting

### Cache Not Working

Check cache key components:
```python
print(f"Video hash: {context.video_hash}")
print(f"Config hash: {context.config_hash}")
```

Ensure configuration hasn't changed between runs.

### Quality Gate Failures

Review quality report:
```bash
cat data/meta/{job_id}.quality.json
```

Check recommendations for fallback strategies.

### Missing Explainability Data

Ensure step completed successfully:
```bash
cat data/meta/{job_id}.json | jq '.steps_completed'
```

## Future Enhancements

1. **Parallel Execution** - Run independent steps (diarization + entities) in parallel
2. **Streaming Diarization** - Process audio in chunks for memory efficiency
3. **Pluggable NER** - Swap spaCy/HF pipelines via config
4. **Local People Registry** - Override Wikidata for frequent guests
5. **Temporal Alignment** - Map entity mentions to precise timestamps for web UI
6. **Metrics Export** - Prometheus/GA4 integration for throughput monitoring

## Files Created

### Core Infrastructure
- `src/core/intelligence_models.py` - Typed pydantic models
- `src/core/intelligence_cache.py` - Content-addressed caching
- `src/core/intelligence_executor.py` - Step execution orchestrator
- `src/core/intelligence_quality.py` - Quality gates
- `src/core/intelligence_adapters.py` - Legacy JSON adapters
- `src/core/intelligence_chain_v2.py` - Main orchestrator

### Tools
- `scripts/run_intelligence_chain.py` - CLI tool

### Documentation
- `docs/INTELLIGENCE_CHAIN_V2.md` - This file

## Migration Guide

### From V1 to V2

1. **Update imports:**
   ```python
   from core.intelligence_chain_v2 import IntelligenceChainOrchestratorV2
   ```

2. **Initialize with config:**
   ```python
   orchestrator = IntelligenceChainOrchestratorV2(config)
   ```

3. **Call with same interface:**
   ```python
   result = await orchestrator.process_episode(episode, audio_path, transcript)
   ```

4. **Access typed results:**
   ```python
   # V1: result.diarization.data (dict)
   # V2: result.diarization (DiarizationResult)
   
   num_speakers = result.diarization.num_speakers  # Type-safe!
   ```

### Gradual Rollout

1. Run V2 in parallel with V1 for validation
2. Compare outputs using quality reports
3. Switch to V2 once confidence is high
4. Deprecate V1 after migration period

## Support

For questions or issues:
- Check quality reports: `data/meta/{job_id}.quality.json`
- Review explainability: `data/meta/{job_id}.explain.json`
- Examine metadata: `data/meta/{job_id}.json`
- Enable debug logging: Set `PIPELINE_LOG_LEVEL=DEBUG`
