"""
Structured logging with JSONL output for n8n integration

Provides dual-mode logging:
- Human-readable console output with Rich formatting
- Machine-readable JSONL files for parsing and analysis
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from contextlib import contextmanager

import structlog
from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_structured_logging(
    log_dir: Path,
    level: str = "INFO",
    console_output: bool = True,
    jsonl_output: bool = True
) -> None:
    """
    Setup structured logging with JSONL and console outputs
    
    Args:
        log_dir: Directory for log files
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Enable human-readable console output
        jsonl_output: Enable JSONL file output
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped JSONL log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = log_dir / f"run_{timestamp}.jsonl"
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add JSONL file processor
    if jsonl_output:
        jsonl_file = open(jsonl_path, 'a', encoding='utf-8')
        processors.append(
            structlog.processors.JSONRenderer()
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib, level.upper(), structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=jsonl_file if jsonl_output else sys.stdout),
        cache_logger_on_first_use=True,
    )
    
    # Setup console logging with Rich
    if console_output:
        import logging
        logging.basicConfig(
            level=level,
            format="%(message)s",
            handlers=[RichHandler(rich_tracebacks=True, console=console)]
        )


class RunLogger:
    """
    Context manager for logging a complete run with summary
    
    Tracks stage execution, errors, and generates n8n-friendly summaries
    """
    
    def __init__(self, command: str, episode_id: Optional[str] = None):
        self.command = command
        self.episode_id = episode_id
        self.start_time = datetime.now()
        self.stages: Dict[str, Dict[str, Any]] = {}
        self.errors: list = []
        self.logger = structlog.get_logger()
    
    def __enter__(self):
        self.logger.info(
            "run_started",
            command=self.command,
            episode_id=self.episode_id,
            timestamp=self.start_time.isoformat()
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        success = exc_type is None
        
        # Log run completion
        self.logger.info(
            "run_completed",
            command=self.command,
            episode_id=self.episode_id,
            duration_seconds=duration,
            success=success,
            stages_completed=len(self.stages),
            error_count=len(self.errors)
        )
        
        # Generate n8n summary
        summary = self.generate_summary(duration, success)
        
        # Output JSON summary to stdout for n8n
        print(json.dumps(summary), flush=True)
        
        return False  # Don't suppress exceptions
    
    @contextmanager
    def stage(self, stage_name: str):
        """Context manager for logging a processing stage"""
        stage_start = datetime.now()
        
        self.logger.info(
            "stage_started",
            stage=stage_name,
            episode_id=self.episode_id
        )
        
        try:
            yield
            
            stage_end = datetime.now()
            stage_duration = (stage_end - stage_start).total_seconds()
            
            self.stages[stage_name] = {
                "status": "completed",
                "duration_seconds": stage_duration,
                "timestamp": stage_end.isoformat()
            }
            
            self.logger.info(
                "stage_completed",
                stage=stage_name,
                episode_id=self.episode_id,
                duration_seconds=stage_duration
            )
            
        except Exception as e:
            stage_end = datetime.now()
            stage_duration = (stage_end - stage_start).total_seconds()
            
            error_info = {
                "stage": stage_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": stage_end.isoformat()
            }
            
            self.stages[stage_name] = {
                "status": "failed",
                "duration_seconds": stage_duration,
                "error": str(e),
                "timestamp": stage_end.isoformat()
            }
            
            self.errors.append(error_info)
            
            self.logger.error(
                "stage_failed",
                stage=stage_name,
                episode_id=self.episode_id,
                duration_seconds=stage_duration,
                error=str(e),
                error_type=type(e).__name__
            )
            
            raise
    
    def log_metric(self, metric_name: str, value: Any) -> None:
        """Log a metric for the current run"""
        self.logger.info(
            "metric",
            metric=metric_name,
            value=value,
            episode_id=self.episode_id
        )
    
    def generate_summary(self, duration: float, success: bool) -> Dict[str, Any]:
        """
        Generate n8n-friendly JSON summary
        
        Returns:
            Dictionary with run summary for n8n parsing
        """
        return {
            "command": self.command,
            "episode_id": self.episode_id,
            "success": success,
            "duration_seconds": round(duration, 2),
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "stages": self.stages,
            "errors": self.errors,
            "error_count": len(self.errors),
            "stages_completed": sum(1 for s in self.stages.values() if s["status"] == "completed"),
            "stages_failed": sum(1 for s in self.stages.values() if s["status"] == "failed")
        }


class BatchLogger:
    """Logger for batch processing operations"""
    
    def __init__(self, command: str, total_items: int):
        self.command = command
        self.total_items = total_items
        self.processed = 0
        self.failed = 0
        self.start_time = datetime.now()
        self.logger = structlog.get_logger()
        
        self.logger.info(
            "batch_started",
            command=command,
            total_items=total_items
        )
    
    def log_item_success(self, item_id: str, duration: float) -> None:
        """Log successful item processing"""
        self.processed += 1
        self.logger.info(
            "item_processed",
            item_id=item_id,
            duration_seconds=duration,
            progress=f"{self.processed}/{self.total_items}"
        )
    
    def log_item_failure(self, item_id: str, error: str) -> None:
        """Log failed item processing"""
        self.failed += 1
        self.logger.error(
            "item_failed",
            item_id=item_id,
            error=error,
            progress=f"{self.processed + self.failed}/{self.total_items}"
        )
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate batch processing summary"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        summary = {
            "command": self.command,
            "success": self.failed == 0,
            "total_items": self.total_items,
            "processed": self.processed,
            "failed": self.failed,
            "success_rate": round(self.processed / self.total_items, 3) if self.total_items > 0 else 0,
            "duration_seconds": round(duration, 2),
            "items_per_second": round(self.processed / duration, 2) if duration > 0 else 0,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        self.logger.info("batch_completed", **summary)
        
        return summary


# Convenience functions
def get_run_logger(command: str, episode_id: Optional[str] = None) -> RunLogger:
    """Get a run logger instance"""
    return RunLogger(command, episode_id)


def get_batch_logger(command: str, total_items: int) -> BatchLogger:
    """Get a batch logger instance"""
    return BatchLogger(command, total_items)


def log_to_console(message: str, style: str = "info") -> None:
    """Log a styled message to console"""
    styles = {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "debug": "dim"
    }
    console.print(f"[{styles.get(style, 'white')}]{message}[/{styles.get(style, 'white')}]")
