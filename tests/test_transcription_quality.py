"""
Tests for enhanced transcription quality validation functionality

Tests the enhanced transcription quality validation and retry logic.
"""

import pytest
from unittest.mock import Mock

from src.core.transcription import (
    TranscriptionValidator, EnhancedTranscriptionRetryHandler
)
from src.core.models import TranscriptionResult
from src.core.media_preparation import ValidationResult
from src.core.exceptions import ProcessingError


class TestEnhancedTranscriptionValidator:
    """Test enhanced transcription validator"""
    
    def setup_method(self):
        """Setup test validator"""
        self.validator = TranscriptionValidator(
            min_confidence=0.3,
            max_duration_ratio_diff=0.1,
            max_repetition_ratio=0.3,
            min_text_length=10
        )
    
    def create_sample_transcription(self, text="Hello world this is a test", 
                                  confidence=0.8, segments=None):
        """Create sample transcription result for testing"""
        if segments is None:
            segments = [
                {'start': 0.0, 'end': 2.0, 'text': 'Hello world', 'confidence': 0.9},
                {'start': 2.0, 'end': 4.0, 'text': 'this is a test', 'confidence': 0.7}
            ]
        
        return TranscriptionResult(
            text=text,
            vtt_content="WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nHello world\n\n",
            segments=segments,
            confidence=confidence,
            language="en",
            model_used="base"
        )
    
    def test_validation_with_good_quality(self):
        """Test validation with good quality transcription"""
        result = self.create_sample_transcription(confidence=0.8)
        validation = self.validator.validate_transcription(result, audio_duration=4.0)
        
        assert validation.is_valid
        assert len(validation.errors) == 0
        assert 'overall_quality_score' in validation.metrics
        assert validation.metrics['quality_assessment'] in ['excellent', 'good', 'fair']
        
        # Check enhanced metrics
        assert 'word_count' in validation.metrics
        assert 'text_length' in validation.metrics
        assert 'min_confidence' in validation.metrics
        assert 'max_confidence' in validation.metrics
    
    def test_validation_with_poor_confidence(self):
        """Test validation with poor confidence"""
        result = self.create_sample_transcription(confidence=0.2)
        validation = self.validator.validate_transcription(result)
        
        assert not validation.is_valid
        assert any('confidence' in error.lower() for error in validation.errors)
        assert validation.metrics.get('overall_quality_score', 1.0) < 0.5
    
    def test_validation_with_empty_text(self):
        """Test validation with empty text"""
        result = self.create_sample_transcription(text="", segments=[])
        validation = self.validator.validate_transcription(result)
        
        assert not validation.is_valid
        assert any('empty' in error.lower() for error in validation.errors)
    
    def test_validation_with_short_text(self):
        """Test validation with very short text"""
        result = self.create_sample_transcription(text="Hi", segments=[])
        validation = self.validator.validate_transcription(result)
        
        assert not validation.is_valid
        assert any('short' in error.lower() for error in validation.errors)
    
    def test_validation_with_duration_mismatch(self):
        """Test validation with significant duration mismatch"""
        result = self.create_sample_transcription()
        validation = self.validator.validate_transcription(result, audio_duration=10.0)
        
        # Should have warnings about duration mismatch
        assert any('duration' in warning.lower() for warning in validation.warnings)
        assert 'duration_ratio' in validation.metrics
    
    def test_validation_with_repetitive_text(self):
        """Test validation with highly repetitive text"""
        # Create text with more than 10 words to trigger repetition analysis
        repetitive_text = "test test test test test test test test test test other words"
        repetitive_segments = [
            {'start': 0.0, 'end': 5.0, 'text': repetitive_text, 'confidence': 0.8}
        ]
        result = self.create_sample_transcription(
            text=repetitive_text,
            segments=repetitive_segments
        )
        validation = self.validator.validate_transcription(result)
        
        # Should have warnings about repetition
        assert any('repetition' in warning.lower() for warning in validation.warnings)
        assert validation.metrics.get('repetition_ratio', 0) > 0.3
    
    def test_enhanced_quality_metrics(self):
        """Test enhanced quality metrics calculation"""
        result = self.create_sample_transcription(confidence=0.8)
        validation = self.validator.validate_transcription(result, audio_duration=4.0)
        
        # Check that enhanced metrics are calculated
        expected_metrics = [
            'text_length', 'word_count', 'avg_word_length', 'estimated_sentences',
            'min_confidence', 'max_confidence', 'confidence_std',
            'audio_duration', 'transcription_duration', 'duration_difference',
            'silence_ratio', 'speaking_time_seconds', 'words_per_minute',
            'overall_quality_score', 'quality_assessment'
        ]
        
        for metric in expected_metrics:
            assert metric in validation.metrics, f"Missing metric: {metric}"
        
        # Note: repetition_ratio is only calculated for texts with >10 words


