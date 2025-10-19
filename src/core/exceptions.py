"""
Base exception classes for the Video Processing Pipeline

This module defines the exception hierarchy used throughout the pipeline
to provide clear error categorization and handling strategies.
"""

from typing import Optional, Dict, Any


class PipelineError(Exception):
    """Base exception for all pipeline-related errors"""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class ConfigurationError(PipelineError):
    """Raised when there are configuration-related issues"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if config_key:
            context['config_key'] = config_key
        super().__init__(message, context)
        self.config_key = config_key


class ProcessingError(PipelineError):
    """Raised when processing operations fail"""
    
    def __init__(self, message: str, stage: Optional[str] = None, episode_id: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if stage:
            context['stage'] = stage
        if episode_id:
            context['episode_id'] = episode_id
        super().__init__(message, context)
        self.stage = stage
        self.episode_id = episode_id


class ValidationError(PipelineError):
    """Raised when data validation fails"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        context = kwargs.get('context', {})
        if field:
            context['field'] = field
        if value is not None:
            context['value'] = str(value)
        super().__init__(message, context)
        self.field = field
        self.value = value


class TransientError(PipelineError):
    """Raised for temporary errors that may succeed on retry"""
    
    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3, **kwargs):
        context = kwargs.get('context', {})
        context.update({
            'retry_count': retry_count,
            'max_retries': max_retries
        })
        super().__init__(message, context)
        self.retry_count = retry_count
        self.max_retries = max_retries
    
    @property
    def should_retry(self) -> bool:
        """Check if this error should be retried"""
        return self.retry_count < self.max_retries


class FileSystemError(PipelineError):
    """Raised for file system related errors"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if file_path:
            context['file_path'] = file_path
        super().__init__(message, context)
        self.file_path = file_path


class ExternalServiceError(TransientError):
    """Raised when external services (APIs, databases) fail"""
    
    def __init__(self, message: str, service: Optional[str] = None, status_code: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if service:
            context['service'] = service
        if status_code:
            context['status_code'] = status_code
        super().__init__(message, **kwargs)
        self.service = service
        self.status_code = status_code


class DatabaseError(PipelineError):
    """Raised for database-related errors"""
    
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if query:
            context['query'] = query
        super().__init__(message, context)
        self.query = query


class DiscoveryError(PipelineError):
    """Raised when video discovery operations fail"""
    
    def __init__(self, message: str, source_path: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if source_path:
            context['source_path'] = source_path
        super().__init__(message, context)
        self.source_path = source_path


class NormalizationError(PipelineError):
    """Raised when episode normalization fails"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if file_path:
            context['file_path'] = file_path
        super().__init__(message, context)
        self.file_path = file_path