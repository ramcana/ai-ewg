"""
Pydantic-based settings validation for the Video Processing Pipeline

Validates configuration on startup and provides type-safe settings access.
"""

from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class SourceSettings(BaseModel):
    """Video source configuration"""
    path: str
    include: List[str] = Field(default_factory=lambda: ["*.mp4", "*.mkv", "*.avi", "*.mov"])
    exclude: List[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path exists or warn"""
        path = Path(v)
        if not path.exists():
            # Warning only - path might be created later or on network
            pass
        return v


class StagingSettings(BaseModel):
    """Staging area configuration"""
    enabled: bool = True
    path: str = "staging"
    cleanup_after_processing: bool = True


class DiscoverySettings(BaseModel):
    """Video discovery configuration"""
    stability_minutes: int = Field(default=5, ge=0, le=60)
    max_concurrent_scans: int = Field(default=4, ge=1, le=64)
    scan_interval_seconds: int = Field(default=300, ge=30)


class ModelSettings(BaseModel):
    """AI model configuration"""
    whisper: Literal["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"] = "large-v3"
    whisper_device: Literal["auto", "cuda", "cpu"] = "auto"
    whisper_compute_type: Literal["int8", "int8_float16", "int16", "float16", "float32"] = "float16"
    llm: str = "mistral"
    diarization_device: Literal["cuda", "cpu"] = "cuda"
    num_speakers: int = Field(default=2, ge=1, le=10)


class OllamaSettings(BaseModel):
    """Ollama LLM configuration"""
    enabled: bool = True
    host: str = "http://localhost:11434"
    model: str = "llama3.1:latest"
    timeout: int = Field(default=300, ge=30, le=3600)


class EnrichmentSettings(BaseModel):
    """Enrichment configuration"""
    ollama_enabled: bool = True
    summary_max_tokens: int = Field(default=500, ge=100, le=2000)
    takeaways_count: int = Field(default=7, ge=3, le=15)
    topics_count: int = Field(default=10, ge=5, le=30)
    segment_chunk_size: int = Field(default=10, ge=5, le=50)


class ThresholdSettings(BaseModel):
    """Confidence thresholds"""
    confidence_min: float = Field(default=0.6, ge=0.0, le=1.0)
    entity_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    expert_score: float = Field(default=0.75, ge=0.0, le=1.0)
    publish_score: float = Field(default=0.6, ge=0.0, le=1.0)


class DatabaseSettings(BaseModel):
    """Database configuration"""
    path: str = "data/pipeline.db"
    backup_enabled: bool = True
    backup_interval_hours: int = Field(default=24, ge=1)


class LoggingSettings(BaseModel):
    """Logging configuration"""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    directory: str = "logs"
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    backup_count: int = Field(default=5, ge=1, le=30)
    console: bool = True
    structured: bool = True


class ProcessingSettings(BaseModel):
    """Processing limits and concurrency"""
    max_concurrent_episodes: int = Field(default=4, ge=1, le=32)
    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=30, ge=5, le=300)
    timeout_minutes: int = Field(default=120, ge=10, le=480)


class ResourceSettings(BaseModel):
    """Resource limits"""
    max_memory_percent: float = Field(default=95.0, ge=50.0, le=99.0)
    max_cpu_percent: float = Field(default=95.0, ge=50.0, le=100.0)
    max_disk_usage_percent: float = Field(default=95.0, ge=50.0, le=99.0)
    max_open_files: int = Field(default=4000, ge=100, le=10000)


class PipelineSettings(BaseSettings):
    """Main pipeline settings with validation"""
    
    model_config = SettingsConfigDict(
        env_prefix="PIPELINE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core settings
    sources: List[SourceSettings] = Field(default_factory=list)
    staging: StagingSettings = Field(default_factory=StagingSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    resources: ResourceSettings = Field(default_factory=ResourceSettings)
    
    # API settings
    api_rate_limit_delay: float = Field(default=0.5, ge=0.0, le=10.0)
    
    # Environment overrides
    newsroom_path: Optional[str] = None
    hf_token: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_settings(self):
        """Cross-field validation"""
        # Ensure at least one source is configured
        if not self.sources:
            raise ValueError("At least one video source must be configured")
        
        # Validate GPU settings consistency
        if self.models.whisper_device == "cuda" and self.models.diarization_device == "cpu":
            # Warning: mixed device usage might be intentional
            pass
        
        return self
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> "PipelineSettings":
        """Load settings from YAML file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        
        return cls(**config_data)
    
    def to_dict(self) -> dict:
        """Export settings as dictionary"""
        return self.model_dump(mode='json', exclude_none=True)
    
    def save_effective_config(self, output_path: Path) -> None:
        """Save effective configuration to JSON"""
        import json
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


# Singleton pattern for settings
_settings_instance: Optional[PipelineSettings] = None


def get_settings(config_path: Optional[Path] = None) -> PipelineSettings:
    """Get or create settings instance"""
    global _settings_instance
    
    if _settings_instance is None:
        if config_path is None:
            config_path = Path("config/pipeline.yaml")
        _settings_instance = PipelineSettings.from_yaml(config_path)
    
    return _settings_instance


def reload_settings(config_path: Path) -> PipelineSettings:
    """Force reload settings from file"""
    global _settings_instance
    _settings_instance = PipelineSettings.from_yaml(config_path)
    return _settings_instance
