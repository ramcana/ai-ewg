"""
Tests for the TranscriptionEngine core functionality

Tests the main TranscriptionEngine class and TranscriptionPipeline.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from src.core.transcription import (
    TranscriptionEngine, TranscriptionConfig, TranscriptionPipeline,
    TranscriptionSegment
)
from src.core.models import TranscriptionResult, EpisodeObject, ProcessingStage
from src.core.media_preparation import AudioFile
from src.core.exceptions import ProcessingError


class TestTranscriptionSegment:
    """Test TranscriptionSegment functionality"""
    
    def test_segment_creation(self):
        """Test creating a transcription segment"""
        segment = TranscriptionSegment(
            start=0.0,
            end=2.5,
            text="Hello world",
            confidence=0.8,
            no_speech_prob=0.1
        )
        
        assert segment.start == 0.0
        assert segment.end == 2.5
        assert segment.text == "Hello world"
        assert segment.confidence == 0.8
        assert segment.no_speech_prob == 0.1
    
    def test_segment_duration(self):
        """Test segment duration calculation"""
        segment = TranscriptionSegment(start=1.0, end=3.5, text="test")
        assert segment.duration() == 2.5
    
    def test_segment_to_dict(self):
        """Test segment dictionary conversion"""
        segment = TranscriptionSegment(
            start=0.0, end=2.0, text="test", confidence=0.9
        )
        
        result = segment.to_dict()
        expected = {
            'start': 0.0,
            'end': 2.0,
            'text': 'test',
            'confidence': 0.9,
            'no_speech_prob': 0.0
        }
        assert result == expected


class TestTranscriptionConfig:
    """Test TranscriptionConfig functionality"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = TranscriptionConfig()
        
        assert config.model_size == "base"
        assert config.device == "auto"
        assert config.beam_size == 5
        assert config.temperature == 0.0
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = TranscriptionConfig(
            model_size="large",
            device="cpu",
            beam_size=10,
            temperature=0.2
        )
        
        assert config.model_size == "large"
        assert config.device == "cpu"
        assert config.beam_size == 10
        assert config.temperature == 0.2


