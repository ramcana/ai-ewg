# Naming Service Fix Applied

## 🐛 Issues Found

From your test with `FD1314_10-27-25.mp4`:

1. **Episode ID not regenerated** - Stayed as `temp-uploaded-fd1314_10-27-25`
2. **AI didn't extract episode number** - Only got show name "Forum Daily"
3. **spaCy model missing** - Intelligence chain failed with `en_core_web_lg` not found

## ✅ Fixes Applied

### 1. Episode Number Extraction from Filename
**File:** `src/core/pipeline.py` (lines 545-584)

**Change:** Now extracts episode number from filename if AI doesn't provide it

```python
# If no episode number from AI, try to extract from filename
if not episode_number and episode.source and episode.source.path:
    filename = Path(episode.source.path).stem
    # Look for patterns like FD1314, EP140, etc.
    match = re.search(r'(?:FD|EP|E)?(\d{3,4})', filename, re.IGNORECASE)
    if match:
        episode_number = match.group(1)
```

**Result:** For `FD1314_10-27-25.mp4` → extracts `1314`

### 2. ID Regeneration Trigger Relaxed
**Change:** Now triggers with just show name (episode number optional)

```python
# Before: Required both show_name AND episode_number
if enrichment_result.show_name and enrichment_result.episode_number:

# After: Only requires show_name
if enrichment_result.show_name:
```

### 3. spaCy Model Installed
**Command:** `python -m spacy download en_core_web_lg`

**Status:** ✅ Successfully installed

## 🎯 Expected Behavior Now

When you process `FD1314_10-27-25.mp4`:

1. **Discovery:** Creates `temp-uploaded-fd1314_10-27-25`
2. **Enrichment:** 
   - AI extracts: "Forum Daily" (show name)
   - Regex extracts: "1314" (from filename)
   - Generates new ID: `ForumDailyNews_ep1314_2024-10-27`
3. **Logs show:**
   ```
   Extracted episode number from filename: FD1314_10-27-25, episode_number=1314
   Regenerating episode ID with AI metadata:
     old_id=temp-uploaded-fd1314_10-27-25
     new_id=ForumDailyNews_ep1314_2024-10-27
     show_name=Forum Daily
     episode_number=1314
   ```

## 📁 New Folder Structure

After the fix, files will be organized as:

```
data/outputs/ForumDailyNews/2024/ForumDailyNews_ep1314_2024-10-27/
├── clips/
├── html/
└── meta/

data/social_packages/ForumDailyNews/2024/ForumDailyNews_ep1314_2024-10-27/
├── youtube/
├── instagram/
└── tiktok/
```

## 🧪 Testing

### Restart API Server
```powershell
# Stop current server (Ctrl+C)
# Start fresh
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### Process New Episode
1. Upload a new video (or reprocess existing)
2. Watch logs for:
   - `"Extracted episode number from filename"`
   - `"Regenerating episode ID with AI metadata"`
3. Verify new episode ID in database
4. Check folder structure in `data/outputs/`

### Verify Intelligence Chain
The spaCy model should now work, so you'll get:
- ✅ Entity extraction
- ✅ Disambiguation
- ✅ Proficiency scoring

## 📊 Supported Filename Patterns

The regex will extract episode numbers from:

| Filename | Extracted Number |
|----------|------------------|
| `FD1314_10-27-25.mp4` | `1314` |
| `EP140.mp4` | `140` |
| `E025.mp4` | `025` |
| `BB580.mp4` | `580` |
| `CI166.mp4` | `166` |
| `episode_1234.mp4` | `1234` |

Pattern: `(?:FD|EP|E)?(\d{3,4})` matches 3-4 digits optionally preceded by FD, EP, or E.

## 🔄 What Happens to Old Episodes?

**Existing episodes:** Keep old IDs until migration script runs  
**New episodes:** Get new organized structure immediately  
**Reprocessed episodes:** Will get new IDs if enrichment runs again

## ⚠️ Known Limitations

1. **File paths not renamed yet** - Episode ID changes in database, but files stay in old location
2. **Migration needed** - Existing episodes need migration script to reorganize
3. **Episode number format** - Only extracts 3-4 digit numbers

## 🚀 Next Steps

1. **Test the fix** - Process a new episode and verify logs
2. **Verify folder structure** - Check that clips/packages use new paths
3. **Phase 5** - Update API & Dashboard for show-based navigation
4. **Phase 6** - Create migration script for existing episodes

## 📝 Related Files

- `src/core/pipeline.py` - Episode ID regeneration logic
- `src/core/naming_service.py` - Naming conventions
- `src/api/clip_endpoints.py` - Clip paths
- `src/core/package_generator.py` - Social package paths

---

**Status:** Fix Applied ✅  
**Ready to Test:** Yes  
**Date:** October 27, 2025
