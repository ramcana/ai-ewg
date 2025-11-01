# Content Verification & Improvement Plan

## 🎯 Current State

### ✅ Implemented Features

1. **Transcript Cleaning** (`src/utils/transcript_cleaner.py`)
   - Removes Whisper hallucinations
   - Fixes repetitive phrases
   - Cleans punctuation and spacing
   - Applied automatically during enrichment

2. **Content Quality Validation** (Partial)
   - Quality metrics framework exists
   - Editorial validation tests
   - SEO optimization checks

3. **Platform Content Validation**
   - Policy engine validates content
   - Platform-specific requirements
   - Metadata compliance checks

## ❌ Missing Features

### 1. Spelling Correction

**Problem:** Whisper transcription may produce:
- Misspelled proper nouns
- Incorrect homophones (their/there/they're)
- Technical term errors
- Brand name mistakes

**Proposed Solution:**

#### Option A: AI-Powered Correction (Recommended)
Use Ollama to correct spelling in context:

```python
# src/utils/spelling_corrector.py

async def correct_spelling_with_ai(text: str, ollama_client) -> str:
    """
    Use AI to correct spelling while preserving context
    """
    prompt = f"""Review this transcript and fix any spelling errors.
Preserve the original meaning and style. Only fix obvious mistakes.

Transcript:
{text}

Corrected transcript:"""
    
    corrected = await ollama_client.generate(prompt)
    return corrected
```

**Pros:**
- Context-aware corrections
- Handles proper nouns and technical terms
- Can fix homophones based on context

**Cons:**
- Slower (requires AI call)
- May introduce unwanted changes

#### Option B: Dictionary-Based Correction
Use spaCy or pyspellchecker:

```python
# src/utils/spelling_corrector.py
from spellchecker import SpellChecker

def correct_spelling_basic(text: str) -> str:
    """
    Basic dictionary-based spelling correction
    """
    spell = SpellChecker()
    words = text.split()
    corrected = []
    
    for word in words:
        # Skip proper nouns (capitalized)
        if word[0].isupper():
            corrected.append(word)
            continue
        
        # Correct misspelled words
        correction = spell.correction(word)
        corrected.append(correction or word)
    
    return ' '.join(corrected)
```

**Pros:**
- Fast
- Deterministic
- No AI required

**Cons:**
- May miss context-dependent errors
- Struggles with proper nouns
- Can't fix homophones

#### Option C: Hybrid Approach (Best)
1. Dictionary-based for obvious errors
2. AI review for ambiguous cases
3. User review interface for corrections

### 2. Content Verification Dashboard

**Proposed Feature:**

```python
# New Streamlit page: pages/content_verification.py

def show_verification_dashboard():
    """
    Dashboard for reviewing and correcting content
    """
    st.title("📝 Content Verification")
    
    # Select episode
    episode = select_episode()
    
    # Show original vs cleaned transcript
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Transcript")
        st.text_area("", episode.transcript_raw, height=400)
    
    with col2:
        st.subheader("Cleaned Transcript")
        st.text_area("", episode.transcript_cleaned, height=400)
    
    # Spelling suggestions
    st.subheader("Spelling Suggestions")
    suggestions = get_spelling_suggestions(episode.transcript)
    
    for suggestion in suggestions:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.write(f"**Original:** {suggestion.original}")
        with col2:
            st.write(f"**Suggested:** {suggestion.corrected}")
        with col3:
            if st.button("Apply", key=suggestion.id):
                apply_correction(episode, suggestion)
    
    # Manual corrections
    st.subheader("Manual Corrections")
    corrections = st.text_area("Enter corrections (one per line)")
    
    if st.button("Apply All Corrections"):
        apply_manual_corrections(episode, corrections)
        st.success("Corrections applied!")
```

### 3. AI-Powered Content Improvement

**Proposed Feature:**

```python
# src/stages/improvement_stage.py

class ContentImprovementStage:
    """
    Post-processing stage to improve content quality
    """
    
    async def improve_content(self, episode: EpisodeObject):
        """
        Apply AI-powered improvements to content
        """
        improvements = []
        
        # 1. Spelling correction
        if self.config.enable_spelling_correction:
            corrected_transcript = await self.correct_spelling(
                episode.transcription.text
            )
            improvements.append({
                'type': 'spelling',
                'original_length': len(episode.transcription.text),
                'corrected_length': len(corrected_transcript)
            })
            episode.transcription.text = corrected_transcript
        
        # 2. Grammar improvement
        if self.config.enable_grammar_check:
            improved_text = await self.improve_grammar(
                episode.transcription.text
            )
            improvements.append({
                'type': 'grammar',
                'changes': self.count_changes(
                    episode.transcription.text,
                    improved_text
                )
            })
            episode.transcription.text = improved_text
        
        # 3. Proper noun correction
        if self.config.enable_proper_noun_correction:
            corrected_text = await self.correct_proper_nouns(
                episode.transcription.text,
                episode.enrichment.topics
            )
            improvements.append({
                'type': 'proper_nouns',
                'corrections': self.get_corrections(
                    episode.transcription.text,
                    corrected_text
                )
            })
            episode.transcription.text = corrected_text
        
        return improvements
```

## 🚀 Implementation Plan

### Phase 1: Spelling Correction (2-3 hours)
1. Create `src/utils/spelling_corrector.py`
2. Implement hybrid approach (dictionary + AI)
3. Add to enrichment stage as optional step
4. Add configuration flag: `enable_spelling_correction`

### Phase 2: Verification Dashboard (3-4 hours)
1. Create `pages/content_verification.py`
2. Add side-by-side comparison view
3. Implement suggestion review interface
4. Add manual correction capability

### Phase 3: Content Improvement Stage (4-5 hours)
1. Create `src/stages/improvement_stage.py`
2. Implement grammar checking
3. Add proper noun correction
4. Integrate with pipeline

### Phase 4: Testing & Documentation (2-3 hours)
1. Create test cases
2. Document configuration options
3. Add usage examples
4. Update README

## 📋 Configuration

Add to `config/pipeline.yaml`:

```yaml
content_improvement:
  enabled: true
  
  spelling_correction:
    enabled: true
    method: "hybrid"  # Options: "dictionary", "ai", "hybrid"
    confidence_threshold: 0.8
    
  grammar_check:
    enabled: false  # Optional, slower
    
  proper_noun_correction:
    enabled: true
    use_topic_context: true
    
  manual_review:
    enabled: true
    require_approval: false  # Auto-apply or require review
```

## 🎯 Success Criteria

1. ✅ Spelling errors reduced by 90%+
2. ✅ Proper nouns correctly capitalized
3. ✅ User can review and approve corrections
4. ✅ Processing time increase < 10%
5. ✅ No false corrections introduced

## 📊 Metrics to Track

- Corrections per episode
- Correction accuracy rate
- Processing time impact
- User approval rate
- False positive rate

## 🔗 Related Files

- `src/utils/transcript_cleaner.py` - Existing cleaning
- `src/stages/enrichment_stage.py` - Where to integrate
- `config/pipeline.yaml` - Configuration
- `tests/test_content_improvement.py` - Tests

---

**Status:** Planned  
**Priority:** Medium  
**Estimated Effort:** 11-15 hours  
**Dependencies:** Ollama, spaCy, pyspellchecker
