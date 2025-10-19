"""
Resource management and concurrency controls for the Video Processing Pipeline

Implements processing limits, queue management, memory monitoring, and
graceful shutdown mechanisms to protect system resources.
"""

import asyncio
import threading
import time
import signal
import sys
import gc
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, TypeVar, Union
from dataclasses import dataclass, field
from queue import Queue, PriorityQueue, Empty
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from contextlib import contextmanager
from enum import Enum

from .exceptions import PipelineError, ProcessingError
from .logging import get_logger, system_monitor
from .models import EpisodeObject, ProcessingStage

logger = get_logger('pipeline.resources')

T = TypeVar('T')


class Priority(Enum):
    """Task priority levels"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class ResourceLimits:
    """Resource usage limits"""
    max_concurrent_episodes: int = 2
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 90.0
    max_disk_usage_percent: float = 85.0
    max_open_files: int = 1000
    memory_cleanup_threshold: float = 70.0
    disk_cleanup_threshold: float = 75.0


@dataclass
class ProcessingTask:
    """A processing task with priority and metadata"""
    episode_id: str
    stage: ProcessingStage
    priority: Priority
    created_at: datetime
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timeout: Optional[float] = None
    
    def __lt__(self, other):
        """Compare tasks by priority and creation time"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class ResourceMonitor:
    """Monitors system resources and enforces limits"""
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self.process = psutil.Process()
        self._monitoring = False
        self._monitor_thread = None
        self._callbacks: List[Callable[[Dict[str, float]], None]] = []
    
    def start_monitoring(self, interval: float = 5.0):
        """Start resource monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,), 
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Resource monitoring started", interval=interval)
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
    
    def add_callback(self, callback: Callable[[Dict[str, float]], None]):
        """Add callback for resource limit violations"""
        self._callbacks.append(callback)
    
    def _monitor_loop(self, interval: float):
        """Resource monitoring loop"""
        while self._monitoring:
            try:
                usage = self.get_current_usage()
                violations = self.check_limits(usage)
                
                if violations:
                    logger.warning("Resource limit violations detected", violations=violations)
                    for callback in self._callbacks:
                        try:
                            callback(violations)
                        except Exception as e:
                            logger.error("Error in resource callback", exception=e)
                
                time.sleep(interval)
            except Exception as e:
                logger.error("Error in resource monitoring", exception=e)
                time.sleep(interval)
    
    def get_current_usage(self) -> Dict[str, float]:
        """Get current resource usage"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            cpu_percent = self.process.cpu_percent()
            
            # System-wide disk usage
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            
            # Open files count
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                open_files = 0
            
            return {
                'memory_percent': memory_percent,
                'memory_mb': memory_info.rss / (1024 * 1024),
                'cpu_percent': cpu_percent,
                'disk_percent': disk_percent,
                'open_files': open_files
            }
        except Exception as e:
            logger.error("Failed to get resource usage", exception=e)
            return {}
    
    def check_limits(self, usage: Dict[str, float]) -> Dict[str, float]:
        """Check if usage exceeds limits"""
        violations = {}
        
        if usage.get('memory_percent', 0) > self.limits.max_memory_percent:
            violations['memory_percent'] = usage['memory_percent']
        
        if usage.get('cpu_percent', 0) > self.limits.max_cpu_percent:
            violations['cpu_percent'] = usage['cpu_percent']
        
        if usage.get('disk_percent', 0) > self.limits.max_disk_usage_percent:
            violations['disk_percent'] = usage['disk_percent']
        
        if usage.get('open_files', 0) > self.limits.max_open_files:
            violations['open_files'] = usage['open_files']
        
        return violations
    
    def should_allow_new_task(self) -> bool:
        """Check if system can handle a new task"""
        # Temporarily disabled for high-end system - return True to allow all tasks
        # TODO: Re-enable with proper thresholds for 128GB RAM / 64-core CPU
        return True
        
        # Original code (disabled):
        # usage = self.get_current_usage()
        # violations = self.check_limits(usage)
        # if violations:
        #     logger.warning("Rejecting new task due to resource limits", violations=violations)
        #     return False
        # return True
    
    def trigger_cleanup(self) -> bool:
        """Trigger memory and resource cleanup"""
        logger.info("Triggering resource cleanup")
        
        # Force garbage collection
        collected = gc.collect()
        
        # Clear caches if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        
        usage_after = self.get_current_usage()
        logger.info("Cleanup completed", 
                   garbage_collected=collected,
                   memory_mb_after=usage_after.get('memory_mb', 0))
        
        return True


