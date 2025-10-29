"""
Clip Generation Resource Management Integration

Integrates clip generation with existing pipeline resource management,
database retry mechanisms, and reliability features.
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, TypeVar
from contextlib import contextmanager
from dataclasses import dataclass

from .resource_manager import (
    ResourceMonitor, ResourceLimits, MemoryManager, 
    default_concurrency_controller, default_memory_manager
)
from .database import DatabaseConnection
from .exceptions import (
    ClipGenerationError, EmbeddingError, ExportError, 
    DatabaseError, TransientError
)
from .logging import get_logger

logger = get_logger('clip_generation.resource_manager')

T = TypeVar('T')


@dataclass
class ClipResourceLimits:
    """Resource limits specific to clip generation"""
    max_embedding_memory_mb: float = 16000.0  # 16GB for embedding models (high-end system)
    max_ffmpeg_concurrent: int = 2  # Limit concurrent FFmpeg processes
    max_llm_concurrent: int = 1  # Limit concurrent LLM requests
    embedding_batch_size: int = 32  # Batch size for embedding generation
    ffmpeg_timeout_seconds: int = 300  # 5 minutes per clip
    llm_timeout_seconds: int = 30  # 30 seconds per LLM request


class ClipResourceManager:
    """
    Resource manager for clip generation operations
    
    Integrates with existing pipeline resource management and provides
    clip-specific resource controls and monitoring.
    """
    
    def __init__(self, 
                 clip_limits: Optional[ClipResourceLimits] = None,
                 use_pipeline_limits: bool = True):
        """
        Initialize clip resource manager
        
        Args:
            clip_limits: Clip-specific resource limits
            use_pipeline_limits: Whether to respect pipeline-wide resource limits
        """
        self.clip_limits = clip_limits or ClipResourceLimits()
        self.use_pipeline_limits = use_pipeline_limits
        
        # Get pipeline resource monitor if available
        self.pipeline_monitor = None
        if use_pipeline_limits and default_concurrency_controller._running:
            self.pipeline_monitor = default_concurrency_controller.resource_monitor
        
        # Semaphores for concurrent operation limits
        self._ffmpeg_semaphore = threading.Semaphore(self.clip_limits.max_ffmpeg_concurrent)
        self._llm_semaphore = threading.Semaphore(self.clip_limits.max_llm_concurrent)
        
        # Memory manager
        self.memory_manager = default_memory_manager
        
        logger.info("ClipResourceManager initialized",
                   clip_limits=self.clip_limits.__dict__,
                   use_pipeline_limits=use_pipeline_limits)
    
    def check_resource_availability(self) -> Dict[str, bool]:
        """
        Check if resources are available for clip generation
        
        Returns:
            Dictionary indicating availability of different resources
        """
        availability = {
            'memory': True,
            'cpu': True,
            'ffmpeg_slots': True,
            'llm_slots': True
        }
        
        try:
            # Check pipeline-wide resource limits
            if self.pipeline_monitor:
                if not self.pipeline_monitor.should_allow_new_task():
                    availability['memory'] = False
                    availability['cpu'] = False
                    logger.debug("Pipeline resource limits exceeded")
            
            # Check clip-specific limits
            current_usage = self.memory_manager.check_memory_usage()
            current_rss_mb = current_usage.get('rss_mb', 0)
            if current_rss_mb > self.clip_limits.max_embedding_memory_mb:
                availability['memory'] = False
                logger.warning("Embedding memory limit exceeded",
                           current_mb=current_rss_mb,
                           limit_mb=self.clip_limits.max_embedding_memory_mb)
            else:
                logger.debug("Memory check passed",
                           current_mb=current_rss_mb,
                           limit_mb=self.clip_limits.max_embedding_memory_mb,
                           usage_percent=round((current_rss_mb / self.clip_limits.max_embedding_memory_mb) * 100, 1))
            
            # Check semaphore availability (non-blocking)
            availability['ffmpeg_slots'] = self._ffmpeg_semaphore._value > 0
            availability['llm_slots'] = self._llm_semaphore._value > 0
            
        except Exception as e:
            logger.error("Error checking resource availability", error=str(e))
            # Default to conservative approach - assume resources not available
            availability = {k: False for k in availability}
        
        return availability
    
    @contextmanager
    def ffmpeg_resource_context(self):
        """
        Context manager for FFmpeg operations with resource management
        
        Acquires FFmpeg slot and manages memory during video processing.
        """
        acquired = False
        try:
            # Check resource availability first
            availability = self.check_resource_availability()
            if not availability['memory'] or not availability['cpu']:
                raise ExportError("Insufficient system resources for FFmpeg operation",
                                export_stage="resource_check")
            
            # Acquire FFmpeg semaphore
            logger.debug("Acquiring FFmpeg resource slot")
            self._ffmpeg_semaphore.acquire(timeout=60)  # 1 minute timeout
            acquired = True
            
            # Trigger memory cleanup if needed
            if self.memory_manager.should_cleanup():
                self.memory_manager.cleanup()
            
            logger.debug("FFmpeg resource acquired")
            yield
            
        except Exception as e:
            if isinstance(e, ExportError):
                raise
            else:
                raise ExportError(f"FFmpeg resource management failed: {str(e)}",
                                export_stage="resource_management")
        finally:
            if acquired:
                self._ffmpeg_semaphore.release()
                logger.debug("FFmpeg resource released")
    
    @contextmanager
    def llm_resource_context(self):
        """
        Context manager for LLM operations with resource management
        
        Acquires LLM slot and manages concurrent LLM requests.
        """
        acquired = False
        try:
            # Check resource availability first
            availability = self.check_resource_availability()
            if not availability['memory'] or not availability['cpu']:
                logger.warning("System resources low, proceeding with LLM operation but may fallback")
            
            # Acquire LLM semaphore
            logger.debug("Acquiring LLM resource slot")
            self._llm_semaphore.acquire(timeout=30)  # 30 second timeout
            acquired = True
            
            logger.debug("LLM resource acquired")
            yield
            
        except Exception as e:
            # Don't raise for LLM failures - allow fallback to keyword extraction
            logger.warning("LLM resource management failed, fallback will be used", error=str(e))
            yield  # Still yield to allow fallback mechanisms to work
        finally:
            if acquired:
                self._llm_semaphore.release()
                logger.debug("LLM resource released")
    
    @contextmanager
    def embedding_resource_context(self):
        """
        Context manager for embedding operations with resource management
        
        Manages memory during embedding generation and provides cleanup.
        """
        try:
            # Check memory availability
            availability = self.check_resource_availability()
            if not availability['memory']:
                # Skip aggressive cleanup before embedding - model needs to stay in memory
                # cleanup_result = self.memory_manager.cleanup()
                # logger.info("Memory cleanup performed before embedding generation",
                #           freed_mb=cleanup_result.get('memory_freed_mb', 0))
                
                # Log warning but proceed - embedding model is already loaded
                logger.warning("Low memory detected but proceeding with embedding generation",
                             reason="Cleanup would clear the loaded embedding model")
                
                # Check again after cleanup
                # availability = self.check_resource_availability()
                # if not availability['memory']:
                #     raise EmbeddingError("Insufficient memory for embedding generation",
                #                        model_name="resource_check")
            
            logger.debug("Embedding resource context acquired")
            yield
            
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Embedding resource management failed: {str(e)}")
        finally:
            # Cleanup after embedding generation if needed
            if self.memory_manager.should_cleanup():
                self.memory_manager.cleanup()
            logger.debug("Embedding resource context released")


class ClipDatabaseRetryManager:
    """
    Database retry manager for clip generation operations
    
    Integrates with existing database retry mechanisms and provides
    clip-specific database operation handling.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        Initialize database retry manager
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        logger.info("ClipDatabaseRetryManager initialized",
                   max_retries=max_retries,
                   base_delay=base_delay)
    
    def execute_with_retry(self, operation: Callable[[], T], 
                          operation_name: str = "database_operation") -> T:
        """
        Execute database operation with retry logic
        
        Args:
            operation: Database operation to execute
            operation_name: Name of operation for logging
            
        Returns:
            Result of the operation
            
        Raises:
            DatabaseError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("Executing database operation",
                           operation=operation_name,
                           attempt=attempt + 1,
                           max_attempts=self.max_retries + 1)
                
                result = operation()
                
                if attempt > 0:
                    logger.info("Database operation succeeded after retry",
                              operation=operation_name,
                              attempt=attempt + 1)
                
                return result
                
            except DatabaseError as e:
                last_error = e
                
                # Check if this is a transient error that should be retried
                if self._should_retry_error(e) and attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning("Database operation failed, retrying",
                                 operation=operation_name,
                                 attempt=attempt + 1,
                                 error=str(e),
                                 retry_delay=delay)
                    time.sleep(delay)
                    continue
                else:
                    # Don't retry or max retries reached
                    break
                    
            except Exception as e:
                # Wrap non-database errors
                error_msg = f"Database operation {operation_name} failed: {str(e)}"
                last_error = DatabaseError(error_msg)
                
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning("Database operation failed with unexpected error, retrying",
                                 operation=operation_name,
                                 attempt=attempt + 1,
                                 error=str(e),
                                 retry_delay=delay)
                    time.sleep(delay)
                    continue
                else:
                    break
        
        # All attempts failed
        if last_error:
            logger.error("Database operation failed after all retry attempts",
                       operation=operation_name,
                       max_attempts=self.max_retries + 1,
                       final_error=str(last_error))
            raise last_error
        else:
            raise DatabaseError(f"Database operation {operation_name} failed after {self.max_retries + 1} attempts")
    
    def _should_retry_error(self, error: DatabaseError) -> bool:
        """
        Determine if a database error should be retried
        
        Args:
            error: Database error to check
            
        Returns:
            True if error should be retried
        """
        error_message = str(error).lower()
        
        # Retry on common transient database errors
        transient_indicators = [
            'database is locked',
            'database disk image is malformed',
            'disk i/o error',
            'temporary failure',
            'connection lost',
            'timeout',
            'busy'
        ]
        
        return any(indicator in error_message for indicator in transient_indicators)
    
    @contextmanager
    def database_transaction_context(self, db_connection: DatabaseConnection):
        """
        Context manager for database transactions with retry logic
        
        Args:
            db_connection: Database connection to use
        """
        def transaction_operation():
            return db_connection.transaction()
        
        try:
            with self.execute_with_retry(transaction_operation, "transaction_begin"):
                yield
        except Exception as e:
            logger.error("Database transaction failed", error=str(e))
            raise


# Global instances for clip generation
default_clip_resource_manager = ClipResourceManager()
default_clip_db_retry_manager = ClipDatabaseRetryManager()


# Utility functions and decorators
def with_clip_resource_management(resource_type: str = "general"):
    """
    Decorator to add resource management to clip generation functions
    
    Args:
        resource_type: Type of resource management ('ffmpeg', 'llm', 'embedding', 'general')
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if resource_type == "ffmpeg":
                with default_clip_resource_manager.ffmpeg_resource_context():
                    return func(*args, **kwargs)
            elif resource_type == "llm":
                with default_clip_resource_manager.llm_resource_context():
                    return func(*args, **kwargs)
            elif resource_type == "embedding":
                with default_clip_resource_manager.embedding_resource_context():
                    return func(*args, **kwargs)
            else:
                # General resource check
                availability = default_clip_resource_manager.check_resource_availability()
                if not all(availability.values()):
                    logger.warning("Some resources not available, proceeding with caution",
                                 availability=availability)
                return func(*args, **kwargs)
        return wrapper
    return decorator


