"""
Advanced Transcription Quality Assessment

Provides comprehensive quality metrics, confidence scoring, and validation
for transcription results with detailed analysis and reporting.
"""

import re
import math
import statistics
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import Counter
from pathlib import Path

from src.core.logging import get_logger
from src.core.models import TranscriptionResult
from src.core.exceptions import ProcessingError, ValidationError
from src.core.media_preparation import ValidationResult

logger = get_logger('pipeline.transcription_quality')


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for transcription results"""
    
    # Basic metrics
    text_length: int = 0
    word_count: int = 0
    segment_count: int = 0
    
    # Confidence metrics
    overall_confidence: float = 0.0
    min_confidence: float = 0.0
    max_confidence: float = 0.0
    confidence_std: float = 0.0
    low_confidence_segments: int = 0
    low_confidence_ratio: float = 0.0
    
    # Duration metrics
    audio_duration: Optional[float] = None
    transcription_duration: Optional[float] = None
    duration_difference: Optional[float] = None
    duration_ratio: Optional[float] = None
    
    # Speech rate metrics
    words_per_minute: Optional[float] = None
    speaking_time_seconds: Optional[float] = None
    silence_ratio: float = 0.0
    
    # Content quality metrics
    repetition_ratio: float = 0.0
    max_word_repetition: int = 0
    avg_word_length: float = 0.0
    estimated_sentences: int = 0
    avg_words_per_sentence: Optional[float] = None
    
    # Technical metrics
    timing_issues: int = 0
    no_speech_segments: int = 0
    no_speech_ratio: float = 0.0
    
    # Quality scores
    content_quality_score: float = 0.0
    technical_quality_score: float = 0.0
    overall_quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class QualityThresholds:
    """Configurable quality thresholds for validation"""
    
    # Confidence thresholds
    min_confidence: float = 0.3
    warning_confidence: float = 0.5
    max_low_confidence_ratio: float = 0.5
    
    # Duration thresholds
    max_duration_ratio_diff: float = 0.1
    
    # Speech rate thresholds
    min_words_per_minute: float = 50.0
    max_words_per_minute: float = 300.0
    
    # Content quality thresholds
    max_repetition_ratio: float = 0.3
    min_text_length: int = 10
    max_silence_ratio: float = 0.8
    
    # Technical thresholds
    max_no_speech_ratio: float = 0.8
    max_timing_issues_ratio: float = 0.1