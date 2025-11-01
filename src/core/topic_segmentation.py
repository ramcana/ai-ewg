"""
Topic Segmentation Engine

Creates coherent story segments using sentence embeddings and boundary detection.
Uses local embedding models with caching and the ruptures library for topic
boundary detection to identify natural story segments in episodes.
"""

import os
import pickle
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
import torch

try:
    from sentence_transformers import SentenceTransformer
except (ImportError, AttributeError, Exception) as e:
    SentenceTransformer = None

try:
    import ruptures as rpt
except ImportError:
    rpt = None

from .sentence_alignment import Sentence
from .logging import get_logger
from .exceptions import EmbeddingError, SegmentationError
from .clip_resource_manager import with_clip_resource_management

logger = get_logger('clip_generation.topic_segmentation')


@dataclass
class TopicSegment:
    """Coherent topic segment with sentences"""
    sentences: List[Sentence]
    start_ms: int
    end_ms: int
    topic_embedding: Optional[np.ndarray] = None
    
    def __post_init__(self):
        """Validate segment data"""
        if not self.sentences:
            raise ValueError("TopicSegment must contain at least one sentence")
        
        # Calculate timing from sentences if not provided
        if self.start_ms == 0 and self.end_ms == 0:
            self.start_ms = self.sentences[0].start_ms
            self.end_ms = self.sentences[-1].end_ms
        
        # Validate timing
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be less than end_ms")
    
    @property
    def duration_ms(self) -> int:
        """Get segment duration in milliseconds"""
        return self.end_ms - self.start_ms
    
    @property
    def text(self) -> str:
        """Get combined text of all sentences in segment"""
        return ' '.join(sentence.text for sentence in self.sentences)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'start_ms': self.start_ms,
            'end_ms': self.end_ms,
            'duration_ms': self.duration_ms,
            'text': self.text,
            'sentence_count': len(self.sentences),
            'sentences': [
                {
                    'text': s.text,
                    'start_ms': s.start_ms,
                    'end_ms': s.end_ms,
                    'speaker': s.speaker
                } for s in self.sentences
            ]
        }


