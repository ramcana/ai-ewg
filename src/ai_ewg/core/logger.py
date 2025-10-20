"""Structured logging with JSON and rich console output."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import json


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "stage"):
            log_data["stage"] = record.stage
        if hasattr(record, "episode_id"):
            log_data["episode_id"] = record.episode_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(log_dir: Path, log_level: str = "INFO", log_format: str = "json"):
    """Setup logging configuration."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # JSON file handler
    if log_format == "json":
        json_handler = logging.FileHandler(
            log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    else:
        # Text file handler
        text_handler = logging.FileHandler(
            log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        )
        text_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(text_handler)
    
    # Console handler (always text for readability)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