class TestEnhancedTranscriptionRetryHandler:
    """Test enhanced transcription retry handler"""
    
    def setup_method(self):
        """Setup test retry handler"""
        self.retry_handler = EnhancedTranscriptionRetryHandler(
            max_retries=2,
            base_delay=0.01,  # Very short delay for testing
            quality_threshold=0.6
        )
        self.validator = TranscriptionValidator()
    
    def create_sample_transcription(self, confidence=0.8):
        """Create sample transcription result for testing"""
        return TranscriptionResult(
            text="Hello world this is a test transcription",
            vtt_content="WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nHello world\n\n",
            segments=[
                {'start': 0.0, 'end': 2.0, 'text': 'Hello world', 'confidence': confidence},
                {'start': 2.0, 'end': 4.0, 'text': 'this is a test transcription', 'confidence': confidence}
            ],
            confidence=confidence,
            language="en",
            model_used="base"
        )
    
    def test_successful_transcription_on_first_try(self):
        """Test successful transcription on first attempt"""
        def mock_transcribe(audio_path, **kwargs):
            return self.create_sample_transcription(confidence=0.8)
        
        result, validation = self.retry_handler.execute_with_quality_retry(
            mock_transcribe, self.validator, "test.wav", audio_duration=4.0
        )
        
        assert result is not None
        assert validation.is_valid
        assert result.confidence == 0.8
        assert validation.metrics.get('overall_quality_score', 0) >= 0.6
    
    def test_retry_with_improving_quality(self):
        """Test retry logic with improving quality"""
        attempt_count = 0
        
        def mock_transcribe(audio_path, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            # First attempt poor, second attempt good
            confidence = 0.1 if attempt_count == 1 else 0.8
            return self.create_sample_transcription(confidence=confidence)
        
        result, validation = self.retry_handler.execute_with_quality_retry(
            mock_transcribe, self.validator, "test.wav", audio_duration=4.0
        )
        
        assert attempt_count == 2  # Should retry once
        assert result.confidence == 0.8  # Should get the better result
        assert validation.metrics.get('overall_quality_score', 0) >= 0.6
    
    def test_retry_exhaustion_with_poor_quality(self):
        """Test retry exhaustion with consistently poor quality"""
        def mock_transcribe(audio_path, **kwargs):
            return self.create_sample_transcription(confidence=0.1)  # Always very poor
        
        with pytest.raises(ProcessingError) as exc_info:
            self.retry_handler.execute_with_quality_retry(
                mock_transcribe, self.validator, "test.wav", audio_duration=4.0
            )
        
        assert "quality unacceptable" in str(exc_info.value).lower()
    
    def test_basic_retry_functionality(self):
        """Test basic retry functionality without quality assessment"""
        attempt_count = 0
        
        def mock_transcribe(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("Transcription failed")
            return self.create_sample_transcription(confidence=0.8)
        
        result = self.retry_handler.execute_with_retry(mock_transcribe, "test.wav")
        
        assert attempt_count == 2  # Should retry once after exception
        assert result.confidence == 0.8


class TestIntegration:
    """Integration tests for enhanced transcription quality components"""
    
    def test_end_to_end_quality_validation(self):
        """Test complete enhanced quality validation workflow"""
        # Create a realistic transcription result
        segments = [
            {'start': 0.0, 'end': 2.5, 'text': 'Welcome to our podcast', 'confidence': 0.85, 'no_speech_prob': 0.1},
            {'start': 2.5, 'end': 5.0, 'text': 'Today we discuss technology', 'confidence': 0.78, 'no_speech_prob': 0.15},
            {'start': 5.0, 'end': 7.5, 'text': 'and its impact on society', 'confidence': 0.82, 'no_speech_prob': 0.12}
        ]
        
        result = TranscriptionResult(
            text="Welcome to our podcast Today we discuss technology and its impact on society",
            vtt_content="WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.500\nWelcome to our podcast\n\n",
            segments=segments,
            confidence=0.82,
            language="en",
            model_used="base"
        )
        
        # Validate with enhanced validator
        validator = TranscriptionValidator()
        validation = validator.validate_transcription(result, audio_duration=7.8)
        
        # Assertions
        assert validation.metrics['word_count'] == 13
        assert validation.metrics['segment_count'] == 3
        assert validation.metrics['overall_confidence'] == 0.82
        assert abs(validation.metrics['duration_difference'] - 0.3) < 0.1  # 7.8 - 7.5
        assert validation.metrics['words_per_minute'] > 0
        
        assert validation.is_valid
        assert validation.metrics['overall_quality_score'] > 0.6  # Should be good quality
        assert validation.metrics['quality_assessment'] in ['good', 'excellent']
    
    def test_poor_quality_detection(self):
        """Test detection of poor quality transcription"""
        # Create a poor quality transcription
        poor_segments = [
            {'start': 0.0, 'end': 1.0, 'text': 'um um um', 'confidence': 0.1, 'no_speech_prob': 0.9}
        ]
        
        poor_result = TranscriptionResult(
            text="um um um",
            vtt_content="WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\num um um\n\n",
            segments=poor_segments,
            confidence=0.1,
            language="en",
            model_used="base"
        )
        
        validator = TranscriptionValidator()
        validation = validator.validate_transcription(poor_result, audio_duration=1.0)
        
        # Should detect poor quality
        assert not validation.is_valid
        assert validation.metrics['overall_quality_score'] < 0.4
        assert validation.metrics['quality_assessment'] == 'poor'
        assert len(validation.errors) > 0