"""
Error Reporting System for GUI Control Panel

Provides comprehensive error reporting and logging for failed processing steps.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ProcessingStage(Enum):
    """Processing stages for error context"""
    DISCOVERY = "discovery"
    TRANSCRIPTION = "transcription"
    ENRICHMENT = "enrichment"
    CLIP_GENERATION = "clip_generation"
    SOCIAL_PACKAGE = "social_package"
    HTML_GENERATION = "html_generation"
    FILE_ORGANIZATION = "file_organization"

class ErrorReport:
    """Individual error report"""
    
    def __init__(
        self,
        error_id: str,
        severity: ErrorSeverity,
        stage: ProcessingStage,
        message: str,
        episode_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        self.error_id = error_id
        self.severity = severity
        self.stage = stage
        self.message = message
        self.episode_id = episode_id
        self.details = details or {}
        self.exception = exception
        self.timestamp = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error report to dictionary"""
        return {
            "error_id": self.error_id,
            "severity": self.severity.value,
            "stage": self.stage.value,
            "message": self.message,
            "episode_id": self.episode_id,
            "details": self.details,
            "exception": str(self.exception) if self.exception else None,
            "timestamp": self.timestamp.isoformat()
        }

class ErrorReporter:
    """Central error reporting and logging system"""
    
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger("gui_control_panel")
        self.logger.setLevel(logging.INFO)
        
        # File handler for error logs
        error_log_file = self.log_dir / "gui_errors.log"
        file_handler = logging.FileHandler(error_log_file)
        file_handler.setLevel(logging.WARNING)
        
        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Error storage
        self.errors: List[ErrorReport] = []
    
    def report_error(
        self,
        error_id: str,
        severity: ErrorSeverity,
        stage: ProcessingStage,
        message: str,
        episode_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> ErrorReport:
        """Report a new error"""
        
        error_report = ErrorReport(
            error_id=error_id,
            severity=severity,
            stage=stage,
            message=message,
            episode_id=episode_id,
            details=details,
            exception=exception
        )
        
        self.errors.append(error_report)
        
        # Log the error
        log_message = f"[{stage.value}] {message}"
        if episode_id:
            log_message = f"Episode {episode_id}: {log_message}"
        
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        return error_report
    
    def get_errors_by_episode(self, episode_id: str) -> List[ErrorReport]:
        """Get all errors for a specific episode"""
        return [error for error in self.errors if error.episode_id == episode_id]
    
    def get_errors_by_stage(self, stage: ProcessingStage) -> List[ErrorReport]:
        """Get all errors for a specific processing stage"""
        return [error for error in self.errors if error.stage == stage]
    
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[ErrorReport]:
        """Get all errors of a specific severity"""
        return [error for error in self.errors if error.severity == severity]
    
    def get_recent_errors(self, hours: int = 24) -> List[ErrorReport]:
        """Get errors from the last N hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [
            error for error in self.errors 
            if error.timestamp.timestamp() > cutoff_time
        ]
    
    def clear_errors(self, episode_id: Optional[str] = None):
        """Clear errors, optionally for a specific episode"""
        if episode_id:
            self.errors = [error for error in self.errors if error.episode_id != episode_id]
        else:
            self.errors.clear()
    
    def export_error_report(self, output_file: Optional[Path] = None) -> Path:
        """Export error report to JSON file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"error_report_{timestamp}.json"
        
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "total_errors": len(self.errors),
            "errors_by_severity": {
                severity.value: len(self.get_errors_by_severity(severity))
                for severity in ErrorSeverity
            },
            "errors_by_stage": {
                stage.value: len(self.get_errors_by_stage(stage))
                for stage in ProcessingStage
            },
            "errors": [error.to_dict() for error in self.errors]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return output_file
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors"""
        if not self.errors:
            return {"total_errors": 0, "message": "No errors reported"}
        
        recent_errors = self.get_recent_errors(24)
        
        return {
            "total_errors": len(self.errors),
            "recent_errors_24h": len(recent_errors),
            "errors_by_severity": {
                severity.value: len(self.get_errors_by_severity(severity))
                for severity in ErrorSeverity
            },
            "errors_by_stage": {
                stage.value: len(self.get_errors_by_stage(stage))
                for stage in ProcessingStage
            },
            "most_recent_error": self.errors[-1].to_dict() if self.errors else None
        }

# Global error reporter instance
_error_reporter = None

def get_error_reporter() -> ErrorReporter:
    """Get global error reporter instance"""
    global _error_reporter
    if _error_reporter is None:
        _error_reporter = ErrorReporter()
    return _error_reporter

def report_processing_error(
    stage: ProcessingStage,
    message: str,
    episode_id: Optional[str] = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    details: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
) -> ErrorReport:
    """Convenience function to report processing errors"""
    
    error_id = f"{stage.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if episode_id:
        error_id = f"{episode_id}_{error_id}"
    
    return get_error_reporter().report_error(
        error_id=error_id,
        severity=severity,
        stage=stage,
        message=message,
        episode_id=episode_id,
        details=details,
        exception=exception
    )

def get_processing_errors(episode_id: Optional[str] = None) -> List[ErrorReport]:
    """Get processing errors, optionally filtered by episode"""
    reporter = get_error_reporter()
    if episode_id:
        return reporter.get_errors_by_episode(episode_id)
    return reporter.errors

def clear_processing_errors(episode_id: Optional[str] = None):
    """Clear processing errors"""
    get_error_reporter().clear_errors(episode_id)

def export_error_report() -> Path:
    """Export current error report"""
    return get_error_reporter().export_error_report()