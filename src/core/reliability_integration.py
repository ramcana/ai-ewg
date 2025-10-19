"""
Integration module for reliability features

Provides a unified interface for retry logic, circuit breakers, monitoring,
and resource management across the Video Processing Pipeline.
"""

from typing import Dict, Any, Optional, Callable, TypeVar
from contextlib import contextmanager
from dataclasses import dataclass

from .reliability import (
    ReliabilityManager, RetryConfig, CircuitBreakerConfig,
    reliability_manager
)
from .resource_manager import (
    ConcurrencyController, ResourceLimits, Priority,
    GracefulShutdownHandler,
    default_concurrency_controller, default_memory_manager,
    default_shutdown_handler
)
from .logging import (
    get_logger, system_monitor, processing_tracker, 
    audit_trail, metrics_exporter
)
from .models import ProcessingStage
from .exceptions import PipelineError, ProcessingError

logger = get_logger('pipeline.reliability_integration')

T = TypeVar('T')


@dataclass
class PipelineReliabilityConfig:
    """Unified configuration for pipeline reliability features"""
    # Retry configuration
    max_retry_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    
    # Circuit breaker configuration
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 60.0
    circuit_success_threshold: int = 3
    
    # Resource limits
    max_concurrent_episodes: int = 2
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 90.0
    
    # Monitoring
    enable_system_monitoring: bool = True
    monitoring_interval: int = 60
    enable_audit_trail: bool = True
    
    # Graceful shutdown
    shutdown_timeout: float = 60.0


