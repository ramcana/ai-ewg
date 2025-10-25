"""
Clip Discovery Engine

Orchestrates the complete clip discovery pipeline from sentence alignment
through topic segmentation, highlight scoring, and clip selection.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import json

from . import get_logger
from .models import ClipObject, ClipStatus
from .sentence_alignment import SentenceAlignmentEngine
from .topic_segmentation import TopicSegmentationEngine
from .highlight_scoring import HighlightScoringSystem
from .clip_selection import ClipSelectionEngine
from .metadata_generation import MetadataGenerationEngine

logger = get_logger('pipeline.core.clip_discovery')


class ClipDiscoveryEngine:
    """
    Main orchestrator for clip discovery pipeline
    
    Coordinates sentence alignment, topic segmentation, highlight scoring,
    and clip selection to produce a set of scored clip specifications.
    """
    
    def __init__(self, config, registry, min_duration_ms: int = 20000, max_duration_ms: int = 120000):
        """Initialize clip discovery engine with configuration"""
        self.config = config
        self.registry = registry
        
        # Import here to avoid circular imports
        from .clip_selection import ClipSelectionPolicies
        
        # Initialize pipeline components
        self.sentence_alignment = SentenceAlignmentEngine()
        self.topic_segmentation = TopicSegmentationEngine(
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms
        )
        self.highlight_scoring = HighlightScoringSystem()
        
        # Store max_clips for later use
        self._default_max_clips = 8
        self._default_aspect_ratios = ["9x16", "16x9"]
        
        # Initialize clip selection with default policies
        self.clip_selection = ClipSelectionEngine()
        self.metadata_generation = MetadataGenerationEngine()
        
        logger.info("Clip discovery engine initialized",
                   min_duration_ms=min_duration_ms,
                   max_duration_ms=max_duration_ms)
    
    async def discover_clips(
        self,
        episode_id: str,
        max_clips: int = 8,
        min_duration_ms: int = 20000,
        max_duration_ms: int = 120000,
        aspect_ratios: List[str] = None,
        score_threshold: float = 0.3
    ) -> List[ClipObject]:
        """
        Discover clips for an episode
        
        Args:
            episode_id: Episode identifier
            max_clips: Maximum number of clips to discover
            min_duration_ms: Minimum clip duration
            max_duration_ms: Maximum clip duration
            aspect_ratios: Target aspect ratios
            score_threshold: Minimum score threshold
            
        Returns:
            List of discovered clip objects
        """
        try:
            logger.info(f"Starting clip discovery", 
                       episode_id=episode_id,
                       max_clips=max_clips,
                       min_duration=min_duration_ms,
                       max_duration=max_duration_ms)
            
            # Get episode data
            episode = self.registry.get_episode(episode_id)
            if not episode:
                raise ValueError(f"Episode not found: {episode_id}")
            
            if not episode.transcription or not episode.transcription.words:
                raise ValueError(f"Episode missing transcription data: {episode_id}")
            
            # Step 1: Sentence alignment
            logger.info(f"Aligning sentences", episode_id=episode_id)
            sentences = self.sentence_alignment.align_sentences(
                words=episode.transcription.words
            )
            
            if not sentences:
                logger.warning(f"No sentences found for episode", episode_id=episode_id)
                return []
            
            logger.info(f"Aligned {len(sentences)} sentences", episode_id=episode_id)
            
            # Step 1.5: Attach speaker labels if diarization available
            if episode.transcription and episode.transcription.diarization:
                logger.info(f"Attaching speaker labels", episode_id=episode_id)
                sentences = self.sentence_alignment.attach_speakers(
                    sentences=sentences,
                    diarization=episode.transcription.diarization
                )
            else:
                logger.info(f"No diarization data available, skipping speaker attachment", episode_id=episode_id)
            
            # Step 2: Topic segmentation
            logger.info(f"Creating topic segments", episode_id=episode_id)
            segments = self.topic_segmentation.segment_sentences(
                sentences=sentences,
                episode_id=episode_id
            )
            
            if not segments:
                logger.warning(f"No topic segments found for episode", episode_id=episode_id)
                return []
            
            logger.info(f"Created {len(segments)} topic segments", episode_id=episode_id)
            
            # Step 3: Highlight scoring
            logger.info(f"Scoring segments", episode_id=episode_id)
            scored_segments = self.highlight_scoring.score_segments(segments)
            
            # Filter by score threshold
            filtered_segments = [
                seg for seg in scored_segments 
                if seg.final_score >= score_threshold
            ]
            
            logger.info(f"Filtered to {len(filtered_segments)} segments above threshold {score_threshold}", 
                       episode_id=episode_id)
            
            if not filtered_segments:
                logger.warning(f"No segments above score threshold", episode_id=episode_id)
                return []
            
            # Step 4: Clip selection
            logger.info(f"Selecting clips", episode_id=episode_id)
            
            # Update policies if needed
            if max_clips != self.clip_selection.policies.max_clips_per_episode:
                from .clip_selection import ClipSelectionPolicies
                self.clip_selection.policies.max_clips_per_episode = max_clips
            
            if aspect_ratios and aspect_ratios != self.clip_selection.policies.aspect_ratios:
                self.clip_selection.policies.aspect_ratios = aspect_ratios
            
            clip_specs = self.clip_selection.select_clips(
                scored_segments=filtered_segments,
                episode_id=episode_id
            )
            
            if not clip_specs:
                logger.warning(f"No clips selected", episode_id=episode_id)
                return []
            
            # Step 5: Generate metadata
            logger.info(f"Generating metadata for {len(clip_specs)} clips", episode_id=episode_id)
            clips = []
            
            # Create a lookup map from source segment timing to scored segment
            segment_map = {}
            for scored_seg in filtered_segments:
                key = (scored_seg.segment.start_ms, scored_seg.segment.end_ms)
                segment_map[key] = scored_seg.segment
            
            for spec in clip_specs:
                # Find the source segment for this clip
                source_key = (spec.source_segment_start_ms, spec.source_segment_end_ms)
                source_segment = segment_map.get(source_key)
                
                if source_segment:
                    # Generate metadata from source segment
                    title = self.metadata_generation.generate_title(source_segment)
                    caption = self.metadata_generation.generate_caption(source_segment)
                    hashtags = self.metadata_generation.generate_hashtags(source_segment)
                else:
                    # Fallback to generic metadata
                    logger.warning(f"Could not find source segment for clip {spec.id}, using fallback metadata")
                    title = f"Clip from {episode_id}"
                    caption = f"Duration: {spec.duration_ms / 1000:.1f}s"
                    hashtags = []
                
                # Create clip object
                clip = ClipObject(
                    id=spec.id,
                    episode_id=episode_id,
                    start_ms=spec.start_ms,
                    end_ms=spec.end_ms,
                    duration_ms=spec.duration_ms,
                    score=spec.score,
                    title=title,
                    caption=caption,
                    hashtags=hashtags,
                    status=ClipStatus.PENDING
                )
                
                clips.append(clip)
            
            # Save clips metadata to file
            await self._save_clips_metadata(episode_id, clips)
            
            logger.info(f"Discovered {len(clips)} clips", episode_id=episode_id)
            return clips
            
        except Exception as e:
            logger.error(f"Error discovering clips", 
                        episode_id=episode_id, 
                        error=str(e))
            raise
    
    async def _save_clips_metadata(self, episode_id: str, clips: List[ClipObject]):
        """Save clips metadata to JSON file"""
        try:
            meta_dir = Path("data/meta")
            meta_dir.mkdir(parents=True, exist_ok=True)
            
            meta_file = meta_dir / f"{episode_id}_clips.json"
            
            # Convert clips to serializable format
            clips_data = []
            for clip in clips:
                clips_data.append({
                    "id": clip.id,
                    "episode_id": clip.episode_id,
                    "start_ms": clip.start_ms,
                    "end_ms": clip.end_ms,
                    "duration_ms": clip.duration_ms,
                    "score": clip.score,
                    "title": clip.title,
                    "caption": clip.caption,
                    "hashtags": clip.hashtags,
                    "status": clip.status,
                    "created_at": clip.created_at.isoformat() if clip.created_at else None
                })
            
            metadata = {
                "episode_id": episode_id,
                "clips_count": len(clips),
                "clips": clips_data,
                "generated_at": clips[0].created_at.isoformat() if clips else None
            }
            
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved clips metadata", 
                       episode_id=episode_id, 
                       file=str(meta_file),
                       count=len(clips))
            
        except Exception as e:
            logger.error(f"Error saving clips metadata", 
                        episode_id=episode_id, 
                        error=str(e))
            # Don't raise - this is not critical for the discovery process