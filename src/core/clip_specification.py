"""
Clip Specification Engine

Generates unique clip IDs and metadata, specifies aspect ratios and variants
for each selected clip, and stores clip specifications in database with
pending status.
"""

import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .clip_selection import ClipSpec
from .clip_registry import ClipRegistry
from .models import ClipObject, ClipStatus
from .logging import get_logger

logger = get_logger('clip_generation.clip_specification')


@dataclass
class ClipVariantSpec:
    """Specification for a specific clip variant"""
    aspect_ratio: str  # '9x16', '16x9', '1x1'
    variant: str       # 'clean', 'subtitled'
    output_path: str   # Expected output file path
    
    def __post_init__(self):
        """Validate variant specification"""
        valid_ratios = ["9x16", "16x9", "1x1"]
        if self.aspect_ratio not in valid_ratios:
            raise ValueError(f"Invalid aspect ratio: {self.aspect_ratio}. Must be one of {valid_ratios}")
        
        valid_variants = ["clean", "subtitled"]
        if self.variant not in valid_variants:
            raise ValueError(f"Invalid variant: {self.variant}. Must be one of {valid_variants}")


@dataclass
class ClipSpecification:
    """Complete clip specification with all variants and metadata"""
    clip_id: str
    episode_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    score: float
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    variants: List[ClipVariantSpec] = field(default_factory=list)
    duration_target: Optional[str] = None
    source_segment_start_ms: Optional[int] = None
    source_segment_end_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize creation timestamp"""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'clip_id': self.clip_id,
            'episode_id': self.episode_id,
            'start_ms': self.start_ms,
            'end_ms': self.end_ms,
            'duration_ms': self.duration_ms,
            'score': self.score,
            'title': self.title,
            'caption': self.caption,
            'hashtags': self.hashtags,
            'variants': [
                {
                    'aspect_ratio': v.aspect_ratio,
                    'variant': v.variant,
                    'output_path': v.output_path
                } for v in self.variants
            ],
            'duration_target': self.duration_target,
            'source_segment_start_ms': self.source_segment_start_ms,
            'source_segment_end_ms': self.source_segment_end_ms,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_clip_object(self) -> ClipObject:
        """Convert to ClipObject for database storage"""
        return ClipObject(
            id=self.clip_id,
            episode_id=self.episode_id,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            duration_ms=self.duration_ms,
            score=self.score,
            title=self.title,
            caption=self.caption,
            hashtags=self.hashtags,
            status=ClipStatus.PENDING,
            created_at=self.created_at
        )


class ClipSpecificationEngine:
    """
    Generates clip specifications with unique IDs and metadata
    
    Creates complete clip specifications including all aspect ratio and variant
    combinations, generates unique identifiers, and stores specifications in
    database with pending status.
    """
    
    def __init__(self, 
                 clip_registry: ClipRegistry,
                 output_base_dir: str = "data/clips",
                 variants: Optional[List[str]] = None):
        """
        Initialize clip specification engine
        
        Args:
            clip_registry: Registry for database operations
            output_base_dir: Base directory for output files (default: data/clips for consistency)
            variants: List of variants to generate (defaults to ['clean', 'subtitled'])
        """
        self.clip_registry = clip_registry
        self.output_base_dir = Path(output_base_dir)
        self.variants = variants or ['clean', 'subtitled']
        
        logger.info("ClipSpecificationEngine initialized",
                   output_base_dir=str(self.output_base_dir),
                   variants=self.variants)
    
    def create_specifications(self, clip_specs: List[ClipSpec]) -> List[ClipSpecification]:
        """
        Create complete clip specifications from clip selection results
        
        Args:
            clip_specs: List of clip specifications from selection engine
            
        Returns:
            List of complete clip specifications with variants and metadata
        """
        try:
            logger.info("Creating clip specifications", clips=len(clip_specs))
            
            specifications = []
            
            for clip_spec in clip_specs:
                # Generate unique clip ID if not provided
                clip_id = clip_spec.id or self._generate_clip_id()
                
                # Create variant specifications
                variants = self._create_variant_specs(clip_id, clip_spec)
                
                # Create complete specification
                specification = ClipSpecification(
                    clip_id=clip_id,
                    episode_id=clip_spec.episode_id,
                    start_ms=clip_spec.start_ms,
                    end_ms=clip_spec.end_ms,
                    duration_ms=clip_spec.duration_ms,
                    score=clip_spec.score,
                    title=clip_spec.title,
                    caption=clip_spec.caption,
                    hashtags=clip_spec.hashtags,
                    variants=variants,
                    duration_target=clip_spec.duration_target,
                    source_segment_start_ms=clip_spec.source_segment_start_ms,
                    source_segment_end_ms=clip_spec.source_segment_end_ms,
                    metadata=self._generate_metadata(clip_spec)
                )
                
                specifications.append(specification)
            
            logger.info("Clip specifications created",
                       specifications=len(specifications),
                       total_variants=sum(len(spec.variants) for spec in specifications))
            
            return specifications
            
        except Exception as e:
            logger.error("Failed to create clip specifications", error=str(e))
            raise
    
    def store_specifications(self, specifications: List[ClipSpecification]) -> None:
        """
        Store clip specifications in database with pending status
        
        Args:
            specifications: List of clip specifications to store
            
        Raises:
            DatabaseError: If database operations fail
        """
        try:
            logger.info("Storing clip specifications", specifications=len(specifications))
            
            stored_count = 0
            
            for specification in specifications:
                try:
                    # Convert to ClipObject and store in database
                    clip_object = specification.to_clip_object()
                    self.clip_registry.register_clip(clip_object)
                    
                    # Store specification metadata as JSON file
                    self._store_specification_metadata(specification)
                    
                    stored_count += 1
                    
                    logger.debug("Clip specification stored",
                               clip_id=specification.clip_id,
                               episode_id=specification.episode_id,
                               variants=len(specification.variants))
                    
                except Exception as e:
                    logger.error("Failed to store clip specification",
                               clip_id=specification.clip_id,
                               error=str(e))
                    # Continue with other specifications
                    continue
            
            logger.info("Clip specifications storage completed",
                       stored=stored_count,
                       total=len(specifications))
            
            if stored_count == 0:
                raise RuntimeError("No clip specifications were stored successfully")
            
        except Exception as e:
            logger.error("Failed to store clip specifications", error=str(e))
            raise
    
    def get_specification(self, clip_id: str) -> Optional[ClipSpecification]:
        """
        Retrieve clip specification by ID
        
        Args:
            clip_id: Unique clip identifier
            
        Returns:
            ClipSpecification or None if not found
        """
        try:
            # Get clip from database
            clip_object = self.clip_registry.get_clip(clip_id)
            if not clip_object:
                return None
            
            # Load specification metadata
            metadata_path = self._get_metadata_path(clip_object.episode_id, clip_id)
            
            if not metadata_path.exists():
                logger.warning("Specification metadata not found",
                             clip_id=clip_id,
                             metadata_path=str(metadata_path))
                # Create basic specification from database data
                return self._create_basic_specification(clip_object)
            
            # Load full specification from metadata
            with open(metadata_path, 'r', encoding='utf-8') as f:
                spec_data = json.load(f)
            
            return self._specification_from_dict(spec_data)
            
        except Exception as e:
            logger.error("Failed to retrieve clip specification",
                        clip_id=clip_id,
                        error=str(e))
            return None
    
    def get_specifications_for_episode(self, episode_id: str) -> List[ClipSpecification]:
        """
        Get all clip specifications for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            List of clip specifications for the episode
        """
        try:
            # Get clips from database
            clip_objects = self.clip_registry.get_clips_for_episode(episode_id)
            
            specifications = []
            
            for clip_object in clip_objects:
                specification = self.get_specification(clip_object.id)
                if specification:
                    specifications.append(specification)
            
            logger.info("Retrieved clip specifications for episode",
                       episode_id=episode_id,
                       specifications=len(specifications))
            
            return specifications
            
        except Exception as e:
            logger.error("Failed to retrieve clip specifications for episode",
                        episode_id=episode_id,
                        error=str(e))
            return []
    
    def update_specification_metadata(self, clip_id: str, 
                                    title: Optional[str] = None,
                                    caption: Optional[str] = None,
                                    hashtags: Optional[List[str]] = None) -> None:
        """
        Update clip specification metadata
        
        Args:
            clip_id: Clip to update
            title: New title (optional)
            caption: New caption (optional)
            hashtags: New hashtags (optional)
        """
        try:
            # Update database
            self.clip_registry.update_clip_metadata(clip_id, title, caption, hashtags)
            
            # Update specification file if it exists
            specification = self.get_specification(clip_id)
            if specification:
                if title is not None:
                    specification.title = title
                if caption is not None:
                    specification.caption = caption
                if hashtags is not None:
                    specification.hashtags = hashtags
                
                self._store_specification_metadata(specification)
            
            logger.info("Clip specification metadata updated",
                       clip_id=clip_id,
                       updated_title=title is not None,
                       updated_caption=caption is not None,
                       updated_hashtags=hashtags is not None)
            
        except Exception as e:
            logger.error("Failed to update clip specification metadata",
                        clip_id=clip_id,
                        error=str(e))
            raise
    
    def _generate_clip_id(self) -> str:
        """Generate unique clip ID"""
        return f"clip_{uuid.uuid4().hex[:12]}"
    
    def _create_variant_specs(self, clip_id: str, clip_spec: ClipSpec) -> List[ClipVariantSpec]:
        """
        Create variant specifications for all aspect ratios and variants
        
        Args:
            clip_id: Unique clip identifier
            clip_spec: Clip specification from selection engine
            
        Returns:
            List of variant specifications
        """
        variants = []
        
        for aspect_ratio in clip_spec.aspect_ratios:
            for variant in self.variants:
                # Generate output path
                output_path = self._generate_output_path(
                    clip_spec.episode_id, clip_id, aspect_ratio, variant
                )
                
                variant_spec = ClipVariantSpec(
                    aspect_ratio=aspect_ratio,
                    variant=variant,
                    output_path=output_path
                )
                
                variants.append(variant_spec)
        
        return variants
    
    def _generate_output_path(self, episode_id: str, clip_id: str, 
                            aspect_ratio: str, variant: str) -> str:
        """
        Generate output file path for a clip variant
        
        Args:
            episode_id: Episode identifier
            clip_id: Clip identifier
            aspect_ratio: Aspect ratio (9x16, 16x9, 1x1)
            variant: Variant type (clean, subtitled)
            
        Returns:
            Relative output file path
        """
        # Format: outputs/{episode_id}/clips/{clip_id}/{aspect_ratio}_{variant}.mp4
        filename = f"{aspect_ratio}_{variant}.mp4"
        
        output_path = self.output_base_dir / episode_id / "clips" / clip_id / filename
        
        return str(output_path)
    
    def _generate_metadata(self, clip_spec: ClipSpec) -> Dict[str, Any]:
        """
        Generate additional metadata for clip specification
        
        Args:
            clip_spec: Clip specification from selection engine
            
        Returns:
            Dictionary of additional metadata
        """
        metadata = {
            'duration_seconds': clip_spec.duration_ms / 1000,
            'aspect_ratio_count': len(clip_spec.aspect_ratios),
            'variant_count': len(self.variants),
            'total_outputs': len(clip_spec.aspect_ratios) * len(self.variants)
        }
        
        if clip_spec.duration_target:
            metadata['duration_target'] = clip_spec.duration_target
        
        if clip_spec.source_segment_start_ms is not None:
            metadata['source_segment_duration_ms'] = (
                clip_spec.source_segment_end_ms - clip_spec.source_segment_start_ms
            )
        
        return metadata
    
    def _store_specification_metadata(self, specification: ClipSpecification) -> None:
        """
        Store specification metadata as JSON file
        
        Args:
            specification: Clip specification to store
        """
        try:
            metadata_path = self._get_metadata_path(
                specification.episode_id, specification.clip_id
            )
            
            # Ensure directory exists
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write specification data
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(specification.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.debug("Specification metadata stored",
                        clip_id=specification.clip_id,
                        metadata_path=str(metadata_path))
            
        except Exception as e:
            logger.error("Failed to store specification metadata",
                        clip_id=specification.clip_id,
                        error=str(e))
            raise
    
    def _get_metadata_path(self, episode_id: str, clip_id: str) -> Path:
        """
        Get path for specification metadata file
        
        Args:
            episode_id: Episode identifier
            clip_id: Clip identifier
            
        Returns:
            Path to metadata file
        """
        return Path("data/meta") / f"{episode_id}_clip_{clip_id}_spec.json"
    
    def _create_basic_specification(self, clip_object: ClipObject) -> ClipSpecification:
        """
        Create basic specification from database clip object
        
        Args:
            clip_object: Clip object from database
            
        Returns:
            Basic clip specification
        """
        # Create default variants for common aspect ratios
        variants = []
        default_ratios = ["9x16", "16x9"]
        
        for aspect_ratio in default_ratios:
            for variant in self.variants:
                output_path = self._generate_output_path(
                    clip_object.episode_id, clip_object.id, aspect_ratio, variant
                )
                
                variant_spec = ClipVariantSpec(
                    aspect_ratio=aspect_ratio,
                    variant=variant,
                    output_path=output_path
                )
                
                variants.append(variant_spec)
        
        return ClipSpecification(
            clip_id=clip_object.id,
            episode_id=clip_object.episode_id,
            start_ms=clip_object.start_ms,
            end_ms=clip_object.end_ms,
            duration_ms=clip_object.duration_ms,
            score=clip_object.score,
            title=clip_object.title,
            caption=clip_object.caption,
            hashtags=clip_object.hashtags,
            variants=variants,
            created_at=clip_object.created_at
        )
    
    def _specification_from_dict(self, data: Dict[str, Any]) -> ClipSpecification:
        """
        Create specification from dictionary data
        
        Args:
            data: Specification data dictionary
            
        Returns:
            ClipSpecification object
        """
        # Parse variants
        variants = []
        for variant_data in data.get('variants', []):
            variant_spec = ClipVariantSpec(
                aspect_ratio=variant_data['aspect_ratio'],
                variant=variant_data['variant'],
                output_path=variant_data['output_path']
            )
            variants.append(variant_spec)
        
        # Parse creation timestamp
        created_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'])
        
        return ClipSpecification(
            clip_id=data['clip_id'],
            episode_id=data['episode_id'],
            start_ms=data['start_ms'],
            end_ms=data['end_ms'],
            duration_ms=data['duration_ms'],
            score=data['score'],
            title=data.get('title'),
            caption=data.get('caption'),
            hashtags=data.get('hashtags', []),
            variants=variants,
            duration_target=data.get('duration_target'),
            source_segment_start_ms=data.get('source_segment_start_ms'),
            source_segment_end_ms=data.get('source_segment_end_ms'),
            metadata=data.get('metadata', {}),
            created_at=created_at
        )


# Utility functions
def create_clip_specification_engine(clip_registry: ClipRegistry,
                                   output_base_dir: str = "data/clips",
                                   variants: Optional[List[str]] = None) -> ClipSpecificationEngine:
    """Factory function to create clip specification engine"""
    return ClipSpecificationEngine(clip_registry, output_base_dir, variants)