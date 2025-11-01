"""
End-to-End Workflow Integration for Content Publishing Platform

Implements complete publishing pipeline from content to production with
social package generation, queue integration, monitoring, and reporting.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .publishing_system import PublishingSystem, PublishingConfig, WorkflowResult, WorkflowStage
from .publishing_config import ConfigurationManager, Environment, FeatureFlag
from .publishing_models import (
    PublishManifest, Episode, ValidationResult, ValidationError, 
    ValidationWarning, ErrorType, Severity, PackageStatus
)
from .content_registry import ContentRegistry
from .social_queue_manager import SocialQueueManager, QueueItem, QueueItemStatus
from .analytics_tracker import AnalyticsTracker
from .error_handling import ErrorHandler, ErrorClassification, RecoveryAction


class WorkflowPhase(Enum):
    """Detailed workflow phases for monitoring"""
    INITIALIZATION = "initialization"
    MANIFEST_VALIDATION = "manifest_validation"
    CONTENT_DISCOVERY = "content_discovery"
    WEB_CONTENT_GENERATION = "web_content_generation"
    SOCIAL_PACKAGE_GENERATION = "social_package_generation"
    STAGING_DEPLOYMENT = "staging_deployment"
    VALIDATION_GATES = "validation_gates"
    PRODUCTION_DEPLOYMENT = "production_deployment"
    SOCIAL_QUEUE_PROCESSING = "social_queue_processing"
    PLATFORM_INTEGRATION = "platform_integration"
    CDN_OPTIMIZATION = "cdn_optimization"
    ANALYTICS_REPORTING = "analytics_reporting"
    CLEANUP = "cleanup"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowMetrics:
    """Comprehensive workflow execution metrics"""
    workflow_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Content metrics
    total_episodes: int = 0
    total_series: int = 0
    total_hosts: int = 0
    
    # Generation metrics
    pages_generated: int = 0
    feeds_generated: int = 0
    social_packages_generated: int = 0
    social_packages_valid: int = 0
    
    # Deployment metrics
    staging_deployment_time: Optional[timedelta] = None
    production_deployment_time: Optional[timedelta] = None
    validation_time: Optional[timedelta] = None
    
    # Social media metrics
    social_queue_items: int = 0
    social_posts_successful: int = 0
    social_posts_failed: int = 0
    
    # Platform integration metrics
    sitemaps_submitted: int = 0
    search_engines_notified: int = 0
    
    # Performance metrics
    peak_memory_usage_mb: Optional[float] = None
    peak_cpu_usage_percent: Optional[float] = None
    total_processing_time: Optional[timedelta] = None
    
    # Error metrics
    total_errors: int = 0
    total_warnings: int = 0
    recoverable_errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_episodes': self.total_episodes,
            'total_series': self.total_series,
            'total_hosts': self.total_hosts,
            'pages_generated': self.pages_generated,
            'feeds_generated': self.feeds_generated,
            'social_packages_generated': self.social_packages_generated,
            'social_packages_valid': self.social_packages_valid,
            'staging_deployment_time': str(self.staging_deployment_time) if self.staging_deployment_time else None,
            'production_deployment_time': str(self.production_deployment_time) if self.production_deployment_time else None,
            'validation_time': str(self.validation_time) if self.validation_time else None,
            'social_queue_items': self.social_queue_items,
            'social_posts_successful': self.social_posts_successful,
            'social_posts_failed': self.social_posts_failed,
            'sitemaps_submitted': self.sitemaps_submitted,
            'search_engines_notified': self.search_engines_notified,
            'peak_memory_usage_mb': self.peak_memory_usage_mb,
            'peak_cpu_usage_percent': self.peak_cpu_usage_percent,
            'total_processing_time': str(self.total_processing_time) if self.total_processing_time else None,
            'total_errors': self.total_errors,
            'total_warnings': self.total_warnings,
            'recoverable_errors': self.recoverable_errors
        }


@dataclass
class WorkflowReport:
    """Comprehensive workflow execution report"""
    workflow_result: WorkflowResult
    metrics: WorkflowMetrics
    phase_timings: Dict[WorkflowPhase, timedelta] = field(default_factory=dict)
    validation_details: Optional[ValidationResult] = None
    social_queue_report: Dict[str, Any] = field(default_factory=dict)
    platform_integration_report: Dict[str, Any] = field(default_factory=dict)
    performance_report: Dict[str, Any] = field(default_factory=dict)
    error_summary: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_result': self.workflow_result.to_dict(),
            'metrics': self.metrics.to_dict(),
            'phase_timings': {phase.value: str(timing) for phase, timing in self.phase_timings.items()},
            'validation_details': self.validation_details.to_dict() if self.validation_details else None,
            'social_queue_report': self.social_queue_report,
            'platform_integration_report': self.platform_integration_report,
            'performance_report': self.performance_report,
            'error_summary': self.error_summary,
            'recommendations': self.recommendations
        }


class WorkflowOrchestrator:
    """
    End-to-end workflow orchestrator for complete publishing pipeline
    
    Coordinates the entire publishing workflow from content ingestion to
    production deployment with comprehensive monitoring, reporting, and
    social media integration.
    """
    
    def __init__(self, 
                 config_manager: ConfigurationManager,
                 publishing_system: Optional[PublishingSystem] = None):
        """
        Initialize workflow orchestrator
        
        Args:
            config_manager: Configuration manager instance
            publishing_system: Optional pre-configured publishing system
        """
        self.config_manager = config_manager
        self.environment = config_manager.environment
        
        # Initialize publishing system if not provided
        if publishing_system:
            self.publishing_system = publishing_system
        else:
            self.publishing_system = self._create_publishing_system()
        
        # Workflow tracking
        self.active_workflows: Dict[str, WorkflowMetrics] = {}
        self.completed_workflows: List[WorkflowReport] = []
        
        # Performance monitoring
        self.performance_monitor = self._create_performance_monitor()
        
        # Error handling
        self.error_handler = ErrorHandler()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Progress callbacks
        self.progress_callbacks: List[Callable[[str, float, Dict[str, Any]], None]] = []
    
    def _create_publishing_system(self) -> PublishingSystem:
        """Create publishing system from configuration"""
        env_config = self.config_manager.get_environment_config()
        integration_config = self.config_manager.get_integration_config()
        
        # Create publishing configuration
        publishing_config = PublishingConfig(
            base_url=env_config.base_url,
            site_name=self.config_manager._base_config.get('site_name', 'Content Publishing Platform'),
            site_description=self.config_manager._base_config.get('site_description', 'Educational content archive'),
            deployment_config=self.config_manager.create_deployment_config(),
            url_patterns=self.config_manager.create_url_patterns(),
            social_generation_enabled=self.config_manager.is_feature_enabled(FeatureFlag.SOCIAL_GENERATION),
            platform_integration_enabled=self.config_manager.is_feature_enabled(FeatureFlag.PLATFORM_INTEGRATION),
            analytics_enabled=self.config_manager.is_feature_enabled(FeatureFlag.ANALYTICS_TRACKING),
            cdn_enabled=self.config_manager.is_feature_enabled(FeatureFlag.CDN_MANAGEMENT),
            auto_promote_to_production=self.config_manager.is_feature_enabled(FeatureFlag.AUTO_PROMOTION),
            content_base_path=env_config.content_base_path,
            temp_dir=env_config.temp_dir,
            social_platforms=integration_config.get_enabled_platforms(),
            social_profiles_config=integration_config.social_profiles_config,
            platform_credentials_path=integration_config.platform_credentials_config
        )
        
        return PublishingSystem(publishing_config)
    
    def _create_performance_monitor(self) -> Optional[Any]:
        """Create performance monitoring system"""
        # This would integrate with system monitoring tools
        # For now, return None as placeholder
        return None
    
    def add_progress_callback(self, callback: Callable[[str, float, Dict[str, Any]], None]) -> None:
        """Add progress callback for workflow monitoring"""
        self.progress_callbacks.append(callback)
        self.publishing_system.set_progress_callback(self._aggregate_progress_callbacks)
    
    def _aggregate_progress_callbacks(self, message: str, progress: float, metadata: Dict[str, Any]) -> None:
        """Aggregate and forward progress to all callbacks"""
        for callback in self.progress_callbacks:
            try:
                callback(message, progress, metadata)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    def execute_complete_workflow(self, 
                                 manifest_path: str,
                                 workflow_options: Optional[Dict[str, Any]] = None) -> WorkflowReport:
        """
        Execute complete end-to-end publishing workflow
        
        Args:
            manifest_path: Path to publish manifest
            workflow_options: Optional workflow configuration overrides
            
        Returns:
            WorkflowReport with comprehensive execution details
        """
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Initialize workflow metrics
        metrics = WorkflowMetrics(
            workflow_id=workflow_id,
            started_at=datetime.now()
        )
        
        self.active_workflows[workflow_id] = metrics
        
        # Initialize workflow report
        report = WorkflowReport(
            workflow_result=WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStage.INITIALIZATION,
                started_at=metrics.started_at
            ),
            metrics=metrics
        )
        
        try:
            self.logger.info(f"Starting complete workflow: {workflow_id}")
            
            # Phase 1: Initialization and validation
            phase_start = datetime.now()
            self._execute_initialization_phase(manifest_path, metrics, report)
            report.phase_timings[WorkflowPhase.INITIALIZATION] = datetime.now() - phase_start
            
            # Phase 2: Content discovery and analysis
            phase_start = datetime.now()
            self._execute_content_discovery_phase(manifest_path, metrics, report)
            report.phase_timings[WorkflowPhase.CONTENT_DISCOVERY] = datetime.now() - phase_start
            
            # Phase 3: Web content generation
            phase_start = datetime.now()
            self._execute_web_generation_phase(metrics, report)
            report.phase_timings[WorkflowPhase.WEB_CONTENT_GENERATION] = datetime.now() - phase_start
            
            # Phase 4: Social package generation (if enabled)
            if self.config_manager.is_feature_enabled(FeatureFlag.SOCIAL_GENERATION):
                phase_start = datetime.now()
                self._execute_social_generation_phase(metrics, report)
                report.phase_timings[WorkflowPhase.SOCIAL_PACKAGE_GENERATION] = datetime.now() - phase_start
            
            # Phase 5: Deployment pipeline
            phase_start = datetime.now()
            self._execute_deployment_phase(manifest_path, metrics, report, workflow_options)
            report.phase_timings[WorkflowPhase.STAGING_DEPLOYMENT] = datetime.now() - phase_start
            
            # Phase 6: Platform integration (if enabled)
            if self.config_manager.is_feature_enabled(FeatureFlag.PLATFORM_INTEGRATION):
                phase_start = datetime.now()
                self._execute_platform_integration_phase(metrics, report)
                report.phase_timings[WorkflowPhase.PLATFORM_INTEGRATION] = datetime.now() - phase_start
            
            # Phase 7: CDN optimization (if enabled)
            if self.config_manager.is_feature_enabled(FeatureFlag.CDN_MANAGEMENT):
                phase_start = datetime.now()
                self._execute_cdn_optimization_phase(metrics, report)
                report.phase_timings[WorkflowPhase.CDN_OPTIMIZATION] = datetime.now() - phase_start
            
            # Phase 8: Analytics and reporting
            if self.config_manager.is_feature_enabled(FeatureFlag.ANALYTICS_TRACKING):
                phase_start = datetime.now()
                self._execute_analytics_phase(metrics, report)
                report.phase_timings[WorkflowPhase.ANALYTICS_REPORTING] = datetime.now() - phase_start
            
            # Phase 9: Cleanup and finalization
            phase_start = datetime.now()
            self._execute_cleanup_phase(metrics, report)
            report.phase_timings[WorkflowPhase.CLEANUP] = datetime.now() - phase_start
            
            # Finalize workflow
            metrics.completed_at = datetime.now()
            metrics.total_processing_time = metrics.completed_at - metrics.started_at
            report.workflow_result.status = WorkflowStage.COMPLETED
            report.workflow_result.completed_at = metrics.completed_at
            
            # Generate recommendations
            self._generate_workflow_recommendations(report)
            
            self.logger.info(f"Workflow completed successfully: {workflow_id}")
            
        except Exception as e:
            # Handle workflow failure
            metrics.completed_at = datetime.now()
            metrics.total_processing_time = metrics.completed_at - metrics.started_at
            report.workflow_result.status = WorkflowStage.FAILED
            report.workflow_result.error_message = str(e)
            report.workflow_result.completed_at = metrics.completed_at
            
            # Add error to summary
            report.error_summary.append({
                'type': type(e).__name__,
                'message': str(e),
                'phase': 'workflow_execution',
                'timestamp': datetime.now().isoformat()
            })
            
            self.logger.error(f"Workflow failed: {workflow_id} - {str(e)}")
        
        finally:
            # Move from active to completed
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
            
            self.completed_workflows.append(report)
            
            # Limit completed workflow history
            if len(self.completed_workflows) > 100:
                self.completed_workflows = self.completed_workflows[-100:]
        
        return report
    
    def _execute_initialization_phase(self, 
                                    manifest_path: str, 
                                    metrics: WorkflowMetrics, 
                                    report: WorkflowReport) -> None:
        """Execute initialization and validation phase"""
        self._report_progress("Initializing workflow", 0.05, {"phase": "initialization"})
        
        # Validate configuration
        config_validation = self.config_manager.validate_configuration()
        if not config_validation.is_valid:
            raise ValueError(f"Configuration validation failed: {len(config_validation.errors)} errors")
        
        # Validate manifest file exists
        manifest_file = Path(manifest_path)
        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
        # System health check
        system_health = self.publishing_system.get_system_health()
        if system_health["overall_status"] != "healthy":
            report.workflow_result.warnings.append(f"System health check: {system_health['overall_status']}")
    
    def _execute_content_discovery_phase(self, 
                                       manifest_path: str, 
                                       metrics: WorkflowMetrics, 
                                       report: WorkflowReport) -> None:
        """Execute content discovery and analysis phase"""
        self._report_progress("Discovering and analyzing content", 0.1, {"phase": "content_discovery"})
        
        # Load manifest and get content statistics
        content_registry = self.publishing_system.content_registry
        manifest = content_registry.load_manifest(manifest_path)
        
        report.workflow_result.manifest_build_id = manifest.build_id
        
        # Get content counts
        episodes = content_registry.get_episodes()
        series = content_registry.get_all_series()
        hosts = content_registry.get_all_hosts()
        
        metrics.total_episodes = len(episodes)
        metrics.total_series = len(series)
        metrics.total_hosts = len(hosts)
        
        # Validate cross-references
        cross_ref_validation = content_registry.validate_cross_references()
        if not cross_ref_validation.is_valid:
            metrics.total_errors += len(cross_ref_validation.errors)
            metrics.total_warnings += len(cross_ref_validation.warnings)
    
    def _execute_web_generation_phase(self, 
                                    metrics: WorkflowMetrics, 
                                    report: WorkflowReport) -> None:
        """Execute web content generation phase"""
        self._report_progress("Generating web content", 0.2, {"phase": "web_generation"})
        
        # This phase is handled by the publishing system's internal workflow
        # We just track the metrics here
        pass
    
    def _execute_social_generation_phase(self, 
                                       metrics: WorkflowMetrics, 
                                       report: WorkflowReport) -> None:
        """Execute social media package generation phase"""
        self._report_progress("Generating social media packages", 0.3, {"phase": "social_generation"})
        
        # Social generation is handled by publishing system
        # Track metrics from social queue manager
        if hasattr(self.publishing_system, 'social_queue_manager') and self.publishing_system.social_queue_manager:
            queue_stats = self.publishing_system.social_queue_manager.get_queue_statistics()
            metrics.social_queue_items = queue_stats.get('total_items', 0)
    
    def _execute_deployment_phase(self, 
                                manifest_path: str,
                                metrics: WorkflowMetrics, 
                                report: WorkflowReport,
                                workflow_options: Optional[Dict[str, Any]]) -> None:
        """Execute deployment phase"""
        self._report_progress("Executing deployment pipeline", 0.5, {"phase": "deployment"})
        
        # Execute main publishing workflow
        auto_promote = workflow_options.get('auto_promote') if workflow_options else None
        
        workflow_result = self.publishing_system.publish_content(manifest_path, auto_promote)
        
        # Update report with workflow result
        report.workflow_result = workflow_result
        
        # Extract metrics from deployment results
        if workflow_result.staging_deployment:
            metrics.pages_generated = workflow_result.staging_deployment.content_counts.pages_generated
            metrics.feeds_generated = workflow_result.staging_deployment.content_counts.feeds_generated
        
        if workflow_result.validation_report:
            report.validation_details = workflow_result.validation_report
            metrics.total_errors += workflow_result.validation_report.total_errors
            metrics.total_warnings += workflow_result.validation_report.total_warnings
        
        # Social package metrics
        metrics.social_packages_generated = workflow_result.social_packages_generated
        metrics.social_packages_valid = workflow_result.social_packages_valid
    
    def _execute_platform_integration_phase(self, 
                                          metrics: WorkflowMetrics, 
                                          report: WorkflowReport) -> None:
        """Execute platform integration phase"""
        self._report_progress("Integrating with external platforms", 0.8, {"phase": "platform_integration"})
        
        integration_results = {}
        
        try:
            # Process social media queue
            if hasattr(self.publishing_system, 'social_queue_manager') and self.publishing_system.social_queue_manager:
                queue_results = self._process_social_media_queue(metrics)
                integration_results['social_queue'] = queue_results
            
            # Submit sitemaps to search engines
            if hasattr(self.publishing_system, 'platform_integrator') and self.publishing_system.platform_integrator:
                sitemap_results = self._submit_sitemaps(metrics)
                integration_results['sitemaps'] = sitemap_results
            
            report.platform_integration_report = integration_results
            
        except Exception as e:
            report.error_summary.append({
                'type': 'PlatformIntegrationError',
                'message': str(e),
                'phase': 'platform_integration',
                'timestamp': datetime.now().isoformat()
            })
    
    def _execute_cdn_optimization_phase(self, 
                                      metrics: WorkflowMetrics, 
                                      report: WorkflowReport) -> None:
        """Execute CDN optimization phase"""
        self._report_progress("Optimizing CDN configuration", 0.85, {"phase": "cdn_optimization"})
        
        try:
            if hasattr(self.publishing_system, 'cdn_manager') and self.publishing_system.cdn_manager:
                # Trigger cache warming and optimization
                # This would be implemented based on specific CDN provider
                pass
        except Exception as e:
            report.error_summary.append({
                'type': 'CDNOptimizationError',
                'message': str(e),
                'phase': 'cdn_optimization',
                'timestamp': datetime.now().isoformat()
            })
    
    def _execute_analytics_phase(self, 
                               metrics: WorkflowMetrics, 
                               report: WorkflowReport) -> None:
        """Execute analytics and reporting phase"""
        self._report_progress("Generating analytics reports", 0.9, {"phase": "analytics"})
        
        try:
            if hasattr(self.publishing_system, 'analytics_tracker') and self.publishing_system.analytics_tracker:
                # Generate analytics report
                analytics_report = {
                    'workflow_id': metrics.workflow_id,
                    'content_published': metrics.pages_generated,
                    'social_packages_created': metrics.social_packages_generated,
                    'deployment_time': str(metrics.total_processing_time) if metrics.total_processing_time else None
                }
                
                report.performance_report = analytics_report
        except Exception as e:
            report.error_summary.append({
                'type': 'AnalyticsError',
                'message': str(e),
                'phase': 'analytics',
                'timestamp': datetime.now().isoformat()
            })
    
    def _execute_cleanup_phase(self, 
                             metrics: WorkflowMetrics, 
                             report: WorkflowReport) -> None:
        """Execute cleanup and finalization phase"""
        self._report_progress("Finalizing workflow", 0.95, {"phase": "cleanup"})
        
        try:
            # Clean up temporary files
            env_config = self.config_manager.get_environment_config()
            temp_dir = Path(env_config.temp_dir)
            
            # Clean up old temporary files (older than 1 day)
            if temp_dir.exists():
                cutoff_time = datetime.now() - timedelta(days=1)
                for temp_file in temp_dir.rglob("*"):
                    if temp_file.is_file():
                        file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            try:
                                temp_file.unlink()
                            except Exception:
                                pass  # Ignore cleanup errors
            
            # Archive old deployment backups if needed
            # This would be implemented based on backup retention policy
            
        except Exception as e:
            report.error_summary.append({
                'type': 'CleanupError',
                'message': str(e),
                'phase': 'cleanup',
                'timestamp': datetime.now().isoformat()
            })
    
    def _process_social_media_queue(self, metrics: WorkflowMetrics) -> Dict[str, Any]:
        """Process social media posting queue"""
        if not hasattr(self.publishing_system, 'social_queue_manager'):
            return {}
        
        queue_manager = self.publishing_system.social_queue_manager
        
        # Get all pending queue items
        pending_items = queue_manager.get_pending_items()
        
        results = {
            'total_items': len(pending_items),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for item in pending_items:
            try:
                # In a real implementation, this would post to the actual platform
                # For now, we'll simulate the process
                
                # Update item status to processing
                queue_manager.update_item_status(item.item_id, QueueItemStatus.PROCESSING)
                
                # Simulate posting (this would be actual API calls)
                success = True  # Placeholder
                
                if success:
                    queue_manager.update_item_status(item.item_id, QueueItemStatus.POSTED)
                    results['successful'] += 1
                    metrics.social_posts_successful += 1
                else:
                    queue_manager.update_item_status(item.item_id, QueueItemStatus.FAILED)
                    results['failed'] += 1
                    metrics.social_posts_failed += 1
                
                results['processed'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
                metrics.social_posts_failed += 1
        
        return results
    
    def _submit_sitemaps(self, metrics: WorkflowMetrics) -> Dict[str, Any]:
        """Submit sitemaps to search engines"""
        if not hasattr(self.publishing_system, 'platform_integrator'):
            return {}
        
        platform_integrator = self.publishing_system.platform_integrator
        env_config = self.config_manager.get_environment_config()
        
        sitemap_url = f"{env_config.base_url}/feeds/sitemap.xml"
        
        results = {
            'sitemap_url': sitemap_url,
            'submissions': {}
        }
        
        # Submit to enabled search engines
        integration_config = self.config_manager.get_integration_config()
        
        if integration_config.google_search_console_enabled:
            try:
                result = platform_integrator.submit_sitemap("google", sitemap_url)
                results['submissions']['google'] = result.to_dict() if result else None
                if result and result.success:
                    metrics.sitemaps_submitted += 1
                    metrics.search_engines_notified += 1
            except Exception as e:
                results['submissions']['google'] = {'error': str(e)}
        
        if integration_config.bing_webmaster_tools_enabled:
            try:
                result = platform_integrator.submit_sitemap("bing", sitemap_url)
                results['submissions']['bing'] = result.to_dict() if result else None
                if result and result.success:
                    metrics.sitemaps_submitted += 1
                    metrics.search_engines_notified += 1
            except Exception as e:
                results['submissions']['bing'] = {'error': str(e)}
        
        return results
    
    def _generate_workflow_recommendations(self, report: WorkflowReport) -> None:
        """Generate recommendations based on workflow execution"""
        recommendations = []
        
        # Performance recommendations
        if report.metrics.total_processing_time:
            total_seconds = report.metrics.total_processing_time.total_seconds()
            if total_seconds > 1800:  # 30 minutes
                recommendations.append("Consider increasing batch size or concurrent workers to improve performance")
        
        # Error rate recommendations
        if report.metrics.total_errors > 0:
            error_rate = report.metrics.total_errors / max(report.metrics.total_episodes, 1)
            if error_rate > 0.1:  # 10% error rate
                recommendations.append("High error rate detected - review validation thresholds and content quality")
        
        # Social media recommendations
        if report.metrics.social_packages_generated > 0:
            success_rate = report.metrics.social_packages_valid / report.metrics.social_packages_generated
            if success_rate < 0.8:  # 80% success rate
                recommendations.append("Low social package success rate - review platform profiles and content compliance")
        
        # Platform integration recommendations
        if report.metrics.social_posts_failed > report.metrics.social_posts_successful:
            recommendations.append("Social media posting failures exceed successes - check API credentials and rate limits")
        
        report.recommendations = recommendations
    
    def _report_progress(self, message: str, progress: float, metadata: Dict[str, Any]) -> None:
        """Report workflow progress"""
        for callback in self.progress_callbacks:
            try:
                callback(message, progress, metadata)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    def get_active_workflows(self) -> Dict[str, WorkflowMetrics]:
        """Get currently active workflows"""
        return self.active_workflows.copy()
    
    def get_workflow_history(self, limit: int = 50) -> List[WorkflowReport]:
        """Get recent workflow history"""
        return sorted(self.completed_workflows, 
                     key=lambda r: r.metrics.started_at, 
                     reverse=True)[:limit]
    
    def get_workflow_report(self, workflow_id: str) -> Optional[WorkflowReport]:
        """Get specific workflow report"""
        for report in self.completed_workflows:
            if report.workflow_result.workflow_id == workflow_id:
                return report
        return None
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel an active workflow
        
        Args:
            workflow_id: Workflow to cancel
            
        Returns:
            True if workflow was cancelled, False if not found or already completed
        """
        if workflow_id in self.active_workflows:
            # In a real implementation, this would signal the workflow to stop
            # For now, we'll just remove it from active workflows
            del self.active_workflows[workflow_id]
            self.logger.info(f"Workflow cancelled: {workflow_id}")
            return True
        return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment.value,
            'active_workflows': len(self.active_workflows),
            'completed_workflows_today': len([
                r for r in self.completed_workflows 
                if r.metrics.started_at.date() == datetime.now().date()
            ]),
            'system_health': self.publishing_system.get_system_health(),
            'configuration_valid': self.config_manager.validate_configuration().is_valid,
            'feature_flags': {
                flag.value: self.config_manager.is_feature_enabled(flag)
                for flag in FeatureFlag
            }
        }


# Factory functions

def create_workflow_orchestrator(config_dir: str = "config", 
                               environment: Optional[Environment] = None) -> WorkflowOrchestrator:
    """
    Create workflow orchestrator with configuration
    
    Args:
        config_dir: Configuration directory
        environment: Target environment
        
    Returns:
        Configured WorkflowOrchestrator
    """
    from .publishing_config import create_configuration_manager
    
    config_manager = create_configuration_manager(config_dir, environment)
    return WorkflowOrchestrator(config_manager)


def create_workflow_orchestrator_from_config(config_manager: ConfigurationManager) -> WorkflowOrchestrator:
    """
    Create workflow orchestrator from existing configuration manager
    
    Args:
        config_manager: Configured ConfigurationManager
        
    Returns:
        WorkflowOrchestrator instance
    """
    return WorkflowOrchestrator(config_manager)