class TopicSegmentationEngine:
    """
    Creates coherent story segments using embeddings and boundary detection
    
    Uses local embedding models (bge-small-en or all-MiniLM-L6-v2) with filesystem
    caching and the ruptures library PELT algorithm for boundary detection.
    """
    
    def __init__(self, 
                 model_name: str = "bge-small-en",
                 min_duration_ms: int = 20000,
                 max_duration_ms: int = 120000,
                 embedding_batch_size: int = 32,
                 cache_dir: Optional[str] = None):
        """
        Initialize topic segmentation engine
        
        Args:
            model_name: Embedding model name (bge-small-en or all-MiniLM-L6-v2)
            min_duration_ms: Minimum segment duration (20 seconds default)
            max_duration_ms: Maximum segment duration (120 seconds default)
            embedding_batch_size: Batch size for embedding generation
            cache_dir: Directory for embedding cache (defaults to data/cache/embeddings)
        """
        self.model_name = model_name
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.embedding_batch_size = embedding_batch_size
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = os.path.join("data", "cache", "embeddings")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding model
        self.embedding_model = None
        self._initialize_embedding_model()
        
        # Validate ruptures availability
        if rpt is None:
            raise ImportError("ruptures library is required for topic segmentation. Install with: pip install ruptures")
        
        logger.info("TopicSegmentationEngine initialized",
                   model_name=model_name,
                   min_duration_ms=min_duration_ms,
                   max_duration_ms=max_duration_ms,
                   batch_size=embedding_batch_size,
                   cache_dir=str(self.cache_dir))
    
    def _initialize_embedding_model(self) -> None:
        """Initialize the sentence embedding model with fallback mechanisms"""
        if SentenceTransformer is None:
            logger.warning("SentenceTransformer not available, using fallback mode")
            self.embedding_model = None
            return
        
        # List of models to try in order of preference
        models_to_try = [
            self.model_name,
            "all-MiniLM-L6-v2",  # Lightweight fallback
            "all-mpnet-base-v2",  # High-quality fallback
            "paraphrase-MiniLM-L6-v2"  # Final fallback
        ]
        
        # Remove duplicates while preserving order
        unique_models = []
        seen = set()
        for model in models_to_try:
            if model not in seen:
                unique_models.append(model)
                seen.add(model)
        
        last_error = None
        
        for i, model_name in enumerate(unique_models):
            try:
                # Detect GPU availability
                device = "cuda" if torch.cuda.is_available() else "cpu"
                
                logger.info("Loading embedding model", 
                          model_name=model_name,
                          attempt=i + 1,
                          total_attempts=len(unique_models),
                          device=device)
                
                self.embedding_model = SentenceTransformer(model_name, device=device)
                self.model_name = model_name
                
                logger.info("Embedding model loaded successfully",
                          model_name=model_name,
                          attempt=i + 1)
                return
                
            except Exception as e:
                error_msg = f"Failed to load embedding model {model_name}: {str(e)}"
                last_error = EmbeddingError(error_msg, model_name=model_name)
                
                logger.warning("Failed to load embedding model",
                             model_name=model_name,
                             attempt=i + 1,
                             error=str(e))
                
                # Continue to next model
                continue
        
        # All models failed
        if last_error:
            logger.error("All embedding models failed to load",
                       models_tried=unique_models,
                       final_error=str(last_error))
            raise last_error
        else:
            raise EmbeddingError("No embedding models could be loaded")
    
    @with_clip_resource_management("embedding")
    def create_embeddings(self, sentences: List[Sentence], episode_id: str) -> np.ndarray:
        """
        Generate sentence embeddings with caching and batch processing
        
        Args:
            sentences: List of sentences to embed
            episode_id: Episode ID for cache key generation
            
        Returns:
            Array of sentence embeddings (n_sentences, embedding_dim)
            
        Raises:
            EmbeddingError: If embedding generation fails and no fallback is available
        """
        if not sentences:
            logger.warning("No sentences provided for embedding generation")
            return np.array([])
        
        # Fallback mode: return random embeddings if model not available
        if self.embedding_model is None:
            logger.warning("Embedding model not available, using random embeddings as fallback")
            # Return random embeddings with consistent dimensions
            return np.random.rand(len(sentences), 384).astype(np.float32)
        
        # Generate cache key based on sentences and model
        cache_key = self._generate_cache_key(sentences, episode_id)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        # Try to load from cache
        if cache_file.exists():
            try:
                logger.info("Loading embeddings from cache", cache_file=str(cache_file))
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                # Validate cache data
                if self._validate_cached_embeddings(cached_data, sentences):
                    logger.info("Using cached embeddings", sentences=len(sentences))
                    return cached_data['embeddings']
                else:
                    logger.warning("Cache validation failed, regenerating embeddings")
            except Exception as e:
                logger.warning("Failed to load cached embeddings", error=str(e))
        
        # Try to generate embeddings with the model
        try:
            logger.info("Generating new embeddings", sentences=len(sentences), model=self.model_name)
            embeddings = self._generate_embeddings_batch(sentences)
            
            # Cache the results
            try:
                cache_data = {
                    'embeddings': embeddings,
                    'model_name': self.model_name,
                    'sentence_count': len(sentences),
                    'sentence_texts': [s.text for s in sentences],
                    'generated_at': np.datetime64('now').astype(str)
                }
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                
                logger.info("Embeddings cached successfully", cache_file=str(cache_file))
            except Exception as e:
                logger.warning("Failed to cache embeddings", error=str(e))
            
            return embeddings
            
        except Exception as e:
            logger.error("Embedding generation failed, attempting fallback", error=str(e))
            
            # Try fallback embedding generation
            try:
                fallback_embeddings = self._generate_fallback_embeddings(sentences)
                logger.info("Fallback embeddings generated successfully", 
                          sentences=len(sentences),
                          method="keyword_based")
                return fallback_embeddings
                
            except Exception as fallback_error:
                error_msg = f"Both embedding generation and fallback failed: {str(fallback_error)}"
                logger.error("All embedding methods failed", 
                           original_error=str(e),
                           fallback_error=str(fallback_error))
                raise EmbeddingError(error_msg, model_name=self.model_name)
    
    def _generate_cache_key(self, sentences: List[Sentence], episode_id: str) -> str:
        """
        Generate cache key based on sentences content and model
        
        Args:
            sentences: List of sentences
            episode_id: Episode identifier
            
        Returns:
            Cache key string
        """
        # Create hash from sentence texts, model name, and episode ID
        content = f"{episode_id}:{self.model_name}:"
        content += ":".join(s.text for s in sentences)
        
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return f"{episode_id}_{hash_obj.hexdigest()[:16]}"
    
    def _validate_cached_embeddings(self, cached_data: Dict[str, Any], sentences: List[Sentence]) -> bool:
        """
        Validate cached embedding data matches current sentences
        
        Args:
            cached_data: Cached embedding data
            sentences: Current sentences
            
        Returns:
            True if cache is valid
        """
        try:
            # Check model name
            if cached_data.get('model_name') != self.model_name:
                logger.debug("Cache model mismatch", 
                           cached=cached_data.get('model_name'),
                           current=self.model_name)
                return False
            
            # Check sentence count
            if cached_data.get('sentence_count') != len(sentences):
                logger.debug("Cache sentence count mismatch",
                           cached=cached_data.get('sentence_count'),
                           current=len(sentences))
                return False
            
            # Check sentence texts (sample first few for performance)
            cached_texts = cached_data.get('sentence_texts', [])
            current_texts = [s.text for s in sentences]
            
            sample_size = min(10, len(sentences))
            for i in range(sample_size):
                if i >= len(cached_texts) or cached_texts[i] != current_texts[i]:
                    logger.debug("Cache sentence text mismatch", index=i)
                    return False
            
            # Check embeddings shape
            embeddings = cached_data.get('embeddings')
            if embeddings is None or embeddings.shape[0] != len(sentences):
                logger.debug("Cache embeddings shape mismatch")
                return False
            
            return True
            
        except Exception as e:
            logger.debug("Cache validation error", error=str(e))
            return False
    
    def _generate_embeddings_batch(self, sentences: List[Sentence]) -> np.ndarray:
        """
        Generate embeddings using batch processing for efficiency
        
        Args:
            sentences: List of sentences to embed
            
        Returns:
            Array of embeddings
        """
        if self.embedding_model is None:
            raise RuntimeError("Embedding model not initialized")
        
        sentence_texts = [s.text for s in sentences]
        
        try:
            # Process in batches for memory efficiency
            all_embeddings = []
            
            for i in range(0, len(sentence_texts), self.embedding_batch_size):
                batch_texts = sentence_texts[i:i + self.embedding_batch_size]
                
                logger.debug("Processing embedding batch",
                           batch_start=i,
                           batch_size=len(batch_texts),
                           total_sentences=len(sentence_texts))
                
                batch_embeddings = self.embedding_model.encode(
                    batch_texts,
                    convert_to_numpy=True,
                    show_progress_bar=False
                )
                
                all_embeddings.append(batch_embeddings)
            
            # Concatenate all batches
            embeddings = np.vstack(all_embeddings)
            
            logger.info("Embeddings generated successfully",
                       sentences=len(sentences),
                       embedding_dim=embeddings.shape[1])
            
            return embeddings
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise
    
    def detect_boundaries(self, embeddings: np.ndarray, target_segments: int = 12) -> List[int]:
        """
        Use ruptures PELT algorithm to find topic boundaries
        
        Uses cosine similarity for topic boundary detection with PELT algorithm.
        Configures penalty parameter to produce 6-20 segments for typical episodes.
        
        Args:
            embeddings: Sentence embeddings array
            target_segments: Target number of segments (6-20 for typical episodes)
            
        Returns:
            List of boundary indices (sentence indices where segments end)
        """
        if embeddings.shape[0] < 2:
            logger.warning("Not enough sentences for boundary detection", sentences=embeddings.shape[0])
            return [embeddings.shape[0] - 1] if embeddings.shape[0] > 0 else []
        
        # Fallback mode: use simple time-based segmentation if ruptures not available
        if rpt is None:
            logger.warning("Ruptures library not available, using time-based segmentation fallback")
            return self._fallback_time_based_segmentation(embeddings.shape[0], target_segments)
        
        try:
            logger.info("Detecting topic boundaries with PELT algorithm",
                       sentences=embeddings.shape[0],
                       target_segments=target_segments)
            
            # Use cosine distance for semantic similarity
            from sklearn.metrics.pairwise import cosine_distances
            
            # Calculate pairwise cosine distances for semantic change detection
            distance_matrix = cosine_distances(embeddings)
            
            # Use PELT algorithm with RBF kernel for change point detection
            # RBF kernel works well with cosine distance matrices
            algo = rpt.Pelt(model="rbf", jump=1, min_size=2)
            algo.fit(distance_matrix)
            
            # Try multiple penalty values to get target segment count
            best_change_points = self._find_optimal_penalty(algo, embeddings.shape[0], target_segments)
            
            # Remove the last point (which is always n_samples)
            if best_change_points and best_change_points[-1] == embeddings.shape[0]:
                best_change_points = best_change_points[:-1]
            
            # Validate segment count is within acceptable range (6-20)
            segment_count = len(best_change_points) + 1
            if segment_count < 6 or segment_count > 20:
                logger.warning("Segment count outside target range",
                             actual_segments=segment_count,
                             target_range="6-20")
                
                # If too few segments, try lower penalty
                if segment_count < 6:
                    best_change_points = self._force_more_segments(algo, embeddings.shape[0], 6)
                # If too many segments, try higher penalty  
                elif segment_count > 20:
                    best_change_points = self._force_fewer_segments(algo, embeddings.shape[0], 20)
            
            logger.info("Boundary detection completed",
                       boundaries=len(best_change_points),
                       segments=len(best_change_points) + 1,
                       boundary_indices=best_change_points)
            
            return best_change_points
            
        except Exception as e:
            logger.error("Boundary detection failed", error=str(e))
            # Fallback: create uniform segments
            return self._create_uniform_boundaries(embeddings.shape[0], target_segments)
    
    def _find_optimal_penalty(self, algo, n_sentences: int, target_segments: int) -> List[int]:
        """
        Find optimal penalty parameter to achieve target segment count
        
        Args:
            algo: Fitted PELT algorithm instance
            n_sentences: Number of sentences
            target_segments: Target number of segments
            
        Returns:
            List of change points with optimal penalty
        """
        # Start with base penalty calculation
        base_penalty = self._calculate_penalty_base(n_sentences, target_segments)
        
        # Try different penalty multipliers
        penalty_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        best_change_points = []
        best_score = float('inf')
        
        for multiplier in penalty_multipliers:
            penalty = base_penalty * multiplier
            
            try:
                change_points = algo.predict(pen=penalty)
                if change_points and change_points[-1] == n_sentences:
                    change_points = change_points[:-1]
                
                segment_count = len(change_points) + 1
                
                # Score based on distance from target
                score = abs(segment_count - target_segments)
                
                logger.debug("Penalty trial",
                           penalty=penalty,
                           multiplier=multiplier,
                           segments=segment_count,
                           score=score)
                
                if score < best_score:
                    best_score = score
                    best_change_points = change_points
                    
                # If we hit the target exactly, use it
                if score == 0:
                    break
                    
            except Exception as e:
                logger.debug("Penalty trial failed", penalty=penalty, error=str(e))
                continue
        
        logger.info("Optimal penalty found",
                   best_segments=len(best_change_points) + 1,
                   target_segments=target_segments,
                   score=best_score)
        
        return best_change_points
    
    def _calculate_penalty_base(self, n_sentences: int, target_segments: int) -> float:
        """
        Calculate base penalty parameter
        
        Args:
            n_sentences: Number of sentences
            target_segments: Desired number of segments
            
        Returns:
            Base penalty value for PELT algorithm
        """
        # Base penalty scales with number of sentences and target segments
        base_penalty = (n_sentences / target_segments) * 2.0
        
        # Adjust for very short or very long sequences
        if n_sentences < 50:
            base_penalty *= 0.5  # Lower penalty for short sequences
        elif n_sentences > 200:
            base_penalty *= 1.5  # Higher penalty for long sequences
        
        return base_penalty
    
    def _force_more_segments(self, algo, n_sentences: int, min_segments: int) -> List[int]:
        """
        Force algorithm to produce more segments by reducing penalty
        
        Args:
            algo: Fitted PELT algorithm instance
            n_sentences: Number of sentences
            min_segments: Minimum required segments
            
        Returns:
            List of change points with more segments
        """
        # Try progressively lower penalties
        base_penalty = self._calculate_penalty_base(n_sentences, min_segments)
        
        for multiplier in [0.1, 0.2, 0.3, 0.4, 0.5]:
            penalty = base_penalty * multiplier
            
            try:
                change_points = algo.predict(pen=penalty)
                if change_points and change_points[-1] == n_sentences:
                    change_points = change_points[:-1]
                
                segment_count = len(change_points) + 1
                
                if segment_count >= min_segments:
                    logger.info("Forced more segments",
                               segments=segment_count,
                               penalty=penalty)
                    return change_points
                    
            except Exception as e:
                logger.debug("Force more segments failed", penalty=penalty, error=str(e))
                continue
        
        # Fallback to uniform segments
        logger.warning("Could not force more segments, using uniform fallback")
        return self._create_uniform_boundaries(n_sentences, min_segments)
    
    def _force_fewer_segments(self, algo, n_sentences: int, max_segments: int) -> List[int]:
        """
        Force algorithm to produce fewer segments by increasing penalty
        
        Args:
            algo: Fitted PELT algorithm instance
            n_sentences: Number of sentences
            max_segments: Maximum allowed segments
            
        Returns:
            List of change points with fewer segments
        """
        # Try progressively higher penalties
        base_penalty = self._calculate_penalty_base(n_sentences, max_segments)
        
        for multiplier in [2.0, 3.0, 4.0, 5.0, 10.0]:
            penalty = base_penalty * multiplier
            
            try:
                change_points = algo.predict(pen=penalty)
                if change_points and change_points[-1] == n_sentences:
                    change_points = change_points[:-1]
                
                segment_count = len(change_points) + 1
                
                if segment_count <= max_segments:
                    logger.info("Forced fewer segments",
                               segments=segment_count,
                               penalty=penalty)
                    return change_points
                    
            except Exception as e:
                logger.debug("Force fewer segments failed", penalty=penalty, error=str(e))
                continue
        
        # Fallback to uniform segments
        logger.warning("Could not force fewer segments, using uniform fallback")
        return self._create_uniform_boundaries(n_sentences, max_segments)
    
    def _create_uniform_boundaries(self, n_sentences: int, target_segments: int) -> List[int]:
        """
        Fallback: create uniform segment boundaries
        
        Args:
            n_sentences: Number of sentences
            target_segments: Target number of segments
            
        Returns:
            List of boundary indices
        """
        if n_sentences <= target_segments:
            return list(range(n_sentences))
        
        segment_size = n_sentences // target_segments
        boundaries = []
        
        for i in range(1, target_segments):
            boundary = i * segment_size
            if boundary < n_sentences:
                boundaries.append(boundary)
        
        logger.info("Created uniform boundaries as fallback",
                   boundaries=len(boundaries),
                   segment_size=segment_size)
        
        return boundaries
    
    def _fallback_time_based_segmentation(self, num_sentences: int, target_segments: int) -> List[int]:
        """
        Fallback segmentation based on equal time intervals
        
        Args:
            num_sentences: Total number of sentences
            target_segments: Target number of segments
            
        Returns:
            List of boundary indices
        """
        if num_sentences <= target_segments:
            return list(range(1, num_sentences + 1))
        
        # Create roughly equal segments
        segment_size = num_sentences // target_segments
        boundaries = []
        
        for i in range(1, target_segments):
            boundary = i * segment_size
            if boundary < num_sentences:
                boundaries.append(boundary)
        
        # Always include the final boundary
        boundaries.append(num_sentences)
        
        logger.info("Created fallback time-based segments", 
                   boundaries=len(boundaries), 
                   sentences=num_sentences)
        
        return boundaries
    
    def create_segments(self, sentences: List[Sentence], boundaries: List[int]) -> List[TopicSegment]:
        """
        Create topic segments enforcing min/max duration constraints
        
        Args:
            sentences: List of sentences
            boundaries: Boundary indices from boundary detection
            
        Returns:
            List of topic segments with duration constraints applied
        """
        if not sentences:
            logger.warning("No sentences provided for segment creation")
            return []
        
        logger.info("Creating topic segments",
                   sentences=len(sentences),
                   boundaries=len(boundaries))
        
        # Create initial segments from boundaries
        initial_segments = self._create_initial_segments(sentences, boundaries)
        
        # Apply duration constraints
        final_segments = self._apply_duration_constraints(initial_segments)
        
        logger.info("Topic segments created",
                   initial_segments=len(initial_segments),
                   final_segments=len(final_segments),
                   avg_duration_s=np.mean([s.duration_ms / 1000 for s in final_segments]))
        
        return final_segments
    
    def _create_initial_segments(self, sentences: List[Sentence], boundaries: List[int]) -> List[TopicSegment]:
        """
        Create initial segments from boundary indices
        
        Args:
            sentences: List of sentences
            boundaries: Boundary indices
            
        Returns:
            List of initial topic segments
        """
        segments = []
        start_idx = 0
        
        # Add boundaries and ensure we end at the last sentence
        all_boundaries = sorted(boundaries) + [len(sentences)]
        
        for boundary in all_boundaries:
            if boundary > start_idx:
                segment_sentences = sentences[start_idx:boundary]
                
                if segment_sentences:
                    segment = TopicSegment(
                        sentences=segment_sentences,
                        start_ms=segment_sentences[0].start_ms,
                        end_ms=segment_sentences[-1].end_ms
                    )
                    segments.append(segment)
                
                start_idx = boundary
        
        return segments
    
    def _apply_duration_constraints(self, segments: List[TopicSegment]) -> List[TopicSegment]:
        """
        Apply minimum and maximum duration constraints
        
        Merges segments that are too short and splits segments that are too long.
        
        Args:
            segments: Initial segments
            
        Returns:
            Segments with duration constraints applied
        """
        if not segments:
            return segments
        
        # First pass: merge segments that are too short
        merged_segments = self._merge_short_segments(segments)
        
        # Second pass: split segments that are too long
        final_segments = self._split_long_segments(merged_segments)
        
        return final_segments
    
    def _merge_short_segments(self, segments: List[TopicSegment]) -> List[TopicSegment]:
        """
        Merge segments that are below minimum duration threshold
        
        Enforces minimum segment length of 20 seconds by merging micro-segments
        with neighbors using intelligent merging strategies.
        
        Args:
            segments: Input segments
            
        Returns:
            Segments with short ones merged
        """
        if len(segments) <= 1:
            return segments
        
        logger.info("Merging short segments",
                   input_segments=len(segments),
                   min_duration_s=self.min_duration_ms / 1000)
        
        merged = []
        i = 0
        
        while i < len(segments):
            current_segment = segments[i]
            
            # Check if current segment is too short
            if current_segment.duration_ms < self.min_duration_ms:
                # Find best merge candidate
                merge_candidate = self._find_best_merge_candidate(segments, i)
                
                if merge_candidate is not None:
                    # Merge with the best candidate
                    if merge_candidate > i:
                        # Merge with next segment(s)
                        combined_sentences = []
                        combined_start = current_segment.start_ms
                        combined_end = segments[merge_candidate].end_ms
                        
                        for j in range(i, merge_candidate + 1):
                            combined_sentences.extend(segments[j].sentences)
                        
                        merged_segment = TopicSegment(
                            sentences=combined_sentences,
                            start_ms=combined_start,
                            end_ms=combined_end
                        )
                        
                        merged.append(merged_segment)
                        
                        logger.debug("Merged short segment with next",
                                   original_count=merge_candidate - i + 1,
                                   new_duration_ms=merged_segment.duration_ms,
                                   segments_merged=f"{i}-{merge_candidate}")
                        
                        i = merge_candidate + 1
                    else:
                        # Merge with previous segment (already in merged list)
                        if merged:
                            prev_segment = merged[-1]
                            combined_sentences = prev_segment.sentences + current_segment.sentences
                            
                            merged_segment = TopicSegment(
                                sentences=combined_sentences,
                                start_ms=prev_segment.start_ms,
                                end_ms=current_segment.end_ms
                            )
                            
                            merged[-1] = merged_segment
                            
                            logger.debug("Merged short segment with previous",
                                       new_duration_ms=merged_segment.duration_ms)
                        else:
                            # No previous segment, keep as is
                            merged.append(current_segment)
                        
                        i += 1
                else:
                    # No good merge candidate, keep as is
                    merged.append(current_segment)
                    logger.debug("Kept short segment (no merge candidate)",
                               duration_ms=current_segment.duration_ms)
                    i += 1
            else:
                # Segment is long enough, keep as is
                merged.append(current_segment)
                i += 1
        
        logger.info("Short segment merging completed",
                   input_segments=len(segments),
                   output_segments=len(merged),
                   segments_merged=len(segments) - len(merged))
        
        return merged
    
    def _find_best_merge_candidate(self, segments: List[TopicSegment], current_index: int) -> Optional[int]:
        """
        Find the best segment to merge with the current short segment
        
        Args:
            segments: All segments
            current_index: Index of current short segment
            
        Returns:
            Index of best merge candidate or None
        """
        current_segment = segments[current_index]
        
        # Prefer merging with next segment if it exists and won't create too long segment
        if current_index + 1 < len(segments):
            next_segment = segments[current_index + 1]
            combined_duration = current_segment.duration_ms + next_segment.duration_ms
            
            # Check if combined duration is reasonable
            if combined_duration <= self.max_duration_ms:
                return current_index + 1
            
            # If next segment is also short, try merging multiple segments
            if next_segment.duration_ms < self.min_duration_ms and current_index + 2 < len(segments):
                next_next_segment = segments[current_index + 2]
                triple_duration = combined_duration + next_next_segment.duration_ms
                
                if triple_duration <= self.max_duration_ms:
                    return current_index + 2
        
        # Fallback: merge with previous segment if it exists
        if current_index > 0:
            return current_index - 1
        
        return None
    
    def _split_long_segments(self, segments: List[TopicSegment]) -> List[TopicSegment]:
        """
        Split segments that exceed maximum duration
        
        Args:
            segments: Input segments
            
        Returns:
            Segments with long ones split
        """
        final_segments = []
        
        for segment in segments:
            if segment.duration_ms <= self.max_duration_ms:
                final_segments.append(segment)
            else:
                # Split long segment
                split_segments = self._split_segment(segment)
                final_segments.extend(split_segments)
                
                logger.debug("Split long segment",
                           original_duration_ms=segment.duration_ms,
                           split_count=len(split_segments))
        
        return final_segments
    
    def _split_segment(self, segment: TopicSegment) -> List[TopicSegment]:
        """
        Split a single segment that exceeds maximum duration
        
        Applies maximum segment duration limits by intelligently splitting
        long segments at natural boundaries while respecting minimum duration.
        
        Args:
            segment: Segment to split
            
        Returns:
            List of smaller segments
        """
        sentences = segment.sentences
        target_duration = self.max_duration_ms * 0.75  # Target 75% of max for buffer
        
        logger.debug("Splitting long segment",
                    original_duration_ms=segment.duration_ms,
                    sentence_count=len(sentences),
                    target_duration_ms=target_duration)
        
        split_segments = []
        current_sentences = []
        current_start_ms = sentences[0].start_ms
        
        for i, sentence in enumerate(sentences):
            current_sentences.append(sentence)
            current_duration = sentence.end_ms - current_start_ms
            
            # Check if we should split here
            should_split = False
            
            # Split if we've reached target duration and have enough sentences
            if current_duration >= target_duration and len(current_sentences) > 1:
                should_split = True
            
            # Force split if we're approaching max duration
            elif current_duration >= self.max_duration_ms * 0.9 and len(current_sentences) > 1:
                should_split = True
                logger.debug("Force splitting at max duration threshold")
            
            # Split at natural boundaries (speaker changes, long pauses)
            elif current_duration >= target_duration * 0.8 and self._is_natural_split_point(sentence, sentences, i):
                should_split = True
                logger.debug("Splitting at natural boundary")
            
            if should_split:
                # Ensure the split segment meets minimum duration
                if current_duration >= self.min_duration_ms:
                    split_segment = TopicSegment(
                        sentences=current_sentences,
                        start_ms=current_start_ms,
                        end_ms=current_sentences[-1].end_ms
                    )
                    split_segments.append(split_segment)
                    
                    # Start new segment with next sentence
                    current_sentences = []
                    if i + 1 < len(sentences):
                        current_start_ms = sentences[i + 1].start_ms
                else:
                    # Current segment too short, continue accumulating
                    logger.debug("Segment too short to split, continuing",
                               current_duration_ms=current_duration)
        
        # Add remaining sentences as final segment
        if current_sentences:
            final_duration = current_sentences[-1].end_ms - current_start_ms
            
            # If final segment is too short, merge with previous segment
            if (final_duration < self.min_duration_ms and 
                split_segments and 
                len(split_segments[-1].sentences) + len(current_sentences) <= 50):  # Reasonable sentence limit
                
                # Merge with last segment
                last_segment = split_segments[-1]
                combined_sentences = last_segment.sentences + current_sentences
                
                merged_segment = TopicSegment(
                    sentences=combined_sentences,
                    start_ms=last_segment.start_ms,
                    end_ms=current_sentences[-1].end_ms
                )
                
                split_segments[-1] = merged_segment
                
                logger.debug("Merged final short segment with previous",
                           final_duration_ms=merged_segment.duration_ms)
            else:
                # Keep as separate segment
                split_segment = TopicSegment(
                    sentences=current_sentences,
                    start_ms=current_start_ms,
                    end_ms=current_sentences[-1].end_ms
                )
                split_segments.append(split_segment)
        
        logger.debug("Segment splitting completed",
                    original_segments=1,
                    split_segments=len(split_segments),
                    avg_duration_ms=np.mean([s.duration_ms for s in split_segments]) if split_segments else 0)
        
        return split_segments if split_segments else [segment]
    
    def _is_natural_split_point(self, sentence: Sentence, all_sentences: List[Sentence], index: int) -> bool:
        """
        Determine if this is a natural point to split a segment
        
        Args:
            sentence: Current sentence
            all_sentences: All sentences in segment
            index: Current sentence index
            
        Returns:
            True if this is a good split point
        """
        # Don't split at the very beginning or end
        if index == 0 or index >= len(all_sentences) - 1:
            return False
        
        next_sentence = all_sentences[index + 1]
        
        # Speaker change is a natural boundary
        if sentence.speaker != next_sentence.speaker and sentence.speaker and next_sentence.speaker:
            return True
        
        # Long pause between sentences (>2 seconds)
        pause_ms = next_sentence.start_ms - sentence.end_ms
        if pause_ms > 2000:
            return True
        
        # Sentence ends with strong punctuation
        if sentence.text.strip().endswith(('.', '!', '?')):
            return True
        
        return False
    
    def segment_sentences(self, sentences: List[Sentence], episode_id: str) -> List[TopicSegment]:
        """
        Complete topic segmentation pipeline
        
        Args:
            sentences: List of sentences with timing and speaker info
            episode_id: Episode identifier for caching
            
        Returns:
            List of topic segments with duration constraints applied
        """
        try:
            logger.info("Starting topic segmentation",
                       sentences=len(sentences),
                       episode_id=episode_id)
            
            if not sentences:
                logger.warning("No sentences provided for segmentation")
                return []
            
            # Generate embeddings with caching
            embeddings = self.create_embeddings(sentences, episode_id)
            
            if embeddings.size == 0:
                logger.warning("No embeddings generated")
                return []
            
            # Calculate target segments based on episode length
            total_duration_s = (sentences[-1].end_ms - sentences[0].start_ms) / 1000
            target_segments = max(6, min(20, int(total_duration_s / 180)))  # ~3 minutes per segment
            
            # Detect boundaries
            boundaries = self.detect_boundaries(embeddings, target_segments)
            
            # Create segments with duration constraints
            segments = self.create_segments(sentences, boundaries)
            
            logger.info("Topic segmentation completed",
                       segments=len(segments),
                       total_duration_s=total_duration_s,
                       avg_segment_duration_s=np.mean([s.duration_ms / 1000 for s in segments]) if segments else 0)
            
            return segments
            
        except Exception as e:
            logger.error("Topic segmentation failed", error=str(e))
            raise
    
    def _generate_fallback_embeddings(self, sentences: List[Sentence]) -> np.ndarray:
        """
        Generate fallback embeddings using keyword-based approach
        
        When embedding models fail, this method creates simple embeddings based on
        keyword frequency and sentence similarity using basic NLP techniques.
        
        Args:
            sentences: List of sentences to embed
            
        Returns:
            Array of fallback embeddings (n_sentences, embedding_dim)
            
        Raises:
            EmbeddingError: If fallback embedding generation fails
        """
        try:
            logger.info("Generating fallback embeddings using keyword-based approach",
                       sentences=len(sentences))
            
            # Import required libraries for fallback
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.decomposition import TruncatedSVD
            except ImportError:
                raise EmbeddingError("scikit-learn is required for fallback embeddings. Install with: pip install scikit-learn")
            
            # Extract sentence texts
            sentence_texts = [s.text for s in sentences]
            
            # Create TF-IDF vectors
            vectorizer = TfidfVectorizer(
                max_features=1000,  # Limit vocabulary size
                stop_words='english',
                ngram_range=(1, 2),  # Include bigrams
                min_df=1,  # Include all terms (small corpus)
                max_df=0.95  # Remove very common terms
            )
            
            tfidf_matrix = vectorizer.fit_transform(sentence_texts)
            
            # Reduce dimensionality to create dense embeddings
            # Use smaller dimension for fallback (similar to lightweight models)
            target_dim = min(384, tfidf_matrix.shape[1], tfidf_matrix.shape[0])
            
            if target_dim < tfidf_matrix.shape[1]:
                svd = TruncatedSVD(n_components=target_dim, random_state=42)
                embeddings = svd.fit_transform(tfidf_matrix)
            else:
                embeddings = tfidf_matrix.toarray()
            
            # Normalize embeddings (similar to sentence transformers)
            from sklearn.preprocessing import normalize
            embeddings = normalize(embeddings, norm='l2')
            
            logger.info("Fallback embeddings generated successfully",
                       sentences=len(sentences),
                       embedding_dim=embeddings.shape[1],
                       method="tfidf_svd")
            
            return embeddings.astype(np.float32)
            
        except Exception as e:
            error_msg = f"Fallback embedding generation failed: {str(e)}"
            logger.error("Fallback embedding generation failed", error=str(e))
            raise EmbeddingError(error_msg)