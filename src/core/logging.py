"""
Logging infrastructure for the Video Processing Pipeline

Provides structured logging with timing, performance metrics, and
comprehensive error reporting for monitoring and troubleshooting.
"""

import logging
import logging.handlers
import json
import time
import threading
import psutil
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import defaultdict, deque

from .exceptions import PipelineError


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add custom fields from extra
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add pipeline-specific context
        for attr in ['episode_id', 'stage', 'duration', 'performance_metrics']:
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        
        return json.dumps(log_entry, default=str)


class PipelineLogger:
    """Enhanced logger with pipeline-specific functionality"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._timers: Dict[str, float] = {}
        self._active_stages: Dict[str, Any] = {}
    
    def info(self, message: str, **kwargs):
        """Log info message with optional context"""
        extra = {'extra_fields': kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional context"""
        extra = {'extra_fields': kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception and context"""
        extra = {'extra_fields': kwargs} if kwargs else {}
        if exception:
            self.logger.error(message, exc_info=exception, extra=extra)
        else:
            self.logger.error(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional context"""
        extra = {'extra_fields': kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)
    
    def start_timer(self, operation: str) -> None:
        """Start timing an operation"""
        self._timers[operation] = time.time()
    
    def end_timer(self, operation: str, **kwargs) -> float:
        """End timing an operation and log the duration"""
        if operation not in self._timers:
            self.warning(f"Timer '{operation}' was not started")
            return 0.0
        
        duration = time.time() - self._timers[operation]
        del self._timers[operation]
        
        self.info(f"Operation '{operation}' completed", 
                 duration=duration, 
                 operation=operation,
                 **kwargs)
        return duration
    
    @contextmanager
    def timer(self, operation: str, **kwargs):
        """Context manager for timing operations"""
        self.start_timer(operation)
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            if operation in self._timers:
                del self._timers[operation]
            self.info(f"Operation '{operation}' completed", 
                     duration=duration, 
                     operation=operation,
                     **kwargs)
    
    def start_processing_stage(self, episode_id: str, stage: str, 
                             input_size_mb: Optional[float] = None):
        """Start tracking a processing stage"""
        metrics = processing_tracker.start_stage(episode_id, stage, input_size_mb)
        stage_key = f"{episode_id}:{stage}"
        self._active_stages[stage_key] = metrics
        
        self.info(f"Started processing stage {stage}", 
                 episode_id=episode_id,
                 stage=stage,
                 input_size_mb=input_size_mb,
                 event_type='stage_start')
        
        return metrics
    
    def complete_processing_stage(self, episode_id: str, stage: str,
                                status: str = "completed",
                                error_message: Optional[str] = None,
                                output_size_mb: Optional[float] = None):
        """Complete a processing stage"""
        stage_key = f"{episode_id}:{stage}"
        if stage_key in self._active_stages:
            del self._active_stages[stage_key]
        
        metrics = processing_tracker.complete_stage(
            episode_id, stage, status, error_message, output_size_mb
        )
        
        if status == "completed":
            self.info(f"Completed processing stage {stage}", 
                     episode_id=episode_id,
                     stage=stage,
                     duration=metrics.duration_seconds if metrics else None,
                     output_size_mb=output_size_mb,
                     event_type='stage_complete')
        else:
            self.error(f"Failed processing stage {stage}", 
                      episode_id=episode_id,
                      stage=stage,
                      error_message=error_message,
                      event_type='stage_error')
        
        return metrics
    
    @contextmanager
    def processing_stage(self, episode_id: str, stage: str, 
                        input_size_mb: Optional[float] = None):
        """Context manager for processing stages"""
        metrics = self.start_processing_stage(episode_id, stage, input_size_mb)
        try:
            yield metrics
            self.complete_processing_stage(episode_id, stage, "completed")
        except Exception as e:
            self.complete_processing_stage(episode_id, stage, "failed", str(e))
            raise
    
    def log_processing_event(self, episode_id: str, stage: str, status: str, 
                           duration: Optional[float] = None, error: Optional[str] = None):
        """Log a processing event with structured data"""
        event_data = {
            'episode_id': episode_id,
            'stage': stage,
            'status': status,
            'event_type': 'processing'
        }
        
        if duration is not None:
            event_data['duration'] = duration
        
        if error:
            event_data['error'] = error
            self.error(f"Processing {status} for {episode_id} at stage {stage}", **event_data)
        else:
            self.info(f"Processing {status} for {episode_id} at stage {stage}", **event_data)
    
    def log_performance_metrics(self, metrics: Dict[str, Any]):
        """Log performance metrics"""
        self.info("Performance metrics", performance_metrics=metrics, event_type='metrics')
    
    def log_decision(self, episode_id: str, stage: str, decision: str, 
                    reasoning: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a processing decision to audit trail"""
        audit_trail.log_decision(episode_id, stage, decision, reasoning, metadata)
        
        self.info(f"Processing decision: {decision}", 
                 episode_id=episode_id,
                 stage=stage,
                 decision=decision,
                 reasoning=reasoning,
                 event_type='decision')
    
    def log_resource_usage(self):
        """Log current resource usage"""
        metrics = system_monitor.collect_metrics()
        self.info("Resource usage snapshot", 
                 cpu_percent=metrics.cpu_percent,
                 memory_mb=metrics.memory_mb,
                 memory_percent=metrics.memory_percent,
                 active_threads=metrics.active_threads,
                 open_files=metrics.open_files,
                 event_type='resource_usage')
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Export current metrics in specified format"""
        if format_type == "prometheus":
            return metrics_exporter.export_prometheus_metrics()
        else:
            metrics = metrics_exporter.export_dashboard_metrics()
            return json.dumps(metrics, indent=2, default=str)


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Set up logging infrastructure based on configuration
    
    Args:
        config: Configuration dictionary containing logging settings
    """
    log_config = config.get('logging', {})
    
    # Get configuration values with defaults
    log_level = log_config.get('level', 'INFO').upper()
    log_dir = Path(log_config.get('directory', 'logs'))
    max_file_size = log_config.get('max_file_size_mb', 10) * 1024 * 1024
    backup_count = log_config.get('backup_count', 5)
    console_logging = log_config.get('console', True)
    structured_format = log_config.get('structured', True)
    
    # Create log directory
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Set up formatters
    if structured_format:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'pipeline.log',
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'pipeline_errors.log',
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Console handler
    if console_logging:
        console_handler = logging.StreamHandler()
        if structured_format:
            # Use simpler format for console
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
        else:
            console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Log startup message
    logger = PipelineLogger('pipeline.setup')
    logger.info("Logging system initialized", 
               log_level=log_level,
               log_directory=str(log_dir),
               structured_format=structured_format)


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    active_threads: int = 0
    open_files: int = 0
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_mb': self.memory_mb,
            'disk_io_read_mb': self.disk_io_read_mb,
            'disk_io_write_mb': self.disk_io_write_mb,
            'network_sent_mb': self.network_sent_mb,
            'network_recv_mb': self.network_recv_mb,
            'active_threads': self.active_threads,
            'open_files': self.open_files,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class ProcessingStageMetrics:
    """Metrics for a specific processing stage"""
    stage_name: str
    episode_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: str = "started"  # started, completed, failed
    error_message: Optional[str] = None
    input_size_mb: Optional[float] = None
    output_size_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    
    def complete(self, status: str = "completed", error_message: Optional[str] = None):
        """Mark stage as complete"""
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = status
        if error_message:
            self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage_name': self.stage_name,
            'episode_id': self.episode_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'status': self.status,
            'error_message': self.error_message,
            'input_size_mb': self.input_size_mb,
            'output_size_mb': self.output_size_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb
        }


class SystemMonitor:
    """Monitors system resources and performance"""
    
    def __init__(self, collection_interval: int = 60):
        self.collection_interval = collection_interval
        self.metrics_history: deque = deque(maxlen=1440)  # 24 hours at 1-minute intervals
        self.process = psutil.Process()
        self.last_disk_io = None
        self.last_network_io = None
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None
    
    def start_monitoring(self):
        """Start background monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger = get_logger('pipeline.monitor')
        logger.info("System monitoring started", interval=self.collection_interval)
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                metrics = self.collect_metrics()
                with self._lock:
                    self.metrics_history.append(metrics)
                time.sleep(self.collection_interval)
            except Exception as e:
                logger = get_logger('pipeline.monitor')
                logger.error("Error in monitoring loop", exception=e)
                time.sleep(self.collection_interval)
    
    def collect_metrics(self) -> PerformanceMetrics:
        """Collect current system metrics"""
        try:
            # CPU and memory
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # Disk I/O
            disk_io = self.process.io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024)
            disk_write_mb = disk_io.write_bytes / (1024 * 1024)
            
            # Network I/O (system-wide)
            network_io = psutil.net_io_counters()
            network_sent_mb = network_io.bytes_sent / (1024 * 1024)
            network_recv_mb = network_io.bytes_recv / (1024 * 1024)
            
            # Process info
            active_threads = self.process.num_threads()
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                open_files = 0
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_info.rss / (1024 * 1024),
                disk_io_read_mb=disk_read_mb,
                disk_io_write_mb=disk_write_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_threads=active_threads,
                open_files=open_files
            )
        
        except Exception as e:
            logger = get_logger('pipeline.monitor')
            logger.error("Failed to collect system metrics", exception=e)
            return PerformanceMetrics()
    
    def get_recent_metrics(self, minutes: int = 60) -> List[PerformanceMetrics]:
        """Get metrics from the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            return [
                metrics for metrics in self.metrics_history
                if metrics.timestamp and metrics.timestamp >= cutoff_time
            ]
    
    def get_average_metrics(self, minutes: int = 60) -> Optional[PerformanceMetrics]:
        """Get average metrics over the last N minutes"""
        recent_metrics = self.get_recent_metrics(minutes)
        if not recent_metrics:
            return None
        
        count = len(recent_metrics)
        return PerformanceMetrics(
            cpu_percent=sum(m.cpu_percent for m in recent_metrics) / count,
            memory_percent=sum(m.memory_percent for m in recent_metrics) / count,
            memory_mb=sum(m.memory_mb for m in recent_metrics) / count,
            disk_io_read_mb=sum(m.disk_io_read_mb for m in recent_metrics) / count,
            disk_io_write_mb=sum(m.disk_io_write_mb for m in recent_metrics) / count,
            network_sent_mb=sum(m.network_sent_mb for m in recent_metrics) / count,
            network_recv_mb=sum(m.network_recv_mb for m in recent_metrics) / count,
            active_threads=int(sum(m.active_threads for m in recent_metrics) / count),
            open_files=int(sum(m.open_files for m in recent_metrics) / count)
        )


class AuditTrail:
    """Maintains audit trail of processing decisions"""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.entries: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
    
    def log_decision(self, 
                    episode_id: str,
                    stage: str,
                    decision: str,
                    reasoning: str,
                    metadata: Optional[Dict[str, Any]] = None):
        """Log a processing decision"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'episode_id': episode_id,
            'stage': stage,
            'decision': decision,
            'reasoning': reasoning,
            'metadata': metadata or {}
        }
        
        with self._lock:
            self.entries.append(entry)
        
        logger = get_logger('pipeline.audit')
        logger.info("Processing decision logged", **entry)
    
    def get_decisions_for_episode(self, episode_id: str) -> List[Dict[str, Any]]:
        """Get all decisions for a specific episode"""
        with self._lock:
            return [
                entry for entry in self.entries
                if entry['episode_id'] == episode_id
            ]
    
    def get_recent_decisions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get decisions from the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        with self._lock:
            return [
                entry for entry in self.entries
                if datetime.fromisoformat(entry['timestamp']) >= cutoff_time
            ]
    
    def export_audit_trail(self, output_path: Path, hours: int = 24) -> None:
        """Export audit trail to JSON file"""
        decisions = self.get_recent_decisions(hours)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'hours_covered': hours,
            'total_decisions': len(decisions),
            'decisions': decisions
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)


