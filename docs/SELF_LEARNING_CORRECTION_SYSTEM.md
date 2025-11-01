# Self-Learning Correction System

## 🎯 Overview

A self-learning system that remembers and applies user corrections to transcripts, including:
- **Names:** Teresa Skubik → Theresa Skubic
- **Brands:** Apple Inc → Apple Inc.
- **Technical Terms:** AI ML → AI/ML
- **Show-Specific Terms:** Custom vocabulary per show
- **Contextual Corrections:** Based on topic/guest context

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Correction Input                  │
│  (Dashboard, API, or Manual Review Interface)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Correction Learning Engine                  │
│  • Stores correction in database                         │
│  • Analyzes context (show, topic, guest)                 │
│  • Builds correction patterns                            │
│  • Updates confidence scores                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 Correction Database                      │
│  corrections table:                                      │
│    - original_text                                       │
│    - corrected_text                                      │
│    - correction_type (name, brand, term, etc.)           │
│    - context (show, topic, guest)                        │
│    - confidence_score                                    │
│    - usage_count                                         │
│    - created_at, last_used                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            Intelligent Correction Engine                 │
│  • Applies corrections during enrichment                 │
│  • Context-aware matching                                │
│  • Fuzzy matching for variations                         │
│  • Learns from usage patterns                            │
└─────────────────────────────────────────────────────────┘
```

## 📊 Database Schema

### Corrections Table

```sql
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Core correction data
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    correction_type TEXT NOT NULL,  -- 'name', 'brand', 'term', 'phrase', 'technical'
    
    -- Context for intelligent matching
    show_name TEXT,                 -- Apply only to specific show
    topic_context TEXT,             -- Apply when topic matches
    guest_context TEXT,             -- Apply when guest appears
    
    -- Learning metrics
    confidence_score REAL DEFAULT 1.0,
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    rejection_count INTEGER DEFAULT 0,
    
    -- Matching configuration
    case_sensitive BOOLEAN DEFAULT 0,
    whole_word_only BOOLEAN DEFAULT 1,
    fuzzy_threshold REAL DEFAULT 0.85,  -- For fuzzy matching
    
    -- Metadata
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    notes TEXT,
    
    -- Indexes for fast lookup
    UNIQUE(original_text, show_name, correction_type)
);

CREATE INDEX idx_corrections_original ON corrections(original_text);
CREATE INDEX idx_corrections_show ON corrections(show_name);
CREATE INDEX idx_corrections_type ON corrections(correction_type);
CREATE INDEX idx_corrections_confidence ON corrections(confidence_score);
```

### Correction History Table

```sql
CREATE TABLE correction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correction_id INTEGER,
    episode_id TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    was_successful BOOLEAN,
    user_feedback TEXT,
    
    FOREIGN KEY (correction_id) REFERENCES corrections(id)
);
```

## 🔧 Implementation

### 1. Correction Service

```python
# src/core/correction_service.py

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import re
from fuzzywuzzy import fuzz
from .registry import Registry
from .logging import get_logger

logger = get_logger('pipeline.correction_service')

@dataclass
class Correction:
    """Represents a learned correction"""
    id: Optional[int]
    original_text: str
    corrected_text: str
    correction_type: str
    show_name: Optional[str] = None
    topic_context: Optional[str] = None
    guest_context: Optional[str] = None
    confidence_score: float = 1.0
    usage_count: int = 0
    case_sensitive: bool = False
    whole_word_only: bool = True
    fuzzy_threshold: float = 0.85
    notes: Optional[str] = None