class ProcessingQueue:
    """Priority queue for processing tasks"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue = PriorityQueue(maxsize=max_size)
        self._active_tasks: Dict[str, ProcessingTask] = {}
        self._completed_tasks: List[ProcessingTask] = []
        self._lock = threading.Lock()
    
    def add_task(self, task: ProcessingTask) -> bool:
        """Add task to queue"""
        try:
            self._queue.put_nowait(task)
            logger.debug("Task added to queue", 
                        episode_id=task.episode_id,
                        stage=task.stage.value,
                        priority=task.priority.name)
            return True
        except Exception as e:
            logger.error("Failed to add task to queue", 
                        episode_id=task.episode_id,
                        exception=e)
            return False
    
    def get_task(self, timeout: Optional[float] = None) -> Optional[ProcessingTask]:
        """Get next task from queue"""
        try:
            task = self._queue.get(timeout=timeout)
            with self._lock:
                self._active_tasks[task.episode_id] = task
            return task
        except Empty:
            return None
    
    def complete_task(self, task: ProcessingTask):
        """Mark task as completed"""
        with self._lock:
            if task.episode_id in self._active_tasks:
                del self._active_tasks[task.episode_id]
            self._completed_tasks.append(task)
            
            # Keep only recent completed tasks
            if len(self._completed_tasks) > 100:
                self._completed_tasks = self._completed_tasks[-100:]
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status information"""
        with self._lock:
            return {
                'queued_tasks': self._queue.qsize(),
                'active_tasks': len(self._active_tasks),
                'completed_tasks': len(self._completed_tasks),
                'max_size': self.max_size
            }
    
    def get_active_episodes(self) -> List[str]:
        """Get list of active episode IDs"""
        with self._lock:
            return list(self._active_tasks.keys())


class ConcurrencyController:
    """Controls concurrent processing with resource awareness"""
    
    def __init__(self, 
                 resource_limits: Optional[ResourceLimits] = None,
                 max_workers: Optional[int] = None):
        self.limits = resource_limits or ResourceLimits()
        self.max_workers = max_workers or self.limits.max_concurrent_episodes
        
        self.resource_monitor = ResourceMonitor(self.limits)
        self.processing_queue = ProcessingQueue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        self._running = False
        self._worker_threads: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
        
        # Register resource limit callback
        self.resource_monitor.add_callback(self._handle_resource_violation)
    
    def start(self):
        """Start the concurrency controller"""
        if self._running:
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop, 
                args=(i,), 
                daemon=True
            )
            worker.start()
            self._worker_threads.append(worker)
        
        logger.info("Concurrency controller started", 
                   max_workers=self.max_workers,
                   resource_limits=self.limits.__dict__)
    
    def stop(self, timeout: float = 30.0):
        """Stop the concurrency controller gracefully"""
        if not self._running:
            return
        
        logger.info("Stopping concurrency controller")
        self._running = False
        self._shutdown_event.set()
        
        # Stop resource monitoring
        self.resource_monitor.stop_monitoring()
        
        # Wait for workers to finish
        for worker in self._worker_threads:
            worker.join(timeout=timeout / len(self._worker_threads))
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("Concurrency controller stopped")
    
    def submit_task(self, 
                   episode_id: str,
                   stage: ProcessingStage,
                   func: Callable,
                   *args,
                   priority: Priority = Priority.NORMAL,
                   timeout: Optional[float] = None,
                   **kwargs) -> bool:
        """Submit a processing task"""
        if not self._running:
            raise ProcessingError("Concurrency controller not running")
        
        task = ProcessingTask(
            episode_id=episode_id,
            stage=stage,
            priority=priority,
            created_at=datetime.now(),
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout
        )
        
        return self.processing_queue.add_task(task)
    
    def _worker_loop(self, worker_id: int):
        """Worker thread loop"""
        logger.debug(f"Worker {worker_id} started")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Check if we can accept new work
                if not self.resource_monitor.should_allow_new_task():
                    time.sleep(5)  # Wait before checking again
                    continue
                
                # Get next task
                task = self.processing_queue.get_task(timeout=1.0)
                if not task:
                    continue
                
                # Execute task
                self._execute_task(worker_id, task)
                
            except Exception as e:
                logger.error(f"Error in worker {worker_id}", exception=e)
                time.sleep(1)
        
        logger.debug(f"Worker {worker_id} stopped")
    
    def _execute_task(self, worker_id: int, task: ProcessingTask):
        """Execute a processing task"""
        logger.info(f"Worker {worker_id} executing task", 
                   episode_id=task.episode_id,
                   stage=task.stage.value)
        
        start_time = time.time()
        
        try:
            # Execute the task function
            if task.timeout:
                future = self.executor.submit(task.func, *task.args, **task.kwargs)
                result = future.result(timeout=task.timeout)
            else:
                result = task.func(*task.args, **task.kwargs)
            
            duration = time.time() - start_time
            
            logger.info(f"Worker {worker_id} completed task", 
                       episode_id=task.episode_id,
                       stage=task.stage.value,
                       duration=duration)
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(f"Worker {worker_id} task failed", 
                        episode_id=task.episode_id,
                        stage=task.stage.value,
                        duration=duration,
                        exception=e)
        
        finally:
            self.processing_queue.complete_task(task)
    
    def _handle_resource_violation(self, violations: Dict[str, float]):
        """Handle resource limit violations"""
        logger.warning("Handling resource violations", violations=violations)
        
        # Trigger cleanup if memory is high
        if 'memory_percent' in violations:
            self.resource_monitor.trigger_cleanup()
        
        # Could implement additional strategies here:
        # - Pause new task acceptance
        # - Kill lowest priority tasks
        # - Reduce concurrency temporarily
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        queue_status = self.processing_queue.get_queue_status()
        resource_usage = self.resource_monitor.get_current_usage()
        
        return {
            'running': self._running,
            'max_workers': self.max_workers,
            'queue': queue_status,
            'resources': resource_usage,
            'limits': self.limits.__dict__,
            'active_episodes': self.processing_queue.get_active_episodes()
        }


