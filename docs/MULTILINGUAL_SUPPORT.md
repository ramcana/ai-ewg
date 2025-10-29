# Multilingual Support Documentation

## Overview

AI-EWG now supports multilingual transcription with automatic language detection, translation capabilities, and comprehensive language validation. This feature enables processing of international news content in multiple languages.

## Features

### ✅ Automatic Language Detection
- Whisper automatically detects the spoken language
- Supports 10+ major languages out of the box
- Fallback to English if detection fails

### ✅ Translation Support
- Optional translation to English for non-English content
- Preserves original language metadata
- Configurable translation behavior

### ✅ Language Validation
- Validates detected languages against supported list
- Configurable supported languages
- Graceful handling of unsupported languages

### ✅ Enhanced Metadata
- Stores detected language information
- Tracks translation status
- Preserves original language detection

## Configuration

### Pipeline Configuration (`config/pipeline.yaml`)

```yaml
# Multilingual transcription configuration
transcription:
  language: "auto"  # Auto-detect language, or specify: en, es, fr, de, it, pt, etc.
  translate_to_english: false  # Set true to translate non-English audio to English
  task: "transcribe"  # Options: "transcribe" or "translate"
  supported_languages:
    - en  # English
    - es  # Spanish
    - fr  # French
    - de  # German
    - it  # Italian
    - pt  # Portuguese
    - ru  # Russian
    - ja  # Japanese
    - ko  # Korean
    - zh  # Chinese
  fallback_language: "en"  # Fallback if detection fails
```

### Configuration Options

| Option | Description | Default | Examples |
|--------|-------------|---------|----------|
| `language` | Language detection mode | `"auto"` | `"auto"`, `"en"`, `"es"`, `"fr"` |
| `translate_to_english` | Translate non-English to English | `false` | `true`, `false` |
| `task` | Whisper task type | `"transcribe"` | `"transcribe"`, `"translate"` |
| `supported_languages` | List of supported language codes | See above | ISO 639-1 codes |
| `fallback_language` | Fallback if detection fails | `"en"` | Any supported language |

## Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | `en` | ✅ Fully supported |
| Spanish | `es` | ✅ Fully supported |
| French | `fr` | ✅ Fully supported |
| German | `de` | ✅ Fully supported |
| Italian | `it` | ✅ Fully supported |
| Portuguese | `pt` | ✅ Fully supported |
| Russian | `ru` | ✅ Fully supported |
| Japanese | `ja` | ✅ Fully supported |
| Korean | `ko` | ✅ Fully supported |
| Chinese | `zh` | ✅ Fully supported |

*Note: Whisper supports 99+ languages. Add more language codes to `supported_languages` as needed.*

## Usage Examples

### 1. Auto-Detection (Recommended)

```yaml
transcription:
  language: "auto"
  translate_to_english: false
```

**Result:** Automatically detects language, transcribes in original language.

### 2. Auto-Detection with Translation

```yaml
transcription:
  language: "auto"
  translate_to_english: true
```

**Result:** Detects language, translates everything to English.

### 3. Force Specific Language

```yaml
transcription:
  language: "es"  # Force Spanish
  translate_to_english: false
```

**Result:** Forces Spanish transcription (useful if detection is unreliable).

### 4. Multilingual Newsroom Setup

```yaml
transcription:
  language: "auto"
  translate_to_english: false
  supported_languages:
    - en  # English
    - es  # Spanish
    - fr  # French
  fallback_language: "en"
```

**Result:** Supports English, Spanish, French content with English fallback.

## Data Structure

### TranscriptionResult Fields

The `TranscriptionResult` model now includes multilingual metadata:

```python
@dataclass
class TranscriptionResult:
    # Existing fields
    text: str
    vtt_content: str
    segments: List[Dict[str, Any]]
    language: str  # Validated detected language
    
    # New multilingual fields
    detected_language: Optional[str]  # Language detected by Whisper
    original_language: Optional[str]  # Raw Whisper language detection
    task_performed: str  # "transcribe" or "translate"
    translated_to_english: bool  # True if content was translated
```

### Example Output

```json
{
  "text": "Bonjour, voici les nouvelles du jour...",
  "language": "fr",
  "detected_language": "fr",
  "original_language": "fr",
  "task_performed": "transcribe",
  "translated_to_english": false,
  "segments": [...],
  "words": [...]
}
```

## API Integration

### Episode Processing

When processing episodes, the API now returns language information:

```python
# GET /episodes/{episode_id}
{
  "episode_id": "news-fr-001",
  "transcription": {
    "text": "Bonjour, voici les nouvelles...",
    "language": "fr",
    "detected_language": "fr",
    "translated_to_english": false,
    ...
  }
}
```

### Language-Aware Clip Generation

Clips inherit language metadata from episodes:

```python
# POST /episodes/{episode_id}/discover_clips
{
  "clips": [
    {
      "clip_id": "clip_001",
      "language": "fr",
      "detected_language": "fr",
      "start_ms": 1000,
      "end_ms": 30000,
      ...
    }
  ]
}
```