class ProcessingTracker:
    """Tracks processing stages and performance"""
    
    def __init__(self):
        self.active_stages: Dict[str, ProcessingStageMetrics] = {}
        self.completed_stages: deque = deque(maxlen=1000)
        self.stage_statistics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'total_duration': 0.0,
            'average_duration': 0.0,
            'min_duration': float('inf'),
            'max_duration': 0.0
        })
        self._lock = threading.Lock()
    
    def start_stage(self, episode_id: str, stage_name: str, 
                   input_size_mb: Optional[float] = None) -> ProcessingStageMetrics:
        """Start tracking a processing stage"""
        stage_key = f"{episode_id}:{stage_name}"
        
        metrics = ProcessingStageMetrics(
            stage_name=stage_name,
            episode_id=episode_id,
            start_time=datetime.now(),
            input_size_mb=input_size_mb
        )
        
        with self._lock:
            self.active_stages[stage_key] = metrics
        
        logger = get_logger('pipeline.tracker')
        logger.info("Processing stage started", 
                   episode_id=episode_id, 
                   stage=stage_name,
                   input_size_mb=input_size_mb)
        
        return metrics
    
    def complete_stage(self, episode_id: str, stage_name: str, 
                      status: str = "completed",
                      error_message: Optional[str] = None,
                      output_size_mb: Optional[float] = None) -> Optional[ProcessingStageMetrics]:
        """Complete a processing stage"""
        stage_key = f"{episode_id}:{stage_name}"
        
        with self._lock:
            if stage_key not in self.active_stages:
                logger = get_logger('pipeline.tracker')
                logger.warning("Attempted to complete unknown stage", 
                             episode_id=episode_id, 
                             stage=stage_name)
                return None
            
            metrics = self.active_stages.pop(stage_key)
            metrics.complete(status, error_message)
            if output_size_mb:
                metrics.output_size_mb = output_size_mb
            
            # Update statistics
            stats = self.stage_statistics[stage_name]
            stats['total_count'] += 1
            
            if status == "completed":
                stats['success_count'] += 1
            else:
                stats['failure_count'] += 1
            
            if metrics.duration_seconds:
                stats['total_duration'] += metrics.duration_seconds
                stats['average_duration'] = stats['total_duration'] / stats['total_count']
                stats['min_duration'] = min(stats['min_duration'], metrics.duration_seconds)
                stats['max_duration'] = max(stats['max_duration'], metrics.duration_seconds)
            
            self.completed_stages.append(metrics)
        
        logger = get_logger('pipeline.tracker')
        logger.info("Processing stage completed", 
                   episode_id=episode_id, 
                   stage=stage_name,
                   status=status,
                   duration=metrics.duration_seconds,
                   output_size_mb=output_size_mb)
        
        return metrics
    
    def get_active_stages(self) -> List[ProcessingStageMetrics]:
        """Get all currently active stages"""
        with self._lock:
            return list(self.active_stages.values())
    
    def get_stage_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get processing statistics by stage"""
        with self._lock:
            # Clean up infinite values
            stats = {}
            for stage, data in self.stage_statistics.items():
                stats[stage] = data.copy()
                if stats[stage]['min_duration'] == float('inf'):
                    stats[stage]['min_duration'] = 0.0
            return stats
    
    def get_recent_completions(self, hours: int = 24) -> List[ProcessingStageMetrics]:
        """Get recently completed stages"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        with self._lock:
            return [
                stage for stage in self.completed_stages
                if stage.end_time and stage.end_time >= cutoff_time
            ]


