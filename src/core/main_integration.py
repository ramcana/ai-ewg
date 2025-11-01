"""
Main Integration Module for Content Publishing Platform

Provides high-level interface for complete publishing system integration
with simplified setup and execution for end-to-end workflows.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .publishing_config import (
    ConfigurationManager, Environment, FeatureFlag, 
    create_configuration_manager, setup_default_config_files
)
from .publishing_system import PublishingSystem, PublishingConfig
from .workflow_orchestrator import (
    WorkflowOrchestrator, WorkflowReport, WorkflowMetrics,
    create_workflow_orchestrator_from_config
)
from .publishing_models import ValidationResult


class ContentPublishingPlatform:
    """
    Main integration class for the Content Publishing Platform
    
    Provides a simplified interface for setting up and running the complete
    publishing system with configuration management, workflow orchestration,
    and comprehensive monitoring.
    """
    
    def __init__(self, 
                 config_dir: str = "config",
                 environment: Optional[Environment] = None,
                 auto_setup: bool = True):
        """
        Initialize Content Publishing Platform
        
        Args:
            config_dir: Configuration directory path
            environment: Target environment (auto-detected if None)
            auto_setup: Whether to automatically set up default configuration
        """
        self.config_dir = Path(config_dir)
        self.environment = environment
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize configuration manager
        if auto_setup and not self.config_dir.exists():
            self.setup_default_configuration()
        
        self.config_manager = create_configuration_manager(str(self.config_dir), environment)
        
        # Initialize workflow orchestrator
        self.workflow_orchestrator = create_workflow_orchestrator_from_config(self.config_manager)
        
        # Get publishing system from orchestrator
        self.publishing_system = self.workflow_orchestrator.publishing_system
        
        # Progress tracking
        self.progress_callbacks: List[Callable[[str, float, Dict[str, Any]], None]] = []
        
        self.logger.info(f"Content Publishing Platform initialized for environment: {self.config_manager.environment.value}")
    
    def setup_default_configuration(self) -> None:
        """Set up default configuration files"""
        self.logger.info(f"Setting up default configuration in: {self.config_dir}")
        setup_default_config_files(str(self.config_dir))
    
    def add_progress_callback(self, callback: Callable[[str, float, Dict[str, Any]], None]) -> None:
        """
        Add progress callback for workflow monitoring
        
        Args:
            callback: Function that receives (message, progress, metadata)
        """
        self.progress_callbacks.append(callback)
        self.workflow_orchestrator.add_progress_callback(callback)
    
    def validate_system(self) -> ValidationResult:
        """
        Validate complete system configuration and health
        
        Returns:
            ValidationResult with comprehensive system validation
        """
        self.logger.info("Validating system configuration and health")
        
        # Validate configuration
        config_validation = self.config_manager.validate_configuration()
        
        # Validate publishing system
        system_validation = self.publishing_system.validate_configuration()
        
        # Combine validation results
        all_errors = config_validation.errors + system_validation.errors
        all_warnings = config_validation.warnings + system_validation.warnings
        
        combined_metadata = {
            'config_validation': config_validation.metadata,
            'system_validation': system_validation.metadata,
            'system_health': self.publishing_system.get_system_health()
        }
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            metadata=combined_metadata
        )
    
    def publish_content(self, 
                       manifest_path: str,
                       workflow_options: Optional[Dict[str, Any]] = None) -> WorkflowReport:
        """
        Execute complete content publishing workflow
        
        Args:
            manifest_path: Path to publish manifest file
            workflow_options: Optional workflow configuration overrides
            
        Returns:
            WorkflowReport with comprehensive execution details
        """
        self.logger.info(f"Starting content publishing workflow: {manifest_path}")
        
        # Execute complete workflow through orchestrator
        report = self.workflow_orchestrator.execute_complete_workflow(
            manifest_path, 
            workflow_options
        )
        
        # Log workflow completion
        if report.workflow_result.status.value == "completed":
            self.logger.info(f"Workflow completed successfully: {report.workflow_result.workflow_id}")
        else:
            self.logger.error(f"Workflow failed: {report.workflow_result.workflow_id} - {report.workflow_result.error_message}")
        
        return report
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status
        
        Returns:
            Dictionary with complete system status information
        """
        return {
            'platform_info': {
                'environment': self.config_manager.environment.value,
                'config_dir': str(self.config_dir),
                'timestamp': datetime.now().isoformat()
            },
            'system_health': self.publishing_system.get_system_health(),
            'workflow_status': self.workflow_orchestrator.get_system_status(),
            'configuration': {
                'valid': self.config_manager.validate_configuration().is_valid,
                'feature_flags': {
                    flag.value: self.config_manager.is_feature_enabled(flag)
                    for flag in FeatureFlag
                },
                'integrations': self.config_manager.get_integration_config().to_dict()
            },
            'active_workflows': len(self.workflow_orchestrator.get_active_workflows()),
            'recent_workflows': len(self.workflow_orchestrator.get_workflow_history(10))
        }
    
    def get_workflow_history(self, limit: int = 20) -> List[WorkflowReport]:
        """
        Get recent workflow execution history
        
        Args:
            limit: Maximum number of workflows to return
            
        Returns:
            List of recent WorkflowReport objects
        """
        return self.workflow_orchestrator.get_workflow_history(limit)
    
    def get_workflow_report(self, workflow_id: str) -> Optional[WorkflowReport]:
        """
        Get specific workflow report
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            WorkflowReport if found, None otherwise
        """
        return self.workflow_orchestrator.get_workflow_report(workflow_id)
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel an active workflow
        
        Args:
            workflow_id: Workflow to cancel
            
        Returns:
            True if workflow was cancelled, False if not found
        """
        return self.workflow_orchestrator.cancel_workflow(workflow_id)
    
    def reload_configuration(self) -> ValidationResult:
        """
        Reload system configuration from files
        
        Returns:
            ValidationResult from reloaded configuration
        """
        self.logger.info("Reloading system configuration")
        
        # Reload configuration manager
        validation_result = self.config_manager.reload_configuration()
        
        # Recreate workflow orchestrator with new configuration
        self.workflow_orchestrator = create_workflow_orchestrator_from_config(self.config_manager)
        self.publishing_system = self.workflow_orchestrator.publishing_system
        
        # Re-add progress callbacks
        for callback in self.progress_callbacks:
            self.workflow_orchestrator.add_progress_callback(callback)
        
        return validation_result
    
    def export_configuration(self, output_path: str, include_secrets: bool = False) -> None:
        """
        Export current configuration to file
        
        Args:
            output_path: Path to output file
            include_secrets: Whether to include secret values (dangerous!)
        """
        self.config_manager.export_configuration(output_path, include_secrets)
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """
        Get content statistics from the registry
        
        Returns:
            Dictionary with content statistics
        """
        return self.publishing_system.content_registry.get_content_statistics()
    
    def rollback_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """
        Rollback a production deployment
        
        Args:
            deployment_id: Deployment to rollback
            
        Returns:
            Dictionary with rollback result
        """
        self.logger.info(f"Rolling back deployment: {deployment_id}")
        
        try:
            result = self.publishing_system.rollback_deployment(deployment_id)
            return {
                'success': True,
                'deployment_result': result.to_dict() if hasattr(result, 'to_dict') else str(result)
            }
        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def enable_feature(self, feature: FeatureFlag) -> bool:
        """
        Enable a feature flag (runtime override)
        
        Args:
            feature: Feature flag to enable
            
        Returns:
            True if feature was enabled
        """
        # This would require extending the configuration manager
        # to support runtime feature flag changes
        self.logger.info(f"Feature flag enable requested: {feature.value}")
        return False  # Placeholder
    
    def disable_feature(self, feature: FeatureFlag) -> bool:
        """
        Disable a feature flag (runtime override)
        
        Args:
            feature: Feature flag to disable
            
        Returns:
            True if feature was disabled
        """
        # This would require extending the configuration manager
        # to support runtime feature flag changes
        self.logger.info(f"Feature flag disable requested: {feature.value}")
        return False  # Placeholder
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics
        
        Returns:
            Dictionary with performance metrics
        """
        # Get recent workflow metrics
        recent_workflows = self.get_workflow_history(10)
        
        if not recent_workflows:
            return {'message': 'No recent workflows available'}
        
        # Calculate aggregate metrics
        total_workflows = len(recent_workflows)
        successful_workflows = len([w for w in recent_workflows if w.workflow_result.status.value == "completed"])
        
        total_episodes = sum(w.metrics.total_episodes for w in recent_workflows)
        total_processing_time = sum(
            (w.metrics.total_processing_time.total_seconds() if w.metrics.total_processing_time else 0)
            for w in recent_workflows
        )
        
        avg_processing_time = total_processing_time / total_workflows if total_workflows > 0 else 0
        
        return {
            'recent_workflows': total_workflows,
            'success_rate': successful_workflows / total_workflows if total_workflows > 0 else 0,
            'total_episodes_processed': total_episodes,
            'average_processing_time_seconds': avg_processing_time,
            'average_episodes_per_workflow': total_episodes / total_workflows if total_workflows > 0 else 0,
            'last_workflow': recent_workflows[0].workflow_result.to_dict() if recent_workflows else None
        }


