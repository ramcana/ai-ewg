"""
Configuration and Environment Management for Content Publishing Platform

Provides comprehensive configuration management with environment-specific settings,
secret management, feature flags, and optional integration controls.
"""

import os
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from .publishing_models import ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity
from .deployment_pipeline import DeploymentConfig
from .web_generator import URLPattern


class Environment(Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class FeatureFlag(Enum):
    """Available feature flags"""
    SOCIAL_GENERATION = "social_generation"
    PLATFORM_INTEGRATION = "platform_integration"
    ANALYTICS_TRACKING = "analytics_tracking"
    CDN_MANAGEMENT = "cdn_management"
    AUTO_PROMOTION = "auto_promotion"
    VALIDATION_STRICT_MODE = "validation_strict_mode"
    SOCIAL_STRICT_MODE = "social_strict_mode"
    BATCH_PROCESSING = "batch_processing"
    CACHE_OPTIMIZATION = "cache_optimization"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class SecretConfig:
    """Configuration for secret management"""
    # Secret sources
    use_environment_variables: bool = True
    use_config_files: bool = False
    use_external_vault: bool = False
    
    # Environment variable prefixes
    env_prefix: str = "PUBLISHING_"
    
    # Secret file paths (per environment)
    secret_files: Dict[str, str] = field(default_factory=dict)
    
    # External vault configuration
    vault_url: Optional[str] = None
    vault_token_path: Optional[str] = None
    vault_mount_path: str = "secret"
    
    # Required secrets
    required_secrets: Set[str] = field(default_factory=lambda: {
        "database_url", "cdn_api_key", "analytics_tracking_id"
    })
    
    # Optional secrets (per integration)
    optional_secrets: Dict[str, Set[str]] = field(default_factory=lambda: {
        "google": {"google_search_console_key", "google_analytics_key"},
        "youtube": {"youtube_api_key", "youtube_client_secret"},
        "instagram": {"instagram_api_key", "instagram_client_secret"},
        "bing": {"bing_webmaster_key"},
        "cloudflare": {"cloudflare_api_key", "cloudflare_zone_id"}
    })


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration"""
    name: Environment
    base_url: str
    
    # Paths (environment-specific)
    content_base_path: str = "data"
    staging_root: str = "data/staging"
    production_root: str = "data/public"
    backup_root: str = "data/backups"
    temp_dir: str = "temp"
    log_dir: str = "logs"
    
    # Database configuration
    database_url: Optional[str] = None
    database_pool_size: int = 10
    database_timeout: int = 30
    
    # CDN configuration
    cdn_enabled: bool = False
    cdn_provider: str = "cloudflare"
    cdn_base_url: Optional[str] = None
    
    # Cache settings
    cache_ttl_html: int = 3600  # 1 hour
    cache_ttl_feeds: int = 1800  # 30 minutes
    cache_ttl_assets: int = 86400  # 24 hours
    
    # Performance settings
    max_concurrent_workers: int = 4
    batch_size: int = 50
    timeout_seconds: int = 300
    
    # Validation thresholds (can be relaxed in dev/staging)
    html_parse_failure_threshold: int = 0
    broken_link_threshold: int = 0
    schema_compliance_threshold: float = 1.0
    feed_validation_threshold: float = 1.0
    social_package_failure_threshold: float = 0.1
    
    # Feature flags (environment-specific overrides)
    feature_overrides: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name.value,
            'base_url': self.base_url,
            'content_base_path': self.content_base_path,
            'staging_root': self.staging_root,
            'production_root': self.production_root,
            'backup_root': self.backup_root,
            'temp_dir': self.temp_dir,
            'log_dir': self.log_dir,
            'database_url': self.database_url,
            'database_pool_size': self.database_pool_size,
            'database_timeout': self.database_timeout,
            'cdn_enabled': self.cdn_enabled,
            'cdn_provider': self.cdn_provider,
            'cdn_base_url': self.cdn_base_url,
            'cache_ttl_html': self.cache_ttl_html,
            'cache_ttl_feeds': self.cache_ttl_feeds,
            'cache_ttl_assets': self.cache_ttl_assets,
            'max_concurrent_workers': self.max_concurrent_workers,
            'batch_size': self.batch_size,
            'timeout_seconds': self.timeout_seconds,
            'html_parse_failure_threshold': self.html_parse_failure_threshold,
            'broken_link_threshold': self.broken_link_threshold,
            'schema_compliance_threshold': self.schema_compliance_threshold,
            'feed_validation_threshold': self.feed_validation_threshold,
            'social_package_failure_threshold': self.social_package_failure_threshold,
            'feature_overrides': self.feature_overrides
        }


@dataclass
class IntegrationConfig:
    """Configuration for optional integrations"""
    # Platform integration settings
    google_search_console_enabled: bool = False
    bing_webmaster_tools_enabled: bool = False
    google_news_enabled: bool = False
    apple_news_enabled: bool = False
    microsoft_start_enabled: bool = False
    
    # Social media platforms
    youtube_enabled: bool = False
    instagram_enabled: bool = False
    twitter_enabled: bool = False
    facebook_enabled: bool = False
    tiktok_enabled: bool = False
    
    # Analytics platforms
    google_analytics_enabled: bool = False
    adobe_analytics_enabled: bool = False
    custom_analytics_enabled: bool = False
    
    # CDN providers
    cloudflare_enabled: bool = False
    aws_cloudfront_enabled: bool = False
    azure_cdn_enabled: bool = False
    
    # Configuration files for integrations
    social_profiles_config: str = "config/social_profiles.yaml"
    platform_credentials_config: str = "config/platform_credentials.json"
    analytics_config: str = "config/analytics.yaml"
    cdn_config: str = "config/cdn.yaml"
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled social media platforms"""
        platforms = []
        if self.youtube_enabled:
            platforms.append("youtube")
        if self.instagram_enabled:
            platforms.append("instagram")
        if self.twitter_enabled:
            platforms.append("twitter")
        if self.facebook_enabled:
            platforms.append("facebook")
        if self.tiktok_enabled:
            platforms.append("tiktok")
        return platforms
    
    def get_enabled_search_engines(self) -> List[str]:
        """Get list of enabled search engine integrations"""
        engines = []
        if self.google_search_console_enabled:
            engines.append("google")
        if self.bing_webmaster_tools_enabled:
            engines.append("bing")
        return engines
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'google_search_console_enabled': self.google_search_console_enabled,
            'bing_webmaster_tools_enabled': self.bing_webmaster_tools_enabled,
            'google_news_enabled': self.google_news_enabled,
            'apple_news_enabled': self.apple_news_enabled,
            'microsoft_start_enabled': self.microsoft_start_enabled,
            'youtube_enabled': self.youtube_enabled,
            'instagram_enabled': self.instagram_enabled,
            'twitter_enabled': self.twitter_enabled,
            'facebook_enabled': self.facebook_enabled,
            'tiktok_enabled': self.tiktok_enabled,
            'google_analytics_enabled': self.google_analytics_enabled,
            'adobe_analytics_enabled': self.adobe_analytics_enabled,
            'custom_analytics_enabled': self.custom_analytics_enabled,
            'cloudflare_enabled': self.cloudflare_enabled,
            'aws_cloudfront_enabled': self.aws_cloudfront_enabled,
            'azure_cdn_enabled': self.azure_cdn_enabled,
            'social_profiles_config': self.social_profiles_config,
            'platform_credentials_config': self.platform_credentials_config,
            'analytics_config': self.analytics_config,
            'cdn_config': self.cdn_config
        }