class MetricsExporter:
    """Exports metrics in dashboard-ready formats"""
    
    def __init__(self, system_monitor: SystemMonitor, 
                 processing_tracker: ProcessingTracker,
                 audit_trail: AuditTrail):
        self.system_monitor = system_monitor
        self.processing_tracker = processing_tracker
        self.audit_trail = audit_trail
    
    def export_dashboard_metrics(self) -> Dict[str, Any]:
        """Export comprehensive metrics for dashboard consumption"""
        current_time = datetime.now()
        
        # System metrics
        current_metrics = self.system_monitor.collect_metrics()
        avg_metrics_1h = self.system_monitor.get_average_metrics(60)
        avg_metrics_24h = self.system_monitor.get_average_metrics(1440)
        
        # Processing metrics
        active_stages = self.processing_tracker.get_active_stages()
        stage_stats = self.processing_tracker.get_stage_statistics()
        recent_completions = self.processing_tracker.get_recent_completions(24)
        
        # Audit metrics
        recent_decisions = self.audit_trail.get_recent_decisions(24)
        
        return {
            'timestamp': current_time.isoformat(),
            'system': {
                'current': current_metrics.to_dict(),
                'average_1h': avg_metrics_1h.to_dict() if avg_metrics_1h else None,
                'average_24h': avg_metrics_24h.to_dict() if avg_metrics_24h else None
            },
            'processing': {
                'active_stages': len(active_stages),
                'active_episodes': len(set(stage.episode_id for stage in active_stages)),
                'stage_statistics': stage_stats,
                'completions_24h': len(recent_completions),
                'success_rate_24h': self._calculate_success_rate(recent_completions)
            },
            'audit': {
                'decisions_24h': len(recent_decisions),
                'decision_breakdown': self._breakdown_decisions(recent_decisions)
            }
        }
    
    def _calculate_success_rate(self, completions: List[ProcessingStageMetrics]) -> float:
        """Calculate success rate from completions"""
        if not completions:
            return 1.0
        
        successful = sum(1 for c in completions if c.status == "completed")
        return successful / len(completions)
    
    def _breakdown_decisions(self, decisions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Break down decisions by type"""
        breakdown = defaultdict(int)
        for decision in decisions:
            breakdown[decision['decision']] += 1
        return dict(breakdown)
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        metrics = self.export_dashboard_metrics()
        lines = []
        
        # System metrics
        if metrics['system']['current']:
            current = metrics['system']['current']
            lines.extend([
                f"pipeline_cpu_percent {current['cpu_percent']}",
                f"pipeline_memory_percent {current['memory_percent']}",
                f"pipeline_memory_mb {current['memory_mb']}",
                f"pipeline_active_threads {current['active_threads']}",
                f"pipeline_open_files {current['open_files']}"
            ])
        
        # Processing metrics
        processing = metrics['processing']
        lines.extend([
            f"pipeline_active_stages {processing['active_stages']}",
            f"pipeline_active_episodes {processing['active_episodes']}",
            f"pipeline_completions_24h {processing['completions_24h']}",
            f"pipeline_success_rate_24h {processing['success_rate_24h']}"
        ])
        
        # Stage statistics
        for stage, stats in processing['stage_statistics'].items():
            stage_clean = stage.replace('-', '_').replace(' ', '_')
            lines.extend([
                f"pipeline_stage_total_count{{stage=\"{stage}\"}} {stats['total_count']}",
                f"pipeline_stage_success_count{{stage=\"{stage}\"}} {stats['success_count']}",
                f"pipeline_stage_failure_count{{stage=\"{stage}\"}} {stats['failure_count']}",
                f"pipeline_stage_average_duration{{stage=\"{stage}\"}} {stats['average_duration']}"
            ])
        
        return '\n'.join(lines)


# Global instances
system_monitor = SystemMonitor()
processing_tracker = ProcessingTracker()
audit_trail = AuditTrail()
metrics_exporter = MetricsExporter(system_monitor, processing_tracker, audit_trail)


def get_logger(name: str) -> PipelineLogger:
    """Get a pipeline logger instance"""
    return PipelineLogger(name)