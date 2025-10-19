# Host Name Display Update

## Changes Made

Added host name extraction and display to the HTML header, along with improved episode metadata formatting.

---

## What Was Added

### 1. Host Name Extraction (`src/core/ollama_client.py`)

**New Method**: `extract_host_name(transcript)`
- Extracts host's full name from transcript introduction
- Uses first 1000 characters (intro typically contains host introduction)
- Returns host name or empty string if not found

**Updated**: `OllamaAnalysis` dataclass
- Added `host_name` field to store extracted host name

**Updated**: `analyze_transcript()` method
- Now extracts both show name AND host name
- Logs both for verification

### 2. Enrichment Storage (`src/stages/enrichment_stage.py`)

**Updated**: Enrichment data structure
- Added `host_name_extracted` at root level
- Added `host_name` in `ai_analysis` section

**Example enrichment JSON**:
```json
{
  "episode_id": "newsroom-2024-bb580",
  "show_name_extracted": "Boom and Bust",
  "host_name_extracted": "Tony Clement",
  "ai_analysis": {
    "show_name": "Boom and Bust",
    "host_name": "Tony Clement",
    ...
  }
}
```

### 3. HTML Header Display (`src/core/web_artifacts.py`)

**Updated**: `_generate_header()` method

**Now displays**:
1. **Show Name** (large text at top)
   - Uses AI-extracted name, falls back to metadata
   
2. **Episode Title** (main heading)

3. **Host Name** (NEW!) 
   - Styled with blue color (#3498db)
   - "Hosted by [Name]" format
   
4. **Episode Metadata**
   - Episode number (e.g., "S1E5" or "Episode 5")
   - Date (e.g., "2024-10-19")
   - Duration (e.g., "45 min")
   - Separated by bullets (•)

**CSS Added**:
```css
.host-info {
    font-size: 1.1rem;
    color: #3498db;
    font-weight: 500;
    margin-bottom: 0.5rem;
}
```

---

## HTML Output Example

### Before:
```html
<header class="header">
  <div class="container">
    <div class="show-title">Newsroom</div>
    <h1 class="episode-title">Episode Title</h1>
    <div class="episode-meta">Season 1, Episode 5 • Published 2024-10-19 • 45 minutes</div>
  </div>
</header>
```

### After:
```html
<header class="header">
  <div class="container">
    <div class="show-title">Boom and Bust</div>
    <h1 class="episode-title">Economic Policy and Tariffs Discussion</h1>
    <div class="host-info">Hosted by Tony Clement</div>
    <div class="episode-meta">Episode 5 • 2024-10-19 • 45 min</div>
  </div>
</header>
```

---

## Visual Layout

```
┌─────────────────────────────────────────┐
│  Boom and Bust                          │ ← Show name (gray, small)
│                                          │
│  Economic Policy and Tariffs Discussion │ ← Episode title (large, bold)
│                                          │
│  Hosted by Tony Clement                 │ ← Host name (blue, medium) ✨ NEW
│                                          │
│  Episode 5 • 2024-10-19 • 45 min       │ ← Metadata (compact)
└─────────────────────────────────────────┘
```

---

## Processing Flow

```
1. Transcription (Whisper)
   └─> Raw transcript

2. Enrichment Stage
   ├─> Extract show name from intro
   ├─> Extract host name from intro ✨ NEW
   ├─> Generate AI analysis
   └─> Save to enrichment JSON

3. Rendering Stage
   ├─> Load enrichment data
   ├─> Get show name (AI-extracted)
   ├─> Get host name (AI-extracted) ✨ NEW
   ├─> Format episode metadata
   └─> Generate HTML header
```

---

## Files Modified

1. **`src/core/ollama_client.py`**
   - Added `extract_host_name()` method
   - Updated `OllamaAnalysis` dataclass
   - Updated `analyze_transcript()` to extract host

2. **`src/stages/enrichment_stage.py`**
   - Store `host_name_extracted` in enrichment JSON

3. **`src/core/web_artifacts.py`**
   - Updated `_generate_header()` to display host name
   - Added `.host-info` CSS styling
   - Improved episode metadata formatting (S1E5 instead of "Season 1, Episode 5")

---

## Testing

After reprocessing, check:

### 1. Enrichment JSON
```bash
# Check if host name was extracted
cat data/enriched/newsroom-2024-bb580.json | grep -A 1 host_name
```

Expected:
```json
"host_name_extracted": "Tony Clement",
"ai_analysis": {
  "host_name": "Tony Clement",
  ...
}
```

### 2. HTML Header
Open `data/public/shows/newsroom/newsroom-2024-bb580/index.html`

Look for:
- ✅ Show name at top (e.g., "Boom and Bust")
- ✅ Episode title as main heading
- ✅ **"Hosted by Tony Clement"** in blue ✨ NEW
- ✅ Episode metadata: "Episode 5 • 2024-10-19 • 45 min"

### 3. Logs
```bash
# Check extraction logs
grep "Extracted host name" logs/pipeline.log
```

Expected:
```
[INFO] Extracted host name: Tony Clement
```

---

## Performance Impact

**Additional Processing Time**: +5-10 seconds per video
- Host name extraction: ~5-10 seconds

**Total AI Enrichment Time**: ~13-22 minutes
- Show name: ~5-10s
- Host name: ~5-10s ✨ NEW
- Executive summary: ~30-60s
- Key takeaways: ~20-40s
- Deep analysis: ~30-60s
- Topics: ~15-30s
- Segment titles: ~5-10 min

---

## Fallback Behavior

If host name cannot be extracted:
- Header section simply won't display host info line
- No errors or broken layout
- Other metadata displays normally

---

## Example from BB580.mp4

Based on transcript intro:
> "Welcome to another episode of Boom and Bust. I'm your host, Tony Clement, here at the News Forum..."

**Extracted**:
- Show name: "Boom and Bust"
- Host name: "Tony Clement"

**Displayed in HTML**:
```
Boom and Bust

Economic Policy Discussion with Thomas Caldwell

Hosted by Tony Clement

Episode 1 • 2024-10-16 • 45 min
```

---

## Status

✅ Host name extraction implemented  
✅ Enrichment storage updated  
✅ HTML header display updated  
✅ CSS styling added  
✅ Episode metadata formatting improved  

**Ready to reprocess and see host names!** 🎉

---

## Next Steps

1. **Reprocess video** with updated code:
   ```bash
   # Via n8n workflow with force_reprocess: true
   ```

2. **Verify extraction** in enrichment JSON

3. **Check HTML** for host name display

4. **Adjust prompts** if extraction accuracy needs improvement