def with_database_retry(operation_name: str = "clip_database_operation"):
    """
    Decorator to add database retry logic to clip generation functions
    
    Args:
        operation_name: Name of the database operation for logging
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return default_clip_db_retry_manager.execute_with_retry(
                lambda: func(*args, **kwargs),
                operation_name
            )
        return wrapper
    return decorator


@contextmanager
def clip_generation_context():
    """
    Context manager for complete clip generation resource management
    
    Provides comprehensive resource management for clip generation operations
    including memory management, resource monitoring, and cleanup.
    """
    try:
        # Check initial resource availability
        availability = default_clip_resource_manager.check_resource_availability()
        logger.info("Starting clip generation with resource context",
                   availability=availability)
        
        # Perform initial cleanup if needed
        if default_memory_manager.should_cleanup():
            cleanup_result = default_memory_manager.cleanup()
            logger.info("Initial memory cleanup performed",
                       freed_mb=cleanup_result.get('memory_freed_mb', 0))
        
        yield default_clip_resource_manager
        
    except Exception as e:
        logger.error("Error in clip generation context", error=str(e))
        raise
    finally:
        # Final cleanup
        if default_memory_manager.should_cleanup():
            cleanup_result = default_memory_manager.cleanup()
            logger.info("Final memory cleanup performed",
                       freed_mb=cleanup_result.get('memory_freed_mb', 0))
        
        logger.info("Clip generation context completed")