class TestTranscriptionEngine:
    """Test TranscriptionEngine functionality"""
    
    def setup_method(self):
        """Setup test engine"""
        # Mock faster_whisper availability
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            self.config = TranscriptionConfig(model_size="base")
            self.engine = TranscriptionEngine(self.config)
    
    def test_engine_initialization(self):
        """Test engine initialization"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            config = TranscriptionConfig(model_size="base")
            engine = TranscriptionEngine(config)
            
            assert engine.config.model_size == "base"
            assert engine._model is None
            assert engine._model_size is None
    
    def test_engine_initialization_without_faster_whisper(self):
        """Test engine initialization fails without faster-whisper"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', False):
            with pytest.raises(ProcessingError) as exc_info:
                TranscriptionEngine()
            
            assert "faster-whisper is not available" in str(exc_info.value)
    
    def test_invalid_model_size(self):
        """Test initialization with invalid model size"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            config = TranscriptionConfig(model_size="invalid")
            
            with pytest.raises(ProcessingError) as exc_info:
                TranscriptionEngine(config)
            
            assert "Invalid model size" in str(exc_info.value)
    
    def test_generate_vtt(self):
        """Test VTT generation"""
        segments = [
            TranscriptionSegment(0.0, 2.0, "Hello world"),
            TranscriptionSegment(2.0, 4.0, "This is a test")
        ]
        
        vtt_content = self.engine.generate_vtt(segments)
        
        assert vtt_content.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:02.000" in vtt_content
        assert "Hello world" in vtt_content
        assert "00:00:02.000 --> 00:00:04.000" in vtt_content
        assert "This is a test" in vtt_content
    
    def test_generate_txt(self):
        """Test plain text generation"""
        segments = [
            TranscriptionSegment(0.0, 2.0, "Hello world"),
            TranscriptionSegment(2.0, 4.0, "This is a test")
        ]
        
        txt_content = self.engine.generate_txt(segments)
        
        assert txt_content == "Hello world This is a test"
    
    def test_determine_device_auto_cpu(self):
        """Test device determination when CUDA not available"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            engine = TranscriptionEngine(TranscriptionConfig(device="auto"))
            
            with patch('builtins.__import__', side_effect=ImportError):
                device = engine._determine_device()
                assert device == "cpu"
    
    def test_determine_device_explicit(self):
        """Test explicit device setting"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            engine = TranscriptionEngine(TranscriptionConfig(device="cpu"))
            device = engine._determine_device()
            assert device == "cpu"
    
    def test_determine_compute_type_auto(self):
        """Test compute type determination"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            engine = TranscriptionEngine(TranscriptionConfig(compute_type="auto"))
            
            # Test CPU fallback
            compute_type = engine._determine_compute_type("cpu")
            assert compute_type == "int8"
    
    def test_format_vtt_timestamp(self):
        """Test VTT timestamp formatting"""
        # Test various timestamp values
        assert self.engine._format_vtt_timestamp(0.0) == "00:00:00.000"
        assert self.engine._format_vtt_timestamp(65.5) == "00:01:05.500"
        assert self.engine._format_vtt_timestamp(3661.123) == "01:01:01.123"
    
    @patch('src.core.transcription.WhisperModel')
    def test_transcribe_audio_file_not_found(self, mock_whisper_model):
        """Test transcription with non-existent file"""
        with pytest.raises(ProcessingError) as exc_info:
            self.engine.transcribe_audio("nonexistent.wav")
        
        assert "Audio file not found" in str(exc_info.value)
    
    def test_save_transcription_files(self):
        """Test saving transcription files"""
        result = TranscriptionResult(
            text="Hello world",
            vtt_content="WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nHello world\n\n",
            segments=[{'start': 0.0, 'end': 2.0, 'text': 'Hello world'}],
            confidence=0.8,
            language="en",
            model_used="base"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            self.engine._save_transcription_files(result, temp_dir, "test")
            
            # Check files were created
            txt_file = Path(temp_dir) / "test.txt"
            vtt_file = Path(temp_dir) / "test.vtt"
            json_file = Path(temp_dir) / "test_detailed.json"
            
            assert txt_file.exists()
            assert vtt_file.exists()
            assert json_file.exists()
            
            # Check content
            assert txt_file.read_text(encoding='utf-8') == "Hello world"
            assert "WEBVTT" in vtt_file.read_text(encoding='utf-8')


class TestTranscriptionPipeline:
    """Test TranscriptionPipeline functionality"""
    
    def setup_method(self):
        """Setup test pipeline"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            self.pipeline = TranscriptionPipeline()
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            pipeline = TranscriptionPipeline()
            
            assert pipeline.engine is not None
            assert pipeline.validator is not None
            assert pipeline.retry_handler is not None
    
    def test_pipeline_with_custom_config(self):
        """Test pipeline with custom configuration"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            config = TranscriptionConfig(model_size="large")
            validator_config = {'min_confidence': 0.5}
            retry_config = {'max_retries': 5}
            
            pipeline = TranscriptionPipeline(
                config=config,
                validator_config=validator_config,
                retry_config=retry_config
            )
            
            assert pipeline.config.model_size == "large"
            assert pipeline.validator.min_confidence == 0.5
            assert pipeline.retry_handler.max_retries == 5


class TestWhisperIntegration:
    """Test Whisper integration with sample audio"""
    
    def setup_method(self):
        """Setup test engine with mocked Whisper"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            self.config = TranscriptionConfig(model_size="base")
            self.engine = TranscriptionEngine(self.config)
    
    @patch('src.core.transcription.WhisperModel')
    def test_whisper_model_loading(self, mock_whisper_model):
        """Test Whisper model loading and initialization"""
        # Mock the model instance
        mock_model_instance = Mock()
        mock_whisper_model.return_value = mock_model_instance
        
        # Force model loading
        self.engine._ensure_model_loaded()
        
        # Verify model was created with correct parameters (device detection is automatic)
        mock_whisper_model.assert_called_once()
        call_args = mock_whisper_model.call_args
        
        # Verify model size is correct
        assert call_args[0][0] == "base"
        
        # Verify device is either cpu or cuda
        assert call_args[1]['device'] in ['cpu', 'cuda']
        
        # Verify compute type is appropriate for device
        if call_args[1]['device'] == 'cuda':
            assert call_args[1]['compute_type'] == 'float16'
        else:
            assert call_args[1]['compute_type'] == 'int8'
        
        assert self.engine._model == mock_model_instance
        assert self.engine._model_size == "base"
    
    @patch('src.core.transcription.WhisperModel')
    def test_whisper_transcription_with_sample_audio(self, mock_whisper_model):
        """Test Whisper integration with sample audio transcription"""
        # Create mock segments that Whisper would return
        mock_segment1 = Mock()
        mock_segment1.start = 0.0
        mock_segment1.end = 2.5
        mock_segment1.text = " Hello world, this is a test."
        mock_segment1.avg_logprob = -0.2
        mock_segment1.no_speech_prob = 0.1
        
        mock_segment2 = Mock()
        mock_segment2.start = 2.5
        mock_segment2.end = 5.0
        mock_segment2.text = " We are testing transcription quality."
        mock_segment2.avg_logprob = -0.3
        mock_segment2.no_speech_prob = 0.15
        
        # Mock transcription info
        mock_info = Mock()
        mock_info.language = "en"
        
        # Mock model instance and its transcribe method
        mock_model_instance = Mock()
        mock_model_instance.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)
        mock_whisper_model.return_value = mock_model_instance
        
        # Create a temporary audio file for testing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio.write(b"fake audio data")
            temp_audio_path = temp_audio.name
        
        try:
            # Perform transcription
            result = self.engine.transcribe_audio(temp_audio_path)
            
            # Verify transcription result
            assert result.text == "Hello world, this is a test. We are testing transcription quality."
            assert result.language == "en"
            assert result.model_used == "base"
            assert len(result.segments) == 2
            
            # Verify segments
            assert result.segments[0]['start'] == 0.0
            assert result.segments[0]['end'] == 2.5
            assert result.segments[0]['text'] == "Hello world, this is a test."
            assert result.segments[0]['confidence'] == -0.2
            
            assert result.segments[1]['start'] == 2.5
            assert result.segments[1]['end'] == 5.0
            assert result.segments[1]['text'] == "We are testing transcription quality."
            assert result.segments[1]['confidence'] == -0.3
            
            # Verify overall confidence (average)
            expected_confidence = (-0.2 + -0.3) / 2
            assert result.confidence == expected_confidence
            
            # Verify VTT content is generated
            assert result.vtt_content.startswith("WEBVTT")
            assert "Hello world, this is a test." in result.vtt_content
            assert "We are testing transcription quality." in result.vtt_content
            assert "00:00:00.000 --> 00:00:02.500" in result.vtt_content
            assert "00:00:02.500 --> 00:00:05.000" in result.vtt_content
            
        finally:
            # Clean up temporary file
            os.unlink(temp_audio_path)
    
    @patch('src.core.transcription.WhisperModel')
    def test_whisper_gpu_acceleration_detection(self, mock_whisper_model):
        """Test GPU acceleration detection and fallback"""
        mock_model_instance = Mock()
        mock_whisper_model.return_value = mock_model_instance
        
        # Test CUDA detection
        with patch('builtins.__import__') as mock_import:
            mock_torch = Mock()
            mock_torch.cuda.is_available.return_value = True
            mock_import.return_value = mock_torch
            
            device = self.engine._determine_device()
            assert device == "cuda"
            
            compute_type = self.engine._determine_compute_type("cuda")
            assert compute_type == "float16"
        
        # Test CPU fallback
        with patch('builtins.__import__', side_effect=ImportError):
            device = self.engine._determine_device()
            assert device == "cpu"
            
            compute_type = self.engine._determine_compute_type("cpu")
            assert compute_type == "int8"
    
    @patch('src.core.transcription.WhisperModel')
    def test_whisper_model_error_handling(self, mock_whisper_model):
        """Test Whisper model loading error handling"""
        # Mock model loading failure
        mock_whisper_model.side_effect = Exception("Model loading failed")
        
        with pytest.raises(ProcessingError) as exc_info:
            self.engine._ensure_model_loaded()
        
        assert "Failed to load Whisper model" in str(exc_info.value)
        assert "Model loading failed" in str(exc_info.value)


class TestOutputFormatGeneration:
    """Test output format generation (VTT and TXT)"""
    
    def setup_method(self):
        """Setup test engine"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            self.engine = TranscriptionEngine()
    
    def test_vtt_format_generation(self):
        """Test VTT caption file format generation"""
        segments = [
            TranscriptionSegment(0.0, 2.5, "Welcome to our podcast today.", 0.9),
            TranscriptionSegment(2.5, 5.0, "We'll discuss technology trends.", 0.8),
            TranscriptionSegment(5.0, 7.5, "And their impact on society.", 0.85)
        ]
        
        vtt_content = self.engine.generate_vtt(segments)
        lines = vtt_content.split('\n')
        
        # Verify VTT header
        assert lines[0] == "WEBVTT"
        assert lines[1] == ""
        
        # Verify first segment
        assert lines[2] == "1"
        assert lines[3] == "00:00:00.000 --> 00:00:02.500"
        assert lines[4] == "Welcome to our podcast today."
        assert lines[5] == ""
        
        # Verify second segment
        assert lines[6] == "2"
        assert lines[7] == "00:00:02.500 --> 00:00:05.000"
        assert lines[8] == "We'll discuss technology trends."
        assert lines[9] == ""
        
        # Verify third segment
        assert lines[10] == "3"
        assert lines[11] == "00:00:05.000 --> 00:00:07.500"
        assert lines[12] == "And their impact on society."
        assert lines[13] == ""
    
    def test_txt_format_generation(self):
        """Test plain text transcript generation"""
        segments = [
            TranscriptionSegment(0.0, 2.0, "First sentence.", 0.9),
            TranscriptionSegment(2.0, 4.0, "Second sentence.", 0.8),
            TranscriptionSegment(4.0, 6.0, "Third sentence.", 0.85)
        ]
        
        txt_content = self.engine.generate_txt(segments)
        
        assert txt_content == "First sentence. Second sentence. Third sentence."
    
    def test_vtt_timestamp_formatting_precision(self):
        """Test VTT timestamp formatting with various precision requirements"""
        test_cases = [
            (0.0, "00:00:00.000"),
            (0.001, "00:00:00.001"),
            (0.999, "00:00:00.999"),
            (1.0, "00:00:01.000"),
            (59.999, "00:00:59.999"),
            (60.0, "00:01:00.000"),
            (3661.123, "01:01:01.123"),
            (7200.5, "02:00:00.500")
        ]
        
        for seconds, expected in test_cases:
            result = self.engine._format_vtt_timestamp(seconds)
            assert result == expected, f"Failed for {seconds}s: got {result}, expected {expected}"
    
    def test_empty_segments_handling(self):
        """Test handling of empty segments in format generation"""
        empty_segments = []
        
        vtt_content = self.engine.generate_vtt(empty_segments)
        assert vtt_content == "WEBVTT\n"
        
        txt_content = self.engine.generate_txt(empty_segments)
        assert txt_content == ""
    
    def test_special_characters_in_segments(self):
        """Test handling of special characters in segment text"""
        segments = [
            TranscriptionSegment(0.0, 2.0, "Text with \"quotes\" and 'apostrophes'.", 0.9),
            TranscriptionSegment(2.0, 4.0, "Unicode: café, naïve, résumé.", 0.8),
            TranscriptionSegment(4.0, 6.0, "Symbols: $100, 50% & more!", 0.85)
        ]
        
        vtt_content = self.engine.generate_vtt(segments)
        txt_content = self.engine.generate_txt(segments)
        
        # Verify special characters are preserved
        assert "\"quotes\"" in vtt_content
        assert "'apostrophes'" in vtt_content
        assert "café" in vtt_content
        assert "$100" in vtt_content
        assert "50%" in vtt_content
        
        assert "\"quotes\"" in txt_content
        assert "café" in txt_content
        assert "$100" in txt_content


class TestQualityValidationLogic:
    """Test transcription quality validation logic"""
    
    def setup_method(self):
        """Setup test validator"""
        from src.core.transcription import TranscriptionValidator
        self.validator = TranscriptionValidator(
            min_confidence=0.3,
            max_no_speech_ratio=0.8,
            min_words_per_minute=50.0,
            max_words_per_minute=300.0
        )
    
    def create_test_transcription(self, text="Hello world test", confidence=0.8, segments=None):
        """Create test transcription result"""
        if segments is None:
            segments = [
                {'start': 0.0, 'end': 2.0, 'text': text, 'confidence': confidence, 'no_speech_prob': 0.1}
            ]
        
        return TranscriptionResult(
            text=text,
            vtt_content=f"WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n{text}\n\n",
            segments=segments,
            confidence=confidence,
            language="en",
            model_used="base"
        )
    
    def test_quality_validation_with_good_transcription(self):
        """Test quality validation with high-quality transcription"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'Welcome to our show', 'confidence': 0.9, 'no_speech_prob': 0.05},
            {'start': 2.0, 'end': 4.0, 'text': 'Today we discuss technology', 'confidence': 0.85, 'no_speech_prob': 0.1}
        ]
        
        result = self.create_test_transcription(
            text="Welcome to our show Today we discuss technology",
            confidence=0.875,
            segments=segments
        )
        
        validation = self.validator.validate_transcription(result, audio_duration=4.0)
        
        assert validation.is_valid
        assert len(validation.errors) == 0
        assert validation.metrics['overall_confidence'] == 0.875
        assert validation.metrics['word_count'] == 8  # "Welcome to our show Today we discuss technology" = 8 words
        assert validation.metrics['segment_count'] == 2
    
    def test_quality_validation_with_low_confidence(self):
        """Test quality validation with low confidence transcription"""
        result = self.create_test_transcription(
            text="unclear mumbled speech",
            confidence=0.1  # Below minimum threshold
        )
        
        validation = self.validator.validate_transcription(result)
        
        assert not validation.is_valid
        assert any('confidence' in error.lower() for error in validation.errors)
        assert validation.metrics['overall_confidence'] == 0.1
    
    def test_quality_validation_with_empty_text(self):
        """Test quality validation with empty transcription"""
        result = self.create_test_transcription(text="", segments=[])
        
        validation = self.validator.validate_transcription(result)
        
        assert not validation.is_valid
        assert any('empty' in error.lower() for error in validation.errors)
    
    def test_quality_validation_with_duration_mismatch(self):
        """Test quality validation with audio duration mismatch"""
        result = self.create_test_transcription(
            text="Short transcription",
            segments=[{'start': 0.0, 'end': 2.0, 'text': 'Short transcription', 'confidence': 0.8}]
        )
        
        # Audio is much longer than transcription
        validation = self.validator.validate_transcription(result, audio_duration=10.0)
        
        # Should have warnings about duration mismatch
        assert any('duration' in warning.lower() for warning in validation.warnings)
        assert validation.metrics['duration_difference'] == 8.0  # 10.0 - 2.0
        assert validation.metrics['duration_ratio'] == 0.8  # 8.0 / 10.0
    
    def test_quality_validation_speech_rate_analysis(self):
        """Test speech rate analysis in quality validation"""
        # Create transcription with normal speech rate (18 words in 20 seconds = 54 WPM)
        segments = [
            {'start': 0.0, 'end': 20.0, 'text': 'This is a normal speech rate with eighteen words in twenty seconds which should be acceptable for testing', 'confidence': 0.8, 'no_speech_prob': 0.1}
        ]
        
        result = self.create_test_transcription(
            text="This is a normal speech rate with eighteen words in twenty seconds which should be acceptable for testing",
            segments=segments
        )
        
        validation = self.validator.validate_transcription(result)
        
        # Should calculate words per minute
        assert 'words_per_minute' in validation.metrics
        assert 'speaking_time_seconds' in validation.metrics
        
        # Should be within acceptable range (50-300 WPM)
        wpm = validation.metrics['words_per_minute']
        assert 50 <= wpm <= 300
    
    def test_quality_validation_no_speech_segments(self):
        """Test quality validation with high no-speech probability segments"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'Some speech', 'confidence': 0.8, 'no_speech_prob': 0.1},
            {'start': 2.0, 'end': 4.0, 'text': '', 'confidence': 0.1, 'no_speech_prob': 0.9},  # High no-speech
            {'start': 4.0, 'end': 6.0, 'text': '', 'confidence': 0.1, 'no_speech_prob': 0.95}  # High no-speech
        ]
        
        result = self.create_test_transcription(
            text="Some speech",
            segments=segments
        )
        
        validation = self.validator.validate_transcription(result)
        
        assert 'no_speech_segments' in validation.metrics
        assert 'no_speech_ratio' in validation.metrics
        assert validation.metrics['no_speech_segments'] == 2
        assert validation.metrics['no_speech_ratio'] == 2/3  # 2 out of 3 segments


