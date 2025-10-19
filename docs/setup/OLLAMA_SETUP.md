# Ollama Setup Guide for AI-Enhanced Transcripts

## Overview

This pipeline uses **Ollama** to generate AI-enhanced content for video transcripts:
- **Executive Summaries** (2-3 paragraphs)
- **Key Takeaways** (5-7 bullet points)
- **Deep Analysis** (themes, implications, impact)
- **Topics/Keywords** (8-10 tags)
- **Segment Titles** (AI-generated for each chunk)

## Installation

### 1. Install Ollama

#### Windows:
```powershell
# Download and run the installer from https://ollama.ai
# Or use winget:
winget install Ollama.Ollama
```

#### macOS:
```bash
curl https://ollama.ai/install.sh | sh
```

#### Linux:
```bash
curl https://ollama.ai/install.sh | sh
```

### 2. Install Recommended Model

We recommend **llama3.1:latest** for best news analysis quality:

```bash
ollama pull llama3.1:latest
```

**Alternative models** (if llama3.1 is too slow):
```bash
# Faster, slightly lower quality:
ollama pull llama3:latest

# Smallest/fastest (development only):
ollama pull mistral:latest
```

### 3. Verify Ollama is Running

```bash
# Check Ollama status
ollama list

# Test generation
ollama run llama3.1:latest "Say hello"
```

Expected output: Ollama should respond with a greeting.

## Configuration

Update `config/pipeline.yaml`:

```yaml
# Ollama configuration for AI enrichment
ollama:
  enabled: true  # Set to false to disable AI enrichment
  host: "http://localhost:11434"  # Default Ollama host
  model: "llama3.1:latest"  # Model to use
  timeout: 300  # 5 minutes for AI generation
  
# Enrichment configuration
enrichment:
  ollama_enabled: true
  summary_max_tokens: 500
  takeaways_count: 7
  topics_count: 10
  segment_chunk_size: 10
```

## Testing

### Test Ollama Client

```python
python -c "from src.core.ollama_client import OllamaClient; client = OllamaClient(); print(client.generate('Hello, how are you?'))"
```

Expected: Ollama should generate a response.

### Test Full Enrichment

Process a single video through the pipeline:

```powershell
# PowerShell
python -m src.cli process --episode-id "test-episode-id"
```

Check the output in `data/enriched/{episode_id}.json` for AI-generated content.

## Performance

### Processing Time Estimates

With **llama3.1:latest** on typical hardware:
- Executive Summary: ~30-60 seconds
- Key Takeaways: ~20-40 seconds
- Deep Analysis: ~30-60 seconds
- Topics: ~15-30 seconds
- Segment Titles (20 segments): ~5-10 minutes

**Total per episode**: ~8-12 minutes for AI enrichment

### Optimization Tips

1. **Use GPU acceleration** (if available):
   - Ollama automatically uses GPU if CUDA/ROCm is installed
   - Reduces processing time by 50-70%

2. **Reduce model size** for faster processing:
   ```yaml
   ollama:
     model: "llama3:latest"  # Smaller, faster model
   ```

3. **Adjust timeout** if needed:
   ```yaml
   ollama:
     timeout: 600  # 10 minutes for slower systems
   ```

## Troubleshooting

### "Cannot connect to Ollama"

**Problem**: Pipeline can't reach Ollama server

**Solutions**:
1. Check if Ollama is running:
   ```bash
   ollama list
   ```

2. Restart Ollama service:
   ```bash
   # Windows: Restart from System Tray
   # macOS/Linux:
   systemctl restart ollama
   ```

3. Verify host/port in config:
   ```yaml
   ollama:
     host: "http://localhost:11434"
   ```

### "Model not found"

**Problem**: Requested model isn't pulled

**Solution**:
```bash
# Pull the model specified in your config
ollama pull llama3.1:latest
```

### "Request timed out"

**Problem**: AI generation taking too long

**Solutions**:
1. Increase timeout in config:
   ```yaml
   ollama:
     timeout: 600  # 10 minutes
   ```

2. Use a smaller/faster model:
   ```yaml
   ollama:
     model: "mistral:latest"
   ```

3. Check system resources (CPU/RAM)

### Fallback to Basic Enrichment

If Ollama is unavailable, the pipeline automatically falls back to basic enrichment without AI features:

```
[INFO] Failed to initialize Ollama, will use basic enrichment
[INFO] Using basic enrichment (Ollama unavailable)
```

The pipeline will continue processing, but generated HTML won't include:
- AI-generated summaries
- Key takeaways
- Deep analysis
- AI-extracted topics

## Examples

### Generated Content Sample

**Executive Summary**:
> This episode explores the intersection of artificial intelligence and energy policy in Canada. The discussion covers recent developments in AI data center requirements, renewable energy infrastructure challenges, and potential policy frameworks for sustainable AI deployment. Key experts provide insights into balancing technological advancement with environmental responsibility.

**Key Takeaways**:
1. AI data centers require unprecedented energy infrastructure investment
2. Canada's renewable energy capacity needs 40% expansion by 2030
3. Policy frameworks for AI energy use are still in early development
4. Grid stability concerns emerge with concentrated AI workload deployment
5. Public-private partnerships show promise for sustainable AI infrastructure

**Topics**: AI Infrastructure, Energy Policy, Renewable Energy, Data Centers, Climate Impact, Grid Stability, Policy Development, Sustainable Technology

## Model Comparison

| Model | Size | Speed | Quality | Recommended For |
|-------|------|-------|---------|----------------|
| llama3.1:latest | 8GB | Medium | Excellent | Production use |
| llama3:latest | 7GB | Fast | Very Good | Balanced performance |
| mistral:latest | 7GB | Very Fast | Good | Development/testing |
| llama2:latest | 7GB | Fast | Good | Legacy compatibility |

## API Reference

### OllamaClient Methods

```python
from src.core.ollama_client import OllamaClient

# Initialize client
client = OllamaClient(
    host="http://localhost:11434",
    model="llama3.1:latest",
    timeout=300
)

# Generate executive summary
summary = client.generate_executive_summary(transcript_text)

# Extract key takeaways
takeaways = client.extract_key_takeaways(transcript_text, count=7)

# Generate deep analysis
analysis = client.generate_deep_analysis(transcript_text)

# Extract topics
topics = client.extract_topics(transcript_text, count=10)

# Complete analysis (all of the above)
result = client.analyze_transcript(transcript_text, episode_id)
```

## Disable AI Enrichment

To process videos without AI enrichment:

```yaml
# config/pipeline.yaml
enrichment:
  ollama_enabled: false
```

Or via environment variable:
```bash
export OLLAMA_ENABLED=false
```

## Next Steps

1. ✅ Install Ollama and pull llama3.1:latest
2. ✅ Update config/pipeline.yaml with Ollama settings
3. ✅ Test with a single video
4. ✅ Review generated HTML for AI enhancements
5. Process your video library!

## Resources

- **Ollama Website**: https://ollama.ai
- **Ollama Models**: https://ollama.ai/library
- **Ollama GitHub**: https://github.com/ollama/ollama
- **Model Benchmarks**: https://ollama.ai/benchmarks

## Support

If you encounter issues:
1. Check logs in `logs/pipeline.log`
2. Verify Ollama is running: `ollama list`
3. Test model directly: `ollama run llama3.1:latest "test"`
4. Review config: `cat config/pipeline.yaml`

The pipeline is designed to gracefully handle Ollama failures and will continue processing with basic enrichment if AI features are unavailable.
