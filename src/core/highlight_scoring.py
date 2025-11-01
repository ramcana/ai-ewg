"""
Highlight Scoring System

Hybrid scoring mechanism combining heuristics and LLM re-ranking to rate clip
worthiness for social media content. Uses local processing for privacy and
efficiency with configurable fallback mechanisms.
"""

import re
import json
import subprocess
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

try:
    import spacy
    from spacy import displacy
except ImportError:
    spacy = None

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

from .topic_segmentation import TopicSegment
from .logging import get_logger

logger = get_logger('clip_generation.highlight_scoring')


@dataclass
class ScoredSegment:
    """Topic segment with scoring information"""
    segment: TopicSegment
    heuristic_score: float
    llm_score: Optional[float] = None
    final_score: float = 0.0
    scoring_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate final score if not provided"""
        if self.final_score == 0.0:
            if self.llm_score is not None:
                # Weighted combination: 60% LLM, 40% heuristic
                self.final_score = (self.llm_score * 0.6) + (self.heuristic_score * 0.4)
            else:
                # Use heuristic score only
                self.final_score = self.heuristic_score
        
        # Ensure score is in valid range
        self.final_score = max(0.0, min(1.0, self.final_score))


class HighlightScoringSystem:
    """
    Hybrid scoring using heuristics and LLM re-ranking
    
    Combines fast local heuristic scoring with optional LLM re-ranking for
    top candidates. Includes fallback mechanisms for robust operation.
    """
    
    def __init__(self, 
                 heuristic_weights: Optional[Dict[str, float]] = None,
                 llm_enabled: bool = True,
                 llm_model: str = "llama3",
                 llm_timeout: int = 30):
        """
        Initialize highlight scoring system
        
        Args:
            heuristic_weights: Weights for different heuristic components
            llm_enabled: Whether to use LLM re-ranking
            llm_model: Local LLM model name (Ollama/Qwen/Llama3)
            llm_timeout: Timeout for LLM requests in seconds
        """
        # Default heuristic weights matching design document
        self.heuristic_weights = heuristic_weights or {
            'hook_phrases': 0.3,
            'entity_density': 0.2,
            'sentiment_peaks': 0.2,
            'qa_patterns': 0.2,
            'compression_ratio': 0.1
        }
        
        self.llm_enabled = llm_enabled
        self.llm_model = llm_model
        self.llm_timeout = llm_timeout
        
        # Initialize NLP components
        self.nlp = None
        self._initialize_nlp()
        
        # Compile regex patterns for efficiency
        self._compile_patterns()
        
        logger.info("HighlightScoringSystem initialized",
                   heuristic_weights=self.heuristic_weights,
                   llm_enabled=llm_enabled,
                   llm_model=llm_model,
                   nlp_available=self.nlp is not None)
    
    def _initialize_nlp(self) -> None:
        """Initialize spaCy NLP pipeline for entity extraction"""
        if spacy is None:
            logger.warning("spaCy not available, entity scoring will be limited")
            return
        
        try:
            # Try to load English model
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy English model loaded successfully")
        except OSError:
            try:
                # Fallback to smaller model
                self.nlp = spacy.load("en_core_web_md")
                logger.info("spaCy medium model loaded as fallback")
            except OSError:
                logger.warning("No spaCy English model found. Install with: python -m spacy download en_core_web_sm")
                self.nlp = None
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching"""
        # Hook phrases - imperative, claims, statistics
        self.hook_patterns = {
            'imperative': re.compile(r'\b(you need to|you should|you must|you have to|let me tell you|here\'s what|listen|look)\b', re.IGNORECASE),
            'claims': re.compile(r'\b(the truth is|the fact is|what really happens|the reality is|here\'s the thing|the problem is)\b', re.IGNORECASE),
            'statistics': re.compile(r'\b(\d+%|\d+\s*percent|\d+\s*times|statistics show|studies show|research shows)\b', re.IGNORECASE),
            'superlatives': re.compile(r'\b(most|best|worst|biggest|smallest|fastest|slowest|never|always|everyone|nobody)\b', re.IGNORECASE),
            'controversy': re.compile(r'\b(controversial|shocking|surprising|unbelievable|incredible|amazing|terrible|awful)\b', re.IGNORECASE)
        }
        
        # Question patterns
        self.question_patterns = {
            'direct_question': re.compile(r'\?'),
            'rhetorical': re.compile(r'\b(why|how|what|when|where|who)\b.*\?', re.IGNORECASE),
            'leading': re.compile(r'\b(did you know|have you ever|can you imagine|what if)\b', re.IGNORECASE)
        }
        
        # Answer patterns (following questions)
        self.answer_patterns = {
            'definitive': re.compile(r'\b(the answer is|it turns out|actually|in fact|basically|essentially)\b', re.IGNORECASE),
            'explanatory': re.compile(r'\b(because|since|due to|as a result|therefore|so)\b', re.IGNORECASE)
        }
        
        # Emphasis markers
        self.emphasis_patterns = {
            'caps': re.compile(r'\b[A-Z]{2,}\b'),
            'repetition': re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE),
            'intensifiers': re.compile(r'\b(very|really|extremely|incredibly|absolutely|totally|completely)\b', re.IGNORECASE)
        }
    
    def calculate_heuristic_score(self, segment: TopicSegment) -> Tuple[float, Dict[str, Any]]:
        """
        Fast local scoring using configurable weighted heuristics
        
        Args:
            segment: Topic segment to score
            
        Returns:
            Tuple of (score, metadata) where score is 0-1 and metadata contains component scores
        """
        try:
            text = segment.text
            metadata = {}
            
            # Calculate individual heuristic scores
            hook_score = self._score_hook_phrases(text)
            entity_score = self._score_entity_density(text)
            sentiment_score = self._score_sentiment_peaks(text)
            qa_score = self._score_qa_patterns(segment)
            compression_score = self._score_compression_ratio(segment)
            
            # Store component scores in metadata
            metadata.update({
                'hook_phrases_score': hook_score,
                'entity_density_score': entity_score,
                'sentiment_peaks_score': sentiment_score,
                'qa_patterns_score': qa_score,
                'compression_ratio_score': compression_score,
                'segment_duration_s': segment.duration_ms / 1000,
                'sentence_count': len(segment.sentences),
                'word_count': len(text.split())
            })
            
            # Calculate weighted final score
            final_score = (
                hook_score * self.heuristic_weights['hook_phrases'] +
                entity_score * self.heuristic_weights['entity_density'] +
                sentiment_score * self.heuristic_weights['sentiment_peaks'] +
                qa_score * self.heuristic_weights['qa_patterns'] +
                compression_score * self.heuristic_weights['compression_ratio']
            )
            
            # Normalize to 0-1 range
            final_score = max(0.0, min(1.0, final_score))
            
            logger.debug("Heuristic scoring completed",
                        segment_start_ms=segment.start_ms,
                        final_score=final_score,
                        component_scores={k: v for k, v in metadata.items() if k.endswith('_score')})
            
            return final_score, metadata
            
        except Exception as e:
            logger.error("Heuristic scoring failed", error=str(e))
            return 0.0, {'error': str(e)}
    
    def _score_hook_phrases(self, text: str) -> float:
        """
        Score based on hook phrase detection at segment start
        
        Detects imperative statements, claims, statistics, and other engaging
        opening phrases that make good social media hooks.
        
        Args:
            text: Segment text
            
        Returns:
            Hook phrase score (0-1)
        """
        # Focus on first 100 characters for hook detection
        hook_text = text[:100].lower()
        
        score = 0.0
        matches = []
        
        # Check each hook pattern type
        for pattern_type, pattern in self.hook_patterns.items():
            if pattern.search(hook_text):
                matches.append(pattern_type)
                
                # Different weights for different hook types
                if pattern_type == 'imperative':
                    score += 0.4  # Strong hook
                elif pattern_type == 'claims':
                    score += 0.35  # Strong hook
                elif pattern_type == 'statistics':
                    score += 0.3  # Good hook
                elif pattern_type == 'superlatives':
                    score += 0.2  # Moderate hook
                elif pattern_type == 'controversy':
                    score += 0.25  # Good hook
        
        # Bonus for multiple hook types
        if len(matches) > 1:
            score += 0.1
        
        # Check for numbers/statistics anywhere in first sentence
        first_sentence = text.split('.')[0] if '.' in text else text[:200]
        if re.search(r'\b\d+\b', first_sentence):
            score += 0.1
        
        return min(1.0, score)
    
    def _score_entity_density(self, text: str) -> float:
        """
        Calculate named entity density using spaCy
        
        Higher density of named entities (people, places, organizations)
        often indicates more engaging, specific content.
        
        Args:
            text: Segment text
            
        Returns:
            Entity density score (0-1)
        """
        if self.nlp is None:
            # Fallback: simple capitalized word detection
            return self._fallback_entity_scoring(text)
        
        try:
            doc = self.nlp(text)
            
            # Count different entity types
            entity_counts = {
                'PERSON': 0,
                'ORG': 0,
                'GPE': 0,  # Geopolitical entities
                'MONEY': 0,
                'DATE': 0,
                'EVENT': 0
            }
            
            total_entities = 0
            for ent in doc.ents:
                if ent.label_ in entity_counts:
                    entity_counts[ent.label_] += 1
                    total_entities += 1
            
            # Calculate density relative to text length
            word_count = len(text.split())
            if word_count == 0:
                return 0.0
            
            entity_density = total_entities / word_count
            
            # Normalize to 0-1 scale (density of 0.1 = score of 1.0)
            base_score = min(1.0, entity_density * 10)
            
            # Bonus for diverse entity types
            entity_type_count = sum(1 for count in entity_counts.values() if count > 0)
            diversity_bonus = min(0.2, entity_type_count * 0.05)
            
            final_score = min(1.0, base_score + diversity_bonus)
            
            logger.debug("Entity density scoring",
                        total_entities=total_entities,
                        word_count=word_count,
                        density=entity_density,
                        entity_types=entity_type_count,
                        score=final_score)
            
            return final_score
            
        except Exception as e:
            logger.warning("spaCy entity extraction failed, using fallback", error=str(e))
            return self._fallback_entity_scoring(text)
    
    def _fallback_entity_scoring(self, text: str) -> float:
        """
        Fallback entity scoring using simple heuristics
        
        Args:
            text: Segment text
            
        Returns:
            Estimated entity score (0-1)
        """
        words = text.split()
        if not words:
            return 0.0
        
        # Count capitalized words (potential proper nouns)
        capitalized_count = sum(1 for word in words if word[0].isupper() and len(word) > 1)
        
        # Count numbers
        number_count = sum(1 for word in words if re.search(r'\d', word))
        
        # Estimate entity density
        estimated_entities = capitalized_count + number_count
        density = estimated_entities / len(words)
        
        return min(1.0, density * 8)  # Slightly lower multiplier for fallback
    
    def _score_sentiment_peaks(self, text: str) -> float:
        """
        Detect sentiment peaks and emphasis markers
        
        Looks for emotional language, emphasis patterns, and sentiment
        extremes that indicate engaging content.
        
        Args:
            text: Segment text
            
        Returns:
            Sentiment peak score (0-1)
        """
        score = 0.0
        
        # Check emphasis patterns
        for pattern_type, pattern in self.emphasis_patterns.items():
            matches = pattern.findall(text)
            if matches:
                if pattern_type == 'caps':
                    score += min(0.3, len(matches) * 0.1)
                elif pattern_type == 'repetition':
                    score += min(0.2, len(matches) * 0.1)
                elif pattern_type == 'intensifiers':
                    score += min(0.25, len(matches) * 0.05)
        
        # Use TextBlob for sentiment analysis if available
        if TextBlob is not None:
            try:
                blob = TextBlob(text)
                sentiment_polarity = abs(blob.sentiment.polarity)  # Absolute value for peaks
                sentiment_subjectivity = blob.sentiment.subjectivity
                
                # High absolute polarity indicates strong sentiment
                sentiment_score = sentiment_polarity * 0.4
                
                # High subjectivity indicates opinion/emotion
                subjectivity_score = sentiment_subjectivity * 0.2
                
                score += sentiment_score + subjectivity_score
                
            except Exception as e:
                logger.debug("TextBlob sentiment analysis failed", error=str(e))
        
        # Check for emotional words (simple approach)
        emotional_words = [
            'amazing', 'incredible', 'shocking', 'unbelievable', 'fantastic',
            'terrible', 'awful', 'horrible', 'wonderful', 'brilliant',
            'devastating', 'heartbreaking', 'inspiring', 'motivating'
        ]
        
        text_lower = text.lower()
        emotional_count = sum(1 for word in emotional_words if word in text_lower)
        score += min(0.3, emotional_count * 0.1)
        
        return min(1.0, score)
    
    def _score_qa_patterns(self, segment: TopicSegment) -> float:
        """
        Recognize question-answer patterns within segments
        
        Q&A patterns are highly engaging for social media as they create
        natural hooks and payoffs.
        
        Args:
            segment: Topic segment with sentences
            
        Returns:
            Q&A pattern score (0-1)
        """
        sentences = [s.text for s in segment.sentences]
        if len(sentences) < 2:
            return 0.0
        
        score = 0.0
        
        # Look for question-answer pairs
        for i in range(len(sentences) - 1):
            current_sentence = sentences[i]
            next_sentence = sentences[i + 1]
            
            # Check if current sentence is a question
            is_question = False
            question_type = None
            
            for q_type, pattern in self.question_patterns.items():
                if pattern.search(current_sentence):
                    is_question = True
                    question_type = q_type
                    break
            
            if is_question:
                # Check if next sentence provides an answer
                answer_score = 0.0
                
                for a_type, pattern in self.answer_patterns.items():
                    if pattern.search(next_sentence):
                        if a_type == 'definitive':
                            answer_score = 0.4
                        elif a_type == 'explanatory':
                            answer_score = 0.3
                        break
                
                # Even without explicit answer patterns, questions followed by statements score
                if answer_score == 0.0:
                    answer_score = 0.2
                
                # Bonus for different question types
                if question_type == 'rhetorical':
                    answer_score *= 1.2
                elif question_type == 'leading':
                    answer_score *= 1.1
                
                score += answer_score
        
        # Check for questions at the beginning (good hooks)
        first_sentence = sentences[0]
        if any(pattern.search(first_sentence) for pattern in self.question_patterns.values()):
            score += 0.2
        
        # Bonus for multiple Q&A patterns
        question_count = sum(1 for sentence in sentences 
                           if any(pattern.search(sentence) for pattern in self.question_patterns.values()))
        
        if question_count > 1:
            score += min(0.2, (question_count - 1) * 0.1)
        
        return min(1.0, score)
    
    def _score_compression_ratio(self, segment: TopicSegment) -> float:
        """
        Score based on compression ratio (summary vs original length)
        
        Segments that can be summarized concisely while retaining meaning
        often make better clips as they're more focused.
        
        Args:
            segment: Topic segment
            
        Returns:
            Compression ratio score (0-1)
        """
        text = segment.text
        word_count = len(text.split())
        
        if word_count == 0:
            return 0.0
        
        # Simple heuristic: shorter, more focused segments score higher
        # Optimal range is 50-150 words for social media clips
        
        if word_count <= 50:
            # Very short - might lack substance
            return 0.6
        elif word_count <= 100:
            # Good length for clips
            return 1.0
        elif word_count <= 150:
            # Still good, slight penalty
            return 0.8
        elif word_count <= 200:
            # Getting long, more penalty
            return 0.6
        else:
            # Too long for most social media formats
            return 0.4
        
        # TODO: In future, could implement actual text summarization
        # and compare summary length to original for true compression ratio
    
    def rerank_with_llm(self, segments: List[TopicSegment], top_k: int = 10) -> List[Tuple[TopicSegment, float]]:
        """
        Re-rank top candidates using local LLM
        
        Integrates with local LLM (Ollama/Qwen/Llama3) for clip-worthiness
        scoring with fallback to heuristic-only scoring when unavailable.
        
        Args:
            segments: List of topic segments to re-rank
            top_k: Number of top segments to re-rank with LLM
            
        Returns:
            List of (segment, llm_score) tuples
        """
        if not self.llm_enabled:
            logger.info("LLM re-ranking disabled, skipping")
            return [(segment, None) for segment in segments]
        
        # Take only top candidates to avoid expensive LLM calls
        candidates = segments[:top_k]
        
        logger.info("Starting LLM re-ranking", 
                   candidates=len(candidates),
                   model=self.llm_model)
        
        results = []
        
        for segment in candidates:
            try:
                llm_score = self._score_with_llm(segment)
                results.append((segment, llm_score))
                
            except Exception as e:
                logger.warning("LLM scoring failed for segment", 
                             segment_start_ms=segment.start_ms,
                             error=str(e))
                results.append((segment, None))
        
        # Add remaining segments without LLM scores
        for segment in segments[top_k:]:
            results.append((segment, None))
        
        logger.info("LLM re-ranking completed",
                   scored_segments=sum(1 for _, score in results if score is not None),
                   total_segments=len(results))
        
        return results
    
    def _score_with_llm(self, segment: TopicSegment) -> Optional[float]:
        """
        Score a single segment using local LLM
        
        Args:
            segment: Topic segment to score
            
        Returns:
            LLM score (0-1) or None if failed
        """
        try:
            # Prepare prompt for clip-worthiness scoring
            prompt = self._create_clip_worthiness_prompt(segment)
            
            # Call local LLM via Ollama API
            response = self._call_ollama_api(prompt)
            
            if response is None:
                return None
            
            # Parse score from response
            score = self._parse_llm_score(response)
            
            logger.debug("LLM scoring completed",
                        segment_start_ms=segment.start_ms,
                        score=score,
                        response_length=len(response) if response else 0)
            
            return score
            
        except Exception as e:
            logger.error("LLM scoring failed", error=str(e))
            return None
    
    def _create_clip_worthiness_prompt(self, segment: TopicSegment) -> str:
        """
        Create prompt for LLM clip-worthiness evaluation
        
        Args:
            segment: Topic segment to evaluate
            
        Returns:
            Formatted prompt string
        """
        text = segment.text
        duration_s = segment.duration_ms / 1000
        
        prompt = f"""Evaluate this video segment for social media clip worthiness on a scale of 0-1.

Consider these factors:
- Hook potential (engaging opening)
- Shareability and viral potential
- Clear, standalone message
- Emotional impact or entertainment value
- Educational or informational value
- Appropriate length for social media ({duration_s:.1f} seconds)

Segment text:
"{text}"

Respond with just a number between 0 and 1, where:
- 0.0-0.3: Poor clip potential
- 0.4-0.6: Moderate clip potential  
- 0.7-0.9: Good clip potential
- 0.9-1.0: Excellent clip potential

Score:"""
        
        return prompt
    
    def _call_ollama_api(self, prompt: str) -> Optional[str]:
        """
        Call Ollama API for LLM inference
        
        Args:
            prompt: Input prompt
            
        Returns:
            LLM response text or None if failed
        """
        try:
            # Prepare Ollama API request
            payload = {
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent scoring
                    "top_p": 0.9,
                    "max_tokens": 50  # Short response expected
                }
            }
            
            # Use subprocess to call curl (more reliable than requests for local APIs)
            cmd = [
                "curl", "-s", "-X", "POST",
                "http://localhost:11434/api/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload),
                "--max-time", str(self.llm_timeout)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.llm_timeout + 5)
            
            if result.returncode != 0:
                logger.warning("Ollama API call failed", 
                             return_code=result.returncode,
                             stderr=result.stderr)
                return None
            
            # Parse JSON response
            response_data = json.loads(result.stdout)
            
            if "response" in response_data:
                return response_data["response"].strip()
            else:
                logger.warning("Unexpected Ollama response format", response=response_data)
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning("Ollama API call timed out")
            return None
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Ollama response", error=str(e))
            return None
        except Exception as e:
            logger.error("Ollama API call failed", error=str(e))
            return None
    
    def _parse_llm_score(self, response: str) -> Optional[float]:
        """
        Parse numerical score from LLM response
        
        Args:
            response: LLM response text
            
        Returns:
            Parsed score (0-1) or None if parsing failed
        """
        try:
            # Look for decimal number in response
            import re
            
            # Find first decimal number
            match = re.search(r'(\d*\.?\d+)', response)
            
            if match:
                score = float(match.group(1))
                
                # Ensure score is in valid range
                if 0.0 <= score <= 1.0:
                    return score
                elif score > 1.0 and score <= 10.0:
                    # Handle 0-10 scale responses
                    return score / 10.0
                else:
                    logger.warning("LLM score out of range", score=score)
                    return None
            else:
                logger.warning("No numerical score found in LLM response", response=response)
                return None
                
        except ValueError as e:
            logger.warning("Failed to parse LLM score", response=response, error=str(e))
            return None
    
    def score_segments(self, segments: List[TopicSegment]) -> List[ScoredSegment]:
        """
        Complete scoring pipeline with fallback mechanisms
        
        Args:
            segments: List of topic segments to score
            
        Returns:
            List of scored segments sorted by final score (descending)
        """
        try:
            logger.info("Starting segment scoring pipeline", segments=len(segments))
            
            if not segments:
                return []
            
            scored_segments = []
            
            # Step 1: Calculate heuristic scores for all segments
            for segment in segments:
                heuristic_score, metadata = self.calculate_heuristic_score(segment)
                
                scored_segment = ScoredSegment(
                    segment=segment,
                    heuristic_score=heuristic_score,
                    scoring_metadata=metadata
                )
                
                scored_segments.append(scored_segment)
            
            # Sort by heuristic score to identify top candidates
            scored_segments.sort(key=lambda x: x.heuristic_score, reverse=True)
            
            # Step 2: LLM re-ranking for top candidates (if enabled)
            if self.llm_enabled:
                try:
                    llm_results = self.rerank_with_llm([s.segment for s in scored_segments])
                    
                    # Update scored segments with LLM scores
                    for i, (segment, llm_score) in enumerate(llm_results):
                        if i < len(scored_segments):
                            scored_segments[i].llm_score = llm_score
                            # Recalculate final score with LLM input
                            scored_segments[i].__post_init__()
                            
                except Exception as e:
                    logger.warning("LLM re-ranking failed, using heuristic scores only", error=str(e))
            
            # Step 3: Final sort by combined scores
            scored_segments.sort(key=lambda x: x.final_score, reverse=True)
            
            # Log scoring summary
            avg_heuristic = np.mean([s.heuristic_score for s in scored_segments])
            llm_scored_count = sum(1 for s in scored_segments if s.llm_score is not None)
            avg_final = np.mean([s.final_score for s in scored_segments])
            
            logger.info("Segment scoring completed",
                       total_segments=len(scored_segments),
                       avg_heuristic_score=avg_heuristic,
                       llm_scored_segments=llm_scored_count,
                       avg_final_score=avg_final,
                       top_score=scored_segments[0].final_score if scored_segments else 0)
            
            return scored_segments
            
        except Exception as e:
            logger.error("Segment scoring pipeline failed", error=str(e))
            raise