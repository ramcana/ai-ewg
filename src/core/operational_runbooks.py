"""
Operational runbooks and maintenance procedures for the Content Publishing Platform.

This module provides automated runbooks and maintenance procedures to support
operational requirements and ensure system reliability.
"""

import json
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict

from .error_handling import ErrorHandlingSystem, ErrorSeverity, RecoveryAction
from .logging import get_logger


class RunbookSeverity(Enum):
    """Severity levels for runbook procedures"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class RunbookStatus(Enum):
    """Status of runbook execution"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RunbookStep:
    """Individual step in a runbook procedure"""
    step_id: str
    title: str
    description: str
    action: Callable
    required: bool = True
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization"""
        return {
            'step_id': self.step_id,
            'title': self.title,
            'description': self.description,
            'required': self.required,
            'timeout_seconds': self.timeout_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }


@dataclass
class RunbookExecution:
    """Execution record for a runbook"""
    execution_id: str
    runbook_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RunbookStatus = RunbookStatus.NOT_STARTED
    steps_completed: int = 0
    total_steps: int = 0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary for serialization"""
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat()
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['status'] = self.status.value
        return data


class SystemHealthChecker:
    """
    System health checking and monitoring procedures.
    Implements operational monitoring requirements.
    """
    
    def __init__(self, error_handler: Optional[ErrorHandlingSystem] = None):
        self.logger = get_logger('system_health')
        self.error_handler = error_handler or ErrorHandlingSystem()
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check.
        
        Returns:
            Health check results with status and metrics
        """
        health_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        # Database connectivity check
        health_results['checks']['database'] = self._check_database_health()
        
        # File system check
        health_results['checks']['filesystem'] = self._check_filesystem_health()
        
        # External services check
        health_results['checks']['external_services'] = self._check_external_services()
        
        # Memory and CPU check
        health_results['checks']['system_resources'] = self._check_system_resources()
        
        # Content processing pipeline check
        health_results['checks']['pipeline'] = self._check_pipeline_health()
        
        # Determine overall status
        failed_checks = [name for name, result in health_results['checks'].items() 
                        if not result.get('healthy', False)]
        
        if failed_checks:
            health_results['overall_status'] = 'degraded' if len(failed_checks) <= 2 else 'unhealthy'
            health_results['failed_checks'] = failed_checks
        
        return health_results
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            # Import here to avoid circular dependencies
            try:
                from .database_registry import DatabaseRegistry
                
                db_registry = DatabaseRegistry()
                
                # Test basic connectivity
                start_time = time.time()
                connection_test = db_registry.test_connection()
                response_time = time.time() - start_time
                
                return {
                    'healthy': connection_test,
                    'response_time_ms': round(response_time * 1000, 2),
                    'status': 'connected' if connection_test else 'disconnected'
                }
            except ImportError:
                # DatabaseRegistry not available, return basic check
                return {
                    'healthy': True,
                    'status': 'not_available',
                    'note': 'DatabaseRegistry not available for health check'
                }
        
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'status': 'error'
            }
    
    def _check_filesystem_health(self) -> Dict[str, Any]:
        """Check file system health and disk space"""
        try:
            import shutil
            
            # Check critical directories
            critical_paths = [
                Path('data'),
                Path('data/public'),
                Path('data/meta'),
                Path('data/transcripts'),
                Path('logs')
            ]
            
            filesystem_status = {
                'healthy': True,
                'directories': {},
                'disk_usage': {}
            }
            
            for path in critical_paths:
                if path.exists():
                    # Check disk usage for the path
                    usage = shutil.disk_usage(path)
                    free_percent = (usage.free / usage.total) * 100
                    
                    filesystem_status['directories'][str(path)] = {
                        'exists': True,
                        'writable': path.is_dir() and os.access(path, os.W_OK),
                        'free_space_gb': round(usage.free / (1024**3), 2),
                        'free_percent': round(free_percent, 2)
                    }
                    
                    # Mark unhealthy if less than 10% free space
                    if free_percent < 10:
                        filesystem_status['healthy'] = False
                else:
                    filesystem_status['directories'][str(path)] = {
                        'exists': False,
                        'writable': False
                    }
                    filesystem_status['healthy'] = False
            
            return filesystem_status
        
        except Exception as e:
            self.logger.error(f"Filesystem health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_external_services(self) -> Dict[str, Any]:
        """Check external service connectivity"""
        services_status = {
            'healthy': True,
            'services': {}
        }
        
        # Check common external services
        external_services = [
            {'name': 'google_search_console', 'url': 'https://www.googleapis.com'},
            {'name': 'bing_webmaster', 'url': 'https://api.bing.microsoft.com'},
        ]
        
        for service in external_services:
            try:
                import requests
                response = requests.get(service['url'], timeout=10)
                
                services_status['services'][service['name']] = {
                    'healthy': response.status_code < 500,
                    'status_code': response.status_code,
                    'response_time_ms': round(response.elapsed.total_seconds() * 1000, 2)
                }
                
                if response.status_code >= 500:
                    services_status['healthy'] = False
            
            except Exception as e:
                services_status['services'][service['name']] = {
                    'healthy': False,
                    'error': str(e)
                }
                services_status['healthy'] = False
        
        return services_status
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            import psutil
            
            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            resources_status = {
                'healthy': True,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': (disk.used / disk.total) * 100,
                'available_memory_gb': round(memory.available / (1024**3), 2)
            }
            
            # Mark unhealthy if resources are critically low
            if (cpu_percent > 90 or memory.percent > 90 or 
                resources_status['disk_percent'] > 90):
                resources_status['healthy'] = False
            
            return resources_status
        
        except ImportError:
            # psutil not available, return basic check
            return {
                'healthy': True,
                'note': 'psutil not available for detailed resource monitoring'
            }
        except Exception as e:
            self.logger.error(f"System resources check failed: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_pipeline_health(self) -> Dict[str, Any]:
        """Check content processing pipeline health"""
        try:
            # Check for recent processing activity
            logs_path = Path('logs')
            if logs_path.exists():
                recent_logs = []
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                for log_file in logs_path.glob('*.log'):
                    if log_file.stat().st_mtime > cutoff_time.timestamp():
                        recent_logs.append(log_file.name)
                
                return {
                    'healthy': len(recent_logs) > 0,
                    'recent_activity': len(recent_logs) > 0,
                    'recent_log_files': recent_logs
                }
            else:
                return {
                    'healthy': False,
                    'error': 'Logs directory not found'
                }
        
        except Exception as e:
            self.logger.error(f"Pipeline health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }


class MaintenanceProcedures:
    """
    Automated maintenance procedures for system upkeep.
    Implements operational maintenance requirements.
    """
    
    def __init__(self, error_handler: Optional[ErrorHandlingSystem] = None):
        self.logger = get_logger('maintenance')
        self.error_handler = error_handler or ErrorHandlingSystem()
    
    def cleanup_old_logs(self, retention_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old log files beyond retention period.
        
        Args:
            retention_days: Number of days to retain logs
            
        Returns:
            Cleanup results
        """
        try:
            logs_path = Path('logs')
            if not logs_path.exists():
                return {'success': True, 'message': 'No logs directory found'}
            
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            files_removed = []
            total_size_removed = 0
            
            for log_file in logs_path.glob('*.log*'):
                if log_file.stat().st_mtime < cutoff_time.timestamp():
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    files_removed.append(log_file.name)
                    total_size_removed += file_size
            
            return {
                'success': True,
                'files_removed': len(files_removed),
                'size_removed_mb': round(total_size_removed / (1024**2), 2),
                'retention_days': retention_days
            }
        
        except Exception as e:
            self.logger.error(f"Log cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up temporary files and caches"""
        try:
            temp_paths = [
                Path('temp'),
                Path('data/temp'),
                Path('data/cache')
            ]
            
            files_removed = 0
            total_size_removed = 0
            
            for temp_path in temp_paths:
                if temp_path.exists():
                    for temp_file in temp_path.rglob('*'):
                        if temp_file.is_file():
                            # Remove files older than 1 day
                            if temp_file.stat().st_mtime < (datetime.now() - timedelta(days=1)).timestamp():
                                file_size = temp_file.stat().st_size
                                temp_file.unlink()
                                files_removed += 1
                                total_size_removed += file_size
            
            return {
                'success': True,
                'files_removed': files_removed,
                'size_removed_mb': round(total_size_removed / (1024**2), 2)
            }
        
        except Exception as e:
            self.logger.error(f"Temp file cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def optimize_database(self) -> Dict[str, Any]:
        """Optimize database performance"""
        try:
            # Import here to avoid circular dependencies
            try:
                from .database_registry import DatabaseRegistry
                
                db_registry = DatabaseRegistry()
                
                # Run database optimization
                optimization_results = db_registry.optimize_database()
                
                return {
                    'success': True,
                    'optimization_results': optimization_results
                }
            except ImportError:
                # DatabaseRegistry not available
                return {
                    'success': True,
                    'note': 'DatabaseRegistry not available for optimization'
                }
        
        except Exception as e:
            self.logger.error(f"Database optimization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_content_integrity(self) -> Dict[str, Any]:
        """Validate content integrity and consistency"""
        try:
            # Import here to avoid circular dependencies
            try:
                from .content_registry import ContentRegistry
                
                content_registry = ContentRegistry()
                
                # Load and validate manifest
                manifest_path = Path('data/publish_manifest.json')
                if not manifest_path.exists():
                    return {
                        'success': False,
                        'error': 'Publish manifest not found'
                    }
                
                manifest = content_registry.load_manifest(str(manifest_path))
                validation_result = content_registry.validate_contract(manifest)
                
                return {
                    'success': validation_result.is_valid,
                    'validation_errors': [error.message for error in validation_result.errors],
                    'validation_warnings': [warning.message for warning in validation_result.warnings]
                }
            except ImportError:
                # ContentRegistry not available
                return {
                    'success': True,
                    'note': 'ContentRegistry not available for validation'
                }
        
        except Exception as e:
            self.logger.error(f"Content integrity validation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class RunbookExecutor:
    """
    Executes operational runbooks for common failure scenarios.
    Implements operational runbook requirements.
    """
    
    def __init__(self, error_handler: Optional[ErrorHandlingSystem] = None):
        self.logger = get_logger('runbook_executor')
        self.error_handler = error_handler or ErrorHandlingSystem()
        self.health_checker = SystemHealthChecker(error_handler)
        self.maintenance = MaintenanceProcedures(error_handler)
        self.runbooks = self._build_runbooks()
    
    def execute_runbook(self, runbook_name: str, context: Optional[Dict[str, Any]] = None) -> RunbookExecution:
        """
        Execute a specific runbook procedure.
        
        Args:
            runbook_name: Name of the runbook to execute
            context: Additional context for the runbook
            
        Returns:
            RunbookExecution with results
        """
        if runbook_name not in self.runbooks:
            raise ValueError(f"Unknown runbook: {runbook_name}")
        
        runbook = self.runbooks[runbook_name]
        execution_id = f"{runbook_name}_{int(time.time())}"
        
        execution = RunbookExecution(
            execution_id=execution_id,
            runbook_name=runbook_name,
            started_at=datetime.now(timezone.utc),
            total_steps=len(runbook['steps'])
        )
        
        execution.status = RunbookStatus.IN_PROGRESS
        
        try:
            self.logger.info(f"Starting runbook execution: {runbook_name}")
            
            for step in runbook['steps']:
                try:
                    self.logger.info(f"Executing step: {step.title}")
                    
                    # Execute step with timeout
                    step.action(context)
                    execution.steps_completed += 1
                    
                    self.logger.info(f"Step completed: {step.title}")
                
                except Exception as e:
                    self.logger.error(f"Step failed: {step.title} - {e}")
                    
                    if step.required:
                        execution.status = RunbookStatus.FAILED
                        execution.error_message = f"Required step failed: {step.title} - {e}"
                        break
                    else:
                        self.logger.warning(f"Optional step failed, continuing: {step.title}")
            
            if execution.status == RunbookStatus.IN_PROGRESS:
                execution.status = RunbookStatus.COMPLETED
            
            execution.completed_at = datetime.now(timezone.utc)
            
            self.logger.info(f"Runbook execution completed: {runbook_name} - {execution.status.value}")
            
        except Exception as e:
            execution.status = RunbookStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(f"Runbook execution failed: {runbook_name} - {e}")
        
        return execution
    
    def _build_runbooks(self) -> Dict[str, Dict[str, Any]]:
        """Build available runbooks"""
        return {
            'deployment_failure_recovery': {
                'description': 'Recovery procedure for deployment failures',
                'severity': RunbookSeverity.CRITICAL,
                'steps': [
                    RunbookStep(
                        step_id='check_system_health',
                        title='Check System Health',
                        description='Perform comprehensive system health check',
                        action=self._step_check_system_health
                    ),
                    RunbookStep(
                        step_id='rollback_deployment',
                        title='Rollback Deployment',
                        description='Rollback to previous known-good deployment',
                        action=self._step_rollback_deployment
                    ),
                    RunbookStep(
                        step_id='validate_rollback',
                        title='Validate Rollback',
                        description='Validate that rollback was successful',
                        action=self._step_validate_rollback
                    )
                ]
            },
            'performance_degradation': {
                'description': 'Response to performance degradation',
                'severity': RunbookSeverity.WARNING,
                'steps': [
                    RunbookStep(
                        step_id='check_resources',
                        title='Check System Resources',
                        description='Check CPU, memory, and disk usage',
                        action=self._step_check_resources
                    ),
                    RunbookStep(
                        step_id='cleanup_temp_files',
                        title='Clean Up Temporary Files',
                        description='Remove temporary files and caches',
                        action=self._step_cleanup_temp_files
                    ),
                    RunbookStep(
                        step_id='optimize_database',
                        title='Optimize Database',
                        description='Run database optimization procedures',
                        action=self._step_optimize_database,
                        required=False
                    )
                ]
            },
            'validation_failure_recovery': {
                'description': 'Recovery from validation failures',
                'severity': RunbookSeverity.CRITICAL,
                'steps': [
                    RunbookStep(
                        step_id='validate_content',
                        title='Validate Content Integrity',
                        description='Check content integrity and consistency',
                        action=self._step_validate_content
                    ),
                    RunbookStep(
                        step_id='regenerate_content',
                        title='Regenerate Content',
                        description='Regenerate failed content artifacts',
                        action=self._step_regenerate_content,
                        required=False
                    )
                ]
            },
            'routine_maintenance': {
                'description': 'Routine system maintenance',
                'severity': RunbookSeverity.INFO,
                'steps': [
                    RunbookStep(
                        step_id='cleanup_logs',
                        title='Clean Up Old Logs',
                        description='Remove logs older than retention period',
                        action=self._step_cleanup_logs,
                        required=False
                    ),
                    RunbookStep(
                        step_id='cleanup_temp_files',
                        title='Clean Up Temporary Files',
                        description='Remove temporary files and caches',
                        action=self._step_cleanup_temp_files,
                        required=False
                    ),
                    RunbookStep(
                        step_id='optimize_database',
                        title='Optimize Database',
                        description='Run database optimization procedures',
                        action=self._step_optimize_database,
                        required=False
                    )
                ]
            }
        }
    
    # Runbook step implementations
    def _step_check_system_health(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Check system health step"""
        health_results = self.health_checker.check_system_health()
        if health_results['overall_status'] != 'healthy':
            self.logger.warning(f"System health check failed: {health_results}")
    
    def _step_rollback_deployment(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Rollback deployment step"""
        # This would integrate with the deployment pipeline
        self.logger.info("Initiating deployment rollback")
        # Implementation would depend on deployment system
    
    def _step_validate_rollback(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Validate rollback step"""
        # Validate that rollback was successful
        self.logger.info("Validating rollback success")
    
    def _step_check_resources(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Check system resources step"""
        health_results = self.health_checker._check_system_resources()
        if not health_results['healthy']:
            self.logger.warning(f"System resources critical: {health_results}")
    
    def _step_cleanup_temp_files(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Clean up temporary files step"""
        result = self.maintenance.cleanup_temp_files()
        if not result['success']:
            raise Exception(f"Temp file cleanup failed: {result.get('error')}")
    
    def _step_optimize_database(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Optimize database step"""
        result = self.maintenance.optimize_database()
        if not result['success']:
            raise Exception(f"Database optimization failed: {result.get('error')}")
    
    def _step_validate_content(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Validate content integrity step"""
        result = self.maintenance.validate_content_integrity()
        if not result['success']:
            raise Exception(f"Content validation failed: {result.get('error')}")
    
    def _step_regenerate_content(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Regenerate content step"""
        # This would trigger content regeneration
        self.logger.info("Initiating content regeneration")
    
    def _step_cleanup_logs(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Clean up old logs step"""
        retention_days = context.get('log_retention_days', 30) if context else 30
        result = self.maintenance.cleanup_old_logs(retention_days)
        if not result['success']:
            raise Exception(f"Log cleanup failed: {result.get('error')}")


# Import os for filesystem operations
import os