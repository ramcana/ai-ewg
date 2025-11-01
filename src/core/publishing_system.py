"""
Publishing System Orchestrator for Content Publishing Platform

Main orchestrator class that coordinates all components for end-to-end
publishing workflow from manifest to deployment with social package integration.
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .publishing_models import (
    PublishManifest, Episode, Series, Host, ValidationResult, ValidationError,
    ValidationWarning, ErrorType, Severity, PackageStatus
)
from .content_registry import ContentRegistry
from .web_generator import WebGenerator, URLPattern
from .feed_generator import FeedGenerator
from .social_generator import SocialGenerator
from .deployment_pipeline import (
    DeploymentPipeline, DeploymentConfig, DeploymentResult, DeploymentStatus,
    Environment, ValidationReport
)
from .platform_integrator import PlatformIntegrator
from .cdn_manager import CDNManager
from .analytics_tracker import AnalyticsTracker
from .social_queue_manager import SocialQueueManager
from .error_handling import ErrorHandler, ErrorClassification, RecoveryAction


class WorkflowStage(Enum):
    """Publishing workflow stages"""
    INITIALIZATION = "initialization"
    CONTENT_LOADING = "content_loading"
    WEB_GENERATION = "web_generation"
    SOCIAL_GENERATION = "social_generation"
    STAGING_DEPLOYMENT = "staging_deployment"
    VALIDATION = "validation"
    PRODUCTION_DEPLOYMENT = "production_deployment"
    PLATFORM_INTEGRATION = "platform_integration"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PublishingConfig:
    """Configuration for publishing system"""
    # Base configuration
    base_url: str = "https://example.com"
    site_name: str = "Content Publishing Platform"
    site_description: str = "Educational content archive and publishing platform"
    
    # Component configurations
    deployment_config: DeploymentConfig = field(default_factory=DeploymentConfig)
    url_patterns: URLPattern = field(default_factory=URLPattern)
    
    # Feature flags
    social_generation_enabled: bool = True
    platform_integration_enabled: bool = True
    analytics_enabled: bool = True
    cdn_enabled: bool = True
    
    # Workflow settings
    auto_promote_to_production: bool = False
    validation_failure_action: str = "halt"  # "halt" or "continue"
    social_failure_action: str = "continue"  # "halt" or "continue"
    
    # Paths
    content_base_path: str = "data"
    temp_dir: str = "temp"
    
    # Social media settings
    social_platforms: List[str] = field(default_factory=lambda: ["youtube", "instagram"])
    social_profiles_config: str = "config/social_profiles.yaml"
    
    # Platform integration settings
    platform_credentials_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'base_url': self.base_url,
            'site_name': self.site_name,
            'site_description': self.site_description,
            'social_generation_enabled': self.social_generation_enabled,
            'platform_integration_enabled': self.platform_integration_enabled,
            'analytics_enabled': self.analytics_enabled,
            'cdn_enabled': self.cdn_enabled,
            'auto_promote_to_production': self.auto_promote_to_production,
            'validation_failure_action': self.validation_failure_action,
            'social_failure_action': self.social_failure_action,
            'content_base_path': self.content_base_path,
            'temp_dir': self.temp_dir,
            'social_platforms': self.social_platforms,
            'social_profiles_config': self.social_profiles_config,
            'platform_credentials_path': self.platform_credentials_path
        }


@dataclass
class WorkflowResult:
    """Result from publishing workflow execution"""
    workflow_id: str
    status: WorkflowStage
    started_at: datetime
    completed_at: Optional[datetime] = None
    manifest_build_id: Optional[str] = None
    staging_deployment: Optional[DeploymentResult] = None
    production_deployment: Optional[DeploymentResult] = None
    validation_report: Optional[ValidationReport] = None
    social_packages_generated: int = 0
    social_packages_valid: int = 0
    platform_submissions: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'manifest_build_id': self.manifest_build_id,
            'staging_deployment': self.staging_deployment.to_dict() if self.staging_deployment else None,
            'production_deployment': self.production_deployment.to_dict() if self.production_deployment else None,
            'validation_report': self.validation_report.to_dict() if self.validation_report else None,
            'social_packages_generated': self.social_packages_generated,
            'social_packages_valid': self.social_packages_valid,
            'platform_submissions': self.platform_submissions,
            'error_message': self.error_message,
            'warnings': self.warnings,
            'metadata': self.metadata
        }


class PublishingSystem:
    """
    Main orchestrator for the Content Publishing Platform
    
    Coordinates all components for end-to-end publishing workflow from
    manifest loading to production deployment with social package integration.
    """
    
    def __init__(self, config: PublishingConfig):
        """
        Initialize Publishing System
        
        Args:
            config: Publishing system configuration
        """
        self.config = config
        self.workflow_history: List[WorkflowResult] = []
        
        # Initialize core components
        self._initialize_components()
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        
        # Error handling
        self.error_handler = ErrorHandler()
    
    def _initialize_components(self) -> None:
        """Initialize all system components with dependency injection"""
        # Content registry
        self.content_registry = ContentRegistry(self.config.content_base_path)
        
        # Web generator with URL patterns
        self.web_generator = WebGenerator(
            url_patterns=self.config.url_patterns,
            site_name=self.config.site_name,
            site_description=self.config.site_description
        )
        
        # Feed generator
        self.feed_generator = FeedGenerator(
            content_registry=self.content_registry,
            base_url=self.config.base_url,
            site_name=self.config.site_name,
            site_description=self.config.site_description
        )
        
        # Social generator (if enabled)
        if self.config.social_generation_enabled:
            from .social_generator import create_social_generator
            self.social_generator = create_social_generator(
                self.config.social_profiles_config,
                self.config.temp_dir
            )
            
            # Social queue manager
            queue_root = Path(self.config.content_base_path) / "social" / "queue"
            self.social_queue_manager = SocialQueueManager(str(queue_root))
        else:
            self.social_generator = None
            self.social_queue_manager = None
        
        # Deployment pipeline
        self.deployment_pipeline = DeploymentPipeline(self.config.deployment_config)
        
        # Platform integrator (if enabled)
        if self.config.platform_integration_enabled and self.config.platform_credentials_path:
            from .platform_integrator import create_platform_integrator
            self.platform_integrator = create_platform_integrator(
                self.config.platform_credentials_path
            )
        else:
            self.platform_integrator = None
        
        # CDN manager (if enabled)
        if self.config.cdn_enabled:
            from .cdn_manager import create_cdn_manager
            self.cdn_manager = create_cdn_manager()
        else:
            self.cdn_manager = None
        
        # Analytics tracker (if enabled)
        if self.config.analytics_enabled:
            self.analytics_tracker = AnalyticsTracker()
            # Inject analytics tracker into web generator
            self.web_generator.analytics_tracker = self.analytics_tracker
        else:
            self.analytics_tracker = None
    
    def set_progress_callback(self, callback: Callable[[str, float, Dict[str, Any]], None]) -> None:
        """
        Set callback for progress reporting
        
        Args:
            callback: Function that receives (message, progress, metadata)
        """
        self.progress_callback = callback
    
    def _report_progress(self, message: str, progress: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Report progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(message, progress, metadata or {})
    
    def publish_content(self, manifest_path: str, 
                       auto_promote: Optional[bool] = None) -> WorkflowResult:
        """
        Execute complete publishing workflow from manifest to production
        
        Args:
            manifest_path: Path to publish manifest file
            auto_promote: Override config setting for auto-promotion to production
            
        Returns:
            WorkflowResult with comprehensive workflow execution details
        """
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        result = WorkflowResult(
            workflow_id=workflow_id,
            status=WorkflowStage.INITIALIZATION,
            started_at=datetime.now()
        )
        
        try:
            self._report_progress("Starting publishing workflow", 0.0, {"workflow_id": workflow_id})
            
            # Stage 1: Load and validate manifest
            result.status = WorkflowStage.CONTENT_LOADING
            self._report_progress("Loading content manifest", 0.1)
            
            manifest = self.content_registry.load_manifest(manifest_path)
            result.manifest_build_id = manifest.build_id
            
            # Stage 2: Generate web content
            result.status = WorkflowStage.WEB_GENERATION
            self._report_progress("Generating web content", 0.2)
            
            # Stage 3: Generate social packages (if enabled)
            if self.config.social_generation_enabled and self.social_generator:
                result.status = WorkflowStage.SOCIAL_GENERATION
                self._report_progress("Generating social media packages", 0.3)
                
                social_results = self._generate_social_packages(manifest)
                result.social_packages_generated = social_results["total"]
                result.social_packages_valid = social_results["valid"]
                
                if social_results["total"] > 0:
                    result.warnings.append(f"Generated {social_results['valid']}/{social_results['total']} valid social packages")
            
            # Stage 4: Deploy to staging
            result.status = WorkflowStage.STAGING_DEPLOYMENT
            self._report_progress("Deploying to staging environment", 0.5)
            
            staging_result = self.deployment_pipeline.deploy_to_staging(manifest_path)
            result.staging_deployment = staging_result
            
            if staging_result.status == DeploymentStatus.FAILED:
                raise Exception(f"Staging deployment failed: {staging_result.error_message}")
            
            # Stage 5: Run validation gates
            result.status = WorkflowStage.VALIDATION
            self._report_progress("Running validation gates", 0.7)
            
            validation_report = self.deployment_pipeline.run_validation_gates(
                staging_result.deployment_id
            )
            result.validation_report = validation_report
            
            # Handle validation failures
            if not validation_report.overall_passed:
                if self.config.validation_failure_action == "halt":
                    raise Exception(f"Validation failed with {validation_report.total_errors} errors")
                else:
                    result.warnings.append(f"Validation failed but continuing: {validation_report.total_errors} errors")
            
            # Stage 6: Deploy to production (if auto-promote or validation passed)
            should_promote = auto_promote if auto_promote is not None else self.config.auto_promote_to_production
            if should_promote or validation_report.overall_passed:
                result.status = WorkflowStage.PRODUCTION_DEPLOYMENT
                self._report_progress("Deploying to production", 0.8)
                
                production_result = self.deployment_pipeline.promote_to_production(
                    staging_result.deployment_id
                )
                result.production_deployment = production_result
                
                if production_result.status == DeploymentStatus.FAILED:
                    raise Exception(f"Production deployment failed: {production_result.error_message}")
            
            # Stage 7: Platform integration (if enabled and production deployed)
            if (self.config.platform_integration_enabled and 
                self.platform_integrator and 
                result.production_deployment and 
                result.production_deployment.status == DeploymentStatus.COMPLETED):
                
                result.status = WorkflowStage.PLATFORM_INTEGRATION
                self._report_progress("Integrating with external platforms", 0.9)
                
                platform_results = self._integrate_with_platforms(manifest)
                result.platform_submissions = platform_results
            
            # Workflow completed successfully
            result.status = WorkflowStage.COMPLETED
            result.completed_at = datetime.now()
            
            self._report_progress("Publishing workflow completed", 1.0, {
                "workflow_id": workflow_id,
                "duration_seconds": (result.completed_at - result.started_at).total_seconds()
            })
            
        except Exception as e:
            result.status = WorkflowStage.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            
            # Handle error with recovery if possible
            recovery_action = self.error_handler.handle_error(e, {"workflow_id": workflow_id})
            if recovery_action != RecoveryAction.FAIL:
                result.warnings.append(f"Error handled with recovery action: {recovery_action.value}")
            
            self._report_progress(f"Publishing workflow failed: {str(e)}", 1.0, {
                "workflow_id": workflow_id,
                "error": str(e)
            })
        
        # Store workflow result in history
        self.workflow_history.append(result)
        
        return result
    
    def _generate_social_packages(self, manifest: PublishManifest) -> Dict[str, int]:
        """Generate social media packages for all episodes"""
        if not self.social_generator:
            return {"total": 0, "valid": 0}
        
        episodes = self.content_registry.get_episodes()
        total_packages = 0
        valid_packages = 0
        
        social_base_dir = Path(self.config.content_base_path) / "social"
        
        for episode in episodes:
            for platform in self.config.social_platforms:
                try:
                    # Generate social package
                    from .social_generator import SocialGenerationJob
                    job = SocialGenerationJob(
                        episode=episode,
                        platform_id=platform,
                        output_dir=social_base_dir / platform / episode.episode_id,
                        source_video_path=episode.content_url,
                        source_caption_path=episode.transcript_path
                    )
                    
                    result = self.social_generator.generate_social_package(job)
                    total_packages += 1
                    
                    if result.success and result.social_package and result.social_package.status == PackageStatus.VALID:
                        valid_packages += 1
                        
                        # Add to social queue if queue manager available
                        if self.social_queue_manager:
                            self.social_queue_manager.add_package_to_queue(
                                manifest.build_id,
                                result.social_package
                            )
                
                except Exception as e:
                    total_packages += 1
                    self._report_progress(f"Failed to generate {platform} package for {episode.episode_id}: {str(e)}", None)
        
        return {"total": total_packages, "valid": valid_packages}
    
    def _integrate_with_platforms(self, manifest: PublishManifest) -> Dict[str, Any]:
        """Integrate with external platforms (search engines, social media)"""
        if not self.platform_integrator:
            return {}
        
        results = {}
        
        try:
            # Submit sitemaps to search engines
            sitemap_url = f"{self.config.base_url}/feeds/sitemap.xml"
            
            # Google Search Console
            google_result = self.platform_integrator.submit_sitemap("google", sitemap_url)
            results["google_sitemap"] = google_result.to_dict() if google_result else None
            
            # Bing Webmaster Tools
            bing_result = self.platform_integrator.submit_sitemap("bing", sitemap_url)
            results["bing_sitemap"] = bing_result.to_dict() if bing_result else None
            
            # Process social media queue (if available)
            if self.social_queue_manager:
                queue_results = self._process_social_queue(manifest.build_id)
                results["social_queue"] = queue_results
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def _process_social_queue(self, build_id: str) -> Dict[str, Any]:
        """Process social media posting queue"""
        if not self.social_queue_manager or not self.platform_integrator:
            return {}
        
        try:
            # Get queue items for this build
            queue_items = self.social_queue_manager.get_queue_items(build_id)
            
            results = {
                "total_items": len(queue_items),
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "errors": []
            }
            
            for item in queue_items:
                try:
                    # Post to platform (this would be async in real implementation)
                    post_result = self.platform_integrator.post_to_platform(
                        item.social_package, 
                        item.platform
                    )
                    
                    results["processed"] += 1
                    
                    if post_result and post_result.success:
                        results["successful"] += 1
                        # Update queue item status
                        self.social_queue_manager.update_item_status(
                            item.item_id, 
                            "posted",
                            external_id=post_result.external_id
                        )
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Failed to post {item.episode_id} to {item.platform}")
                
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Error posting {item.episode_id} to {item.platform}: {str(e)}")
            
            return results
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowResult]:
        """
        Get status of a specific workflow
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            WorkflowResult if found, None otherwise
        """
        for result in self.workflow_history:
            if result.workflow_id == workflow_id:
                return result
        return None
    
    def get_recent_workflows(self, limit: int = 10) -> List[WorkflowResult]:
        """
        Get recent workflow results
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent WorkflowResult objects
        """
        return sorted(self.workflow_history, key=lambda r: r.started_at, reverse=True)[:limit]
    
    def rollback_deployment(self, deployment_id: str) -> DeploymentResult:
        """
        Rollback a production deployment
        
        Args:
            deployment_id: Deployment to rollback
            
        Returns:
            DeploymentResult from rollback operation
        """
        return self.deployment_pipeline.rollback_deployment(deployment_id)
    
    def validate_configuration(self) -> ValidationResult:
        """
        Validate system configuration and component health
        
        Returns:
            ValidationResult with configuration validation status
        """
        errors = []
        warnings = []
        
        # Validate base configuration
        if not self.config.base_url:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="Base URL is required",
                location="config.base_url",
                severity=Severity.ERROR
            ))
        
        # Validate component initialization
        if self.config.social_generation_enabled and not self.social_generator:
            warnings.append(ValidationWarning(
                message="Social generation enabled but social generator not initialized",
                location="social_generator"
            ))
        
        if self.config.platform_integration_enabled and not self.platform_integrator:
            warnings.append(ValidationWarning(
                message="Platform integration enabled but platform integrator not initialized",
                location="platform_integrator"
            ))
        
        # Validate paths
        content_path = Path(self.config.content_base_path)
        if not content_path.exists():
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Content base path does not exist: {content_path}",
                location="config.content_base_path",
                severity=Severity.ERROR
            ))
        
        # Test component connectivity
        try:
            # Test content registry
            self.content_registry.get_content_statistics()
        except Exception as e:
            warnings.append(ValidationWarning(
                message=f"Content registry test failed: {str(e)}",
                location="content_registry"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "validation_timestamp": datetime.now().isoformat(),
                "components_initialized": {
                    "content_registry": self.content_registry is not None,
                    "web_generator": self.web_generator is not None,
                    "feed_generator": self.feed_generator is not None,
                    "social_generator": self.social_generator is not None,
                    "deployment_pipeline": self.deployment_pipeline is not None,
                    "platform_integrator": self.platform_integrator is not None,
                    "cdn_manager": self.cdn_manager is not None,
                    "analytics_tracker": self.analytics_tracker is not None
                }
            }
        )
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health information
        
        Returns:
            Dictionary with system health metrics and status
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "recent_workflows": len([r for r in self.workflow_history 
                                  if r.started_at > datetime.now() - timedelta(hours=24)]),
            "failed_workflows": len([r for r in self.workflow_history 
                                   if r.status == WorkflowStage.FAILED]),
            "configuration": self.config.to_dict()
        }
        
        # Check component health
        components = {
            "content_registry": self.content_registry,
            "web_generator": self.web_generator,
            "feed_generator": self.feed_generator,
            "social_generator": self.social_generator,
            "deployment_pipeline": self.deployment_pipeline,
            "platform_integrator": self.platform_integrator,
            "cdn_manager": self.cdn_manager,
            "analytics_tracker": self.analytics_tracker
        }
        
        for name, component in components.items():
            if component is None:
                health["components"][name] = {"status": "disabled", "enabled": False}
            else:
                try:
                    # Basic health check - component exists and is callable
                    health["components"][name] = {
                        "status": "healthy",
                        "enabled": True,
                        "type": type(component).__name__
                    }
                except Exception as e:
                    health["components"][name] = {
                        "status": "unhealthy",
                        "enabled": True,
                        "error": str(e)
                    }
                    health["overall_status"] = "degraded"
        
        return health


# Factory functions for creating publishing system instances

def create_publishing_system(config: Optional[PublishingConfig] = None) -> PublishingSystem:
    """
    Create a PublishingSystem instance with configuration
    
    Args:
        config: Optional publishing configuration
        
    Returns:
        Configured PublishingSystem instance
    """
    if config is None:
        config = PublishingConfig()
    
    return PublishingSystem(config)


def create_default_config() -> PublishingConfig:
    """
    Create default publishing configuration
    
    Returns:
        PublishingConfig with default settings
    """
    return PublishingConfig()


def load_config_from_file(config_path: str) -> PublishingConfig:
    """
    Load publishing configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        PublishingConfig loaded from file
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # Create deployment config if present
    deployment_config = DeploymentConfig()
    if 'deployment_config' in config_data:
        deployment_config = DeploymentConfig(**config_data['deployment_config'])
    
    # Create URL patterns if present
    url_patterns = URLPattern()
    if 'url_patterns' in config_data:
        url_patterns = URLPattern(**config_data['url_patterns'])
    
    # Remove nested configs from main config data
    config_data.pop('deployment_config', None)
    config_data.pop('url_patterns', None)
    
    # Create main config
    config = PublishingConfig(
        deployment_config=deployment_config,
        url_patterns=url_patterns,
        **config_data
    )
    
    return config