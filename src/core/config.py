"""
Configuration management for the Video Processing Pipeline

Handles loading and validation of configuration from YAML files,
environment variables, and provides a unified configuration interface.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field

from .exceptions import ConfigurationError
from .logging import get_logger

logger = get_logger('pipeline.config')


@dataclass
class SourceConfig:
    """Configuration for a video source"""
    path: str
    include: List[str] = field(default_factory=lambda: ["*.mp4", "*.mkv", "*.avi", "*.mov"])
    exclude: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class StagingConfig:
    """Configuration for staging area"""
    enabled: bool = True
    path: str = "staging"
    cleanup_after_processing: bool = True


@dataclass
class DiscoveryConfig:
    """Configuration for video discovery"""
    stability_minutes: int = 5
    max_concurrent_scans: int = 4
    scan_interval_seconds: int = 300


@dataclass
class ModelConfig:
    """Configuration for AI models"""
    whisper: str = "base"
    llm: str = "mistral"
    diarization_device: str = "cuda"
    num_speakers: int = 2


@dataclass
class ThresholdConfig:
    """Configuration for confidence thresholds"""
    confidence_min: float = 0.6
    entity_confidence: float = 0.7
    expert_score: float = 0.75
    publish_score: float = 0.6


@dataclass
class DatabaseConfig:
    """Configuration for database"""
    path: str = "data/pipeline.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    connection_timeout: int = 10  # SQLite connection timeout (seconds)
    max_connections: int = 10
    journal_mode: str = "WAL"  # Write-Ahead Logging for better concurrency
    synchronous: str = "NORMAL"  # Safe with WAL, reduces filesystem thrashing
    busy_timeout: int = 10000  # Wait up to 10 seconds if database is locked (10000ms)


@dataclass
class LoggingConfig:
    """Configuration for logging"""
    level: str = "INFO"
    directory: str = "logs"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console: bool = True
    structured: bool = True


@dataclass
class ProcessingConfig:
    """Configuration for processing limits and concurrency"""
    max_concurrent_episodes: int = 2
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 30
    timeout_minutes: int = 60


@dataclass
class ResourceConfig:
    """Configuration for resource limits"""
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 90.0
    max_disk_usage_percent: float = 85.0
    max_open_files: int = 1000


@dataclass
class TranscriptionConfig:
    """Configuration for multilingual transcription"""
    language: str = "auto"  # Auto-detect or specific language code
    translate_to_english: bool = False
    task: str = "transcribe"  # "transcribe" or "translate"
    supported_languages: List[str] = field(default_factory=lambda: [
        "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"
    ])
    fallback_language: str = "en"


@dataclass
class ClipGenerationConfig:
    """Configuration for clip generation system"""
    enabled: bool = False
    embedding_model: str = "bge-small-en"
    max_clips_per_episode: int = 8
    min_segment_duration_ms: int = 20000
    max_segment_duration_ms: int = 120000
    safe_padding_ms: int = 500
    llm_rerank_enabled: bool = True
    llm_model: str = "llama3"
    llm_timeout: int = 30
    cache_embeddings: bool = True
    embedding_batch_size: int = 32
    
    # Scoring weights
    heuristic_weights: Dict[str, float] = field(default_factory=lambda: {
        'hook_phrases': 0.3,
        'entity_density': 0.2,
        'sentiment_peaks': 0.2,
        'qa_patterns': 0.2,
        'compression_ratio': 0.1
    })
    
    # Export settings
    aspect_ratios: List[str] = field(default_factory=lambda: ["9x16", "16x9"])
    variants: List[str] = field(default_factory=lambda: ["clean", "subtitled"])
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 20
    preset: str = "veryfast"
    
    # Resource limits
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 70.0


@dataclass
class PipelineConfig:
    """Main configuration class for the pipeline"""
    sources: List[SourceConfig] = field(default_factory=list)
    staging: StagingConfig = field(default_factory=StagingConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    clip_generation: ClipGenerationConfig = field(default_factory=ClipGenerationConfig)
    
    # Environment-specific overrides
    newsroom_path: Optional[str] = None
    hf_token: Optional[str] = None
    ollama_url: str = "http://localhost:11434"
    api_rate_limit_delay: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert PipelineConfig to dictionary"""
        from dataclasses import asdict
        return asdict(self)


class ConfigurationManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.config_path = Path(config_path) if config_path else None
        self._config: Optional[PipelineConfig] = None
        self._env_overrides: Dict[str, Any] = {}
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> PipelineConfig:
        """
        Load configuration from YAML file and environment variables
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            PipelineConfig: Loaded and validated configuration
            
        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        if config_path:
            self.config_path = Path(config_path)
        
        # Load base configuration from YAML
        yaml_config = self._load_yaml_config()
        
        # Load environment variable overrides
        env_config = self._load_env_config()
        
        # Merge configurations (env overrides YAML)
        merged_config = self._merge_configs(yaml_config, env_config)
        
        # Validate and create configuration object
        self._config = self._create_config_object(merged_config)
        
        # Validate configuration
        self._validate_config(self._config)
        
        logger.info("Configuration loaded successfully", 
                   config_path=str(self.config_path) if self.config_path else "default",
                   sources_count=len(self._config.sources))
        
        return self._config
    
    def get_config(self) -> PipelineConfig:
        """Get the current configuration"""
        if self._config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._config
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path or not self.config_path.exists():
            logger.info("No YAML config file found, using defaults")
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            logger.debug("YAML configuration loaded", file=str(self.config_path))
            return config
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}", 
                                   config_key="yaml_file")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}",
                                   config_key="yaml_file")
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables"""
        env_config = {}
        
        # Map environment variables to config structure
        env_mappings = {
            'NEWSROOM_PATH': 'newsroom_path',
            'HF_TOKEN': 'hf_token',
            'OLLAMA_URL': 'ollama_url',
            'OLLAMA_MODEL': 'models.llm',
            'DIARIZE_DEVICE': 'models.diarization_device',
            'DIARIZE_NUM_SPEAKERS': 'models.num_speakers',
            'MIN_PUBLISH_SCORE': 'thresholds.publish_score',
            'MIN_EXPERT_SCORE': 'thresholds.expert_score',
            'API_RATE_LIMIT_DELAY': 'api_rate_limit_delay',
            'LOG_LEVEL': 'logging.level',
            'LOG_DIRECTORY': 'logging.directory',
            'DATABASE_PATH': 'database.path',
            'STAGING_PATH': 'staging.path',
            'MAX_CONCURRENT_EPISODES': 'processing.max_concurrent_episodes',
            
            # Clip Generation Settings
            'CLIP_GENERATION_ENABLED': 'clip_generation.enabled',
            'CLIP_EMBEDDING_MODEL': 'clip_generation.embedding_model',
            'CLIP_MAX_PER_EPISODE': 'clip_generation.max_clips_per_episode',
            'CLIP_MIN_DURATION_MS': 'clip_generation.min_segment_duration_ms',
            'CLIP_MAX_DURATION_MS': 'clip_generation.max_segment_duration_ms',
            'CLIP_SAFE_PADDING_MS': 'clip_generation.safe_padding_ms',
            'CLIP_LLM_ENABLED': 'clip_generation.llm_rerank_enabled',
            'CLIP_LLM_MODEL': 'clip_generation.llm_model',
            'CLIP_LLM_TIMEOUT': 'clip_generation.llm_timeout',
            'CLIP_CACHE_EMBEDDINGS': 'clip_generation.cache_embeddings',
            'CLIP_EMBEDDING_BATCH_SIZE': 'clip_generation.embedding_batch_size',
            'CLIP_MAX_MEMORY_PERCENT': 'clip_generation.max_memory_percent',
            'CLIP_MAX_CPU_PERCENT': 'clip_generation.max_cpu_percent'
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(env_config, config_path, self._convert_env_value(value))
        
        if env_config:
            logger.debug("Environment overrides loaded", overrides=list(env_config.keys()))
        
        return env_config
    
    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested configuration value using dot notation"""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type"""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _merge_configs(self, yaml_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge YAML and environment configurations"""
        def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        return deep_merge(yaml_config, env_config)
    
    def _create_config_object(self, config_dict: Dict[str, Any]) -> PipelineConfig:
        """Create PipelineConfig object from dictionary"""
        try:
            # Handle sources
            sources = []
            for source_config in config_dict.get('sources', []):
                if isinstance(source_config, dict):
                    sources.append(SourceConfig(**source_config))
                elif isinstance(source_config, str):
                    sources.append(SourceConfig(path=source_config))
            
            # Create nested config objects
            staging = StagingConfig(**config_dict.get('staging', {}))
            discovery = DiscoveryConfig(**config_dict.get('discovery', {}))
            models = ModelConfig(**config_dict.get('models', {}))
            thresholds = ThresholdConfig(**config_dict.get('thresholds', {}))
            database = DatabaseConfig(**config_dict.get('database', {}))
            logging_config = LoggingConfig(**config_dict.get('logging', {}))
            processing = ProcessingConfig(**config_dict.get('processing', {}))
            resources = ResourceConfig(**config_dict.get('resources', {}))
            clip_generation = ClipGenerationConfig(**config_dict.get('clip_generation', {}))
            
            # Create main config
            return PipelineConfig(
                sources=sources,
                staging=staging,
                discovery=discovery,
                models=models,
                thresholds=thresholds,
                database=database,
                logging=logging_config,
                processing=processing,
                resources=resources,
                clip_generation=clip_generation,
                newsroom_path=config_dict.get('newsroom_path'),
                hf_token=config_dict.get('hf_token'),
                ollama_url=config_dict.get('ollama_url', 'http://localhost:11434'),
                api_rate_limit_delay=config_dict.get('api_rate_limit_delay', 0.5)
            )
        
        except TypeError as e:
            raise ConfigurationError(f"Invalid configuration structure: {e}")
    
    def _validate_config(self, config: PipelineConfig) -> None:
        """Validate configuration values"""
        errors = []
        
        # Validate sources
        if not config.sources:
            errors.append("At least one video source must be configured")
        
        for i, source in enumerate(config.sources):
            if not source.path:
                errors.append(f"Source {i}: path is required")
        
        # Validate paths
        if config.newsroom_path and not Path(config.newsroom_path).exists():
            logger.warning("Newsroom path does not exist", path=config.newsroom_path)
        
        # Validate thresholds
        for threshold_name in ['confidence_min', 'entity_confidence', 'expert_score', 'publish_score']:
            value = getattr(config.thresholds, threshold_name)
            if not 0.0 <= value <= 1.0:
                errors.append(f"Threshold {threshold_name} must be between 0.0 and 1.0, got {value}")
        
        # Validate processing limits
        if config.processing.max_concurrent_episodes < 1:
            errors.append("max_concurrent_episodes must be at least 1")
        
        if config.processing.max_retry_attempts < 0:
            errors.append("max_retry_attempts must be non-negative")
        
        # Validate model configuration
        valid_whisper_models = ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3']
        if config.models.whisper not in valid_whisper_models:
            errors.append(f"Invalid Whisper model: {config.models.whisper}. "
                         f"Valid options: {', '.join(valid_whisper_models)}")
        
        if errors:
            raise ConfigurationError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def save_config(self, output_path: Union[str, Path]) -> None:
        """Save current configuration to YAML file"""
        if self._config is None:
            raise ConfigurationError("No configuration loaded to save")
        
        config_dict = self._config_to_dict(self._config)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        
        logger.info("Configuration saved", output_path=str(output_path))
    
    def _config_to_dict(self, config: PipelineConfig) -> Dict[str, Any]:
        """Convert PipelineConfig to dictionary for serialization"""
        return {
            'sources': [
                {
                    'path': source.path,
                    'include': source.include,
                    'exclude': source.exclude,
                    'enabled': source.enabled
                }
                for source in config.sources
            ],
            'staging': {
                'enabled': config.staging.enabled,
                'path': config.staging.path,
                'cleanup_after_processing': config.staging.cleanup_after_processing
            },
            'discovery': {
                'stability_minutes': config.discovery.stability_minutes,
                'max_concurrent_scans': config.discovery.max_concurrent_scans,
                'scan_interval_seconds': config.discovery.scan_interval_seconds
            },
            'models': {
                'whisper': config.models.whisper,
                'llm': config.models.llm,
                'diarization_device': config.models.diarization_device,
                'num_speakers': config.models.num_speakers
            },
            'thresholds': {
                'confidence_min': config.thresholds.confidence_min,
                'entity_confidence': config.thresholds.entity_confidence,
                'expert_score': config.thresholds.expert_score,
                'publish_score': config.thresholds.publish_score
            },
            'database': {
                'path': config.database.path,
                'backup_enabled': config.database.backup_enabled,
                'backup_interval_hours': config.database.backup_interval_hours,
                'connection_timeout': config.database.connection_timeout,
                'max_connections': config.database.max_connections,
                'journal_mode': config.database.journal_mode,
                'synchronous': config.database.synchronous
            },
            'logging': {
                'level': config.logging.level,
                'directory': config.logging.directory,
                'max_file_size_mb': config.logging.max_file_size_mb,
                'backup_count': config.logging.backup_count,
                'console': config.logging.console,
                'structured': config.logging.structured
            },
            'processing': {
                'max_concurrent_episodes': config.processing.max_concurrent_episodes,
                'max_retry_attempts': config.processing.max_retry_attempts,
                'retry_delay_seconds': config.processing.retry_delay_seconds,
                'timeout_minutes': config.processing.timeout_minutes
            },
            'resources': {
                'max_memory_percent': config.resources.max_memory_percent,
                'max_cpu_percent': config.resources.max_cpu_percent,
                'max_disk_usage_percent': config.resources.max_disk_usage_percent,
                'max_open_files': config.resources.max_open_files
            },
            'clip_generation': {
                'enabled': config.clip_generation.enabled,
                'embedding_model': config.clip_generation.embedding_model,
                'max_clips_per_episode': config.clip_generation.max_clips_per_episode,
                'min_segment_duration_ms': config.clip_generation.min_segment_duration_ms,
                'max_segment_duration_ms': config.clip_generation.max_segment_duration_ms,
                'safe_padding_ms': config.clip_generation.safe_padding_ms,
                'llm_rerank_enabled': config.clip_generation.llm_rerank_enabled,
                'llm_model': config.clip_generation.llm_model,
                'llm_timeout': config.clip_generation.llm_timeout,
                'cache_embeddings': config.clip_generation.cache_embeddings,
                'embedding_batch_size': config.clip_generation.embedding_batch_size,
                'heuristic_weights': config.clip_generation.heuristic_weights,
                'aspect_ratios': config.clip_generation.aspect_ratios,
                'variants': config.clip_generation.variants,
                'video_codec': config.clip_generation.video_codec,
                'audio_codec': config.clip_generation.audio_codec,
                'crf': config.clip_generation.crf,
                'preset': config.clip_generation.preset,
                'max_memory_percent': config.clip_generation.max_memory_percent,
                'max_cpu_percent': config.clip_generation.max_cpu_percent
            },
            'newsroom_path': config.newsroom_path,
            'hf_token': config.hf_token,
            'ollama_url': config.ollama_url,
            'api_rate_limit_delay': config.api_rate_limit_delay
        }