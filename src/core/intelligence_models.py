"""
Typed models for Intelligence Chain with schema versioning

Defines strict pydantic models for each stage of the intelligence chain
to prevent shape drift and enable versioned artifacts.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, validator


# Schema version for intelligence chain artifacts
IC_SCHEMA_VERSION = "ic-1.0.0"


class ChainContext(BaseModel):
    """Context for intelligence chain execution"""
    job_id: str
    episode_id: str
    video_hash: str
    config_hash: str
    paths: Dict[str, str]
    force_rerun: bool = False
    start_from_step: Optional[str] = None
    stop_at_step: Optional[str] = None
    
    class Config:
        frozen = True  # Immutable


class DiarizationSegment(BaseModel):
    """Single speaker segment from diarization"""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    speaker: str = Field(..., description="Speaker ID")
    duration: float = Field(..., description="Duration in seconds")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @validator('duration')
    def validate_duration(cls, v, values):
        if 'start' in values and 'end' in values:
            expected = values['end'] - values['start']
            if abs(v - expected) > 0.01:
                raise ValueError(f"Duration {v} doesn't match end-start {expected}")
        return v


class DiarizationResult(BaseModel):
    """Result of speaker diarization stage"""
    schema_version: str = IC_SCHEMA_VERSION
    audio_file: str
    num_speakers: int
    total_duration: float
    device_used: str
    segments: List[DiarizationSegment]
    validation: Optional[Dict[str, Any]] = None
    consistency: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = True


class EntityMention(BaseModel):
    """Single entity mention from extraction"""
    name: str
    role_guess: Optional[str] = None
    org_guess: Optional[str] = None
    quotes: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    journalistic_relevance: Literal["high", "medium", "low"] = "medium"
    authority_indicators: List[str] = Field(default_factory=list)
    context: Optional[str] = None
    editorial_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class JournalisticFocus(BaseModel):
    """Journalistic analysis of content"""
    main_story_angle: str
    key_stakeholders: List[str]
    credibility_factors: List[str]


class EntitiesResult(BaseModel):
    """Result of entity extraction stage"""
    schema_version: str = IC_SCHEMA_VERSION
    transcript_file: str
    extraction_method: str
    model_used: str
    candidates: List[EntityMention]
    topics: List[str]
    journalistic_focus: Optional[JournalisticFocus] = None
    editorial_filtering_applied: bool = False
    original_candidate_count: int = 0
    filtered_candidate_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = True


class EntityEvidence(BaseModel):
    """Evidence for entity resolution"""
    source: str = Field(..., description="Source of evidence (NER, context, etc)")
    span: Optional[str] = None
    text: Optional[str] = None
    timestamp_range: Optional[tuple[float, float]] = None
    score: float = Field(..., ge=0.0, le=1.0)


class DisambiguationCandidate(BaseModel):
    """Candidate match for disambiguation"""
    qid: str
    label: str
    description: str
    score: float = Field(..., ge=0.0, le=1.0)


class EntityResolution(BaseModel):
    """Resolved entity with disambiguation data"""
    original_name: str
    wikidata_id: str
    name: str
    description: str
    job_title: Optional[str] = None
    affiliation: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    same_as: List[str] = Field(default_factory=list)
    knows_about: List[str] = Field(default_factory=list)
    
    # Authority verification
    authority_score: float = Field(..., ge=0.0, le=1.0)
    authority_level: Literal["high", "medium", "low"]
    authority_sources: List[str]
    biographical_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Journalistic metadata
    journalistic_relevance: Literal["high", "medium", "low"]
    authority_indicators: List[str] = Field(default_factory=list)
    source_credibility: Literal["verified", "unverified"]
    
    # Provenance
    evidence: List[EntityEvidence] = Field(default_factory=list)
    candidates_considered: List[DisambiguationCandidate] = Field(default_factory=list)
    decision_rule: Optional[str] = None


class ResolutionResult(BaseModel):
    """Result of disambiguation stage"""
    schema_version: str = IC_SCHEMA_VERSION
    enriched_people: List[EntityResolution]
    original_candidates: List[EntityMention]
    topics: List[str]
    summary: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = True


class ProficiencyScoreBreakdown(BaseModel):
    """Detailed breakdown of proficiency scoring"""
    roleMatch: float = Field(..., ge=0.0, le=1.0)
    authorityDomain: float = Field(..., ge=0.0, le=1.0)
    knowledgeBase: float = Field(..., ge=0.0, le=1.0)
    publications: float = Field(..., ge=0.0, le=1.0)
    recency: float = Field(..., ge=0.0, le=1.0)
    journalisticRelevance: float = Field(..., ge=0.0, le=1.0)
    authorityVerification: float = Field(..., ge=0.0, le=1.0)
    ambiguityPenalty: float = Field(..., ge=-1.0, le=0.0)


class ScoredPerson(BaseModel):
    """Person with proficiency score"""
    # Identity
    original_name: str
    wikidata_id: Optional[str] = None
    name: str
    
    # Score
    proficiencyScore: float = Field(..., ge=0.0, le=1.0)
    credibilityBadge: str
    verificationBadge: Optional[str] = None
    scoreBreakdown: ProficiencyScoreBreakdown
    
    # Editorial support
    reasoning: str
    editorialDecision: str
    authorityLevel: Literal["high", "medium", "low"]
    journalisticRelevance: Literal["high", "medium", "low"]
    
    # Criteria scores (for sub-scoring)
    criteria_scores: Dict[str, float] = Field(default_factory=dict)


class ProficiencyResult(BaseModel):
    """Result of proficiency scoring stage"""
    schema_version: str = IC_SCHEMA_VERSION
    scored_people: List[ScoredPerson]
    summary: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = True


class StepMetrics(BaseModel):
    """Metrics for a single step execution"""
    step_name: str
    duration_ms: float
    cache_hit: bool
    cache_key: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    
    # Step-specific metrics
    entities_found: Optional[int] = None
    entities_resolved: Optional[int] = None
    tokens_used: Optional[int] = None
    api_calls: Optional[int] = None
    
    timestamp: datetime = Field(default_factory=datetime.now)


class StepWarning(BaseModel):
    """Warning from a step execution"""
    step_name: str
    severity: Literal["info", "warning", "error"]
    message: str
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ChainMetadata(BaseModel):
    """Metadata for complete chain execution"""
    job_id: str
    episode_id: str
    video_hash: str
    config_hash: str
    schema_version: str = IC_SCHEMA_VERSION
    
    # Execution info
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    
    # Step tracking
    steps_completed: List[str] = Field(default_factory=list)
    steps_failed: List[str] = Field(default_factory=list)
    steps_cached: List[str] = Field(default_factory=list)
    
    # Metrics
    metrics: List[StepMetrics] = Field(default_factory=list)
    warnings: List[StepWarning] = Field(default_factory=list)
    
    # Cache info
    cache_hits: int = 0
    cache_misses: int = 0
    
    class Config:
        frozen = False  # Allow updates during execution


class ExplainabilityPayload(BaseModel):
    """Explainability data for debugging and auditing"""
    job_id: str
    episode_id: str
    schema_version: str = IC_SCHEMA_VERSION
    
    # Per-step explanations
    diarization_explain: Optional[Dict[str, Any]] = None
    entities_explain: Optional[Dict[str, Any]] = None
    disambiguation_explain: Optional[Dict[str, Any]] = None
    proficiency_explain: Optional[Dict[str, Any]] = None
    
    # Decision traces
    decision_traces: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Quality gates
    quality_gates: Dict[str, Any] = Field(default_factory=dict)
    
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        frozen = False  # Allow updates during execution


class ChainResult(BaseModel):
    """Complete result of intelligence chain execution"""
    success: bool
    metadata: ChainMetadata
    
    # Stage results
    diarization: Optional[DiarizationResult] = None
    entities: Optional[EntitiesResult] = None
    resolution: Optional[ResolutionResult] = None
    proficiency: Optional[ProficiencyResult] = None
    
    # Error info
    error: Optional[str] = None
    error_step: Optional[str] = None
    
    class Config:
        frozen = True