class CorrectionService:
    """
    Self-learning correction system
    
    Learns from user corrections and applies them intelligently
    based on context (show, topic, guest).
    """
    
    def __init__(self, registry: Registry):
        self.registry = registry
        self._correction_cache = {}
        self._load_corrections()
    
    def _load_corrections(self):
        """Load all corrections into memory for fast access"""
        corrections = self.registry.db.execute("""
            SELECT * FROM corrections 
            WHERE confidence_score >= 0.5
            ORDER BY confidence_score DESC, usage_count DESC
        """).fetchall()
        
        for row in corrections:
            correction = Correction(
                id=row['id'],
                original_text=row['original_text'],
                corrected_text=row['corrected_text'],
                correction_type=row['correction_type'],
                show_name=row['show_name'],
                topic_context=row['topic_context'],
                guest_context=row['guest_context'],
                confidence_score=row['confidence_score'],
                usage_count=row['usage_count'],
                case_sensitive=bool(row['case_sensitive']),
                whole_word_only=bool(row['whole_word_only']),
                fuzzy_threshold=row['fuzzy_threshold']
            )
            
            # Cache by show for fast lookup
            show_key = row['show_name'] or '_global'
            if show_key not in self._correction_cache:
                self._correction_cache[show_key] = []
            self._correction_cache[show_key].append(correction)
        
        logger.info(f"Loaded {len(corrections)} corrections into cache")
    
    def add_correction(
        self,
        original: str,
        corrected: str,
        correction_type: str,
        show_name: Optional[str] = None,
        topic_context: Optional[str] = None,
        guest_context: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """
        Add a new correction to the learning system
        
        Args:
            original: The incorrect text from transcript
            corrected: The correct version
            correction_type: Type of correction (name, brand, term, etc.)
            show_name: Apply only to this show (None = all shows)
            topic_context: Apply when this topic is present
            guest_context: Apply when this guest appears
            notes: Optional notes about the correction
            created_by: User who created the correction
            
        Returns:
            Correction ID
        """
        cursor = self.registry.db.execute("""
            INSERT INTO corrections (
                original_text, corrected_text, correction_type,
                show_name, topic_context, guest_context,
                notes, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(original_text, show_name, correction_type) 
            DO UPDATE SET
                corrected_text = excluded.corrected_text,
                notes = excluded.notes,
                confidence_score = confidence_score + 0.1
        """, (
            original, corrected, correction_type,
            show_name, topic_context, guest_context,
            notes, created_by
        ))
        
        self.registry.db.commit()
        correction_id = cursor.lastrowid
        
        # Reload cache
        self._load_corrections()
        
        logger.info(
            "Correction added",
            original=original,
            corrected=corrected,
            type=correction_type,
            show=show_name
        )
        
        return correction_id
    
    def apply_corrections(
        self,
        text: str,
        show_name: Optional[str] = None,
        topics: Optional[List[str]] = None,
        guests: Optional[List[str]] = None,
        episode_id: Optional[str] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Apply learned corrections to text
        
        Args:
            text: Text to correct
            show_name: Current show (for context-aware corrections)
            topics: Current topics (for context matching)
            guests: Current guests (for context matching)
            episode_id: Episode ID for tracking
            
        Returns:
            Tuple of (corrected_text, list of applied corrections)
        """
        corrected_text = text
        applied_corrections = []
        
        # Get applicable corrections (show-specific + global)
        corrections = self._get_applicable_corrections(
            show_name, topics, guests
        )
        
        for correction in corrections:
            # Check if correction applies
            if not self._should_apply(correction, text, topics, guests):
                continue
            
            # Apply correction
            before = corrected_text
            corrected_text = self._apply_single_correction(
                corrected_text, correction
            )
            
            # Track if correction was applied
            if before != corrected_text:
                applied_corrections.append({
                    'id': correction.id,
                    'original': correction.original_text,
                    'corrected': correction.corrected_text,
                    'type': correction.correction_type,
                    'confidence': correction.confidence_score
                })
                
                # Update usage statistics
                self._record_correction_usage(
                    correction.id, episode_id, success=True
                )
        
        if applied_corrections:
            logger.info(
                "Applied corrections",
                count=len(applied_corrections),
                episode_id=episode_id
            )
        
        return corrected_text, applied_corrections
    
    def _get_applicable_corrections(
        self,
        show_name: Optional[str],
        topics: Optional[List[str]],
        guests: Optional[List[str]]
    ) -> List[Correction]:
        """Get corrections that apply to this context"""
        corrections = []
        
        # Global corrections (no show specified)
        if '_global' in self._correction_cache:
            corrections.extend(self._correction_cache['_global'])
        
        # Show-specific corrections
        if show_name and show_name in self._correction_cache:
            corrections.extend(self._correction_cache[show_name])
        
        return corrections
    
    def _should_apply(
        self,
        correction: Correction,
        text: str,
        topics: Optional[List[str]],
        guests: Optional[List[str]]
    ) -> bool:
        """Determine if correction should be applied based on context"""
        
        # Check if original text exists in transcript
        if correction.case_sensitive:
            if correction.original_text not in text:
                return False
        else:
            if correction.original_text.lower() not in text.lower():
                return False
        
        # Check topic context
        if correction.topic_context and topics:
            if not any(
                correction.topic_context.lower() in topic.lower()
                for topic in topics
            ):
                return False
        
        # Check guest context
        if correction.guest_context and guests:
            if not any(
                correction.guest_context.lower() in guest.lower()
                for guest in guests
            ):
                return False
        
        # Check confidence threshold
        if correction.confidence_score < 0.5:
            return False
        
        return True
    
    def _apply_single_correction(
        self,
        text: str,
        correction: Correction
    ) -> str:
        """Apply a single correction to text"""
        
        if correction.whole_word_only:
            # Use word boundaries
            pattern = r'\b' + re.escape(correction.original_text) + r'\b'
            flags = 0 if correction.case_sensitive else re.IGNORECASE
            return re.sub(pattern, correction.corrected_text, text, flags=flags)
        else:
            # Simple replacement
            if correction.case_sensitive:
                return text.replace(
                    correction.original_text,
                    correction.corrected_text
                )
            else:
                # Case-insensitive replacement (preserve original case)
                pattern = re.compile(
                    re.escape(correction.original_text),
                    re.IGNORECASE
                )
                return pattern.sub(correction.corrected_text, text)
    
    def _record_correction_usage(
        self,
        correction_id: int,
        episode_id: Optional[str],
        success: bool
    ):
        """Record that a correction was used"""
        
        # Update correction statistics
        self.registry.db.execute("""
            UPDATE corrections 
            SET usage_count = usage_count + 1,
                success_count = success_count + ?,
                last_used = CURRENT_TIMESTAMP,
                confidence_score = MIN(1.0, confidence_score + 0.01)
            WHERE id = ?
        """, (1 if success else 0, correction_id))
        
        # Record in history
        if episode_id:
            self.registry.db.execute("""
                INSERT INTO correction_history (
                    correction_id, episode_id, was_successful
                ) VALUES (?, ?, ?)
            """, (correction_id, episode_id, success))
        
        self.registry.db.commit()
    
    def suggest_corrections(
        self,
        text: str,
        show_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Suggest potential corrections based on fuzzy matching
        
        Returns list of suggestions for user review
        """
        suggestions = []
        corrections = self._get_applicable_corrections(show_name, None, None)
        
        for correction in corrections:
            # Use fuzzy matching to find similar text
            ratio = fuzz.partial_ratio(
                correction.original_text.lower(),
                text.lower()
            )
            
            if ratio >= correction.fuzzy_threshold * 100:
                suggestions.append({
                    'original': correction.original_text,
                    'suggested': correction.corrected_text,
                    'confidence': ratio / 100.0,
                    'type': correction.correction_type,
                    'correction_id': correction.id
                })
        
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)
    
    def get_corrections_for_show(
        self,
        show_name: Optional[str] = None
    ) -> List[Dict]:
        """Get all corrections for a show"""
        query = """
            SELECT * FROM corrections 
            WHERE show_name = ? OR show_name IS NULL
            ORDER BY usage_count DESC, confidence_score DESC
        """
        
        rows = self.registry.db.execute(query, (show_name,)).fetchall()
        
        return [dict(row) for row in rows]
    
    def delete_correction(self, correction_id: int):
        """Delete a correction"""
        self.registry.db.execute(
            "DELETE FROM corrections WHERE id = ?",
            (correction_id,)
        )
        self.registry.db.commit()
        self._load_corrections()
        
        logger.info("Correction deleted", correction_id=correction_id)
    
    def export_corrections(self, show_name: Optional[str] = None) -> str:
        """Export corrections as CSV for backup/sharing"""
        import csv
        import io
        
        corrections = self.get_corrections_for_show(show_name)
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'original_text', 'corrected_text', 'correction_type',
            'show_name', 'confidence_score', 'usage_count'
        ])
        writer.writeheader()
        writer.writerows(corrections)
        
        return output.getvalue()
    
    def import_corrections(self, csv_data: str, show_name: Optional[str] = None):
        """Import corrections from CSV"""
        import csv
        import io
        
        reader = csv.DictReader(io.StringIO(csv_data))
        count = 0
        
        for row in reader:
            self.add_correction(
                original=row['original_text'],
                corrected=row['corrected_text'],
                correction_type=row.get('correction_type', 'term'),
                show_name=show_name or row.get('show_name'),
                created_by='import'
            )
            count += 1
        
        logger.info(f"Imported {count} corrections")
        return count


