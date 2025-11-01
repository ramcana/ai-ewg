"""
Clip Selection and Specification Engine

Implements platform-specific selection policies and creates clip specifications
for multi-format video generation. Handles duration targets, safe padding,
and clip metadata generation.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .highlight_scoring import ScoredSegment
from .models import ClipObject
from .logging import get_logger

logger = get_logger('clip_generation.clip_selection')


class PlatformType(Enum):
    """Social media platform types with different requirements"""
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    YOUTUBE_SHORTS = "youtube_shorts"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


@dataclass
class DurationTarget:
    """Duration target for a specific clip type"""
    min_ms: int
    max_ms: int
    optimal_ms: int
    name: str
    
    def __post_init__(self):
        """Validate duration target"""
        if self.min_ms >= self.max_ms:
            raise ValueError("min_ms must be less than max_ms")
        if not (self.min_ms <= self.optimal_ms <= self.max_ms):
            raise ValueError("optimal_ms must be between min_ms and max_ms")


@dataclass
class ClipSelectionPolicies:
    """Platform-specific clip selection policies"""
    target_durations: List[DurationTarget] = field(default_factory=lambda: [
        DurationTarget(15000, 30000, 20000, "short_hook"),    # 15-30s hooks
        DurationTarget(30000, 60000, 45000, "standard_clip"), # 30-60s standard
        DurationTarget(60000, 120000, 90000, "long_form")     # 60-120s long-form
    ])
    aspect_ratios: List[str] = field(default_factory=lambda: ["9x16", "16x9"])
    max_clips_per_segment: int = 2
    max_clips_per_episode: int = 8
    min_score_threshold: float = 0.3
    safe_padding_ms: int = 500
    
    def __post_init__(self):
        """Validate policies"""
        if self.max_clips_per_segment < 1:
            raise ValueError("max_clips_per_segment must be at least 1")
        if self.max_clips_per_episode < 1:
            raise ValueError("max_clips_per_episode must be at least 1")
        if not 0.0 <= self.min_score_threshold <= 1.0:
            raise ValueError("min_score_threshold must be between 0.0 and 1.0")
        if self.safe_padding_ms < 0:
            raise ValueError("safe_padding_ms must be non-negative")


@dataclass
class ClipSpec:
    """Specification for a clip to be generated"""
    id: str
    episode_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    aspect_ratios: List[str]
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    score: float = 0.0
    duration_target: Optional[str] = None
    source_segment_start_ms: Optional[int] = None
    source_segment_end_ms: Optional[int] = None
    
    def __post_init__(self):
        """Validate clip specification"""
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if self.duration_ms != (self.end_ms - self.start_ms):
            raise ValueError("duration_ms must equal (end_ms - start_ms)")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        
        # Validate aspect ratios
        valid_ratios = ["9x16", "16x9", "1x1"]
        for ratio in self.aspect_ratios:
            if ratio not in valid_ratios:
                raise ValueError(f"Invalid aspect ratio: {ratio}. Must be one of {valid_ratios}")
    
    def to_clip_object(self) -> ClipObject:
        """Convert to ClipObject for database storage"""
        return ClipObject.create_clip(
            episode_id=self.episode_id,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            score=self.score,
            title=self.title,
            caption=self.caption,
            hashtags=self.hashtags
        )


class ClipSelectionEngine:
    """
    Applies platform-specific policies for clip selection
    
    Selects optimal clips based on duration targets, score thresholds,
    and platform requirements while applying safe padding margins.
    """
    
    def __init__(self, policies: Optional[ClipSelectionPolicies] = None):
        """
        Initialize clip selection engine
        
        Args:
            policies: Selection policies, uses defaults if None
        """
        self.policies = policies or ClipSelectionPolicies()
        
        logger.info("ClipSelectionEngine initialized",
                   duration_targets=len(self.policies.target_durations),
                   aspect_ratios=self.policies.aspect_ratios,
                   max_clips_per_episode=self.policies.max_clips_per_episode,
                   min_score_threshold=self.policies.min_score_threshold)
    
    def select_clips(self, scored_segments: List[ScoredSegment], 
                    episode_id: str) -> List[ClipSpec]:
        """
        Select optimal clips based on duration and platform requirements
        
        Args:
            scored_segments: List of scored topic segments
            episode_id: Episode identifier
            
        Returns:
            List of clip specifications ready for generation
        """
        try:
            logger.info("Starting clip selection",
                       segments=len(scored_segments),
                       episode_id=episode_id)
            
            if not scored_segments:
                logger.warning("No segments provided for clip selection")
                return []
            
            # Filter segments by minimum score threshold
            qualified_segments = [
                segment for segment in scored_segments
                if segment.final_score >= self.policies.min_score_threshold
            ]
            
            logger.info("Segments after score filtering",
                       qualified=len(qualified_segments),
                       threshold=self.policies.min_score_threshold)
            
            if not qualified_segments:
                logger.warning("No segments meet minimum score threshold")
                return []
            
            # Generate clip specifications for each duration target
            all_clip_specs = []
            
            for duration_target in self.policies.target_durations:
                target_clips = self._select_clips_for_duration_target(
                    qualified_segments, episode_id, duration_target
                )
                all_clip_specs.extend(target_clips)
            
            # Sort by score and apply episode-level limits
            all_clip_specs.sort(key=lambda x: x.score, reverse=True)
            selected_clips = all_clip_specs[:self.policies.max_clips_per_episode]
            
            # Apply safe padding to all selected clips
            padded_clips = [
                self.apply_safe_padding(clip_spec) for clip_spec in selected_clips
            ]
            
            logger.info("Clip selection completed",
                       total_candidates=len(all_clip_specs),
                       selected_clips=len(padded_clips),
                       avg_score=sum(c.score for c in padded_clips) / len(padded_clips) if padded_clips else 0)
            
            return padded_clips
            
        except Exception as e:
            logger.error("Clip selection failed", error=str(e))
            raise
    
    def _select_clips_for_duration_target(self, 
                                        segments: List[ScoredSegment],
                                        episode_id: str,
                                        duration_target: DurationTarget) -> List[ClipSpec]:
        """
        Select clips for a specific duration target
        
        Args:
            segments: Qualified scored segments
            episode_id: Episode identifier
            duration_target: Target duration specification
            
        Returns:
            List of clip specs for this duration target
        """
        clips = []
        
        for segment in segments:
            segment_duration = segment.segment.duration_ms
            
            # Check if segment fits within duration target
            if segment_duration < duration_target.min_ms:
                # Segment too short, skip
                continue
            elif segment_duration <= duration_target.max_ms:
                # Segment fits perfectly, use entire segment
                clip_spec = self._create_clip_spec_from_segment(
                    segment, episode_id, duration_target
                )
                clips.append(clip_spec)
            else:
                # Segment too long, extract optimal sub-clips
                sub_clips = self._extract_sub_clips_from_segment(
                    segment, episode_id, duration_target
                )
                clips.extend(sub_clips)
            
            # Respect per-segment limits
            if len(clips) >= self.policies.max_clips_per_segment * len(segments):
                break
        
        # Sort by score and apply per-target limits
        clips.sort(key=lambda x: x.score, reverse=True)
        
        # Limit clips per duration target (roughly 1/3 of total episode limit)
        max_clips_for_target = max(1, self.policies.max_clips_per_episode // len(self.policies.target_durations))
        
        return clips[:max_clips_for_target]
    
    def _create_clip_spec_from_segment(self, 
                                     segment: ScoredSegment,
                                     episode_id: str,
                                     duration_target: DurationTarget) -> ClipSpec:
        """
        Create clip specification from entire segment
        
        Args:
            segment: Scored segment
            episode_id: Episode identifier
            duration_target: Duration target specification
            
        Returns:
            Clip specification
        """
        clip_id = f"clip_{uuid.uuid4().hex[:12]}"
        
        return ClipSpec(
            id=clip_id,
            episode_id=episode_id,
            start_ms=segment.segment.start_ms,
            end_ms=segment.segment.end_ms,
            duration_ms=segment.segment.duration_ms,
            aspect_ratios=self.policies.aspect_ratios.copy(),
            score=segment.final_score,
            duration_target=duration_target.name,
            source_segment_start_ms=segment.segment.start_ms,
            source_segment_end_ms=segment.segment.end_ms
        )
    
    def _extract_sub_clips_from_segment(self, 
                                      segment: ScoredSegment,
                                      episode_id: str,
                                      duration_target: DurationTarget) -> List[ClipSpec]:
        """
        Extract optimal sub-clips from a long segment
        
        Args:
            segment: Scored segment (longer than target)
            episode_id: Episode identifier
            duration_target: Duration target specification
            
        Returns:
            List of sub-clip specifications
        """
        clips = []
        sentences = segment.segment.sentences
        
        if not sentences:
            return clips
        
        # Strategy: Find the best contiguous sub-sequence of sentences
        # that fits within the duration target
        
        best_clips = []
        
        # Try different starting positions
        for start_idx in range(len(sentences)):
            current_duration = 0
            current_sentences = []
            
            # Add sentences until we exceed the optimal duration
            for end_idx in range(start_idx, len(sentences)):
                sentence = sentences[end_idx]
                sentence_duration = sentence.end_ms - sentence.start_ms
                
                if current_duration + sentence_duration > duration_target.max_ms:
                    break
                
                current_sentences.append(sentence)
                current_duration += sentence_duration
                
                # Check if we have a valid clip duration
                if current_duration >= duration_target.min_ms:
                    # Calculate score for this sub-clip
                    # Use segment score weighted by sentence count ratio
                    sentence_ratio = len(current_sentences) / len(sentences)
                    sub_clip_score = segment.final_score * sentence_ratio
                    
                    clip_id = f"clip_{uuid.uuid4().hex[:12]}"
                    
                    # Calculate actual duration from timestamps (not sum of sentence durations)
                    actual_duration_ms = current_sentences[-1].end_ms - current_sentences[0].start_ms
                    
                    clip_spec = ClipSpec(
                        id=clip_id,
                        episode_id=episode_id,
                        start_ms=current_sentences[0].start_ms,
                        end_ms=current_sentences[-1].end_ms,
                        duration_ms=actual_duration_ms,
                        aspect_ratios=self.policies.aspect_ratios.copy(),
                        score=sub_clip_score,
                        duration_target=duration_target.name,
                        source_segment_start_ms=segment.segment.start_ms,
                        source_segment_end_ms=segment.segment.end_ms
                    )
                    
                    best_clips.append(clip_spec)
        
        # Sort by score and take the best sub-clips
        best_clips.sort(key=lambda x: x.score, reverse=True)
        
        # Limit to max clips per segment for this duration target
        max_sub_clips = min(self.policies.max_clips_per_segment, 2)  # At most 2 sub-clips per segment
        
        return best_clips[:max_sub_clips]
    
    def apply_safe_padding(self, clip_spec: ClipSpec) -> ClipSpec:
        """
        Add safe margins around cut points
        
        Adds configurable padding before and after clip boundaries to ensure
        smooth cuts and avoid cutting off words or important content.
        
        Args:
            clip_spec: Original clip specification
            
        Returns:
            Clip specification with safe padding applied
        """
        try:
            # Apply padding
            padded_start_ms = max(0, clip_spec.start_ms - self.policies.safe_padding_ms)
            padded_end_ms = clip_spec.end_ms + self.policies.safe_padding_ms
            
            # Calculate new duration
            padded_duration_ms = padded_end_ms - padded_start_ms
            
            # Create new clip spec with padding
            padded_clip = ClipSpec(
                id=clip_spec.id,
                episode_id=clip_spec.episode_id,
                start_ms=padded_start_ms,
                end_ms=padded_end_ms,
                duration_ms=padded_duration_ms,
                aspect_ratios=clip_spec.aspect_ratios,
                title=clip_spec.title,
                caption=clip_spec.caption,
                hashtags=clip_spec.hashtags,
                score=clip_spec.score,
                duration_target=clip_spec.duration_target,
                source_segment_start_ms=clip_spec.source_segment_start_ms,
                source_segment_end_ms=clip_spec.source_segment_end_ms
            )
            
            logger.debug("Applied safe padding",
                        clip_id=clip_spec.id,
                        original_start=clip_spec.start_ms,
                        padded_start=padded_start_ms,
                        original_end=clip_spec.end_ms,
                        padded_end=padded_end_ms,
                        padding_ms=self.policies.safe_padding_ms)
            
            return padded_clip
            
        except Exception as e:
            logger.warning("Failed to apply safe padding, using original clip",
                          clip_id=clip_spec.id,
                          error=str(e))
            return clip_spec
    
    def get_platform_policies(self, platform: PlatformType) -> ClipSelectionPolicies:
        """
        Get optimized policies for specific social media platforms
        
        Args:
            platform: Target platform type
            
        Returns:
            Platform-optimized selection policies
        """
        base_policies = ClipSelectionPolicies()
        
        if platform == PlatformType.TIKTOK:
            # TikTok prefers vertical, shorter content
            base_policies.target_durations = [
                DurationTarget(15000, 30000, 20000, "tiktok_hook"),
                DurationTarget(30000, 60000, 45000, "tiktok_standard")
            ]
            base_policies.aspect_ratios = ["9x16"]
            base_policies.max_clips_per_episode = 6
            
        elif platform == PlatformType.INSTAGRAM_REELS:
            # Instagram Reels similar to TikTok but allows longer content
            base_policies.target_durations = [
                DurationTarget(15000, 30000, 25000, "reel_hook"),
                DurationTarget(30000, 90000, 60000, "reel_standard")
            ]
            base_policies.aspect_ratios = ["9x16"]
            base_policies.max_clips_per_episode = 8
            
        elif platform == PlatformType.YOUTUBE_SHORTS:
            # YouTube Shorts allows up to 60s
            base_policies.target_durations = [
                DurationTarget(15000, 30000, 20000, "shorts_hook"),
                DurationTarget(30000, 60000, 45000, "shorts_standard")
            ]
            base_policies.aspect_ratios = ["9x16"]
            base_policies.max_clips_per_episode = 5
            
        elif platform == PlatformType.TWITTER:
            # Twitter prefers shorter, punchy content
            base_policies.target_durations = [
                DurationTarget(15000, 45000, 30000, "twitter_clip")
            ]
            base_policies.aspect_ratios = ["16x9", "1x1"]
            base_policies.max_clips_per_episode = 4
            
        elif platform == PlatformType.LINKEDIN:
            # LinkedIn allows longer, more professional content
            base_policies.target_durations = [
                DurationTarget(30000, 90000, 60000, "linkedin_insight"),
                DurationTarget(60000, 180000, 120000, "linkedin_deep_dive")
            ]
            base_policies.aspect_ratios = ["16x9", "1x1"]
            base_policies.max_clips_per_episode = 6
            
        elif platform == PlatformType.FACEBOOK:
            # Facebook supports various formats
            base_policies.target_durations = [
                DurationTarget(15000, 60000, 30000, "facebook_short"),
                DurationTarget(60000, 180000, 90000, "facebook_long")
            ]
            base_policies.aspect_ratios = ["16x9", "1x1", "9x16"]
            base_policies.max_clips_per_episode = 8
        
        logger.info("Generated platform-specific policies",
                   platform=platform.value,
                   duration_targets=len(base_policies.target_durations),
                   aspect_ratios=base_policies.aspect_ratios,
                   max_clips=base_policies.max_clips_per_episode)
        
        return base_policies