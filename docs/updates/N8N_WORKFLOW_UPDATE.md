# n8n Workflow Update - AI Enrichment Support

## ✅ Changes Applied

### Updated File: `n8n_workflows/configurable_processing_v2.json`

#### 1. **Status Check Timeout**
- **Node**: "Check Episode Status"
- **Timeout**: 30 seconds (30000ms)
- **Purpose**: Quick status lookup

#### 2. **Processing Timeout** (CRITICAL)
- **Node**: "Process Episode"  
- **Timeout**: **30 minutes (1800000ms)**
- **Purpose**: Full processing with AI enrichment

### Why 30 Minutes?

**Processing Time Breakdown per Video**:
- Transcription (Whisper large-v3): **5-7 minutes**
- **AI Enrichment (Ollama - NEW)**: **8-12 minutes**
  - Executive Summary: ~30-60s
  - Key Takeaways: ~20-40s
  - Deep Analysis: ~30-60s
  - Topics: ~15-30s
  - Segment Titles (20): ~5-10 min
- HTML Generation: **<1 minute**

**Total**: ~15-20 minutes per video

**Timeout**: 30 minutes provides safety margin for:
- Slower systems
- Network delays
- Model loading time
- System resource contention

---

## 🚀 How to Apply Changes

### Option 1: Re-import Workflow (Recommended)

1. Open n8n UI
2. Go to **Workflows**
3. Delete old "Configurable Video Processing v2" workflow
4. Click **Import from File**
5. Select: `n8n_workflows/configurable_processing_v2.json`
6. Save and activate

### Option 2: Manual Update

If you prefer to keep your existing workflow:

1. Open n8n UI
2. Open "Configurable Video Processing v2" workflow
3. Click on **"Check Episode Status"** node
4. Add under Options:
   ```
   Timeout: 30000
   ```

5. Click on **"Process Episode"** node
6. Add under Options:
   ```
   Timeout: 1800000
   ```

7. Add note to "Process Episode" node:
   ```
   30 minute timeout for full processing with AI enrichment
   
   Processing breakdown:
   - Transcription (Whisper): 5-7 min
   - AI Enrichment (Ollama): 8-12 min
   - HTML Generation: <1 min
   
   Total: ~15-20 min per video
   
   Timeout set to 30 min (1800000ms) for safety margin
   ```

8. **Save** the workflow

---

## ⚙️ Alternative Timeout Settings

### Conservative (45 minutes)
For slower systems or when processing multiple videos:
```json
"options": {
  "timeout": 2700000
}
```

### Aggressive (20 minutes)
For fast systems with GPU acceleration:
```json
"options": {
  "timeout": 1200000
}
```

### No Timeout (NOT RECOMMENDED)
Only for development/testing:
```json
"options": {
  "timeout": 0
}
```

⚠️ **Warning**: Setting timeout to 0 or very high values can cause n8n to hang if the API server fails.

---

## 📊 Monitoring Processing Time

### View Processing Duration

After workflow completes, check **"Final Summary"** node output:

```json
{
  "timing": {
    "total_duration": "1234.56s",
    "avg_duration": "123.45s"
  },
  "processed_episodes": [
    {
      "episode_id": "newsroom-2024-bb580",
      "duration": 895.2,  // seconds (~15 min)
      "stage": "rendered"
    }
  ]
}
```

### Logs

Check pipeline logs for detailed timing:
```
[INFO] Enrichment completed (episode_id=newsroom-2024-bb580, processing_time=687.3s, ai_enhanced=true)
```

---

## 🧪 Testing

### Test Single Video with AI Enrichment

1. Make sure Ollama is running:
   ```bash
   ollama list
   ```

2. Set workflow configuration:
   - `folder_path`: Your video folder
   - `target_stage`: `rendered`
   - `force_reprocess`: `true` (to reprocess with AI)

3. Run workflow

4. Monitor execution time in n8n UI

