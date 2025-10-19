"""
Transcription Engine for the Video Processing Pipeline

Handles audio transcription using Whisper models with multiple output formats,
GPU acceleration support, and comprehensive quality validation.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None

from .exceptions import ProcessingError, ValidationError
from .logging import get_logger
from .models import TranscriptionResult, EpisodeObject, ProcessingStage
from .media_preparation import AudioFile, ValidationResult

logger = get_logger('pipeline.transcription')


@dataclass
class TranscriptionSegment:
    """Represents a transcription segment with timing and confidence"""
    start: float
    end: float
    text: str
    confidence: float = 0.0
    no_speech_prob: float = 0.0
    
    def duration(self) -> float:
        """Get segment duration in seconds"""
        return self.end - self.start
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'confidence': self.confidence,
            'no_speech_prob': self.no_speech_prob
        }


@dataclass
class TranscriptionConfig:
    """Configuration for transcription processing"""
    model_size: str = "base"
    device: str = "auto"  # auto, cpu, cuda
    compute_type: str = "auto"  # auto, int8, int16, float16, float32
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0
    repetition_penalty: float = 1.0
    no_repeat_ngram_size: int = 0
    temperature: Union[float, List[float]] = 0.0
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = True
    prompt_reset_on_temperature: float = 0.5
    initial_prompt: Optional[str] = None
    prefix: Optional[str] = None
    suppress_blank: bool = True
    suppress_tokens: Optional[List[int]] = None
    without_timestamps: bool = False
    max_initial_timestamp: float = 1.0
    word_timestamps: bool = False
    prepend_punctuations: str = "\"'([{-"
    append_punctuations: str = "\"'.,:!?)]}"
    vad_filter: bool = True
    vad_parameters: Optional[Dict[str, Any]] = None


class TranscriptionEngine:
    """
    Handles audio transcription using Whisper models with multiple output formats
    """
    
    def __init__(self, config: Optional[TranscriptionConfig] = None):
        """
        Initialize the transcription engine
        
        Args:
            config: Optional transcription configuration
        """
        if not FASTER_WHISPER_AVAILABLE:
            raise ProcessingError(
                "faster-whisper is not available. Please install it: pip install faster-whisper"
            )
        
        self.config = config or TranscriptionConfig()
        self._model: Optional[WhisperModel] = None
        self._model_size: Optional[str] = None
        
        # Validate model size
        valid_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
        if self.config.model_size not in valid_models:
            raise ProcessingError(f"Invalid model size: {self.config.model_size}. "
                                f"Valid options: {', '.join(valid_models)}")
        
        logger.info("Transcription engine initialized", 
                   model_size=self.config.model_size,
                   device=self.config.device,
                   compute_type=self.config.compute_type)
    
    def transcribe_audio(self, audio_path: Union[str, Path], 
                        output_dir: Optional[Union[str, Path]] = None,
                        episode_id: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribe audio file to text and VTT formats
        
        Args:
            audio_path: Path to audio file
            output_dir: Optional output directory for transcript files
            episode_id: Optional episode ID for file naming
            
        Returns:
            TranscriptionResult: Complete transcription results
            
        Raises:
            ProcessingError: If transcription fails
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise ProcessingError(f"Audio file not found: {audio_path}")
        
        logger.info("Starting audio transcription", 
                   audio_path=str(audio_path),
                   model_size=self.config.model_size,
                   episode_id=episode_id)
        
        start_time = time.time()
        
        try:
            # Load model if needed
            self._ensure_model_loaded()
            
            # Perform transcription
            segments, info = self._model.transcribe(
                str(audio_path),
                beam_size=self.config.beam_size,
                best_of=self.config.best_of,
                patience=self.config.patience,
                length_penalty=self.config.length_penalty,
                repetition_penalty=self.config.repetition_penalty,
                no_repeat_ngram_size=self.config.no_repeat_ngram_size,
                temperature=self.config.temperature,
                compression_ratio_threshold=self.config.compression_ratio_threshold,
                log_prob_threshold=self.config.log_prob_threshold,
                no_speech_threshold=self.config.no_speech_threshold,
                condition_on_previous_text=self.config.condition_on_previous_text,
                prompt_reset_on_temperature=self.config.prompt_reset_on_temperature,
                initial_prompt=self.config.initial_prompt,
                prefix=self.config.prefix,
                suppress_blank=self.config.suppress_blank,
                suppress_tokens=self.config.suppress_tokens,
                without_timestamps=self.config.without_timestamps,
                max_initial_timestamp=self.config.max_initial_timestamp,
                word_timestamps=self.config.word_timestamps,
                prepend_punctuations=self.config.prepend_punctuations,
                append_punctuations=self.config.append_punctuations,
                vad_filter=self.config.vad_filter,
                vad_parameters=self.config.vad_parameters
            )
            
            # Convert segments to our format
            transcription_segments = []
            full_text_parts = []
            
            for segment in segments:
                trans_segment = TranscriptionSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=getattr(segment, 'avg_logprob', 0.0),
                    no_speech_prob=getattr(segment, 'no_speech_prob', 0.0)
                )
                transcription_segments.append(trans_segment)
                full_text_parts.append(trans_segment.text)
            
            # Generate full text
            full_text = " ".join(full_text_parts).strip()
            
            # Generate VTT content
            vtt_content = self.generate_vtt(transcription_segments)
            
            # Calculate overall confidence
            if transcription_segments:
                avg_confidence = sum(seg.confidence for seg in transcription_segments) / len(transcription_segments)
            else:
                avg_confidence = 0.0
            
            # Create result
            result = TranscriptionResult(
                text=full_text,
                vtt_content=vtt_content,
                segments=[seg.to_dict() for seg in transcription_segments],
                confidence=avg_confidence,
                language=info.language,
                model_used=self.config.model_size
            )
            
            # Save files if output directory specified
            if output_dir:
                self._save_transcription_files(result, output_dir, episode_id or "transcript")
            
            processing_time = time.time() - start_time
            
            logger.info("Audio transcription completed", 
                       audio_path=str(audio_path),
                       duration=processing_time,
                       segments=len(transcription_segments),
                       confidence=avg_confidence,
                       language=info.language,
                       text_length=len(full_text))
            
            return result
            
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(error_msg, 
                        audio_path=str(audio_path),
                        model_size=self.config.model_size)
            raise ProcessingError(error_msg)
    
    def generate_vtt(self, segments: List[TranscriptionSegment]) -> str:
        """
        Generate VTT (WebVTT) caption file content
        
        Args:
            segments: List of transcription segments
            
        Returns:
            str: VTT file content
        """
        vtt_lines = ["WEBVTT", ""]
        
        for i, segment in enumerate(segments):
            # Format timestamps
            start_time = self._format_vtt_timestamp(segment.start)
            end_time = self._format_vtt_timestamp(segment.end)
            
            # Add segment
            vtt_lines.append(f"{i + 1}")
            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(segment.text)
            vtt_lines.append("")
        
        return "\n".join(vtt_lines)
    
    def generate_txt(self, segments: List[TranscriptionSegment]) -> str:
        """
        Generate plain text transcript
        
        Args:
            segments: List of transcription segments
            
        Returns:
            str: Plain text transcript
        """
        return " ".join(segment.text for segment in segments).strip()
    
    def _ensure_model_loaded(self) -> None:
        """Ensure the Whisper model is loaded"""
        if self._model is None or self._model_size != self.config.model_size:
            logger.info("Loading Whisper model", 
                       model_size=self.config.model_size,
                       device=self.config.device)
            
            try:
                # Determine device and compute type
                device = self._determine_device()
                compute_type = self._determine_compute_type(device)
                
                # Load model
                self._model = WhisperModel(
                    self.config.model_size,
                    device=device,
                    compute_type=compute_type
                )
                self._model_size = self.config.model_size
                
                logger.info("Whisper model loaded successfully", 
                           model_size=self.config.model_size,
                           device=device,
                           compute_type=compute_type)
                
            except Exception as e:
                error_msg = f"Failed to load Whisper model: {str(e)}"
                logger.error(error_msg)
                raise ProcessingError(error_msg)
    
    def _determine_device(self) -> str:
        """Determine the best device to use"""
        if self.config.device != "auto":
            return self.config.device
        
        # Auto-detect best device
        try:
            import torch
            if torch.cuda.is_available():
                logger.info("CUDA available, using GPU acceleration")
                return "cuda"
        except ImportError:
            pass
        
        logger.info("Using CPU for transcription")
        return "cpu"
    
    def _determine_compute_type(self, device: str) -> str:
        """Determine the best compute type for the device"""
        if self.config.compute_type != "auto":
            return self.config.compute_type
        
        # Auto-detect best compute type
        if device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    # Use float16 for GPU if available
                    return "float16"
            except ImportError:
                pass
        
        # Default to int8 for CPU or fallback
        return "int8"
    
    def _format_vtt_timestamp(self, seconds: float) -> str:
        """Format timestamp for VTT format (HH:MM:SS.mmm)"""
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = td.total_seconds() % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _save_transcription_files(self, result: TranscriptionResult, 
                                 output_dir: Union[str, Path], 
                                 base_name: str) -> None:
        """Save transcription files to disk"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save plain text
        txt_path = output_dir / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result.text)
        
        # Save VTT
        vtt_path = output_dir / f"{base_name}.vtt"
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(result.vtt_content)
        
        # Save detailed JSON
        json_path = output_dir / f"{base_name}_detailed.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info("Transcription files saved", 
                   output_dir=str(output_dir),
                   base_name=base_name,
                   files=['txt', 'vtt', 'json'])