# Singleton instance
_correction_service = None

def get_correction_service(registry: Registry) -> CorrectionService:
    """Get or create correction service instance"""
    global _correction_service
    if _correction_service is None:
        _correction_service = CorrectionService(registry)
    return _correction_service
```

### 2. Integration with Enrichment Stage

```python
# src/stages/enrichment_stage.py

from ..core.correction_service import get_correction_service

class EnrichmentStageProcessor:
    
    async def _create_ai_enrichment(self, episode, transcript_text, ...):
        # ... existing code ...
        
        # Apply learned corrections BEFORE AI processing
        correction_service = get_correction_service(self.registry)
        
        corrected_transcript, applied_corrections = correction_service.apply_corrections(
            text=transcript_text,
            show_name=episode.metadata.show_name,
            topics=None,  # Will be filled after AI extraction
            guests=None,
            episode_id=episode.episode_id
        )
        
        if applied_corrections:
            logger.info(
                "Applied learned corrections",
                count=len(applied_corrections),
                episode_id=episode.episode_id
            )
            
            # Store corrections in episode metadata
            episode.metadata.applied_corrections = applied_corrections
        
        # Use corrected transcript for AI processing
        transcript_text = corrected_transcript
        
        # ... continue with AI enrichment ...
```

### 3. Streamlit Correction Interface

```python
# pages/correction_manager.py