# Factory functions and utilities

def create_content_publishing_platform(config_dir: str = "config",
                                     environment: Optional[Environment] = None,
                                     auto_setup: bool = True) -> ContentPublishingPlatform:
    """
    Create Content Publishing Platform instance
    
    Args:
        config_dir: Configuration directory path
        environment: Target environment
        auto_setup: Whether to set up default configuration
        
    Returns:
        Configured ContentPublishingPlatform instance
    """
    return ContentPublishingPlatform(config_dir, environment, auto_setup)


def quick_publish(manifest_path: str,
                 config_dir: str = "config",
                 environment: Optional[Environment] = None,
                 progress_callback: Optional[Callable[[str, float, Dict[str, Any]], None]] = None) -> WorkflowReport:
    """
    Quick publish utility for simple workflows
    
    Args:
        manifest_path: Path to publish manifest
        config_dir: Configuration directory
        environment: Target environment
        progress_callback: Optional progress callback
        
    Returns:
        WorkflowReport with execution results
    """
    platform = create_content_publishing_platform(config_dir, environment)
    
    if progress_callback:
        platform.add_progress_callback(progress_callback)
    
    return platform.publish_content(manifest_path)


def setup_new_platform(config_dir: str = "config",
                      environment: Environment = Environment.DEVELOPMENT) -> ContentPublishingPlatform:
    """
    Set up a new Content Publishing Platform with default configuration
    
    Args:
        config_dir: Configuration directory to create
        environment: Target environment
        
    Returns:
        Configured ContentPublishingPlatform instance
    """
    # Ensure config directory exists and set up defaults
    config_path = Path(config_dir)
    if not config_path.exists():
        setup_default_config_files(config_dir)
    
    # Create platform instance
    platform = ContentPublishingPlatform(config_dir, environment, auto_setup=True)
    
    # Validate system
    validation = platform.validate_system()
    if not validation.is_valid:
        print(f"Warning: System validation found {len(validation.errors)} errors")
        for error in validation.errors:
            print(f"  - {error.message}")
    
    return platform


def get_platform_info() -> Dict[str, Any]:
    """
    Get general platform information
    
    Returns:
        Dictionary with platform information
    """
    return {
        'name': 'Content Publishing Platform',
        'version': '1.0.0',
        'description': 'Automated content deployment and web publishing system',
        'supported_environments': [env.value for env in Environment],
        'available_features': [flag.value for flag in FeatureFlag],
        'timestamp': datetime.now().isoformat()
    }