5. Expected result: **15-20 minutes per video**

### Test Without AI (Fallback)

1. Stop Ollama:
   ```bash
   # Stop Ollama service
   ```

2. Run workflow

3. Pipeline should complete with basic enrichment

4. Expected result: **5-8 minutes per video** (no AI enrichment)

---

## 🔍 Troubleshooting

### "Timeout Error" after 10 minutes

**Problem**: Old timeout still active (default 10 min)

**Solution**: 
- Verify timeout is set to 1800000 in workflow JSON
- Re-import workflow to ensure changes applied
- Restart n8n if needed

### Processing Takes Longer Than 30 Minutes

**Possible Causes**:
1. **Slow CPU/No GPU**: Ollama without GPU is much slower
   - Solution: Enable GPU acceleration or use faster model
   
2. **Large Transcripts**: Very long videos (>2 hours)
   - Solution: Increase timeout to 45-60 minutes

3. **System Resource Contention**: Other processes using CPU/RAM
   - Solution: Close other applications or reduce `max_concurrent_episodes`

4. **Model Not Loaded**: First run loads model into memory
   - Solution: First video always slower, subsequent videos faster

### Workflow Hangs/Doesn't Complete

**Problem**: API server crashed or hung

**Solutions**:
1. Check API server logs: `logs/pipeline.log`
2. Restart API server
3. Check system resources (RAM, CPU)
4. Verify Ollama is responding: `ollama list`

---

## 📈 Performance Optimization

### Speed Up Processing

1. **Use GPU Acceleration** (Biggest Impact)
   - Ollama automatically uses CUDA if available
   - Reduces AI time by 50-70%

2. **Use Faster Model**
   ```yaml
   # config/pipeline.yaml
   ollama:
     model: "llama3:latest"  # Faster than llama3.1
   ```

3. **Reduce Concurrent Episodes**
   ```yaml
   processing:
     max_concurrent_episodes: 2  # Less contention
   ```

4. **Disable AI for Testing**
   ```yaml
   enrichment:
     ollama_enabled: false
   ```

---

## 🎯 Expected Behavior

### With AI Enrichment (ollama_enabled: true)
- **Time**: 15-20 min per video
- **Output**: AI-enhanced HTML with summaries, takeaways, analysis, topics
- **Badge**: "AI ENHANCED" visible in HTML

### Without AI Enrichment (ollama_enabled: false)
- **Time**: 5-8 min per video
- **Output**: Basic HTML with transcript
- **Badge**: No AI badge

### Ollama Unavailable (Graceful Fallback)
- **Time**: 5-8 min per video
- **Output**: Basic HTML with transcript
- **Logs**: `"Failed to initialize Ollama, will use basic enrichment"`
- **No Errors**: Pipeline continues successfully

---

## 📋 Checklist

Before running workflow with AI enrichment:

- [ ] Ollama installed and running (`ollama list`)
- [ ] Model pulled (`ollama pull llama3.1:latest`)
- [ ] httpx installed (`pip install httpx`)
- [ ] Config updated (`config/pipeline.yaml`)
- [ ] **Workflow timeout set to 30 min** (this document)
- [ ] API server running (`http://localhost:8000/health`)
- [ ] Test with one video first

---

## 📚 Related Documentation

- **Ollama Setup**: `OLLAMA_SETUP.md`
- **Quick Start**: `QUICK_START_OLLAMA.md`
- **Implementation**: `OLLAMA_IMPLEMENTATION_SUMMARY.md`
- **n8n Testing Guide**: `N8N_TESTING_GUIDE.md`

---

## ✅ Summary

**Updated**: n8n workflow timeout from **10 minutes → 30 minutes**

**Reason**: AI enrichment with Ollama adds 8-12 minutes per video

**Impact**: Workflows will no longer timeout during AI processing

**Next Step**: Re-import workflow and test with one video

🎉 Your n8n workflow is now ready for AI-enhanced processing!