class ConfigurationManager:
    """
    Comprehensive configuration management system
    
    Handles environment-specific settings, secret management, feature flags,
    and optional integration controls with validation and hot-reloading.
    """
    
    def __init__(self, 
                 config_dir: str = "config",
                 environment: Optional[Environment] = None):
        """
        Initialize configuration manager
        
        Args:
            config_dir: Directory containing configuration files
            environment: Target environment (auto-detected if None)
        """
        self.config_dir = Path(config_dir)
        self.environment = environment or self._detect_environment()
        
        # Configuration storage
        self._base_config: Dict[str, Any] = {}
        self._environment_configs: Dict[Environment, EnvironmentConfig] = {}
        self._secrets: Dict[str, str] = {}
        self._feature_flags: Dict[FeatureFlag, bool] = {}
        self._integration_config: Optional[IntegrationConfig] = None
        
        # Secret management
        self.secret_config = SecretConfig()
        
        # Validation cache
        self._validation_cache: Optional[ValidationResult] = None
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def _detect_environment(self) -> Environment:
        """Auto-detect environment from environment variables"""
        env_name = os.getenv("PUBLISHING_ENVIRONMENT", "development").lower()
        
        env_mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "stage": Environment.STAGING,
            "staging": Environment.STAGING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
            "test": Environment.TEST,
            "testing": Environment.TEST
        }
        
        return env_mapping.get(env_name, Environment.DEVELOPMENT)
    
    def load_configuration(self) -> None:
        """Load complete configuration from all sources"""
        self.logger.info(f"Loading configuration for environment: {self.environment.value}")
        
        # Load base configuration
        self._load_base_config()
        
        # Load environment-specific configurations
        self._load_environment_configs()
        
        # Load secrets
        self._load_secrets()
        
        # Load feature flags
        self._load_feature_flags()
        
        # Load integration configuration
        self._load_integration_config()
        
        # Validate configuration
        self._validation_cache = self.validate_configuration()
        
        if not self._validation_cache.is_valid:
            raise ValueError(f"Configuration validation failed: {len(self._validation_cache.errors)} errors")
        
        self.logger.info("Configuration loaded successfully")
    
    def _load_base_config(self) -> None:
        """Load base configuration from main config file"""
        config_file = self.config_dir / "publishing.yaml"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                self._base_config = yaml.safe_load(f) or {}
        else:
            self.logger.warning(f"Base config file not found: {config_file}")
            self._base_config = {}
    
    def _load_environment_configs(self) -> None:
        """Load environment-specific configurations"""
        # Load all environment configs
        for env in Environment:
            config_file = self.config_dir / f"environments" / f"{env.value}.yaml"
            
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    env_data = yaml.safe_load(f) or {}
                
                # Merge with base config
                merged_data = self._merge_configs(self._base_config.get('environment', {}), env_data)
                
                # Create environment config
                self._environment_configs[env] = EnvironmentConfig(
                    name=env,
                    **merged_data
                )
            else:
                # Create default environment config
                self._environment_configs[env] = EnvironmentConfig(
                    name=env,
                    base_url=f"https://{env.value}.example.com"
                )
    
    def _load_secrets(self) -> None:
        """Load secrets from configured sources"""
        # Load from environment variables
        if self.secret_config.use_environment_variables:
            self._load_secrets_from_env()
        
        # Load from config files
        if self.secret_config.use_config_files:
            self._load_secrets_from_files()
        
        # Load from external vault (placeholder for future implementation)
        if self.secret_config.use_external_vault:
            self._load_secrets_from_vault()
    
    def _load_secrets_from_env(self) -> None:
        """Load secrets from environment variables"""
        prefix = self.secret_config.env_prefix
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                secret_name = key[len(prefix):].lower()
                self._secrets[secret_name] = value
    
    def _load_secrets_from_files(self) -> None:
        """Load secrets from environment-specific files"""
        env_name = self.environment.value
        
        if env_name in self.secret_config.secret_files:
            secret_file = Path(self.secret_config.secret_files[env_name])
            
            if secret_file.exists():
                with open(secret_file, 'r', encoding='utf-8') as f:
                    if secret_file.suffix.lower() == '.json':
                        secrets = json.load(f)
                    else:
                        secrets = yaml.safe_load(f)
                
                self._secrets.update(secrets)
    
    def _load_secrets_from_vault(self) -> None:
        """Load secrets from external vault (placeholder)"""
        # This would integrate with HashiCorp Vault, AWS Secrets Manager, etc.
        self.logger.info("External vault integration not implemented")
    
    def _load_feature_flags(self) -> None:
        """Load feature flags from configuration"""
        flags_config = self._base_config.get('feature_flags', {})
        
        # Set default values for all flags
        for flag in FeatureFlag:
            default_value = self._get_default_feature_flag(flag)
            self._feature_flags[flag] = flags_config.get(flag.value, default_value)
        
        # Apply environment-specific overrides
        current_env_config = self._environment_configs.get(self.environment)
        if current_env_config and current_env_config.feature_overrides:
            for flag_name, value in current_env_config.feature_overrides.items():
                try:
                    flag = FeatureFlag(flag_name)
                    self._feature_flags[flag] = value
                except ValueError:
                    self.logger.warning(f"Unknown feature flag: {flag_name}")
    
    def _get_default_feature_flag(self, flag: FeatureFlag) -> bool:
        """Get default value for feature flag based on environment"""
        # More permissive defaults for development
        if self.environment == Environment.DEVELOPMENT:
            return {
                FeatureFlag.SOCIAL_GENERATION: True,
                FeatureFlag.PLATFORM_INTEGRATION: False,  # Disabled in dev by default
                FeatureFlag.ANALYTICS_TRACKING: False,
                FeatureFlag.CDN_MANAGEMENT: False,
                FeatureFlag.AUTO_PROMOTION: False,
                FeatureFlag.VALIDATION_STRICT_MODE: False,
                FeatureFlag.SOCIAL_STRICT_MODE: False,
                FeatureFlag.BATCH_PROCESSING: True,
                FeatureFlag.CACHE_OPTIMIZATION: False,
                FeatureFlag.ERROR_RECOVERY: True
            }.get(flag, False)
        
        # Conservative defaults for production
        elif self.environment == Environment.PRODUCTION:
            return {
                FeatureFlag.SOCIAL_GENERATION: True,
                FeatureFlag.PLATFORM_INTEGRATION: True,
                FeatureFlag.ANALYTICS_TRACKING: True,
                FeatureFlag.CDN_MANAGEMENT: True,
                FeatureFlag.AUTO_PROMOTION: False,  # Manual promotion in prod
                FeatureFlag.VALIDATION_STRICT_MODE: True,
                FeatureFlag.SOCIAL_STRICT_MODE: False,
                FeatureFlag.BATCH_PROCESSING: True,
                FeatureFlag.CACHE_OPTIMIZATION: True,
                FeatureFlag.ERROR_RECOVERY: True
            }.get(flag, False)
        
        # Balanced defaults for staging
        else:
            return {
                FeatureFlag.SOCIAL_GENERATION: True,
                FeatureFlag.PLATFORM_INTEGRATION: True,
                FeatureFlag.ANALYTICS_TRACKING: False,
                FeatureFlag.CDN_MANAGEMENT: True,
                FeatureFlag.AUTO_PROMOTION: True,
                FeatureFlag.VALIDATION_STRICT_MODE: True,
                FeatureFlag.SOCIAL_STRICT_MODE: False,
                FeatureFlag.BATCH_PROCESSING: True,
                FeatureFlag.CACHE_OPTIMIZATION: True,
                FeatureFlag.ERROR_RECOVERY: True
            }.get(flag, False)
    
    def _load_integration_config(self) -> None:
        """Load integration configuration"""
        integration_file = self.config_dir / "integrations.yaml"
        
        if integration_file.exists():
            with open(integration_file, 'r', encoding='utf-8') as f:
                integration_data = yaml.safe_load(f) or {}
            
            self._integration_config = IntegrationConfig(**integration_data)
        else:
            self._integration_config = IntegrationConfig()
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_environment_config(self, environment: Optional[Environment] = None) -> EnvironmentConfig:
        """
        Get configuration for specific environment
        
        Args:
            environment: Target environment (current if None)
            
        Returns:
            EnvironmentConfig for the specified environment
        """
        env = environment or self.environment
        return self._environment_configs[env]
    
    def get_secret(self, secret_name: str, required: bool = True) -> Optional[str]:
        """
        Get secret value by name
        
        Args:
            secret_name: Name of the secret
            required: Whether the secret is required
            
        Returns:
            Secret value or None if not found and not required
            
        Raises:
            ValueError: If required secret is not found
        """
        value = self._secrets.get(secret_name)
        
        if value is None and required:
            raise ValueError(f"Required secret not found: {secret_name}")
        
        return value
    
    def is_feature_enabled(self, feature: FeatureFlag) -> bool:
        """
        Check if a feature flag is enabled
        
        Args:
            feature: Feature flag to check
            
        Returns:
            True if feature is enabled
        """
        return self._feature_flags.get(feature, False)
    
    def get_integration_config(self) -> IntegrationConfig:
        """
        Get integration configuration
        
        Returns:
            IntegrationConfig with all integration settings
        """
        return self._integration_config or IntegrationConfig()
    
    def create_deployment_config(self) -> DeploymentConfig:
        """
        Create deployment configuration for current environment
        
        Returns:
            DeploymentConfig with environment-specific settings
        """
        env_config = self.get_environment_config()
        
        return DeploymentConfig(
            batch_size=env_config.batch_size,
            max_concurrent_workers=env_config.max_concurrent_workers,
            timeout_seconds=env_config.timeout_seconds,
            html_parse_failure_threshold=env_config.html_parse_failure_threshold,
            broken_link_threshold=env_config.broken_link_threshold,
            schema_compliance_threshold=env_config.schema_compliance_threshold,
            feed_validation_threshold=env_config.feed_validation_threshold,
            social_package_failure_threshold=env_config.social_package_failure_threshold,
            staging_root=env_config.staging_root,
            production_root=env_config.production_root,
            backup_root=env_config.backup_root,
            social_validation_enabled=self.is_feature_enabled(FeatureFlag.SOCIAL_GENERATION),
            social_strict_mode=self.is_feature_enabled(FeatureFlag.SOCIAL_STRICT_MODE)
        )
    
    def create_url_patterns(self) -> URLPattern:
        """
        Create URL patterns for current environment
        
        Returns:
            URLPattern with environment-specific base URL
        """
        env_config = self.get_environment_config()
        
        return URLPattern(
            base_url=env_config.base_url,
            episode_pattern="/episodes/{episode_id}",
            series_pattern="/series/{series_slug}",
            host_pattern="/hosts/{host_slug}",
            series_index_pattern="/series",
            hosts_index_pattern="/hosts"
        )
    
    def validate_configuration(self) -> ValidationResult:
        """
        Validate complete configuration
        
        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        
        # Validate environment configuration
        env_config = self.get_environment_config()
        
        if not env_config.base_url:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="Base URL is required",
                location=f"environments.{self.environment.value}.base_url",
                severity=Severity.ERROR
            ))
        
        # Validate paths exist
        for path_name, path_value in [
            ("content_base_path", env_config.content_base_path),
            ("temp_dir", env_config.temp_dir),
            ("log_dir", env_config.log_dir)
        ]:
            path = Path(path_value)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    warnings.append(ValidationWarning(
                        message=f"Created missing directory: {path}",
                        location=f"environments.{self.environment.value}.{path_name}"
                    ))
                except Exception as e:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Cannot create directory {path}: {str(e)}",
                        location=f"environments.{self.environment.value}.{path_name}",
                        severity=Severity.ERROR
                    ))
        
        # Validate required secrets
        for secret_name in self.secret_config.required_secrets:
            if secret_name not in self._secrets:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Required secret not found: {secret_name}",
                    location=f"secrets.{secret_name}",
                    severity=Severity.ERROR
                ))
        
        # Validate integration configuration
        integration_config = self.get_integration_config()
        
        # Check for enabled integrations without required secrets
        if integration_config.google_search_console_enabled:
            if "google_search_console_key" not in self._secrets:
                warnings.append(ValidationWarning(
                    message="Google Search Console enabled but API key not found",
                    location="integrations.google_search_console"
                ))
        
        if integration_config.youtube_enabled:
            if "youtube_api_key" not in self._secrets:
                warnings.append(ValidationWarning(
                    message="YouTube integration enabled but API key not found",
                    location="integrations.youtube"
                ))
        
        # Validate feature flag consistency
        if (self.is_feature_enabled(FeatureFlag.PLATFORM_INTEGRATION) and 
            not any([integration_config.google_search_console_enabled,
                    integration_config.bing_webmaster_tools_enabled])):
            warnings.append(ValidationWarning(
                message="Platform integration enabled but no platforms configured",
                location="feature_flags.platform_integration"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "environment": self.environment.value,
                "feature_flags": {flag.value: enabled for flag, enabled in self._feature_flags.items()},
                "secrets_loaded": len(self._secrets),
                "validation_timestamp": datetime.now().isoformat()
            }
        )
    
    def reload_configuration(self) -> ValidationResult:
        """
        Reload configuration from all sources
        
        Returns:
            ValidationResult from reloaded configuration
        """
        self.logger.info("Reloading configuration")
        
        # Clear existing configuration
        self._base_config.clear()
        self._environment_configs.clear()
        self._secrets.clear()
        self._feature_flags.clear()
        self._integration_config = None
        self._validation_cache = None
        
        # Reload everything
        self.load_configuration()
        
        return self._validation_cache
    
    def export_configuration(self, output_path: str, include_secrets: bool = False) -> None:
        """
        Export current configuration to file
        
        Args:
            output_path: Path to output file
            include_secrets: Whether to include secret values (dangerous!)
        """
        config_export = {
            "environment": self.environment.value,
            "base_config": self._base_config,
            "environment_configs": {
                env.value: config.to_dict() 
                for env, config in self._environment_configs.items()
            },
            "feature_flags": {
                flag.value: enabled 
                for flag, enabled in self._feature_flags.items()
            },
            "integration_config": self._integration_config.to_dict() if self._integration_config else {},
            "validation_result": self._validation_cache.to_dict() if self._validation_cache else None
        }
        
        if include_secrets:
            config_export["secrets"] = self._secrets
        else:
            config_export["secrets"] = {
                name: "***REDACTED***" for name in self._secrets.keys()
            }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            if output_file.suffix.lower() == '.json':
                json.dump(config_export, f, indent=2, default=str)
            else:
                yaml.dump(config_export, f, default_flow_style=False, indent=2)
        
        self.logger.info(f"Configuration exported to: {output_path}")


# Factory functions

def create_configuration_manager(config_dir: str = "config", 
                                environment: Optional[Environment] = None) -> ConfigurationManager:
    """
    Create and initialize configuration manager
    
    Args:
        config_dir: Configuration directory path
        environment: Target environment
        
    Returns:
        Initialized ConfigurationManager
    """
    manager = ConfigurationManager(config_dir, environment)
    manager.load_configuration()
    return manager


def create_default_environment_configs() -> Dict[Environment, EnvironmentConfig]:
    """
    Create default environment configurations
    
    Returns:
        Dictionary of default environment configurations
    """
    return {
        Environment.DEVELOPMENT: EnvironmentConfig(
            name=Environment.DEVELOPMENT,
            base_url="http://localhost:3000",
            cdn_enabled=False,
            max_concurrent_workers=2,
            batch_size=10,
            schema_compliance_threshold=0.8,  # Relaxed for dev
            feature_overrides={
                FeatureFlag.PLATFORM_INTEGRATION.value: False,
                FeatureFlag.ANALYTICS_TRACKING.value: False
            }
        ),
        Environment.STAGING: EnvironmentConfig(
            name=Environment.STAGING,
            base_url="https://staging.example.com",
            cdn_enabled=True,
            max_concurrent_workers=4,
            batch_size=25,
            feature_overrides={
                FeatureFlag.AUTO_PROMOTION.value: True,
                FeatureFlag.ANALYTICS_TRACKING.value: False
            }
        ),
        Environment.PRODUCTION: EnvironmentConfig(
            name=Environment.PRODUCTION,
            base_url="https://example.com",
            cdn_enabled=True,
            max_concurrent_workers=8,
            batch_size=50,
            feature_overrides={
                FeatureFlag.VALIDATION_STRICT_MODE.value: True,
                FeatureFlag.CACHE_OPTIMIZATION.value: True
            }
        )
    }


def setup_default_config_files(config_dir: str = "config") -> None:
    """
    Set up default configuration files in the specified directory
    
    Args:
        config_dir: Directory to create configuration files in
    """
    config_path = Path(config_dir)
    config_path.mkdir(parents=True, exist_ok=True)
    
    # Create environments directory
    env_path = config_path / "environments"
    env_path.mkdir(exist_ok=True)
    
    # Create default environment configs
    default_configs = create_default_environment_configs()
    
    for env, config in default_configs.items():
        env_file = env_path / f"{env.value}.yaml"
        with open(env_file, 'w', encoding='utf-8') as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, indent=2)
    
    # Create main publishing config
    main_config = {
        "site_name": "Content Publishing Platform",
        "site_description": "Educational content archive and publishing platform",
        "feature_flags": {
            flag.value: False for flag in FeatureFlag
        }
    }
    
    main_file = config_path / "publishing.yaml"
    with open(main_file, 'w', encoding='utf-8') as f:
        yaml.dump(main_config, f, default_flow_style=False, indent=2)
    
    # Create integrations config
    integrations_config = IntegrationConfig().to_dict()
    integrations_file = config_path / "integrations.yaml"
    with open(integrations_file, 'w', encoding='utf-8') as f:
        yaml.dump(integrations_config, f, default_flow_style=False, indent=2)
    
    print(f"Default configuration files created in: {config_path}")