class TestIntegration:
    """Integration tests for transcription components"""
    
    def test_vtt_timestamp_formatting_edge_cases(self):
        """Test VTT timestamp formatting with edge cases"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            engine = TranscriptionEngine()
            
            # Test edge cases
            assert engine._format_vtt_timestamp(0.001) == "00:00:00.001"
            assert engine._format_vtt_timestamp(59.999) == "00:00:59.999"
            assert engine._format_vtt_timestamp(3599.999) == "00:59:59.999"
    
    def test_segment_processing_workflow(self):
        """Test complete segment processing workflow"""
        with patch('src.core.transcription.FASTER_WHISPER_AVAILABLE', True):
            engine = TranscriptionEngine()
            
            # Create test segments
            segments = [
                TranscriptionSegment(0.0, 1.5, "First segment", 0.9),
                TranscriptionSegment(1.5, 3.0, "Second segment", 0.8),
                TranscriptionSegment(3.0, 4.5, "Third segment", 0.7)
            ]
            
            # Generate outputs
            vtt_content = engine.generate_vtt(segments)
            txt_content = engine.generate_txt(segments)
            
            # Verify VTT structure
            lines = vtt_content.split('\n')
            assert lines[0] == "WEBVTT"
            assert "First segment" in vtt_content
            assert "Second segment" in vtt_content
            assert "Third segment" in vtt_content
            
            # Verify text content
            assert txt_content == "First segment Second segment Third segment"