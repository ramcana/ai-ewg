# Subprocess Python Environment Fix

## Problem

When the API server spawned subprocess calls to utility scripts (`extract_entities.py`, `diarize.py`, etc.), they were using `"python"` which resolves to the system Python interpreter, not the virtual environment Python. This caused:

1. **spaCy model not found** - Even though `en_core_web_lg` was installed in the venv, subprocesses couldn't find it
2. **Missing dependencies** - Other packages installed in venv were not available to subprocesses
3. **Repeated installation prompts** - Error messages suggesting to reinstall packages that were already installed

## Root Cause

```python
# ❌ WRONG - uses system Python
cmd = ["python", str(script_path), ...]

# ✅ CORRECT - uses venv Python
import sys
cmd = [sys.executable, str(script_path), ...]
```

When you run the API server from within the venv, `sys.executable` points to `d:\n8n\ai-ewg\venv\Scripts\python.exe`, but `"python"` in a subprocess resolves to whatever is in the system PATH (often a different Python installation).

## Solution

### Files Modified

**src/core/intelligence_chain_v2.py**
- Added `import sys` at module level (line 17)
- Replaced all `"python"` with `sys.executable` in subprocess calls:
  - Line 251: Diarization subprocess
  - Line 305: Entity extraction (LLM method)
  - Line 327: Entity extraction (spaCy fallback)
  - Line 374: Disambiguation subprocess
  - Line 425: Proficiency scoring subprocess

**src/core/registry.py**
- Added `update_episode_id()` method (lines 280-312) to handle episode ID migration when AI generates structured IDs

**src/core/pipeline.py**
- Updated enrichment stage (lines 580-590) to call `registry.update_episode_id()` before updating episode object
- This fixes the "Episode not found" error when regenerating IDs with AI metadata

## Testing

1. **Restart the API server**
   ```powershell
   .\start-api-server.ps1
   ```

2. **Process an episode** - The enrichment stage should now:
   - Successfully run entity extraction with spaCy fallback
   - Properly update episode IDs when AI extracts show metadata
   - Save all enrichment data to database

3. **Verify logs** - You should see:
   ```
   ✓ Extracted N candidates
   ✓ Identified N topics
   ✓ Method used: spacy
   ```

## Impact

- ✅ No more "spaCy model not found" errors
- ✅ No more repeated installation prompts
- ✅ Subprocesses use the same Python environment as the main process
- ✅ Episode ID migration works correctly
- ✅ All AI-extracted metadata is saved to database

## Related Issues

- Episode ID mismatch: Fixed by adding `update_episode_id()` method
- Database transaction errors: Fixed by updating ID in database before modifying episode object
- Missing enrichment data: Fixed by proper ID migration flow

## Prevention

**Always use `sys.executable` for subprocess Python calls:**

```python
import sys
import asyncio

# For subprocess calls
cmd = [sys.executable, "script.py", "--arg", "value"]
process = await asyncio.create_subprocess_exec(*cmd, ...)
```

**Never use:**
- `"python"` - resolves to system Python
- `"python3"` - may resolve to different Python version
- Hardcoded paths - not portable across environments