class PipelineReliabilityManager:
    """Unified manager for all reliability features"""
    
    def __init__(self, config: Optional[PipelineReliabilityConfig] = None):
        self.config = config or PipelineReliabilityConfig()
        
        # Initialize reliability components
        self.retry_config = RetryConfig(
            max_attempts=self.config.max_retry_attempts,
            base_delay=self.config.retry_base_delay,
            max_delay=self.config.retry_max_delay
        )
        
        self.circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
            success_threshold=self.config.circuit_success_threshold
        )
        
        self.resource_limits = ResourceLimits(
            max_concurrent_episodes=self.config.max_concurrent_episodes,
            max_memory_percent=self.config.max_memory_percent,
            max_cpu_percent=self.config.max_cpu_percent
        )
        
        # Create instances with configured limits
        self.reliability_manager = reliability_manager
        self.concurrency_controller = ConcurrencyController(
            resource_limits=self.resource_limits,
            max_workers=self.config.max_concurrent_episodes
        )
        self.memory_manager = default_memory_manager
        self.shutdown_handler = GracefulShutdownHandler(self.concurrency_controller)
        
        self._initialized = False
    
    def initialize(self):
        """Initialize all reliability components"""
        if self._initialized:
            return
        
        logger.info("Initializing pipeline reliability features")
        
        # Start system monitoring
        if self.config.enable_system_monitoring:
            system_monitor.start_monitoring()
            logger.info("System monitoring started")
        
        # Start concurrency controller
        self.concurrency_controller.start()
        logger.info("Concurrency controller started")
        
        # Register shutdown callbacks
        self.shutdown_handler.add_shutdown_callback(self._cleanup_on_shutdown)
        
        self._initialized = True
        logger.info("Pipeline reliability features initialized")
    
    def shutdown(self):
        """Shutdown all reliability components"""
        if not self._initialized:
            return
        
        logger.info("Shutting down pipeline reliability features")
        
        # Stop monitoring
        system_monitor.stop_monitoring()
        
        # Stop concurrency controller
        self.concurrency_controller.stop(timeout=self.config.shutdown_timeout)
        
        self._initialized = False
        logger.info("Pipeline reliability features shut down")
    
    def _cleanup_on_shutdown(self):
        """Cleanup callback for graceful shutdown"""
        logger.info("Performing reliability cleanup on shutdown")
        
        # Export final metrics
        try:
            metrics = metrics_exporter.export_dashboard_metrics()
            logger.info("Final metrics exported", metrics_count=len(metrics))
        except Exception as e:
            logger.error("Failed to export final metrics", exception=e)
        
        # Export audit trail
        try:
            from pathlib import Path
            audit_path = Path("logs") / f"audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            audit_trail.export_audit_trail(audit_path, hours=24)
            logger.info("Audit trail exported", path=str(audit_path))
        except Exception as e:
            logger.error("Failed to export audit trail", exception=e)
    
    def execute_with_full_protection(self,
                                   service_name: str,
                                   episode_id: str,
                                   stage: ProcessingStage,
                                   func: Callable[..., T],
                                   *args,
                                   priority: Priority = Priority.NORMAL,
                                   timeout: Optional[float] = None,
                                   **kwargs) -> T:
        """Execute function with full reliability protection"""
        if not self._initialized:
            self.initialize()
        
        # Check resource availability
        if not self.concurrency_controller.resource_monitor.should_allow_new_task():
            raise ProcessingError(
                f"Cannot execute {service_name} due to resource constraints",
                stage=stage.value,
                episode_id=episode_id
            )
        
        # Execute with reliability features
        def protected_execution():
            with logger.processing_stage(episode_id, stage.value):
                return self.reliability_manager.execute_with_reliability(
                    service_name=service_name,
                    func=func,
                    *args,
                    retry_config=self.retry_config,
                    circuit_config=self.circuit_config,
                    **kwargs
                )
        
        # Submit to concurrency controller
        success = self.concurrency_controller.submit_task(
            episode_id=episode_id,
            stage=stage,
            func=protected_execution,
            priority=priority,
            timeout=timeout
        )
        
        if not success:
            raise ProcessingError(
                f"Failed to submit {service_name} task to queue",
                stage=stage.value,
                episode_id=episode_id
            )
        
        # For now, return success indicator
        # In a real implementation, you'd want to return a Future or similar
        return True
    
    @contextmanager
    def reliability_context(self, episode_id: str, stage: ProcessingStage):
        """Context manager for reliability-protected operations"""
        if not self._initialized:
            self.initialize()
        
        # Memory management
        with self.memory_manager.memory_context():
            # Processing stage tracking
            with logger.processing_stage(episode_id, stage.value):
                try:
                    yield self
                except Exception as e:
                    # Log the error with full context
                    logger.error(
                        f"Error in reliability context for {episode_id}",
                        episode_id=episode_id,
                        stage=stage.value,
                        exception=e
                    )
                    raise
    
    def log_processing_decision(self, 
                              episode_id: str,
                              stage: str,
                              decision: str,
                              reasoning: str,
                              metadata: Optional[Dict[str, Any]] = None):
        """Log a processing decision with audit trail"""
        if self.config.enable_audit_trail:
            logger.log_decision(episode_id, stage, decision, reasoning, metadata)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        health_data = {
            'timestamp': datetime.now().isoformat(),
            'initialized': self._initialized
        }
        
        if self._initialized:
            # Reliability manager health
            health_data['reliability'] = self.reliability_manager.get_system_health()
            
            # Concurrency controller status
            health_data['concurrency'] = self.concurrency_controller.get_status()
            
            # Memory status
            health_data['memory'] = self.memory_manager.check_memory_usage()
            
            # Processing statistics
            health_data['processing'] = {
                'active_stages': len(processing_tracker.get_active_stages()),
                'stage_statistics': processing_tracker.get_stage_statistics()
            }
        
        return health_data
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Export comprehensive metrics"""
        return metrics_exporter.export_prometheus_metrics() if format_type == "prometheus" else logger.export_metrics()
    
    def force_cleanup(self) -> Dict[str, Any]:
        """Force system cleanup and return results"""
        cleanup_results = {}
        
        # Memory cleanup
        cleanup_results['memory'] = self.memory_manager.cleanup()
        
        # Resource cleanup
        cleanup_results['resources'] = self.concurrency_controller.resource_monitor.trigger_cleanup()
        
        logger.info("Forced cleanup completed", results=cleanup_results)
        return cleanup_results


# Global pipeline reliability manager
pipeline_reliability = PipelineReliabilityManager()


# Convenience functions
def initialize_reliability(config: Optional[PipelineReliabilityConfig] = None):
    """Initialize pipeline reliability features"""
    global pipeline_reliability
    if config:
        pipeline_reliability = PipelineReliabilityManager(config)
    pipeline_reliability.initialize()


def shutdown_reliability():
    """Shutdown pipeline reliability features"""
    pipeline_reliability.shutdown()


def execute_with_reliability(service_name: str,
                           episode_id: str,
                           stage: ProcessingStage,
                           func: Callable[..., T],
                           *args,
                           **kwargs) -> T:
    """Execute function with full reliability protection"""
    return pipeline_reliability.execute_with_full_protection(
        service_name, episode_id, stage, func, *args, **kwargs
    )


@contextmanager
def reliability_context(episode_id: str, stage: ProcessingStage):
    """Context manager for reliability-protected operations"""
    with pipeline_reliability.reliability_context(episode_id, stage) as manager:
        yield manager


def get_pipeline_health() -> Dict[str, Any]:
    """Get comprehensive pipeline health status"""
    return pipeline_reliability.get_system_health()


def export_pipeline_metrics(format_type: str = "json") -> str:
    """Export comprehensive pipeline metrics"""
    return pipeline_reliability.export_metrics(format_type)


# Import datetime for the cleanup callback
from datetime import datetime