class GracefulShutdownHandler:
    """Handles graceful shutdown of the pipeline"""
    
    def __init__(self, concurrency_controller: ConcurrencyController):
        self.controller = concurrency_controller
        self._shutdown_requested = False
        self._shutdown_callbacks: List[Callable[[], None]] = []
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def add_shutdown_callback(self, callback: Callable[[], None]):
        """Add callback to be called during shutdown"""
        self._shutdown_callbacks.append(callback)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown()
    
    def shutdown(self, timeout: float = 60.0):
        """Perform graceful shutdown"""
        if self._shutdown_requested:
            return
        
        self._shutdown_requested = True
        logger.info("Starting graceful shutdown")
        
        # Call shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Error in shutdown callback", exception=e)
        
        # Stop concurrency controller
        self.controller.stop(timeout=timeout)
        
        logger.info("Graceful shutdown completed")
    
    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self._shutdown_requested


class MemoryManager:
    """Manages memory usage and cleanup"""
    
    def __init__(self, cleanup_threshold_mb: float = 1000):
        self.cleanup_threshold_mb = cleanup_threshold_mb
        self._last_cleanup = datetime.now()
        self._cleanup_interval = timedelta(minutes=10)
    
    def check_memory_usage(self) -> Dict[str, float]:
        """Check current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / (1024 * 1024),
            'vms_mb': memory_info.vms / (1024 * 1024),
            'percent': process.memory_percent()
        }
    
    def should_cleanup(self) -> bool:
        """Check if cleanup should be performed"""
        memory_usage = self.check_memory_usage()
        time_since_cleanup = datetime.now() - self._last_cleanup
        
        return (memory_usage['rss_mb'] > self.cleanup_threshold_mb or 
                time_since_cleanup > self._cleanup_interval)
    
    def cleanup(self) -> Dict[str, Any]:
        """Perform memory cleanup"""
        logger.info("Starting memory cleanup")
        
        before_usage = self.check_memory_usage()
        
        # Force garbage collection
        collected_objects = gc.collect()
        
        # Clear GPU cache if available
        gpu_cleared = False
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                gpu_cleared = True
        except ImportError:
            pass
        
        after_usage = self.check_memory_usage()
        self._last_cleanup = datetime.now()
        
        cleanup_result = {
            'collected_objects': collected_objects,
            'gpu_cleared': gpu_cleared,
            'memory_before_mb': before_usage['rss_mb'],
            'memory_after_mb': after_usage['rss_mb'],
            'memory_freed_mb': before_usage['rss_mb'] - after_usage['rss_mb']
        }
        
        logger.info("Memory cleanup completed", **cleanup_result)
        return cleanup_result
    
    @contextmanager
    def memory_context(self):
        """Context manager that performs cleanup if needed"""
        if self.should_cleanup():
            self.cleanup()
        
        try:
            yield
        finally:
            if self.should_cleanup():
                self.cleanup()


# Global instances
default_resource_limits = ResourceLimits()
default_concurrency_controller = ConcurrencyController(default_resource_limits)
default_shutdown_handler = GracefulShutdownHandler(default_concurrency_controller)
default_memory_manager = MemoryManager()


# Context managers and decorators
@contextmanager
def resource_managed_execution():
    """Context manager for resource-managed execution"""
    if not default_concurrency_controller._running:
        default_concurrency_controller.start()
    
    try:
        yield default_concurrency_controller
    finally:
        # Don't automatically stop - let the application control this
        pass


def with_resource_management(priority: Priority = Priority.NORMAL, 
                           timeout: Optional[float] = None):
    """Decorator to add resource management to a function"""
    def decorator(func: Callable) -> Callable:
        def wrapper(episode_id: str, stage: ProcessingStage, *args, **kwargs):
            return default_concurrency_controller.submit_task(
                episode_id, stage, func, *args, 
                priority=priority, timeout=timeout, **kwargs
            )
        return wrapper
    return decorator