import streamlit as st
from src.core.correction_service import get_correction_service
from src.core.registry import get_registry

st.title("🎓 Self-Learning Correction System")

registry = get_registry()
correction_service = get_correction_service(registry)

tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Add Correction",
    "📋 View Corrections", 
    "🔍 Test Corrections",
    "📊 Statistics"
])

# Tab 1: Add Correction
with tab1:
    st.subheader("Add New Correction")
    
    col1, col2 = st.columns(2)
    
    with col1:
        original = st.text_input("Incorrect Text (from transcript)")
        st.caption("Example: Teresa Skubik")
    
    with col2:
        corrected = st.text_input("Correct Text")
        st.caption("Example: Theresa Skubic")
    
    correction_type = st.selectbox(
        "Correction Type",
        ["name", "brand", "term", "phrase", "technical", "location"]
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        show_name = st.selectbox(
            "Apply to Show",
            ["All Shows", "Forum Daily News", "Boom and Bust", "Canadian Justice"]
        )
        show_name = None if show_name == "All Shows" else show_name
    
    with col2:
        topic_context = st.text_input(
            "Topic Context (optional)",
            help="Only apply when this topic is present"
        )
    
    notes = st.text_area("Notes (optional)")
    
    if st.button("💾 Save Correction", type="primary"):
        if original and corrected:
            correction_id = correction_service.add_correction(
                original=original,
                corrected=corrected,
                correction_type=correction_type,
                show_name=show_name,
                topic_context=topic_context or None,
                notes=notes or None,
                created_by="user"
            )
            st.success(f"✅ Correction saved! (ID: {correction_id})")
            st.balloons()
        else:
            st.error("Please fill in both fields")

# Tab 2: View Corrections
with tab2:
    st.subheader("Learned Corrections")
    
    show_filter = st.selectbox(
        "Filter by Show",
        ["All Shows", "Forum Daily News", "Boom and Bust", "Canadian Justice"],
        key="view_show"
    )
    show_filter = None if show_filter == "All Shows" else show_filter
    
    corrections = correction_service.get_corrections_for_show(show_filter)
    
    if corrections:
        st.write(f"**{len(corrections)} corrections found**")
        
        for correction in corrections:
            with st.expander(
                f"**{correction['original_text']}** → **{correction['corrected_text']}**"
            ):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Type", correction['correction_type'])
                    st.metric("Show", correction['show_name'] or "All Shows")
                
                with col2:
                    st.metric("Usage Count", correction['usage_count'])
                    st.metric("Confidence", f"{correction['confidence_score']:.2f}")
                
                with col3:
                    if correction['notes']:
                        st.write("**Notes:**")
                        st.write(correction['notes'])
                
                if st.button("🗑️ Delete", key=f"del_{correction['id']}"):
                    correction_service.delete_correction(correction['id'])
                    st.success("Deleted!")
                    st.rerun()
    else:
        st.info("No corrections found. Add some in the 'Add Correction' tab!")

# Tab 3: Test Corrections
with tab3:
    st.subheader("Test Corrections on Text")
    
    test_text = st.text_area(
        "Enter text to test",
        height=200,
        placeholder="Paste transcript text here to see what corrections would be applied..."
    )
    
    test_show = st.selectbox(
        "Show Context",
        ["None", "Forum Daily News", "Boom and Bust", "Canadian Justice"],
        key="test_show"
    )
    test_show = None if test_show == "None" else test_show
    
    if st.button("🔍 Apply Corrections"):
        if test_text:
            corrected, applied = correction_service.apply_corrections(
                text=test_text,
                show_name=test_show
            )
            
            st.subheader("Results")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Original:**")
                st.text_area("", test_text, height=200, key="orig")
            
            with col2:
                st.write("**Corrected:**")
                st.text_area("", corrected, height=200, key="corr")
            
            if applied:
                st.success(f"✅ Applied {len(applied)} corrections:")
                for correction in applied:
                    st.write(
                        f"- **{correction['original']}** → **{correction['corrected']}** "
                        f"({correction['type']}, confidence: {correction['confidence']:.2f})"
                    )
            else:
                st.info("No corrections applied")

# Tab 4: Statistics
with tab4:
    st.subheader("Correction Statistics")
    
    corrections = correction_service.get_corrections_for_show(None)
    
    if corrections:
        # Overall stats
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Corrections", len(corrections))
        
        with col2:
            total_usage = sum(c['usage_count'] for c in corrections)
            st.metric("Total Usage", total_usage)
        
        with col3:
            avg_confidence = sum(c['confidence_score'] for c in corrections) / len(corrections)
            st.metric("Avg Confidence", f"{avg_confidence:.2f}")
        
        with col4:
            types = set(c['correction_type'] for c in corrections)
            st.metric("Correction Types", len(types))
        
        # Top corrections
        st.subheader("Most Used Corrections")
        top_corrections = sorted(
            corrections,
            key=lambda x: x['usage_count'],
            reverse=True
        )[:10]
        
        for i, correction in enumerate(top_corrections, 1):
            st.write(
                f"{i}. **{correction['original_text']}** → **{correction['corrected_text']}** "
                f"(used {correction['usage_count']} times)"
            )
        
        # Export
        st.subheader("Export/Import")
        
        if st.button("📥 Export Corrections as CSV"):
            csv_data = correction_service.export_corrections()
            st.download_button(
                "Download CSV",
                csv_data,
                "corrections.csv",
                "text/csv"
            )
    else:
        st.info("No corrections yet. Start adding some!")
```

## 📋 Configuration

Add to `config/pipeline.yaml`:

```yaml
corrections:
  enabled: true
  
  # Apply corrections during enrichment
  apply_during_enrichment: true
  
  # Minimum confidence to auto-apply
  auto_apply_threshold: 0.7
  
  # Suggest corrections below this threshold
  suggest_threshold: 0.5
  
  # Enable fuzzy matching
  fuzzy_matching: true
  fuzzy_threshold: 0.85
```

## 🚀 Usage Examples

### Add Correction via API

```python
POST /corrections/add
{
  "original": "Teresa Skubik",
  "corrected": "Theresa Skubic",
  "correction_type": "name",
  "show_name": "Forum Daily News",
  "notes": "Guest name correction"
}
```

### Apply Corrections

```python
from src.core.correction_service import get_correction_service

correction_service = get_correction_service(registry)

# Apply corrections
corrected_text, applied = correction_service.apply_corrections(
    text=transcript,
    show_name="Forum Daily News",
    topics=["Technology", "AI"],
    guests=["Theresa Skubic"]
)

print(f"Applied {len(applied)} corrections")
```

## 🎯 Benefits

1. **Self-Learning:** System improves over time
2. **Context-Aware:** Different corrections for different shows
3. **Confidence Scoring:** More used corrections = higher confidence
4. **User-Friendly:** Simple interface to add corrections
5. **Exportable:** Share corrections between systems
6. **Auditable:** Full history of corrections applied

## 📊 Success Metrics

- Corrections learned per month
- Correction accuracy rate
- Time saved on manual review
- User satisfaction with corrections

---

**Status:** Designed - Ready to Implement  
**Priority:** High  
**Estimated Effort:** 8-10 hours  
**Dependencies:** SQLite, fuzzywuzzy, existing registry system
