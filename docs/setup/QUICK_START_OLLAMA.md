# 🚀 Quick Start: AI-Enhanced Transcripts

## 5-Minute Setup

### 1. Install Ollama (2 minutes)
```bash
# Windows
winget install Ollama.Ollama

# Mac/Linux
curl https://ollama.ai/install.sh | sh
```

### 2. Pull Model (3 minutes)
```bash
ollama pull llama3.1:latest
```

### 3. Install Python Dependency (30 seconds)
```bash
pip install httpx>=0.27.0
```

### 4. Test (30 seconds)
```python
python -c "from src.core.ollama_client import OllamaClient; client = OllamaClient(); print('✅ Ollama connected!')"
```

### 5. Process Video
```bash
# Run your existing pipeline - AI enrichment is automatic!
python -m src.cli process --episode-id "your-episode-id"
```

---

## What You Get

### Before (Basic):
```
Episode Title
Date | Duration
Raw transcript text...
```

### After (AI-Enhanced):
```
🎨 AI ENHANCED

📋 Executive Summary
This episode explores the intersection of artificial 
intelligence and energy policy...

✨ Key Takeaways
• AI data centers require unprecedented energy investment
• Canada's renewable capacity needs 40% expansion by 2030
• Policy frameworks still in early development
...

🔍 Deep Analysis
The discussion reveals critical intersections between 
technological advancement and environmental responsibility...

🏷️ Topics
AI Infrastructure | Energy Policy | Renewable Energy | 
Data Centers | Climate Impact | Grid Stability
```

---

## Performance

⏱️ **Processing Time**: ~8-12 minutes per episode for AI enrichment
💻 **GPU Acceleration**: Automatic (if CUDA available)
📊 **Quality**: Professional news analysis matching `generate-html-ai.ps1`

---

## Troubleshooting

**"Cannot connect to Ollama"**
```bash
ollama list  # Check if running
```

**"Model not found"**
```bash
ollama pull llama3.1:latest
```

**Too slow?**
```yaml
# config/pipeline.yaml
ollama:
  model: "llama3:latest"  # Faster alternative
```

---

## Full Documentation

- 📖 **Setup Guide**: `OLLAMA_SETUP.md`
- 📝 **Implementation Details**: `OLLAMA_IMPLEMENTATION_SUMMARY.md`
- 🗺️ **Roadmap**: `ROADMAP.md`

---

## Support

✅ **Pipeline continues working even if Ollama is unavailable**  
✅ **Automatic fallback to basic enrichment**  
✅ **No breaking changes to existing code**

**Ready to test?** Process your first AI-enhanced video now! 🎉
