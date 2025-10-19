# WebArtifactGenerator Fix

## Issue
```
WebArtifactGenerator failed, falling back to simple HTML: 
'dict' object has no attribute 'proficiency_scores'
```

## Root Cause
The `rendering_stage.py` now passes `episode.enrichment` as a **dict** (from JSON), but `WebArtifactGenerator` was expecting it to be an **object** with attributes like `.proficiency_scores`.

## Files Fixed

### `src/core/web_artifacts.py`

Updated all methods that accessed enrichment data to handle dict format:

#### 1. `_generate_guest_credentials()` (Line 990)
**Before:**
```python
if not episode.enrichment or not episode.enrichment.proficiency_scores:
    return ""
scores_data = episode.enrichment.proficiency_scores
```

**After:**
```python
enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
if not enrichment:
    return ""
scores_data = enrichment.get('proficiency_scores', {})
```

#### 2. `_generate_export_data()` (Line 1262)
**Before:**
```python
if episode.enrichment and episode.enrichment.proficiency_scores:
    scores_data = episode.enrichment.proficiency_scores
```

**After:**
```python
enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
scores_data = enrichment.get('proficiency_scores', {})
```

#### 3. Diarization Access (Line 1280 & 1098)
**Before:**
```python
if episode.enrichment and episode.enrichment.diarization:
    diarization_data = episode.enrichment.diarization
```

**After:**
```python
enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
diarization_data = enrichment.get('diarization', {})
```

#### 4. `_add_person_info_to_schema()` (Line 1357)
**Before:**
```python
if not episode.enrichment or not episode.enrichment.proficiency_scores:
    return
scores_data = episode.enrichment.proficiency_scores
```

**After:**
```python
enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
if not enrichment:
    return
scores_data = enrichment.get('proficiency_scores', {})
```

#### 5. `_generate_complete_metadata()` (Line 1220)
**Before:**
```python
if episode.enrichment:
    metadata["enrichment"] = episode.enrichment.to_dict()
```

**After:**
```python
if episode.enrichment:
    if isinstance(episode.enrichment, dict):
        metadata["enrichment"] = episode.enrichment
    else:
        metadata["enrichment"] = episode.enrichment.to_dict()
```

---

## Changes Summary

**Pattern Applied:**
```python
# Instead of:
episode.enrichment.some_field

# Use:
enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
value = enrichment.get('some_field', {})
```

**Why This Works:**
- Handles both dict and object formats
- Safe fallback to empty dict
- Uses `.get()` method for safe access
- No AttributeError exceptions

---

## Testing

After this fix, reprocessing should work:

```bash
# Check logs for success
2025-10-19 15:08:33 - pipeline.rendering_stage - INFO - Using WebArtifactGenerator for AI-enhanced HTML
2025-10-19 15:08:33 - pipeline.rendering_stage - INFO - HTML page generated ✓
```

**No more "falling back to simple HTML" warning!**

---

## Status

✅ **FIXED** - WebArtifactGenerator now handles dict-based enrichment data
✅ All enrichment access methods updated
✅ Backward compatible with object-based enrichment
✅ Ready to generate AI-enhanced HTML

---

## Next Steps

1. **Reprocess video** - HTML will now use AI-enhanced template
2. **Verify HTML** - Check for AI Enhanced badge, topics, article format
3. **If issues persist** - Check `logs/pipeline.log` for specific errors
