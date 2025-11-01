"""
Pydantic models for API requests and responses
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from ..core.models import ProcessingStage


class ProcessEpisodeRequest(BaseModel):
    """Request to process a single episode"""
    episode_id: str = Field(..., description="Unique episode identifier")
    target_stage: ProcessingStage = Field(ProcessingStage.RENDERED, description="Target processing stage")
    force_reprocess: bool = Field(False, description="Force reprocessing even if already complete")


class ProcessBatchRequest(BaseModel):
    """Request to process multiple episodes"""
    episode_ids: List[str] = Field(..., description="List of episode identifiers")
    target_stage: ProcessingStage = Field(ProcessingStage.RENDERED, description="Target processing stage")
    max_concurrent: Optional[int] = Field(None, description="Maximum concurrent episodes")
    force_reprocess: bool = Field(False, description="Force reprocessing even if already complete")


class WebhookRequest(BaseModel):
    """Generic webhook request"""
    event_type: str = Field(..., description="Type of webhook event")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp")


class EpisodeMetadata(BaseModel):
    """Normalized metadata block for episode understanding"""
    show_name: Optional[str] = None
    title: Optional[str] = None
    host: Optional[str] = None
    topic: Optional[str] = None
    guests: Optional[List[str]] = None
    date: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None


class ProcessingResponse(BaseModel):
    """Response for processing operations"""
    success: bool
    episode_id: str
    stage: str
    duration: float
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    metadata: EpisodeMetadata = Field(default_factory=EpisodeMetadata)
    outputs: Optional[Dict[str, Any]] = None  # HTML, artifacts, etc.


class BatchProcessingResponse(BaseModel):
    """Response for batch processing operations"""
    total_episodes: int
    processed: int
    failed: int
    success_rate: float
    duration: float
    results: List[ProcessingResponse]


class EpisodeStatusResponse(BaseModel):
    """Response for episode status"""
    episode_id: str
    stage: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    errors: Optional[str] = None
    source_path: str
    file_size: int
    show_name: str
    title: Optional[str] = None
    show: Optional[str] = None
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    enrichment: Optional[Dict[str, Any]] = None
    transcription: Optional[Dict[str, Any]] = None


class SystemHealthResponse(BaseModel):
    """Response for system health"""
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    active_episodes: int = 0
    queue_size: int = 0
    error_rate: float = 0.0
    uptime_seconds: Optional[float] = None


class PipelineStatsResponse(BaseModel):
    """Response for pipeline statistics"""
    total_episodes: int
    processed: int
    failed: int
    success_rate: float
    duration: float


class ConfigurationResponse(BaseModel):
    """Response for configuration"""
    sources: List[Dict[str, Any]]
    processing: Dict[str, Any]
    models: Dict[str, Any]
    thresholds: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseModel):
    """Standard success response"""
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# Clip Generation API Models

class ClipDiscoveryRequest(BaseModel):
    """Request to discover clips for an episode"""
    max_clips: Optional[int] = Field(8, description="Maximum number of clips to discover")
    min_duration_ms: Optional[int] = Field(20000, description="Minimum clip duration in milliseconds")
    max_duration_ms: Optional[int] = Field(120000, description="Maximum clip duration in milliseconds")
    aspect_ratios: Optional[List[str]] = Field(["9x16", "16x9"], description="Target aspect ratios")
    score_threshold: Optional[float] = Field(0.3, description="Minimum score threshold for clips")


class ClipRenderRequest(BaseModel):
    """Request to render a specific clip"""
    variants: Optional[List[str]] = Field(["clean", "subtitled"], description="Variants to render")
    aspect_ratios: Optional[List[str]] = Field(["9x16", "16x9"], description="Aspect ratios to render")
    force_rerender: bool = Field(False, description="Force re-rendering even if assets exist")


class BulkRenderRequest(BaseModel):
    """Request to render multiple clips for an episode"""
    clip_ids: Optional[List[str]] = Field(None, description="Specific clip IDs to render (all if None)")
    variants: Optional[List[str]] = Field(["clean", "subtitled"], description="Variants to render")
    aspect_ratios: Optional[List[str]] = Field(["9x16", "16x9"], description="Aspect ratios to render")
    score_threshold: Optional[float] = Field(0.3, description="Minimum score threshold for clips")
    status_filter: Optional[str] = Field(None, description="Filter clips by status (pending, rendered, failed)")
    force_rerender: bool = Field(False, description="Force re-rendering even if assets exist")


class ClipMetadata(BaseModel):
    """Clip metadata response"""
    id: str
    episode_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    score: float
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    status: str
    created_at: Optional[str] = None


class ClipAssetInfo(BaseModel):
    """Clip asset information"""
    id: str
    path: str
    variant: str
    aspect_ratio: str
    size_bytes: Optional[int] = None
    created_at: Optional[str] = None


class ClipDiscoveryResponse(BaseModel):
    """Response for clip discovery"""
    success: bool
    episode_id: str
    clips_discovered: int
    clips: List[ClipMetadata]
    message: Optional[str] = None
    error: Optional[str] = None


class ClipRenderResponse(BaseModel):
    """Response for clip rendering"""
    success: bool
    clip_id: str
    assets_generated: int
    assets: List[ClipAssetInfo]
    message: Optional[str] = None
    error: Optional[str] = None


class BulkRenderResponse(BaseModel):
    """Response for bulk clip rendering"""
    success: bool
    episode_id: str
    clips_processed: int
    clips_successful: int
    clips_failed: int
    results: List[ClipRenderResponse]
    message: Optional[str] = None
    error: Optional[str] = None