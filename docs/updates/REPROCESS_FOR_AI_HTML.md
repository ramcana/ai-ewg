# Reprocess Video for AI-Enhanced HTML

## Problem
The enrichment JSON contains AI analysis, but the HTML was generated with old code that doesn't display it.

## Solution
Force reprocess the **rendering stage only** to regenerate HTML with new AI-enhanced code.

---

## Quick Fix: Reprocess Just Rendering

### Option 1: Via n8n (Recommended)

1. Open n8n workflow "Configurable Video Processing v2"
2. Update configuration:
   ```
   folder_path: D:/n8n/TNF-Transcripts/test_videos/newsroom/2024
   target_stage: rendered
   force_reprocess: true  ← Keep this true
   ```
3. Run workflow
4. Check new HTML at: `data/public/shows/newsroom/newsroom-2024-bb580/index.html`

### Option 2: Via Python CLI

```powershell
# Reprocess just the rendering stage
python -m src.cli process --episode-id "newsroom-2024-bb580" --target-stage rendered --force-reprocess
```

### Option 3: Quick Workaround - Delete HTML

```powershell
# Delete the HTML so it gets regenerated
Remove-Item "data\public\shows\newsroom\newsroom-2024-bb580\index.html" -Force

# Run workflow again (force_reprocess can be false)
```

---

## What Changed

### Before (Old rendering_stage.py)
- Used simple HTML template
- Ignored AI enrichment data
- Only showed basic transcript

### After (New rendering_stage.py)
- Uses `WebArtifactGenerator` 
- Loads AI enrichment from JSON
- Displays AI-enhanced content:
  - 🎨 "AI ENHANCED" badge
  - 📋 Executive Summary
  - ✨ Key Takeaways
  - 🔍 Deep Analysis
  - 🏷️ Topics

---

## Verify It Worked

After reprocessing, check logs:

```powershell
Get-Content logs\pipeline.log | Select-String "newsroom-2024-bb580" | Select-String -Pattern "rendering|ai_enhanced|WebArtifact"
```

Look for:
```
[INFO] Starting rendering with AI enrichment (episode_id=newsroom-2024-bb580)
[INFO] Enrichment data loaded (ai_enhanced=true, has_ai_analysis=true)
[INFO] Using WebArtifactGenerator for AI-enhanced HTML
[INFO] HTML page generated
```

Then open the HTML and verify you see:
- Purple "AI ENHANCED" badge at top
- Blue "Executive Summary" box
- Green "Key Takeaways" list
- Orange "Deep Analysis" box
- Gray topic tags

---

## If It Still Doesn't Work

Check the output paths match:

```powershell
# Where enrichment is stored
Get-Item "data\enriched\newsroom-2024-bb580.json"

# Where HTML is generated
Get-Item "data\public\shows\newsroom\newsroom-2024-bb580\index.html"
```

Both should exist. If HTML still shows old content, check browser cache (hard refresh: Ctrl+F5).
