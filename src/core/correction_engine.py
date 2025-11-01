"""
Self-Learning Correction Engine
Applies intelligent corrections to transcripts with context awareness
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from .logging import get_logger

logger = get_logger('pipeline.correction_engine')


class CorrectionEngine:
    """
    Intelligent correction engine that applies learned corrections to transcripts
    with context awareness and fuzzy matching
    """
    
    def __init__(self, corrections_file: str = "data/corrections.json",
                 settings_file: str = "data/correction_settings.json"):
        """
        Initialize correction engine
        
        Args:
            corrections_file: Path to corrections database file
            settings_file: Path to settings file
        """
        self.corrections_file = Path(corrections_file)
        self.settings_file = Path(settings_file)
        self.corrections = []
        self.settings = {}
        
        # Load corrections and settings
        self._load_corrections()
        self._load_settings()
        
        logger.info("CorrectionEngine initialized",
                   corrections_count=len(self.corrections),
                   auto_apply=self.settings.get('auto_apply', True))
    
    def _load_corrections(self):
        """Load corrections from file"""
        if not self.corrections_file.exists():
            logger.info("No corrections file found, starting with empty corrections")
            self.corrections = []
            return
        
        try:
            with open(self.corrections_file, 'r', encoding='utf-8') as f:
                self.corrections = json.load(f)
            logger.info(f"Loaded {len(self.corrections)} corrections")
        except Exception as e:
            logger.error(f"Failed to load corrections: {e}")
            self.corrections = []
    
    def _load_settings(self):
        """Load correction settings"""
        if not self.settings_file.exists():
            # Default settings
            self.settings = {
                'auto_apply': True,
                'fuzzy_matching': True,
                'fuzzy_threshold': 0.85,
                'confidence_threshold': 0.7,
                'learn_from_usage': True,
                'suggest_corrections': False
            }
            return
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
            logger.info("Loaded correction settings", settings=self.settings)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.settings = {
                'auto_apply': True,
                'fuzzy_matching': True,
                'fuzzy_threshold': 0.85,
                'confidence_threshold': 0.7,
                'learn_from_usage': True,
                'suggest_corrections': False
            }
    
    def _save_corrections(self):
        """Save corrections to file"""
        try:
            self.corrections_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.corrections_file, 'w', encoding='utf-8') as f:
                json.dump(self.corrections, f, indent=2, ensure_ascii=False)
            logger.debug("Corrections saved to file")
        except Exception as e:
            logger.error(f"Failed to save corrections: {e}")
    
    def apply_corrections(self, text: str, show_name: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Apply corrections to text with context awareness
        
        Args:
            text: Text to correct
            show_name: Show name for context-specific corrections
            context: Additional context (topic, guests, etc.)
            
        Returns:
            Tuple of (corrected_text, applied_corrections)
        """
        if not self.settings.get('auto_apply', True):
            logger.debug("Auto-apply disabled, skipping corrections")
            return text, []
        
        if not self.corrections:
            logger.debug("No corrections available")
            return text, []
        
        corrected_text = text
        applied_corrections = []
        
        # Filter corrections by context
        applicable_corrections = self._filter_corrections(show_name, context)
        
        logger.info(f"Applying corrections to text",
                   text_length=len(text),
                   applicable_corrections=len(applicable_corrections))
        
        # Sort by confidence (highest first) and length (longest first to avoid partial matches)
        applicable_corrections.sort(
            key=lambda x: (x.get('confidence', 0), len(x.get('original', ''))),
            reverse=True
        )
        
        # Apply each correction
        for correction in applicable_corrections:
            original = correction.get('original', '')
            corrected = correction.get('corrected', '')
            confidence = correction.get('confidence', 1.0)
            
            # Skip if below confidence threshold
            if confidence < self.settings.get('confidence_threshold', 0.7):
                continue
            
            # Apply correction
            result = self._apply_single_correction(
                corrected_text, original, corrected, correction
            )
            
            if result['applied']:
                corrected_text = result['text']
                applied_corrections.append({
                    'original': original,
                    'corrected': corrected,
                    'type': correction.get('type'),
                    'confidence': confidence,
                    'occurrences': result['occurrences']
                })
                
                # Update usage statistics
                if self.settings.get('learn_from_usage', True):
                    self._update_correction_usage(correction['id'], success=True)
        
        if applied_corrections:
            logger.info(f"Applied {len(applied_corrections)} corrections",
                       corrections=applied_corrections)
        
        return corrected_text, applied_corrections
    
    def _filter_corrections(self, show_name: Optional[str],
                           context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter corrections based on context"""
        applicable = []
        
        for correction in self.corrections:
            # Check show context
            correction_show = correction.get('show_name')
            if correction_show and show_name:
                if correction_show != show_name:
                    continue
            
            # Check topic context (if provided)
            if context and context.get('topic'):
                correction_topic = correction.get('topic_context')
                if correction_topic and correction_topic not in context.get('topic', ''):
                    continue
            
            # Check guest context (if provided)
            if context and context.get('guests'):
                correction_guest = correction.get('guest_context')
                if correction_guest and correction_guest not in context.get('guests', []):
                    continue
            
            applicable.append(correction)
        
        return applicable
    
    def _apply_single_correction(self, text: str, original: str, corrected: str,
                                correction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a single correction to text
        
        Returns:
            Dict with 'applied' (bool), 'text' (str), 'occurrences' (int)
        """
        case_sensitive = correction.get('case_sensitive', False)
        whole_word_only = correction.get('whole_word_only', True)
        
        # Build regex pattern
        if whole_word_only:
            # Match whole words only
            pattern = r'\b' + re.escape(original) + r'\b'
        else:
            pattern = re.escape(original)
        
        # Compile with appropriate flags
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            regex = re.compile(pattern, flags)
            matches = regex.findall(text)
            
            if matches:
                # Replace all occurrences
                new_text = regex.sub(corrected, text)
                return {
                    'applied': True,
                    'text': new_text,
                    'occurrences': len(matches)
                }
            
            # Try fuzzy matching if enabled
            if self.settings.get('fuzzy_matching', True) and not matches:
                fuzzy_result = self._apply_fuzzy_correction(
                    text, original, corrected, correction
                )
                if fuzzy_result['applied']:
                    return fuzzy_result
            
        except Exception as e:
            logger.error(f"Error applying correction: {e}",
                        original=original,
                        corrected=corrected)
        
        return {'applied': False, 'text': text, 'occurrences': 0}
    
    def _apply_fuzzy_correction(self, text: str, original: str, corrected: str,
                               correction: Dict[str, Any]) -> Dict[str, Any]:
        """Apply correction with fuzzy matching"""
        threshold = correction.get('fuzzy_threshold', self.settings.get('fuzzy_threshold', 0.85))
        words = text.split()
        new_words = []
        occurrences = 0
        
        for word in words:
            # Clean word for comparison
            clean_word = re.sub(r'[^\w\s]', '', word).lower()
            clean_original = re.sub(r'[^\w\s]', '', original).lower()
            
            # Calculate similarity
            similarity = SequenceMatcher(None, clean_word, clean_original).ratio()
            
            if similarity >= threshold:
                # Preserve punctuation
                if word != clean_word:
                    # Has punctuation
                    prefix = word[:len(word) - len(word.lstrip())]
                    suffix = word[len(word.rstrip()):]
                    new_words.append(prefix + corrected + suffix)
                else:
                    new_words.append(corrected)
                occurrences += 1
            else:
                new_words.append(word)
        
        if occurrences > 0:
            return {
                'applied': True,
                'text': ' '.join(new_words),
                'occurrences': occurrences
            }
        
        return {'applied': False, 'text': text, 'occurrences': 0}
    
    def _update_correction_usage(self, correction_id: int, success: bool = True):
        """Update correction usage statistics"""
        for correction in self.corrections:
            if correction.get('id') == correction_id:
                correction['usage_count'] = correction.get('usage_count', 0) + 1
                correction['last_used'] = datetime.now().isoformat()
                
                if success:
                    correction['success_count'] = correction.get('success_count', 0) + 1
                else:
                    correction['rejection_count'] = correction.get('rejection_count', 0) + 1
                
                # Update confidence based on success rate
                total = correction['usage_count']
                successes = correction.get('success_count', 0)
                if total > 0:
                    success_rate = successes / total
                    # Adjust confidence: increase if high success rate, decrease if low
                    current_confidence = correction.get('confidence', 1.0)
                    if success_rate > 0.8:
                        correction['confidence'] = min(1.0, current_confidence + 0.05)
                    elif success_rate < 0.5:
                        correction['confidence'] = max(0.5, current_confidence - 0.05)
                
                break
        
        # Save updated corrections
        self._save_corrections()
    
    def apply_corrections_to_transcript(self, transcript_data: Dict[str, Any],
                                       show_name: Optional[str] = None,
                                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply corrections to full transcript data structure
        
        Args:
            transcript_data: Transcript data with 'text' and optionally 'segments'
            show_name: Show name for context
            context: Additional context
            
        Returns:
            Updated transcript data with corrections applied
        """
        logger.info("Applying corrections to transcript",
                   show_name=show_name,
                   has_segments='segments' in transcript_data)
        
        # Apply to main text
        if 'text' in transcript_data:
            corrected_text, applied = self.apply_corrections(
                transcript_data['text'], show_name, context
            )
            transcript_data['text'] = corrected_text
            
            # Store correction metadata
            if applied:
                if 'metadata' not in transcript_data:
                    transcript_data['metadata'] = {}
                transcript_data['metadata']['corrections_applied'] = applied
                transcript_data['metadata']['corrections_count'] = len(applied)
        
        # Apply to segments if present
        if 'segments' in transcript_data:
            for segment in transcript_data['segments']:
                if 'text' in segment:
                    corrected_text, _ = self.apply_corrections(
                        segment['text'], show_name, context
                    )
                    segment['text'] = corrected_text
        
        # Apply to words if present (for precise timing)
        if 'words' in transcript_data:
            for word_obj in transcript_data['words']:
                if 'word' in word_obj:
                    corrected_word, _ = self.apply_corrections(
                        word_obj['word'], show_name, context
                    )
                    word_obj['word'] = corrected_word
        
        return transcript_data
    
    def suggest_corrections(self, text: str, min_frequency: int = 3) -> List[Dict[str, Any]]:
        """
        Suggest potential corrections based on patterns in text
        (Future enhancement - placeholder for now)
        
        Args:
            text: Text to analyze
            min_frequency: Minimum frequency for suggestion
            
        Returns:
            List of suggested corrections
        """
        if not self.settings.get('suggest_corrections', False):
            return []
        
        # TODO: Implement AI-powered suggestion logic
        # - Detect common misspellings
        # - Identify inconsistent name spellings
        # - Find technical terms that need formatting
        
        logger.info("Correction suggestions not yet implemented")
        return []
    
    def get_correction_stats(self) -> Dict[str, Any]:
        """Get statistics about corrections"""
        if not self.corrections:
            return {
                'total_corrections': 0,
                'total_usage': 0,
                'avg_confidence': 0,
                'active_corrections': 0
            }
        
        total_usage = sum(c.get('usage_count', 0) for c in self.corrections)
        avg_confidence = sum(c.get('confidence', 0) for c in self.corrections) / len(self.corrections)
        active = len([c for c in self.corrections if c.get('usage_count', 0) > 0])
        
        return {
            'total_corrections': len(self.corrections),
            'total_usage': total_usage,
            'avg_confidence': avg_confidence,
            'active_corrections': active,
            'by_type': self._get_type_breakdown(),
            'by_show': self._get_show_breakdown()
        }
    
    def _get_type_breakdown(self) -> Dict[str, int]:
        """Get breakdown of corrections by type"""
        breakdown = {}
        for correction in self.corrections:
            type_name = correction.get('type', 'unknown')
            breakdown[type_name] = breakdown.get(type_name, 0) + 1
        return breakdown
    
    def _get_show_breakdown(self) -> Dict[str, int]:
        """Get breakdown of corrections by show"""
        breakdown = {}
        for correction in self.corrections:
            show = correction.get('show_name', 'All Shows')
            breakdown[show] = breakdown.get(show, 0) + 1
        return breakdown


def create_correction_engine(corrections_file: str = "data/corrections.json",
                            settings_file: str = "data/correction_settings.json") -> CorrectionEngine:
    """Factory function to create correction engine"""
    return CorrectionEngine(corrections_file, settings_file)
