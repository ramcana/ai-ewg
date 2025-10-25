"""
Data models for the Video Processing Pipeline

Defines the core data structures used throughout the pipeline for episodes,
metadata, processing results, and other domain objects.
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
import uuid


class ProcessingStage(Enum):
    """Processing stages for episodes"""
    DISCOVERED = "discovered"
    PREPPED = "prepped"
    TRANSCRIBED = "transcribed"
    ENRICHED = "enriched"
    RENDERED = "rendered"
    CLIPS_DISCOVERED = "clips_discovered"


class ClipStatus(Enum):
    """Status of clip processing"""
    PENDING = "pending"
    RENDERED = "rendered"
    FAILED = "failed"


@dataclass
class SourceInfo:
    """Information about the source of a video file"""
    path: str
    file_size: int
    last_modified: datetime
    source_type: str = "local"  # local, unc, external
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'file_size': self.file_size,
            'last_modified': self.last_modified.isoformat(),
            'source_type': self.source_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SourceInfo':
        return cls(
            path=data['path'],
            file_size=data['file_size'],
            last_modified=datetime.fromisoformat(data['last_modified']),
            source_type=data.get('source_type', 'local')
        )


@dataclass
class MediaInfo:
    """Media file information"""
    duration_seconds: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    resolution: Optional[str] = None
    bitrate: Optional[int] = None
    frame_rate: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MediaInfo':
        return cls(**data)


@dataclass
class EpisodeMetadata:
    """Structured metadata for an episode"""
    show_name: str
    show_slug: str
    season: Optional[int] = None
    episode: Optional[int] = None
    date: Optional[str] = None
    topic: Optional[str] = None
    topic_slug: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpisodeMetadata':
        return cls(**data)
    
    def generate_episode_id(self) -> str:
        """Generate episode ID in format: {show-slug}-s{season}e{episode}-{date}-{topic-slug}"""
        parts = [self.show_slug]
        
        if self.season is not None and self.episode is not None:
            parts.append(f"s{self.season}e{self.episode}")
        
        if self.date:
            parts.append(self.date)
        
        if self.topic_slug:
            parts.append(self.topic_slug)
        
        return "-".join(parts)


@dataclass
class TranscriptionResult:
    """Result of transcription processing"""
    text: str
    vtt_content: str
    segments: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    language: str = "en"
    model_used: str = "base"
    words: List[Dict[str, Any]] = field(default_factory=list)  # Word-level timestamps for clip generation
    diarization: Optional[Dict[str, Any]] = None  # Speaker diarization data
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranscriptionResult':
        return cls(**data)


@dataclass
class EnrichmentResult:
    """Result of AI enrichment processing"""
    diarization: Optional[Dict[str, Any]] = None
    entities: Optional[Dict[str, Any]] = None
    disambiguation: Optional[Dict[str, Any]] = None
    proficiency_scores: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnrichmentResult':
        return cls(**data)


@dataclass
class EditorialContent:
    """Editorial content generated for the episode"""
    key_takeaway: Optional[str] = None
    summary: Optional[str] = None
    topic_tags: List[str] = field(default_factory=list)
    related_episodes: List[str] = field(default_factory=list)
    quality_score: Optional[float] = None
    seo_score: Optional[float] = None
    fact_check_score: Optional[float] = None
    review_status: str = "pending"  # pending, approved, needs_revision
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EditorialContent':
        return cls(**data)


@dataclass
class EpisodeObject:
    """Complete episode object with all processing data"""
    episode_id: str
    content_hash: str
    source: SourceInfo
    media: MediaInfo
    metadata: EpisodeMetadata
    processing_stage: ProcessingStage = ProcessingStage.DISCOVERED
    transcription: Optional[TranscriptionResult] = None
    enrichment: Optional[EnrichmentResult] = None
    editorial: Optional[EditorialContent] = None
    errors: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'episode_id': self.episode_id,
            'content_hash': self.content_hash,
            'source': self.source.to_dict(),
            'media': self.media.to_dict(),
            'metadata': self.metadata.to_dict(),
            'processing_stage': self.processing_stage.value,
            'transcription': self.transcription.to_dict() if self.transcription else None,
            'enrichment': self.enrichment.to_dict() if self.enrichment else None,
            'editorial': self.editorial.to_dict() if self.editorial else None,
            'errors': self.errors,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpisodeObject':
        """Create from dictionary (database retrieval)"""
        return cls(
            episode_id=data['episode_id'],
            content_hash=data['content_hash'],
            source=SourceInfo.from_dict(data['source']),
            media=MediaInfo.from_dict(data['media']),
            metadata=EpisodeMetadata.from_dict(data['metadata']),
            processing_stage=ProcessingStage(data['processing_stage']),
            transcription=TranscriptionResult.from_dict(data['transcription']) if data.get('transcription') else None,
            enrichment=EnrichmentResult.from_dict(data['enrichment']) if data.get('enrichment') else None,
            editorial=EditorialContent.from_dict(data['editorial']) if data.get('editorial') else None,
            errors=data.get('errors'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )
    
    def update_stage(self, new_stage: ProcessingStage) -> None:
        """Update processing stage and timestamp"""
        self.processing_stage = new_stage
        self.updated_at = datetime.now()
    
    def add_error(self, error_message: str) -> None:
        """Add error message to episode"""
        if self.errors:
            self.errors += f"\n{error_message}"
        else:
            self.errors = error_message
        self.updated_at = datetime.now()
    
    def clear_errors(self) -> None:
        """Clear error messages"""
        self.errors = None
        self.updated_at = datetime.now()


@dataclass
class ProcessingEvent:
    """Processing event for logging"""
    episode_id: str
    stage: str
    status: str  # 'started', 'completed', 'failed'
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ContentHasher:
    """Utility class for generating content hashes"""
    
    @staticmethod
    def calculate_file_hash(file_path: Union[str, Path]) -> str:
        """
        Calculate content hash based on file size, path, and modification time
        
        This provides a fast hash that can detect file changes without
        reading the entire file content.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = file_path.stat()
        
        # Create hash from file metadata
        hash_input = f"{file_path.name}:{stat.st_size}:{stat.st_mtime}"
        
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    @staticmethod
    def calculate_content_hash(file_path: Union[str, Path], 
                             chunk_size: int = 8192,
                             sample_size: int = 1024 * 1024) -> str:
        """
        Calculate content hash by sampling file content
        
        For large video files, this samples the beginning, middle, and end
        to create a representative hash without reading the entire file.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path.stat().st_size
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Sample beginning
            chunk = f.read(min(sample_size, file_size))
            hasher.update(chunk)
            
            # Sample middle (if file is large enough)
            if file_size > sample_size * 3:
                f.seek(file_size // 2)
                chunk = f.read(sample_size)
                hasher.update(chunk)
            
            # Sample end (if file is large enough)
            if file_size > sample_size * 2:
                f.seek(max(0, file_size - sample_size))
                chunk = f.read(sample_size)
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    @staticmethod
    def calculate_metadata_hash(source: SourceInfo, media: MediaInfo) -> str:
        """Calculate hash from file metadata for fast deduplication"""
        hash_input = (
            f"{source.path}:"
            f"{source.file_size}:"
            f"{source.last_modified.isoformat()}:"
            f"{media.duration_seconds or 0}"
        )
        
        return hashlib.sha256(hash_input.encode()).hexdigest()


@dataclass
class ClipObject:
    """Clip discovered from an episode with metadata"""
    id: str
    episode_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    score: float
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    status: ClipStatus = ClipStatus.PENDING
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        
        # Validate data
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if self.duration_ms != (self.end_ms - self.start_ms):
            raise ValueError("duration_ms must equal (end_ms - start_ms)")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'episode_id': self.episode_id,
            'start_ms': self.start_ms,
            'end_ms': self.end_ms,
            'duration_ms': self.duration_ms,
            'score': self.score,
            'title': self.title,
            'caption': self.caption,
            'hashtags': self.hashtags,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClipObject':
        """Create from dictionary (database retrieval)"""
        return cls(
            id=data['id'],
            episode_id=data['episode_id'],
            start_ms=data['start_ms'],
            end_ms=data['end_ms'],
            duration_ms=data['duration_ms'],
            score=data['score'],
            title=data.get('title'),
            caption=data.get('caption'),
            hashtags=data.get('hashtags', []),
            status=ClipStatus(data.get('status', 'pending')),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )
    
    @classmethod
    def create_clip(cls, episode_id: str, start_ms: int, end_ms: int, score: float,
                   title: Optional[str] = None, caption: Optional[str] = None,
                   hashtags: Optional[List[str]] = None) -> 'ClipObject':
        """Factory method to create a new clip with generated ID"""
        clip_id = f"clip_{uuid.uuid4().hex[:12]}"
        duration_ms = end_ms - start_ms
        
        return cls(
            id=clip_id,
            episode_id=episode_id,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
            score=score,
            title=title,
            caption=caption,
            hashtags=hashtags or []
        )


@dataclass
class ClipAsset:
    """Generated clip asset file"""
    id: str
    clip_id: str
    path: str
    variant: str  # 'clean' or 'subtitled'
    aspect_ratio: str  # '9x16', '16x9', '1x1'
    size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        
        # Validate variant
        if self.variant not in ['clean', 'subtitled']:
            raise ValueError("variant must be 'clean' or 'subtitled'")
        
        # Validate aspect ratio
        if self.aspect_ratio not in ['9x16', '16x9', '1x1']:
            raise ValueError("aspect_ratio must be '9x16', '16x9', or '1x1'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'id': self.id,
            'clip_id': self.clip_id,
            'path': self.path,
            'variant': self.variant,
            'aspect_ratio': self.aspect_ratio,
            'size_bytes': self.size_bytes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClipAsset':
        """Create from dictionary (database retrieval)"""
        return cls(
            id=data['id'],
            clip_id=data['clip_id'],
            path=data['path'],
            variant=data['variant'],
            aspect_ratio=data['aspect_ratio'],
            size_bytes=data.get('size_bytes'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )
    
    @classmethod
    def create_asset(cls, clip_id: str, path: str, variant: str, aspect_ratio: str,
                    size_bytes: Optional[int] = None) -> 'ClipAsset':
        """Factory method to create a new clip asset with generated ID"""
        asset_id = f"asset_{uuid.uuid4().hex[:12]}"
        
        return cls(
            id=asset_id,
            clip_id=clip_id,
            path=path,
            variant=variant,
            aspect_ratio=aspect_ratio,
            size_bytes=size_bytes
        )


# Utility functions for working with models
def create_episode_from_file(file_path: Union[str, Path], 
                           metadata: EpisodeMetadata,
                           media_info: Optional[MediaInfo] = None) -> EpisodeObject:
    """Create an EpisodeObject from a file path and metadata"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    stat = file_path.stat()
    
    # Create source info
    source = SourceInfo(
        path=str(file_path),
        file_size=stat.st_size,
        last_modified=datetime.fromtimestamp(stat.st_mtime)
    )
    
    # Use provided media info or create empty
    if media_info is None:
        media_info = MediaInfo()
    
    # Calculate content hash
    content_hash = ContentHasher.calculate_metadata_hash(source, media_info)
    
    # Generate episode ID
    episode_id = metadata.generate_episode_id()
    
    return EpisodeObject(
        episode_id=episode_id,
        content_hash=content_hash,
        source=source,
        media=media_info,
        metadata=metadata
    )