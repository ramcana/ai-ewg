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


class TranscriptionError(PipelineError):
    """Raised when transcription operations fail"""
    
    def __init__(self, message: str, audio_path: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if audio_path:
            context['audio_path'] = audio_path
        super().__init__(message, context)
        self.audio_path = audio_path


# Clip Generation Exception Hierarchy

class ClipGenerationError(PipelineError):
    """Base exception for clip generation errors"""
    
    def __init__(self, message: str, episode_id: Optional[str] = None, clip_id: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if episode_id:
            context['episode_id'] = episode_id
        if clip_id:
            context['clip_id'] = clip_id
        super().__init__(message, context)
        self.episode_id = episode_id
        self.clip_id = clip_id


class ClipRequestError(ClipGenerationError):
    """Raised for API request validation and processing errors"""
    
    def __init__(self, message: str, request_type: Optional[str] = None, validation_field: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if request_type:
            context['request_type'] = request_type
        if validation_field:
            context['validation_field'] = validation_field
        super().__init__(message, **kwargs)
        self.request_type = request_type
        self.validation_field = validation_field


class SegmentationError(ClipGenerationError):
    """Raised when topic segmentation fails"""
    
    def __init__(self, message: str, segmentation_stage: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if segmentation_stage:
            context['segmentation_stage'] = segmentation_stage
        super().__init__(message, **kwargs)
        self.segmentation_stage = segmentation_stage


class ScoringError(ClipGenerationError):
    """Raised when highlight scoring fails"""
    
    def __init__(self, message: str, scoring_method: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if scoring_method:
            context['scoring_method'] = scoring_method
        super().__init__(message, **kwargs)
        self.scoring_method = scoring_method


class ExportError(ClipGenerationError):
    """Raised when clip export operations fail"""
    
    def __init__(self, message: str, export_stage: Optional[str] = None, aspect_ratio: Optional[str] = None, 
                 variant: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if export_stage:
            context['export_stage'] = export_stage
        if aspect_ratio:
            context['aspect_ratio'] = aspect_ratio
        if variant:
            context['variant'] = variant
        super().__init__(message, **kwargs)
        self.export_stage = export_stage
        self.aspect_ratio = aspect_ratio
        self.variant = variant


class EmbeddingError(ClipGenerationError):
    """Raised when embedding generation fails"""
    
    def __init__(self, message: str, model_name: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if model_name:
            context['model_name'] = model_name
        super().__init__(message, **kwargs)
        self.model_name = model_name


class LLMError(ClipGenerationError):
    """Raised when LLM operations fail"""
    
    def __init__(self, message: str, model_name: Optional[str] = None, operation: Optional[str] = None, **kwargs):
        context = kwargs.get('context', {})
        if model_name:
            context['model_name'] = model_name
        if operation:
            context['operation'] = operation
        super().__init__(message, **kwargs)
        self.model_name = model_name
        self.operation = operation


class FFmpegError(ExportError):
    """Raised when FFmpeg operations fail"""
    
    def __init__(self, message: str, command: Optional[str] = None, return_code: Optional[int] = None, **kwargs):
        context = kwargs.get('context', {})
        if command:
            context['command'] = command
        if return_code is not None:
            context['return_code'] = return_code
        super().__init__(message, export_stage='ffmpeg', **kwargs)
        self.command = command
        self.return_code = return_code