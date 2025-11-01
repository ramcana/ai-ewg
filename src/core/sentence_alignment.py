"""
Sentence Alignment Engine

Converts word-level timestamps from transcription into sentence-level segments
with speaker labels from diarization data. Handles punctuation-based sentence
boundaries and configurable timing gaps for natural speech flow.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .logging import get_logger

logger = get_logger('clip_generation.sentence_alignment')


@dataclass
class Word:
    """Word with timing information from transcription"""
    text: str
    start: float  # seconds
    end: float    # seconds
    confidence: float = 0.0


@dataclass
class Sentence:
    """Sentence with timing and speaker information"""
    text: str
    start_ms: int
    end_ms: int
    words: List[Word]
    speaker: Optional[str] = None
    confidence: float = 0.0


class SentenceAlignmentEngine:
    """
    Converts word-level timestamps to sentence-level with speaker labels
    
    Merges words into sentences based on punctuation and timing gaps,
    then attaches speaker labels using temporal overlap with diarization data.
    """
    
    def __init__(self, max_gap_ms: int = 2200):
        """
        Initialize sentence alignment engine
        
        Args:
            max_gap_ms: Maximum gap between words before forcing sentence boundary
        """
        self.max_gap_ms = max_gap_ms
        
        # Sentence-ending punctuation patterns
        self.sentence_endings = re.compile(r'[.!?]+\s*$')
        
        # Strong sentence boundaries (always split)
        self.strong_boundaries = re.compile(r'[.!?]+\s*$')
        
        # Weak boundaries (split only with timing gap)
        self.weak_boundaries = re.compile(r'[,:;]\s*$')
        
        logger.info("SentenceAlignmentEngine initialized", max_gap_ms=max_gap_ms)
    
    def align_sentences(self, words: List[Dict[str, Any]] = None, transcription_segments: List[Dict[str, Any]] = None) -> List[Sentence]:
        """
        Convert transcription segments or words with timestamps to sentences
        
        Args:
            words: List of word dictionaries with timing data (from database)
            transcription_segments: Whisper segments with word-level data (legacy)
            
        Returns:
            List of sentences with timing and text
        """
        try:
            # Handle both word lists and segment lists
            if words is not None:
                # Words provided directly (from database)
                logger.info("Starting sentence alignment from words", words=len(words))
                word_objects = [
                    Word(
                        text=w.get('word', w.get('text', '')).strip(),
                        start=w.get('start', 0.0),
                        end=w.get('end', 0.0),
                        confidence=w.get('probability', w.get('confidence', 0.0))
                    )
                    for w in words
                    if w.get('word', w.get('text', '')).strip()
                ]
            elif transcription_segments is not None:
                # Segments provided (legacy path)
                logger.info("Starting sentence alignment from segments", segments=len(transcription_segments))
                word_objects = self._extract_words_from_segments(transcription_segments)
            else:
                raise ValueError("Either 'words' or 'transcription_segments' must be provided")
            
            if not word_objects:
                logger.warning("No words found in transcription data")
                return []
            
            # Group words into sentences
            sentences = self._group_words_into_sentences(word_objects)
            
            logger.info("Sentence alignment completed", 
                       words=len(word_objects), 
                       sentences=len(sentences))
            
            return sentences
            
        except Exception as e:
            logger.error("Sentence alignment failed", error=str(e))
            raise
    
    def attach_speakers(self, sentences: List[Sentence], diarization: Dict[str, Any]) -> List[Sentence]:
        """
        Attach speaker labels to sentences based on temporal overlap
        
        Handles edge cases where speaker boundaries don't align with sentences
        using weighted overlap scoring, nearest neighbor fallback, and multi-speaker
        resolution strategies.
        
        Args:
            sentences: List of sentences with timing
            diarization: Diarization data with speaker segments
            
        Returns:
            Sentences with speaker labels attached
        """
        try:
            logger.info("Attaching speakers to sentences", 
                       sentences=len(sentences),
                       has_diarization=bool(diarization))
            
            if not diarization or 'segments' not in diarization:
                logger.warning("No diarization data available, skipping speaker attachment")
                return sentences
            
            speaker_segments = diarization['segments']
            
            if not speaker_segments:
                logger.warning("No speaker segments in diarization data")
                return sentences
            
            # Validate and sort speaker segments
            speaker_segments = self._validate_speaker_segments(speaker_segments)
            
            # Attach speakers using temporal overlap with edge case handling
            unassigned_count = 0
            multi_speaker_count = 0
            
            for sentence in sentences:
                speaker = self._find_speaker_for_sentence(sentence, speaker_segments)
                sentence.speaker = speaker
                
                if speaker is None:
                    unassigned_count += 1
            
            # Post-process to handle unassigned sentences
            if unassigned_count > 0:
                self._post_process_unassigned_speakers(sentences, speaker_segments)
            
            # Log speaker distribution and quality metrics
            speaker_counts = {}
            for sentence in sentences:
                speaker = sentence.speaker or 'unknown'
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            
            logger.info("Speaker attachment completed", 
                       speaker_distribution=speaker_counts,
                       unassigned_sentences=unassigned_count,
                       total_sentences=len(sentences))
            
            return sentences
            
        except Exception as e:
            logger.error("Speaker attachment failed", error=str(e))
            # Return sentences without speaker labels rather than failing
            return sentences
    
    def _validate_speaker_segments(self, speaker_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean speaker segments data
        
        Args:
            speaker_segments: Raw speaker segments from diarization
            
        Returns:
            Validated and sorted speaker segments
        """
        valid_segments = []
        
        for segment in speaker_segments:
            # Validate required fields
            if not all(key in segment for key in ['start', 'end', 'speaker']):
                logger.warning("Invalid speaker segment missing required fields", segment=segment)
                continue
            
            start = segment.get('start', 0.0)
            end = segment.get('end', 0.0)
            
            # Validate timing
            if start >= end or start < 0:
                logger.warning("Invalid speaker segment timing", 
                              start=start, end=end, speaker=segment.get('speaker'))
                continue
            
            valid_segments.append(segment)
        
        # Sort by start time for efficient processing
        valid_segments.sort(key=lambda x: x['start'])
        
        logger.debug("Speaker segments validated", 
                    original_count=len(speaker_segments),
                    valid_count=len(valid_segments))
        
        return valid_segments
    
    def _post_process_unassigned_speakers(self, sentences: List[Sentence], speaker_segments: List[Dict[str, Any]]) -> None:
        """
        Post-process sentences that couldn't be assigned speakers
        
        Uses context from neighboring sentences and speaker continuity patterns
        to make educated guesses for unassigned sentences.
        
        Args:
            sentences: List of sentences (modified in place)
            speaker_segments: Validated speaker segments
        """
        for i, sentence in enumerate(sentences):
            if sentence.speaker is not None:
                continue
            
            # Try context-based assignment
            context_speaker = self._infer_speaker_from_context(sentences, i)
            if context_speaker:
                sentence.speaker = context_speaker
                logger.debug("Assigned speaker from context",
                           sentence_index=i,
                           speaker=context_speaker,
                           sentence_text=sentence.text[:30])
    
    def _infer_speaker_from_context(self, sentences: List[Sentence], index: int) -> Optional[str]:
        """
        Infer speaker from neighboring sentences
        
        Args:
            sentences: All sentences
            index: Index of sentence to infer speaker for
            
        Returns:
            Inferred speaker or None
        """
        # Check previous sentence
        if index > 0 and sentences[index - 1].speaker:
            prev_speaker = sentences[index - 1].speaker
            
            # Check if there's a reasonable time gap (< 3 seconds)
            time_gap_ms = sentences[index].start_ms - sentences[index - 1].end_ms
            if time_gap_ms < 3000:
                return prev_speaker
        
        # Check next sentence
        if index < len(sentences) - 1 and sentences[index + 1].speaker:
            next_speaker = sentences[index + 1].speaker
            
            # Check if there's a reasonable time gap (< 3 seconds)
            time_gap_ms = sentences[index + 1].start_ms - sentences[index].end_ms
            if time_gap_ms < 3000:
                return next_speaker
        
        # Look for dominant speaker in nearby sentences (within 10 seconds)
        nearby_speakers = {}
        sentence_time = sentences[index].start_ms
        
        for other_sentence in sentences:
            if other_sentence.speaker and abs(other_sentence.start_ms - sentence_time) < 10000:
                speaker = other_sentence.speaker
                nearby_speakers[speaker] = nearby_speakers.get(speaker, 0) + 1
        
        if nearby_speakers:
            # Return most common nearby speaker
            return max(nearby_speakers, key=nearby_speakers.get)
        
        return None
    
    def _extract_words_from_segments(self, segments: List[Dict[str, Any]]) -> List[Word]:
        """
        Extract word-level timestamps from Whisper segments
        
        Args:
            segments: Whisper transcription segments
            
        Returns:
            List of words with timing information
        """
        words = []
        
        for segment in segments:
            # Check if segment has word-level data
            if 'words' in segment and segment['words']:
                # Use word-level timestamps
                for word_data in segment['words']:
                    word = Word(
                        text=word_data.get('word', '').strip(),
                        start=word_data.get('start', 0.0),
                        end=word_data.get('end', 0.0),
                        confidence=word_data.get('probability', 0.0)
                    )
                    if word.text:  # Skip empty words
                        words.append(word)
            else:
                # Fallback: split segment text and estimate timing
                segment_text = segment.get('text', '').strip()
                segment_start = segment.get('start', 0.0)
                segment_end = segment.get('end', 0.0)
                
                if segment_text:
                    segment_words = self._estimate_word_timing(
                        segment_text, segment_start, segment_end
                    )
                    words.extend(segment_words)
        
        return words
    
    def _estimate_word_timing(self, text: str, start: float, end: float) -> List[Word]:
        """
        Estimate word-level timing when not available from transcription
        
        Args:
            text: Segment text
            start: Segment start time
            end: Segment end time
            
        Returns:
            List of words with estimated timing
        """
        words = []
        word_texts = text.split()
        
        if not word_texts:
            return words
        
        duration = end - start
        word_duration = duration / len(word_texts)
        
        for i, word_text in enumerate(word_texts):
            word_start = start + (i * word_duration)
            word_end = word_start + word_duration
            
            word = Word(
                text=word_text,
                start=word_start,
                end=word_end,
                confidence=0.5  # Lower confidence for estimated timing
            )
            words.append(word)
        
        return words
    
    def _group_words_into_sentences(self, words: List[Word]) -> List[Sentence]:
        """
        Group words into sentences based on punctuation and timing gaps
        
        Args:
            words: List of words with timing
            
        Returns:
            List of sentences
        """
        if not words:
            return []
        
        sentences = []
        current_words = []
        
        for i, word in enumerate(words):
            current_words.append(word)
            
            # Check for sentence boundary
            should_split = self._should_split_sentence(word, words, i)
            
            if should_split or i == len(words) - 1:  # Last word
                if current_words:
                    sentence = self._create_sentence_from_words(current_words)
                    sentences.append(sentence)
                    current_words = []
        
        return sentences
    
    def _should_split_sentence(self, word: Word, words: List[Word], index: int) -> bool:
        """
        Determine if we should split sentence after this word
        
        Args:
            word: Current word
            words: All words
            index: Current word index
            
        Returns:
            True if should split sentence
        """
        # Strong punctuation always splits
        if self.strong_boundaries.search(word.text):
            return True
        
        # Check timing gap to next word
        if index < len(words) - 1:
            next_word = words[index + 1]
            gap_ms = (next_word.start - word.end) * 1000
            
            # Large gap forces split
            if gap_ms > self.max_gap_ms:
                return True
            
            # Weak punctuation + moderate gap splits
            if self.weak_boundaries.search(word.text) and gap_ms > 1000:
                return True
        
        return False
    
    def _create_sentence_from_words(self, words: List[Word]) -> Sentence:
        """
        Create sentence object from list of words
        
        Args:
            words: List of words in sentence
            
        Returns:
            Sentence object
        """
        if not words:
            raise ValueError("Cannot create sentence from empty word list")
        
        # Combine text
        text = ' '.join(word.text for word in words).strip()
        
        # Calculate timing
        start_ms = int(words[0].start * 1000)
        end_ms = int(words[-1].end * 1000)
        
        # Calculate average confidence
        confidence = sum(word.confidence for word in words) / len(words)
        
        return Sentence(
            text=text,
            start_ms=start_ms,
            end_ms=end_ms,
            words=words,
            confidence=confidence
        )
    
    def _find_speaker_for_sentence(self, sentence: Sentence, speaker_segments: List[Dict[str, Any]]) -> Optional[str]:
        """
        Find speaker for sentence using temporal overlap with edge case handling
        
        Handles cases where speaker boundaries don't align perfectly with sentences
        by using weighted overlap scoring and fallback strategies.
        
        Args:
            sentence: Sentence to find speaker for
            speaker_segments: Diarization speaker segments
            
        Returns:
            Speaker label or None
        """
        sentence_start_s = sentence.start_ms / 1000.0
        sentence_end_s = sentence.end_ms / 1000.0
        sentence_duration = sentence_end_s - sentence_start_s
        
        if sentence_duration <= 0:
            logger.warning("Invalid sentence duration", 
                          start_ms=sentence.start_ms, 
                          end_ms=sentence.end_ms)
            return None
        
        speaker_overlaps = []
        
        for segment in speaker_segments:
            speaker = segment.get('speaker', 'unknown')
            seg_start = segment.get('start', 0.0)
            seg_end = segment.get('end', 0.0)
            
            # Calculate overlap
            overlap_start = max(sentence_start_s, seg_start)
            overlap_end = min(sentence_end_s, seg_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration > 0:
                # Calculate multiple overlap metrics
                sentence_overlap_ratio = overlap_duration / sentence_duration
                segment_duration = seg_end - seg_start
                segment_overlap_ratio = overlap_duration / segment_duration if segment_duration > 0 else 0
                
                # Weighted score considering both perspectives
                weighted_score = (sentence_overlap_ratio * 0.7) + (segment_overlap_ratio * 0.3)
                
                speaker_overlaps.append({
                    'speaker': speaker,
                    'overlap_duration': overlap_duration,
                    'sentence_overlap_ratio': sentence_overlap_ratio,
                    'segment_overlap_ratio': segment_overlap_ratio,
                    'weighted_score': weighted_score,
                    'segment_start': seg_start,
                    'segment_end': seg_end
                })
        
        if not speaker_overlaps:
            # No overlapping segments - try nearest neighbor fallback
            return self._find_nearest_speaker(sentence, speaker_segments)
        
        # Sort by weighted score
        speaker_overlaps.sort(key=lambda x: x['weighted_score'], reverse=True)
        best_match = speaker_overlaps[0]
        
        # Apply confidence thresholds
        if best_match['sentence_overlap_ratio'] >= 0.5:
            # Strong confidence: >50% of sentence covered
            return best_match['speaker']
        elif best_match['sentence_overlap_ratio'] >= 0.3 and best_match['weighted_score'] >= 0.4:
            # Medium confidence: reasonable overlap with good weighted score
            return best_match['speaker']
        elif len(speaker_overlaps) == 1 and best_match['sentence_overlap_ratio'] >= 0.1:
            # Weak confidence: only one candidate with minimal overlap
            logger.debug("Weak speaker assignment", 
                        sentence_text=sentence.text[:50],
                        overlap_ratio=best_match['sentence_overlap_ratio'],
                        speaker=best_match['speaker'])
            return best_match['speaker']
        
        # Handle edge case: sentence spans multiple speakers
        if len(speaker_overlaps) > 1:
            return self._resolve_multi_speaker_sentence(sentence, speaker_overlaps)
        
        return None
    
    def _find_nearest_speaker(self, sentence: Sentence, speaker_segments: List[Dict[str, Any]]) -> Optional[str]:
        """
        Fallback: find nearest speaker when no temporal overlap exists
        
        Args:
            sentence: Sentence to find speaker for
            speaker_segments: Diarization speaker segments
            
        Returns:
            Nearest speaker label or None
        """
        sentence_start_s = sentence.start_ms / 1000.0
        sentence_end_s = sentence.end_ms / 1000.0
        sentence_center = (sentence_start_s + sentence_end_s) / 2
        
        nearest_speaker = None
        min_distance = float('inf')
        
        for segment in speaker_segments:
            speaker = segment.get('speaker', 'unknown')
            seg_start = segment.get('start', 0.0)
            seg_end = segment.get('end', 0.0)
            seg_center = (seg_start + seg_end) / 2
            
            # Calculate distance from sentence center to segment center
            distance = abs(sentence_center - seg_center)
            
            if distance < min_distance:
                min_distance = distance
                nearest_speaker = speaker
        
        # Only use nearest speaker if reasonably close (within 5 seconds)
        if min_distance <= 5.0:
            logger.debug("Using nearest speaker fallback",
                        sentence_text=sentence.text[:50],
                        distance_s=min_distance,
                        speaker=nearest_speaker)
            return nearest_speaker
        
        return None
    
    def _resolve_multi_speaker_sentence(self, sentence: Sentence, speaker_overlaps: List[Dict[str, Any]]) -> Optional[str]:
        """
        Handle sentences that span multiple speakers
        
        Uses the speaker with the most overlap, but logs the multi-speaker situation
        for potential future handling (e.g., splitting the sentence).
        
        Args:
            sentence: Sentence spanning multiple speakers
            speaker_overlaps: List of speaker overlap data
            
        Returns:
            Primary speaker label
        """
        # Use speaker with highest overlap duration
        primary_speaker = max(speaker_overlaps, key=lambda x: x['overlap_duration'])
        
        # Log multi-speaker situation for analysis
        speaker_list = [f"{s['speaker']}({s['sentence_overlap_ratio']:.2f})" 
                       for s in speaker_overlaps[:3]]  # Top 3 speakers
        
        logger.debug("Multi-speaker sentence detected",
                    sentence_text=sentence.text[:50],
                    speakers=speaker_list,
                    primary_speaker=primary_speaker['speaker'])
        
        return primary_speaker['speaker']