class TranscriptionValidator:
    """
    Enhanced transcription validator with comprehensive quality assessment
    """
    
    def __init__(self, min_confidence: float = 0.3,
                 max_no_speech_ratio: float = 0.8,
                 min_words_per_minute: float = 50.0,
                 max_words_per_minute: float = 300.0,
                 max_duration_ratio_diff: float = 0.1,
                 max_repetition_ratio: float = 0.3,
                 min_text_length: int = 10):
        """
        Initialize enhanced transcription validator
        
        Args:
            min_confidence: Minimum acceptable confidence score
            max_no_speech_ratio: Maximum ratio of no-speech segments
            min_words_per_minute: Minimum expected words per minute
            max_words_per_minute: Maximum expected words per minute
            max_duration_ratio_diff: Maximum acceptable duration difference ratio
            max_repetition_ratio: Maximum acceptable word repetition ratio
            min_text_length: Minimum acceptable text length
        """
        self.min_confidence = min_confidence
        self.max_no_speech_ratio = max_no_speech_ratio
        self.min_words_per_minute = min_words_per_minute
        self.max_words_per_minute = max_words_per_minute
        self.max_duration_ratio_diff = max_duration_ratio_diff
        self.max_repetition_ratio = max_repetition_ratio
        self.min_text_length = min_text_length
        
        logger.info("Enhanced transcription validator initialized", 
                   min_confidence=min_confidence,
                   max_no_speech_ratio=max_no_speech_ratio,
                   min_wpm=min_words_per_minute,
                   max_wpm=max_words_per_minute,
                   max_duration_diff=max_duration_ratio_diff)
    
    def validate_transcription(self, result: TranscriptionResult, 
                             audio_duration: Optional[float] = None) -> ValidationResult:
        """
        Enhanced comprehensive validation of transcription results
        
        Args:
            result: Transcription result to validate
            audio_duration: Optional audio duration for validation
            
        Returns:
            ValidationResult: Detailed validation results with quality metrics
        """
        validation = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        logger.debug("Starting enhanced transcription validation")
        
        # Basic content validation
        self._validate_content(result, validation)
        
        # Confidence validation with enhanced metrics
        self._validate_confidence(result, validation)
        
        # Segment validation
        self._validate_segments(result, validation)
        
        # Duration validation
        if audio_duration:
            self._validate_duration_match(result, audio_duration, validation)
        
        # Enhanced quality metrics calculation
        self._calculate_enhanced_quality_metrics(result, validation, audio_duration)
        
        # Speech rate validation
        self._validate_speech_rate(result, validation)
        
        # Content quality validation
        self._validate_content_quality(result, validation)
        
        # Overall quality assessment
        self._assess_overall_quality(validation)
        
        logger.info("Enhanced transcription validation completed", 
                   is_valid=validation.is_valid,
                   errors=len(validation.errors),
                   warnings=len(validation.warnings),
                   confidence=result.confidence,
                   quality_score=validation.metrics.get('overall_quality_score', 0.0))
        
        return validation
    
    def _validate_content(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Enhanced validation of basic content requirements"""
        if not result.text or not result.text.strip():
            validation.add_error("Transcription text is empty")
            return
        
        if not result.vtt_content:
            validation.add_error("VTT content is missing")
        
        # Check for reasonable text length
        text_length = len(result.text.strip())
        validation.add_metric('text_length', text_length)
        
        if text_length < self.min_text_length:
            validation.add_error(f"Transcription text too short: {text_length} characters")
        elif text_length < self.min_text_length * 2:
            validation.add_warning("Transcription text is very short")
        
        # Word count analysis
        words = result.text.split()
        validation.add_metric('word_count', len(words))
        
        if len(words) == 0:
            validation.add_error("No words detected in transcription")
        elif len(words) < 5:
            validation.add_warning("Very few words detected in transcription")
        
        # Average word length
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            validation.add_metric('avg_word_length', avg_word_length)
        
        # Sentence analysis
        sentence_endings = result.text.count('.') + result.text.count('!') + result.text.count('?')
        validation.add_metric('estimated_sentences', sentence_endings)
        
        if sentence_endings > 0 and words:
            avg_words_per_sentence = len(words) / sentence_endings
            validation.add_metric('avg_words_per_sentence', avg_words_per_sentence)
    
    def _validate_confidence(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Validate confidence scores"""
        validation.add_metric('overall_confidence', result.confidence)
        
        if result.confidence < self.min_confidence:
            validation.add_error(f"Low transcription confidence: {result.confidence:.3f} < {self.min_confidence}")
        elif result.confidence < self.min_confidence + 0.2:
            validation.add_warning(f"Moderate transcription confidence: {result.confidence:.3f}")
        
        # Analyze segment-level confidence
        if result.segments:
            confidences = [seg.get('confidence', 0.0) for seg in result.segments]
            low_confidence_segments = sum(1 for conf in confidences if conf < self.min_confidence)
            low_confidence_ratio = low_confidence_segments / len(result.segments)
            
            validation.add_metric('low_confidence_segments', low_confidence_segments)
            validation.add_metric('low_confidence_ratio', low_confidence_ratio)
            
            if low_confidence_ratio > 0.5:
                validation.add_warning("Many segments have low confidence scores")
    
    def _validate_segments(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Validate segment structure and timing"""
        if not result.segments:
            validation.add_warning("No segments available for detailed analysis")
            return
        
        validation.add_metric('segment_count', len(result.segments))
        
        # Check segment timing consistency
        timing_issues = 0
        no_speech_segments = 0
        
        for i, segment in enumerate(result.segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            no_speech_prob = segment.get('no_speech_prob', 0)
            
            # Check timing validity
            if end <= start:
                timing_issues += 1
            
            # Check for no-speech segments
            if no_speech_prob > self.max_no_speech_ratio:
                no_speech_segments += 1
            
            # Check for overlapping segments
            if i > 0:
                prev_end = result.segments[i-1].get('end', 0)
                if start < prev_end:
                    timing_issues += 1
        
        validation.add_metric('timing_issues', timing_issues)
        validation.add_metric('no_speech_segments', no_speech_segments)
        
        if timing_issues > 0:
            validation.add_warning(f"Timing inconsistencies in {timing_issues} segments")
        
        no_speech_ratio = no_speech_segments / len(result.segments)
        validation.add_metric('no_speech_ratio', no_speech_ratio)
        
        if no_speech_ratio > self.max_no_speech_ratio:
            validation.add_warning(f"High ratio of no-speech segments: {no_speech_ratio:.2f}")
    
    def _validate_duration_match(self, result: TranscriptionResult, 
                               audio_duration: float, validation: ValidationResult) -> None:
        """Validate transcription duration matches audio duration"""
        if not result.segments:
            validation.add_warning("Cannot validate duration without segments")
            return
        
        # Calculate transcription duration from segments
        if result.segments:
            last_segment = result.segments[-1]
            transcription_duration = last_segment.get('end', 0)
        else:
            transcription_duration = 0
        
        duration_diff = abs(transcription_duration - audio_duration)
        duration_ratio = duration_diff / audio_duration if audio_duration > 0 else 0
        
        validation.add_metric('audio_duration', audio_duration)
        validation.add_metric('transcription_duration', transcription_duration)
        validation.add_metric('duration_difference', duration_diff)
        validation.add_metric('duration_ratio', duration_ratio)
        
        if duration_ratio > 0.1:  # More than 10% difference
            validation.add_warning(f"Duration mismatch: audio={audio_duration:.1f}s, "
                                 f"transcription={transcription_duration:.1f}s")
    
    def _calculate_quality_metrics(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Calculate various quality metrics"""
        if not result.text:
            return
        
        words = result.text.split()
        validation.add_metric('word_count', len(words))
        
        # Calculate average word length
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            validation.add_metric('avg_word_length', avg_word_length)
        
        # Count sentences (rough estimate)
        sentence_endings = result.text.count('.') + result.text.count('!') + result.text.count('?')
        validation.add_metric('estimated_sentences', sentence_endings)
        
        # Calculate readability metrics
        if words and sentence_endings > 0:
            avg_words_per_sentence = len(words) / sentence_endings
            validation.add_metric('avg_words_per_sentence', avg_words_per_sentence)
    
    def _validate_speech_rate(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Validate speech rate (words per minute)"""
        if not result.segments or not result.text:
            return
        
        # Calculate total speaking time (excluding silence)
        total_speaking_time = 0
        for segment in result.segments:
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            no_speech_prob = segment.get('no_speech_prob', 0)
            
            # Only count segments with actual speech
            if no_speech_prob < 0.8:  # Threshold for speech detection
                total_speaking_time += (end - start)
        
        if total_speaking_time > 0:
            words = result.text.split()
            words_per_minute = (len(words) / total_speaking_time) * 60
            
            validation.add_metric('words_per_minute', words_per_minute)
            validation.add_metric('speaking_time_seconds', total_speaking_time)
            
            if words_per_minute < self.min_words_per_minute:
                validation.add_warning(f"Very slow speech rate: {words_per_minute:.1f} WPM")
            elif words_per_minute > self.max_words_per_minute:
                validation.add_warning(f"Very fast speech rate: {words_per_minute:.1f} WPM")
    
    def _calculate_enhanced_quality_metrics(self, result: TranscriptionResult, 
                                          validation: ValidationResult,
                                          audio_duration: Optional[float] = None) -> None:
        """Calculate enhanced quality metrics"""
        
        # Confidence metrics
        if result.segments:
            confidences = [seg.get('confidence', 0.0) for seg in result.segments]
            if confidences:
                validation.add_metric('min_confidence', min(confidences))
                validation.add_metric('max_confidence', max(confidences))
                
                # Standard deviation of confidence
                if len(confidences) > 1:
                    import statistics
                    validation.add_metric('confidence_std', statistics.stdev(confidences))
                
                # Low confidence segments
                low_conf_segments = sum(1 for conf in confidences if conf < self.min_confidence)
                validation.add_metric('low_confidence_segments', low_conf_segments)
                validation.add_metric('low_confidence_ratio', low_conf_segments / len(confidences))
        
        # Duration metrics
        if audio_duration and result.segments:
            last_segment = result.segments[-1]
            transcription_duration = last_segment.get('end', 0)
            
            validation.add_metric('audio_duration', audio_duration)
            validation.add_metric('transcription_duration', transcription_duration)
            
            if transcription_duration > 0:
                duration_diff = abs(transcription_duration - audio_duration)
                duration_ratio = duration_diff / audio_duration
                validation.add_metric('duration_difference', duration_diff)
                validation.add_metric('duration_ratio', duration_ratio)
        
        # Speech timing metrics
        if result.segments:
            total_speaking_time = 0
            silence_time = 0
            
            for segment in result.segments:
                start = segment.get('start', 0)
                end = segment.get('end', 0)
                duration = end - start
                no_speech_prob = segment.get('no_speech_prob', 0)
                
                if no_speech_prob < 0.8:
                    total_speaking_time += duration
                else:
                    silence_time += duration
            
            total_time = total_speaking_time + silence_time
            if total_time > 0:
                silence_ratio = silence_time / total_time
                validation.add_metric('silence_ratio', silence_ratio)
                validation.add_metric('speaking_time_seconds', total_speaking_time)
    
    def _validate_content_quality(self, result: TranscriptionResult, validation: ValidationResult) -> None:
        """Validate content quality metrics"""
        if not result.text:
            return
        
        words = result.text.split()
        
        if len(words) > 10:
            # Analyze word repetition
            from collections import Counter
            word_counts = Counter(words)
            max_repetition = max(word_counts.values()) if word_counts else 0
            repetition_ratio = max_repetition / len(words) if words else 0
            
            validation.add_metric('max_word_repetition', max_repetition)
            validation.add_metric('repetition_ratio', repetition_ratio)
            
            if repetition_ratio > self.max_repetition_ratio:
                validation.add_warning(f"High word repetition detected: {repetition_ratio:.2f}")
    
    def _assess_overall_quality(self, validation: ValidationResult) -> None:
        """Assess overall transcription quality and assign quality score"""
        
        # Calculate content quality score (0-1)
        content_score = 1.0
        
        # Penalize for errors and warnings
        if validation.errors:
            content_score *= 0.3  # Severe penalty for errors
        
        warning_penalty = min(0.5, len(validation.warnings) * 0.1)
        content_score *= (1.0 - warning_penalty)
        
        # Confidence-based scoring
        overall_confidence = validation.metrics.get('overall_confidence', 0.0)
        if overall_confidence < self.min_confidence:
            content_score *= 0.5
        elif overall_confidence < 0.5:
            content_score *= 0.8
        
        # Repetition penalty
        repetition_ratio = validation.metrics.get('repetition_ratio', 0.0)
        if repetition_ratio > self.max_repetition_ratio:
            content_score *= (1.0 - repetition_ratio)
        
        # Duration mismatch penalty
        duration_ratio = validation.metrics.get('duration_ratio', 0.0)
        if duration_ratio > self.max_duration_ratio_diff:
            content_score *= (1.0 - min(0.5, duration_ratio))
        
        # Ensure score is between 0 and 1
        content_score = max(0.0, min(1.0, content_score))
        
        validation.add_metric('content_quality_score', content_score)
        validation.add_metric('overall_quality_score', content_score)
        
        # Quality assessment categories
        if content_score >= 0.8:
            validation.add_metric('quality_assessment', 'excellent')
        elif content_score >= 0.6:
            validation.add_metric('quality_assessment', 'good')
        elif content_score >= 0.4:
            validation.add_metric('quality_assessment', 'fair')
        else:
            validation.add_metric('quality_assessment', 'poor')
            
        # Add quality-based errors/warnings
        if content_score < 0.3:
            validation.add_error(f"Poor transcription quality: {content_score:.2f}")
        elif content_score < 0.6:
            validation.add_warning(f"Moderate transcription quality: {content_score:.2f}")


class EnhancedTranscriptionRetryHandler:
    """
    Enhanced retry handler with quality-based retry logic for failed transcriptions
    """
    
    def __init__(self, max_retries: int = 3, 
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_factor: float = 2.0,
                 quality_threshold: float = 0.4):
        """
        Initialize enhanced retry handler
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Exponential backoff factor
            quality_threshold: Minimum quality score to accept result
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.quality_threshold = quality_threshold
        
        logger.info("Enhanced transcription retry handler initialized", 
                   max_retries=max_retries,
                   base_delay=base_delay,
                   backoff_factor=backoff_factor,
                   quality_threshold=quality_threshold)
    
    def execute_with_retry(self, func, *args, **kwargs) -> Any:
        """
        Execute function with basic retry logic
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Any: Function result
            
        Raises:
            ProcessingError: If all retries fail
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = min(self.base_delay * (self.backoff_factor ** (attempt - 1)), self.max_delay)
                    logger.info(f"Retrying transcription (attempt {attempt + 1}/{self.max_retries + 1}) "
                               f"after {delay:.1f}s delay")
                    time.sleep(delay)
                
                return func(*args, **kwargs)
                
            except Exception as e:
                last_error = e
                logger.warning(f"Transcription attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.max_retries:
                    break
        
        # All retries failed
        error_msg = f"Transcription failed after {self.max_retries + 1} attempts. Last error: {str(last_error)}"
        logger.error(error_msg)
        raise ProcessingError(error_msg)
    
    def execute_with_quality_retry(self, transcribe_func, validator: TranscriptionValidator,
                                  audio_path: str, audio_duration: Optional[float] = None,
                                  **kwargs) -> Tuple[TranscriptionResult, ValidationResult]:
        """
        Execute transcription with quality-based retry logic
        
        Args:
            transcribe_func: Transcription function to execute
            validator: Validator to assess quality
            audio_path: Path to audio file
            audio_duration: Optional audio duration for validation
            **kwargs: Additional arguments for transcription function
            
        Returns:
            Tuple[TranscriptionResult, ValidationResult]: Best transcription result and validation
            
        Raises:
            ProcessingError: If all retries fail or quality is unacceptable
        """
        best_result = None
        best_validation = None
        best_quality_score = 0.0
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = min(self.base_delay * (self.backoff_factor ** (attempt - 1)), self.max_delay)
                    logger.info(f"Retrying transcription for quality (attempt {attempt + 1}/{self.max_retries + 1}) "
                               f"after {delay:.1f}s delay", audio_path=audio_path)
                    time.sleep(delay)
                
                # Perform transcription
                result = transcribe_func(audio_path, **kwargs)
                
                # Validate quality
                validation = validator.validate_transcription(result, audio_duration)
                quality_score = validation.metrics.get('overall_quality_score', 0.0)
                
                logger.info(f"Transcription attempt {attempt + 1} completed", 
                           quality_score=quality_score,
                           is_valid=validation.is_valid,
                           audio_path=audio_path)
                
                # Keep track of best result
                if quality_score > best_quality_score:
                    best_result = result
                    best_validation = validation
                    best_quality_score = quality_score
                
                # Check if quality is acceptable
                if quality_score >= self.quality_threshold and validation.is_valid:
                    logger.info("Acceptable transcription quality achieved", 
                               quality_score=quality_score,
                               attempt=attempt + 1)
                    return result, validation
                
                # If this is the last attempt, use best result
                if attempt == self.max_retries:
                    break
                
            except Exception as e:
                last_error = e
                logger.warning(f"Transcription attempt {attempt + 1} failed: {str(e)}", 
                              audio_path=audio_path)
                
                if attempt == self.max_retries:
                    break
        
        # Return best result if we have one, otherwise raise error
        if best_result and best_validation:
            if best_quality_score >= self.quality_threshold * 0.7:  # Accept lower quality if it's the best we got
                logger.warning("Returning best available transcription result", 
                              quality_score=best_quality_score,
                              audio_path=audio_path)
                return best_result, best_validation
        
        # All retries failed or quality unacceptable
        if last_error:
            error_msg = f"Transcription failed after {self.max_retries + 1} attempts. Last error: {str(last_error)}"
        else:
            error_msg = f"Transcription quality unacceptable after {self.max_retries + 1} attempts. Best score: {best_quality_score:.2f}"
        
        logger.error(error_msg, audio_path=audio_path)
        raise ProcessingError(error_msg)


class TranscriptionPipeline:
    """
    Complete transcription pipeline integrating all components with enhanced quality validation
    """
    
    def __init__(self, config: Optional[TranscriptionConfig] = None,
                 validator_config: Optional[Dict[str, Any]] = None,
                 retry_config: Optional[Dict[str, Any]] = None):
        """
        Initialize enhanced transcription pipeline
        
        Args:
            config: Transcription engine configuration
            validator_config: Validator configuration parameters
            retry_config: Retry handler configuration
        """
        self.config = config or TranscriptionConfig()
        
        # Initialize components with enhanced capabilities
        self.engine = TranscriptionEngine(self.config)
        
        validator_params = validator_config or {}
        self.validator = TranscriptionValidator(**validator_params)
        
        retry_params = retry_config or {}
        self.retry_handler = EnhancedTranscriptionRetryHandler(**retry_params)
        
        logger.info("Enhanced transcription pipeline initialized")
    
    def process_episode(self, episode: EpisodeObject, audio_file: AudioFile,
                       output_dir: Optional[Union[str, Path]] = None) -> Tuple[EpisodeObject, ValidationResult]:
        """
        Complete transcription processing for an episode with enhanced quality validation
        
        Args:
            episode: Episode object to process
            audio_file: Audio file to transcribe
            output_dir: Optional output directory for transcript files
            
        Returns:
            Tuple[EpisodeObject, ValidationResult]: Updated episode and validation results
            
        Raises:
            ProcessingError: If transcription processing fails
        """
        logger.info("Starting enhanced episode transcription", episode_id=episode.episode_id)
        
        try:
            # Update episode stage
            episode.update_stage(ProcessingStage.TRANSCRIBED)
            
            # Perform transcription with quality-based retry logic
            transcription_result, validation_result = self.retry_handler.execute_with_quality_retry(
                self.engine.transcribe_audio,
                self.validator,
                audio_file.path,
                audio_file.duration_seconds,
                output_dir=output_dir,
                episode_id=episode.episode_id
            )
            
            # Check if validation passed
            if not validation_result.is_valid:
                error_msg = f"Transcription validation failed: {'; '.join(validation_result.errors)}"
                episode.add_error(error_msg)
                logger.error(error_msg, episode_id=episode.episode_id)
                # Don't raise error - let caller decide how to handle validation failures
            
            # Update episode with transcription results
            episode.transcription = transcription_result
            
            # Clear any previous errors if transcription succeeded
            if validation_result.is_valid:
                episode.clear_errors()
            
            # Log quality metrics
            quality_score = validation_result.metrics.get('overall_quality_score', 0.0)
            quality_assessment = validation_result.metrics.get('quality_assessment', 'unknown')
            
            logger.info("Enhanced episode transcription completed", 
                       episode_id=episode.episode_id,
                       confidence=transcription_result.confidence,
                       quality_score=quality_score,
                       quality_assessment=quality_assessment,
                       text_length=len(transcription_result.text),
                       segments=len(transcription_result.segments),
                       is_valid=validation_result.is_valid)
            
            return episode, validation_result
            
        except Exception as e:
            error_msg = f"Enhanced episode transcription failed: {str(e)}"
            episode.add_error(error_msg)
            logger.error(error_msg, episode_id=episode.episode_id)
            raise ProcessingError(error_msg)