"""Pydantic settings for configuration management."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class TranscriptionSettings(BaseSettings):
    """Transcription stage settings."""
    model: str = Field(default="large-v3", description="Whisper model name")
    compute_type: str = Field(default="fp16", description="Compute type: fp16, int8")
    device: str = Field(default="auto", description="Device: auto, cuda, cpu")
    language: Optional[str] = Field(default=None, description="Force language (e.g., 'en')")
    beam_size: int = Field(default=5, description="Beam size for decoding")
    vad_filter: bool = Field(default=True, description="Enable VAD filtering")
    
    # Concurrency
    max_concurrent: int = Field(default=1, description="Max concurrent transcriptions")


class DiarizationSettings(BaseSettings):
    """Diarization stage settings."""
    model: str = Field(default="pyannote/speaker-diarization-3.1", description="Diarization model")
    min_speakers: Optional[int] = Field(default=None, description="Minimum speakers")
    max_speakers: Optional[int] = Field(default=None, description="Maximum speakers")
    
    # HuggingFace token for pyannote models
    hf_token: Optional[str] = Field(default=None, description="HuggingFace API token")


class EnrichmentSettings(BaseSettings):
    """Enrichment stage settings."""
    # Entity extraction
    spacy_model: str = Field(default="en_core_web_lg", description="SpaCy model")
    use_llm: bool = Field(default=False, description="Use LLM for entity extraction")
    llm_model: Optional[str] = Field(default=None, description="LLM model name")
    
    # Disambiguation
    wikidata_enabled: bool = Field(default=True, description="Enable Wikidata lookups")
    wikipedia_enabled: bool = Field(default=True, description="Enable Wikipedia lookups")
    cache_ttl_days: int = Field(default=30, description="Cache TTL in days")
    
    # Rate limiting
    requests_per_second: float = Field(default=1.0, description="API rate limit")
    max_retries: int = Field(default=3, description="Max retry attempts")


class WebGenerationSettings(BaseSettings):
    """Web generation settings."""
    template_dir: Path = Field(default=Path("templates"), description="Template directory")
    output_dir: Path = Field(default=Path("data/public"), description="Output directory")
    
    # SEO
    site_name: str = Field(default="AI-EWG", description="Site name")
    site_url: str = Field(default="https://example.com", description="Site URL")
    site_description: str = Field(default="Educational video archive", description="Site description")
    
    # Features
    enable_search: bool = Field(default=True, description="Enable search functionality")
    enable_rss: bool = Field(default=True, description="Generate RSS feeds")
    enable_sitemap: bool = Field(default=True, description="Generate sitemaps")


class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AIEWG_",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Project paths
    project_root: Path = Field(default=Path.cwd(), description="Project root directory")
    data_dir: Path = Field(default=Path("data"), description="Data directory")
    config_dir: Path = Field(default=Path("config"), description="Config directory")
    
    # Source discovery
    source_paths: List[Path] = Field(
        default_factory=lambda: [Path("test_videos")],
        description="Source video directories"
    )
    file_patterns: List[str] = Field(
        default_factory=lambda: ["**/*.mp4", "**/*.mkv", "**/*.avi"],
        description="File patterns to match"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: ["**/.*", "**/__*"],
        description="Patterns to exclude"
    )
    
    # Registry database
    registry_db_path: Path = Field(
        default=Path("data/registry.db"),
        description="Registry database path"
    )
    
    # Logging
    log_dir: Path = Field(default=Path("data/logs"), description="Log directory")
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format: json, text")
    
    # Stage settings
    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    diarization: DiarizationSettings = Field(default_factory=DiarizationSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    web: WebGenerationSettings = Field(default_factory=WebGenerationSettings)
    
    # Performance
    max_workers: int = Field(default=4, description="Max worker threads")
    chunk_size: int = Field(default=1000, description="Batch processing chunk size")
    
    @field_validator("project_root", "data_dir", "config_dir", mode="before")
    @classmethod
    def resolve_paths(cls, v):
        """Resolve paths to absolute."""
        if isinstance(v, str):
            v = Path(v)
        return v.resolve() if isinstance(v, Path) else v
    
    @field_validator("source_paths", mode="before")
    @classmethod
    def resolve_source_paths(cls, v):
        """Resolve source paths."""
        if isinstance(v, str):
            v = [Path(p.strip()) for p in v.split(",")]
        return [p.resolve() if isinstance(p, Path) else Path(p).resolve() for p in v]
    
    def ensure_directories(self):
        """Create necessary directories."""
        dirs = [
            self.data_dir,
            self.data_dir / "audio",
            self.data_dir / "transcripts" / "txt",
            self.data_dir / "transcripts" / "vtt",
            self.data_dir / "enriched",
            self.data_dir / "public",
            self.data_dir / "public" / "assets",
            self.data_dir / "public" / "meta",
            self.data_dir / "public" / "shows",
            self.data_dir / "cache",
            self.log_dir,
            Path("output/indices/shows"),
            Path("output/indices/hosts"),
            Path("output/search"),
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export settings as dict."""
        return self.model_dump(mode="json")
    
    def save_snapshot(self, run_id: str):
        """Save config snapshot for a run."""
        snapshot_path = self.data_dir / "meta" / f"run_{run_id}.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(snapshot_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


# Global settings cache
_settings_cache: Optional[Settings] = None


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Get or create settings instance."""
    global _settings_cache
    
    if _settings_cache is not None:
        return _settings_cache
    
    # Load from YAML if provided
    if config_path and config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
        
        # Merge with environment variables
        settings = Settings(**config_data)
    else:
        # Load from environment only
        settings = Settings()
    
    # Ensure directories exist
    settings.ensure_directories()
    
    _settings_cache = settings
    return settings


def reload_settings(config_path: Optional[Path] = None):
    """Force reload settings."""
    global _settings_cache
    _settings_cache = None
    return get_settings(config_path)
