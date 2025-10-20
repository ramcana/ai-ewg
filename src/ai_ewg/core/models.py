"""SQLModel database models for the registry."""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


class EpisodeState(str, Enum):
    """Episode processing state machine."""
    NEW = "NEW"
    NORMALIZED = "NORMALIZED"
    TRANSCRIBED = "TRANSCRIBED"
    DIARIZED = "DIARIZED"
    ENRICHED = "ENRICHED"
    RENDERED = "RENDERED"
    PUBLISHED = "PUBLISHED"
    ERROR = "ERROR"


class ArtifactKind(str, Enum):
    """Types of artifacts generated."""
    AUDIO = "audio"
    TRANSCRIPT_TXT = "transcript_txt"
    TRANSCRIPT_VTT = "transcript_vtt"
    DIARIZATION = "diarization"
    ENTITIES = "entities"
    METADATA = "metadata"
    HTML = "html"
    THUMBNAIL = "thumbnail"


class Episode(SQLModel, table=True):
    """Core episode registry."""
    __tablename__ = "episodes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: str = Field(unique=True, index=True)  # URL-safe slug
    abs_path: str = Field(index=True)  # Absolute path to source video
    sha256: Optional[str] = Field(default=None, index=True)
    size_bytes: Optional[int] = None
    mtime: Optional[datetime] = None
    
    # Metadata
    show: str = Field(index=True)
    show_slug: str = Field(index=True)
    episode_title: Optional[str] = None
    episode_date: Optional[datetime] = Field(default=None, index=True)
    duration_seconds: Optional[float] = None
    
    # State tracking
    state: EpisodeState = Field(default=EpisodeState.NEW, index=True)
    last_error: Optional[str] = None
    retry_count: int = Field(default=0)
    
    # Timestamps
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Relationships
    artifacts: list["Artifact"] = Relationship(back_populates="episode")
    entity_mentions: list["EntityMention"] = Relationship(back_populates="episode")


class Artifact(SQLModel, table=True):
    """Generated artifacts per episode."""
    __tablename__ = "artifacts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episodes.id", index=True)
    
    kind: ArtifactKind = Field(index=True)
    rel_path: str  # Relative to data/ root
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    
    # Processing metadata
    duration_ms: Optional[int] = None  # How long it took to generate
    model_version: Optional[str] = None  # e.g., "faster-whisper-large-v3"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    episode: Episode = Relationship(back_populates="artifacts")


class Person(SQLModel, table=True):
    """Disambiguated people registry."""
    __tablename__ = "people"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    norm_name: str = Field(index=True)  # Normalized for matching
    
    # External IDs
    wikidata_id: Optional[str] = Field(default=None, unique=True, index=True)
    wikipedia_url: Optional[str] = None
    
    # Disambiguation metadata
    confidence: float = Field(default=0.0)  # 0.0-1.0
    birth_year: Optional[int] = None
    country: Optional[str] = None
    occupation: Optional[str] = None
    description: Optional[str] = None
    
    # Stats
    mention_count: int = Field(default=0)
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    mentions: list["EntityMention"] = Relationship(back_populates="person")


class EntityMention(SQLModel, table=True):
    """Entity mentions in episodes (many-to-many)."""
    __tablename__ = "entity_mentions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episodes.id", index=True)
    person_id: Optional[int] = Field(default=None, foreign_key="people.id", index=True)
    
    # Raw mention data
    raw_name: str
    mention_count: int = Field(default=1)
    context: Optional[str] = None  # Surrounding text
    
    # Scoring
    relevance_score: float = Field(default=0.0)
    is_primary: bool = Field(default=False)  # Host or main guest
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    episode: Episode = Relationship(back_populates="entity_mentions")
    person: Optional[Person] = Relationship(back_populates="mentions")


class ProcessingRun(SQLModel, table=True):
    """Audit trail for pipeline runs."""
    __tablename__ = "runs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True, index=True)  # UUID or timestamp-based
    
    # Context
    stage: str = Field(index=True)
    command: str
    user: Optional[str] = None
    hostname: Optional[str] = None
    git_commit: Optional[str] = None
    
    # Results
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    success: bool = Field(default=False)
    error_message: Optional[str] = None
    
    # Stats
    episodes_processed: int = Field(default=0)
    episodes_failed: int = Field(default=0)
    episodes_skipped: int = Field(default=0)
    summary_json: Optional[str] = None  # JSON blob with detailed stats


class EntityCache(SQLModel, table=True):
    """Cache for entity disambiguation lookups."""
    __tablename__ = "entity_cache"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    norm_name: str = Field(unique=True, index=True)
    
    # Cached data
    wikidata_id: Optional[str] = None
    wikipedia_url: Optional[str] = None
    metadata_json: Optional[str] = None  # Full response cache
    
    # Cache metadata
    confidence: float = Field(default=0.0)
    hit_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # For TTL-based invalidation