## Dashboard Integration

The Streamlit dashboard displays language information:

- **Episodes Tab:** Shows detected language for each episode
- **Transcription View:** Displays language detection status
- **Clips Tab:** Shows language for each clip
- **Processing Logs:** Includes language detection details

## Testing

### Run Multilingual Tests

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run multilingual test suite
python test_multilingual.py
```

### Test with Non-English Content

1. **Upload Spanish Video:**
   ```bash
   # Place Spanish video in input folder
   cp spanish_news.mp4 data/temp/uploaded/
   ```

2. **Process via API:**
   ```python
   import requests
   
   # Discover episodes
   response = requests.post("http://localhost:8000/episodes/discover")
   
   # Process with multilingual support
   episode_id = response.json()["episodes"][0]["episode_id"]
   response = requests.post(f"http://localhost:8000/episodes/{episode_id}/process")
   ```

3. **Verify Language Detection:**
   ```python
   # Check transcription results
   response = requests.get(f"http://localhost:8000/episodes/{episode_id}")
   transcription = response.json()["transcription"]
   
   print(f"Detected: {transcription['detected_language']}")
   print(f"Translated: {transcription['translated_to_english']}")
   ```

## Performance Impact

### Transcription Performance

| Configuration | Performance Impact | Use Case |
|---------------|-------------------|----------|
| Auto-detection | +2-5% processing time | Recommended for mixed content |
| Fixed language | No impact | Single-language newsrooms |
| Translation enabled | +10-15% processing time | International content |

### GPU Acceleration

Multilingual support maintains full GPU acceleration:

- **Language Detection:** No additional GPU overhead
- **Transcription:** Same GPU performance as English-only
- **Translation:** Utilizes GPU for faster processing

## Troubleshooting

### Common Issues

#### 1. Language Not Detected Correctly

**Problem:** Whisper detects wrong language
**Solution:** 
```yaml
transcription:
  language: "es"  # Force correct language
```

#### 2. Unsupported Language Detected

**Problem:** Content in unsupported language
**Solution:**
```yaml
transcription:
  supported_languages:
    - en
    - es
    - your_language_code  # Add your language
```

#### 3. Translation Quality Issues

**Problem:** Poor translation quality
**Solution:**
- Use `translate_to_english: false` for better accuracy
- Consider post-processing with dedicated translation service

### Debugging

Enable debug logging for language detection:

```yaml
logging:
  level: "DEBUG"
```

Check logs for language detection details:
```
INFO - Detected language 'es' is supported
INFO - Task performed: transcribe
INFO - Translation enabled: false
```

## Migration Guide

### From English-Only Setup

1. **Update Configuration:**
   ```yaml
   # Add to config/pipeline.yaml
   transcription:
     language: "auto"
     translate_to_english: false
     supported_languages: ["en", "es", "fr"]  # Add your languages
   ```

2. **Restart API Server:**
   ```bash
   python src/cli.py --config config/pipeline.yaml api --port 8000
   ```

3. **Test with Existing Episodes:**
   - Existing episodes retain original language metadata
   - New episodes will use multilingual detection

### Database Compatibility

- **Backward Compatible:** Existing episodes work unchanged
- **New Fields:** New language fields added to TranscriptionResult
- **Migration:** No database migration required

## Best Practices

### 1. Language Configuration

```yaml
# For international newsrooms
transcription:
  language: "auto"
  supported_languages: ["en", "es", "fr", "de"]  # Your target languages
  fallback_language: "en"
```

### 2. Performance Optimization

```yaml
# For high-volume processing
transcription:
  language: "en"  # If content is primarily English
  translate_to_english: false
```

### 3. Quality Assurance

```yaml
# For maximum accuracy
transcription:
  language: "auto"
  translate_to_english: false  # Keep original language
  fallback_language: "en"
```

## Future Enhancements

### Planned Features

- [ ] **Language-Specific Enrichment:** AI summaries in detected language
- [ ] **Subtitle Localization:** Generate subtitles in multiple languages
- [ ] **Language Analytics:** Track language distribution in content
- [ ] **Custom Language Models:** Fine-tuned models for specific languages

### Integration Roadmap

- [ ] **Dashboard Language Selector:** Filter content by language
- [ ] **Social Media Localization:** Platform-specific language handling
- [ ] **Automated Translation:** Integration with Google Translate API
- [ ] **Language-Based Routing:** Route content based on detected language

## Support

### Documentation
- [Configuration Guide](../config/pipeline.yaml)
- [API Documentation](../api/README.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

### Testing
- [Test Suite](../test_multilingual.py)
- [Performance Benchmarks](./PERFORMANCE.md)

### Community
- GitHub Issues for bug reports
- Discussions for feature requests
- Wiki for community contributions

---

**Version:** 1.0.0  
**Last Updated:** 2025-01-28  
**Compatibility:** AI-EWG v2.0+
