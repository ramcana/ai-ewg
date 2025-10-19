"""
Media Preparation Engine for the Video Processing Pipeline

Handles audio extraction, file staging, media validation, and cleanup operations.
Provides comprehensive media health checks and quality assessment.
"""

import os
import shutil
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from datetime import datetime

from .exceptions import ProcessingError, ValidationError
from .logging import get_logger
from .models import MediaInfo, EpisodeObject, ProcessingStage

logger = get_logger('pipeline.media_preparation')


@dataclass
class AudioFile:
    """Represents an extracted audio file"""
    path: str
    format: str
    duration_seconds: float
    sample_rate: int
    channels: int
    bitrate: Optional[int] = None
    size_bytes: int = 0
    
    def __post_init__(self):
        if os.path.exists(self.path):
            self.size_bytes = os.path.getsize(self.path)


@dataclass
class ValidationResult:
    """Result of media validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.metrics is None:
            self.metrics = {}
    
    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)
    
    def add_metric(self, key: str, value: Any) -> None:
        """Add a validation metric"""
        self.metrics[key] = value


class MediaPreparationEngine:
    """
    Handles media preparation including audio extraction, staging, and validation
    """
    
    def __init__(self, staging_path: str = "staging", cleanup_enabled: bool = True):
        """
        Initialize the media preparation engine
        
        Args:
            staging_path: Path to staging directory for temporary files
            cleanup_enabled: Whether to automatically cleanup temporary files
        """
        self.staging_path = Path(staging_path)
        self.cleanup_enabled = cleanup_enabled
        self.temp_files: List[str] = []
        
        # Create staging directory if it doesn't exist
        self.staging_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("Media preparation engine initialized", 
                   staging_path=str(self.staging_path),
                   cleanup_enabled=cleanup_enabled)
    
    def extract_audio(self, video_path: Union[str, Path], 
                     output_path: Optional[Union[str, Path]] = None,
                     format: str = "wav") -> AudioFile:
        """
        Extract audio from video file using FFmpeg
        
        Args:
            video_path: Path to source video file
            output_path: Optional output path for audio file
            format: Audio format (wav, mp3, flac)
            
        Returns:
            AudioFile: Information about extracted audio file
            
        Raises:
            ProcessingError: If audio extraction fails
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise ProcessingError(f"Video file not found: {video_path}")
        
        # Generate output path if not provided
        if output_path is None:
            output_path = self.staging_path / f"{video_path.stem}_audio.{format}"
        else:
            output_path = Path(output_path)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting audio extraction", 
                   video_path=str(video_path),
                   output_path=str(output_path),
                   format=format)
        
        try:
            # Build FFmpeg command for audio extraction
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
                "-ar", "16000",  # 16kHz sample rate for speech recognition
                "-ac", "1",      # Mono channel
                "-y",            # Overwrite output file
                str(output_path)
            ]
            
            # Execute FFmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"FFmpeg failed: {result.stderr}"
                logger.error("Audio extraction failed", 
                           video_path=str(video_path),
                           error=error_msg)
                raise ProcessingError(error_msg)
            
            # Get audio file information
            audio_info = self._get_audio_info(output_path)
            
            # Create AudioFile object
            audio_file = AudioFile(
                path=str(output_path),
                format=format,
                duration_seconds=audio_info.get('duration', 0.0),
                sample_rate=audio_info.get('sample_rate', 16000),
                channels=audio_info.get('channels', 1),
                bitrate=audio_info.get('bitrate')
            )
            
            # Track for cleanup
            self.temp_files.append(str(output_path))
            
            logger.info("Audio extraction completed", 
                       video_path=str(video_path),
                       output_path=str(output_path),
                       duration=audio_file.duration_seconds,
                       size_mb=audio_file.size_bytes / (1024 * 1024))
            
            return audio_file
            
        except subprocess.TimeoutExpired:
            error_msg = "Audio extraction timed out"
            logger.error(error_msg, video_path=str(video_path))
            raise ProcessingError(error_msg)
        except Exception as e:
            error_msg = f"Audio extraction failed: {str(e)}"
            logger.error(error_msg, video_path=str(video_path))
            raise ProcessingError(error_msg)
    
    def copy_to_staging(self, source_path: Union[str, Path], 
                       staging_name: Optional[str] = None) -> str:
        """
        Copy file to staging area for processing
        
        Args:
            source_path: Path to source file
            staging_name: Optional name for staged file
            
        Returns:
            str: Path to staged file
            
        Raises:
            ProcessingError: If copy operation fails
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            raise ProcessingError(f"Source file not found: {source_path}")
        
        # Generate staging filename
        if staging_name is None:
            staging_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_path.name}"
        
        staging_file = self.staging_path / staging_name
        
        logger.info("Copying file to staging", 
                   source=str(source_path),
                   staging=str(staging_file))
        
        try:
            # Copy file to staging
            shutil.copy2(source_path, staging_file)
            
            # Track for cleanup
            self.temp_files.append(str(staging_file))
            
            logger.info("File copied to staging", 
                       source=str(source_path),
                       staging=str(staging_file),
                       size_mb=staging_file.stat().st_size / (1024 * 1024))
            
            return str(staging_file)
            
        except Exception as e:
            error_msg = f"Failed to copy file to staging: {str(e)}"
            logger.error(error_msg, source=str(source_path))
            raise ProcessingError(error_msg)
    
    def get_media_info(self, file_path: Union[str, Path]) -> MediaInfo:
        """
        Extract comprehensive media information using FFprobe
        
        Args:
            file_path: Path to media file
            
        Returns:
            MediaInfo: Comprehensive media information
            
        Raises:
            ProcessingError: If media info extraction fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise ProcessingError(f"Media file not found: {file_path}")
        
        logger.debug("Extracting media info", file_path=str(file_path))
        
        try:
            # Use FFprobe to get media information
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = f"FFprobe failed: {result.stderr}"
                logger.error("Media info extraction failed", 
                           file_path=str(file_path),
                           error=error_msg)
                raise ProcessingError(error_msg)
            
            # Parse FFprobe output
            probe_data = json.loads(result.stdout)
            
            # Extract relevant information
            format_info = probe_data.get('format', {})
            streams = probe_data.get('streams', [])
            
            # Find video and audio streams
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            # Create MediaInfo object
            media_info = MediaInfo(
                duration_seconds=float(format_info.get('duration', 0)),
                video_codec=video_stream.get('codec_name') if video_stream else None,
                audio_codec=audio_stream.get('codec_name') if audio_stream else None,
                resolution=f"{video_stream.get('width')}x{video_stream.get('height')}" if video_stream else None,
                bitrate=int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None,
                frame_rate=self._parse_frame_rate(video_stream.get('r_frame_rate')) if video_stream else None
            )
            
            logger.debug("Media info extracted", 
                        file_path=str(file_path),
                        duration=media_info.duration_seconds,
                        video_codec=media_info.video_codec,
                        audio_codec=media_info.audio_codec)
            
            return media_info
            
        except subprocess.TimeoutExpired:
            error_msg = "Media info extraction timed out"
            logger.error(error_msg, file_path=str(file_path))
            raise ProcessingError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse FFprobe output: {str(e)}"
            logger.error(error_msg, file_path=str(file_path))
            raise ProcessingError(error_msg)
        except Exception as e:
            error_msg = f"Media info extraction failed: {str(e)}"
            logger.error(error_msg, file_path=str(file_path))
            raise ProcessingError(error_msg)
    
    def _get_audio_info(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """Get detailed audio file information"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a:0",
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {}
            
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            
            if not streams:
                return {}
            
            stream = streams[0]
            
            return {
                'duration': float(stream.get('duration', 0)),
                'sample_rate': int(stream.get('sample_rate', 0)),
                'channels': int(stream.get('channels', 0)),
                'bitrate': int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None
            }
            
        except Exception:
            return {}
    
    def _parse_frame_rate(self, frame_rate_str: Optional[str]) -> Optional[float]:
        """Parse frame rate string (e.g., '30/1') to float"""
        if not frame_rate_str:
            return None
        
        try:
            if '/' in frame_rate_str:
                num, den = frame_rate_str.split('/')
                return float(num) / float(den)
            else:
                return float(frame_rate_str)
        except (ValueError, ZeroDivisionError):
            return None
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files created during processing"""
        if not self.cleanup_enabled:
            logger.debug("Cleanup disabled, skipping temp file cleanup")
            return
        
        cleaned_count = 0
        failed_count = 0
        
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    cleaned_count += 1
                    logger.debug("Cleaned up temp file", file=temp_file)
            except Exception as e:
                failed_count += 1
                logger.warning("Failed to cleanup temp file", 
                             file=temp_file, 
                             error=str(e))
        
        # Clear the list
        self.temp_files.clear()
        
        if cleaned_count > 0 or failed_count > 0:
            logger.info("Temp file cleanup completed", 
                       cleaned=cleaned_count,
                       failed=failed_count)
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup_temp_files()


class MediaValidator:
    """
    Provides comprehensive media validation and health checks
    """
    
    def __init__(self, min_duration_seconds: float = 10.0,
                 max_duration_seconds: float = 14400.0):  # 4 hours max
        """
        Initialize media validator
        
        Args:
            min_duration_seconds: Minimum acceptable duration
            max_duration_seconds: Maximum acceptable duration
        """
        self.min_duration = min_duration_seconds
        self.max_duration = max_duration_seconds
        
        logger.info("Media validator initialized", 
                   min_duration=min_duration_seconds,
                   max_duration=max_duration_seconds)
    
    def validate_video_file(self, file_path: Union[str, Path], 
                           media_info: Optional[MediaInfo] = None) -> ValidationResult:
        """
        Comprehensive validation of video file
        
        Args:
            file_path: Path to video file
            media_info: Optional pre-extracted media info
            
        Returns:
            ValidationResult: Detailed validation results
        """
        file_path = Path(file_path)
        result = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        logger.debug("Starting video file validation", file_path=str(file_path))
        
        # Basic file existence and accessibility
        if not self._validate_file_access(file_path, result):
            return result
        
        # Get media info if not provided
        if media_info is None:
            try:
                prep_engine = MediaPreparationEngine()
                media_info = prep_engine.get_media_info(file_path)
            except ProcessingError as e:
                result.add_error(f"Failed to extract media info: {str(e)}")
                return result
        
        # Validate duration
        self._validate_duration(media_info, result)
        
        # Validate codecs
        self._validate_codecs(media_info, result)
        
        # Validate file integrity
        self._validate_file_integrity(file_path, result)
        
        # Add metrics
        result.add_metric('file_size_mb', file_path.stat().st_size / (1024 * 1024))
        result.add_metric('duration_seconds', media_info.duration_seconds)
        result.add_metric('video_codec', media_info.video_codec)
        result.add_metric('audio_codec', media_info.audio_codec)
        
        logger.info("Video file validation completed", 
                   file_path=str(file_path),
                   is_valid=result.is_valid,
                   errors=len(result.errors),
                   warnings=len(result.warnings))
        
        return result
    
    def validate_audio_file(self, audio_file: AudioFile) -> ValidationResult:
        """
        Validate extracted audio file
        
        Args:
            audio_file: AudioFile object to validate
            
        Returns:
            ValidationResult: Detailed validation results
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        logger.debug("Starting audio file validation", audio_path=audio_file.path)
        
        # Basic file existence
        if not self._validate_file_access(Path(audio_file.path), result):
            return result
        
        # Validate duration
        if audio_file.duration_seconds < self.min_duration:
            result.add_error(f"Audio too short: {audio_file.duration_seconds}s < {self.min_duration}s")
        elif audio_file.duration_seconds > self.max_duration:
            result.add_error(f"Audio too long: {audio_file.duration_seconds}s > {self.max_duration}s")
        
        # Validate audio properties
        if audio_file.sample_rate < 8000:
            result.add_warning(f"Low sample rate: {audio_file.sample_rate}Hz")
        elif audio_file.sample_rate > 48000:
            result.add_warning(f"High sample rate: {audio_file.sample_rate}Hz")
        
        if audio_file.channels > 2:
            result.add_warning(f"Multiple channels: {audio_file.channels}")
        
        # Validate file size
        if audio_file.size_bytes == 0:
            result.add_error("Audio file is empty")
        elif audio_file.size_bytes < 1024:  # Less than 1KB
            result.add_error("Audio file suspiciously small")
        
        # Add metrics
        result.add_metric('duration_seconds', audio_file.duration_seconds)
        result.add_metric('sample_rate', audio_file.sample_rate)
        result.add_metric('channels', audio_file.channels)
        result.add_metric('size_bytes', audio_file.size_bytes)
        result.add_metric('bitrate', audio_file.bitrate)
        
        logger.info("Audio file validation completed", 
                   audio_path=audio_file.path,
                   is_valid=result.is_valid,
                   errors=len(result.errors),
                   warnings=len(result.warnings))
        
        return result
    
    def validate_duration_match(self, video_duration: float, 
                               audio_duration: float,
                               tolerance_seconds: float = 2.0) -> ValidationResult:
        """
        Validate that audio and video durations match within tolerance
        
        Args:
            video_duration: Duration of video in seconds
            audio_duration: Duration of audio in seconds
            tolerance_seconds: Acceptable difference in seconds
            
        Returns:
            ValidationResult: Validation results
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        duration_diff = abs(video_duration - audio_duration)
        
        if duration_diff > tolerance_seconds:
            result.add_error(
                f"Duration mismatch: video={video_duration}s, audio={audio_duration}s, "
                f"difference={duration_diff}s > tolerance={tolerance_seconds}s"
            )
        elif duration_diff > tolerance_seconds / 2:
            result.add_warning(
                f"Duration difference: video={video_duration}s, audio={audio_duration}s, "
                f"difference={duration_diff}s"
            )
        
        result.add_metric('video_duration', video_duration)
        result.add_metric('audio_duration', audio_duration)
        result.add_metric('duration_difference', duration_diff)
        
        return result
    
    def _validate_file_access(self, file_path: Path, result: ValidationResult) -> bool:
        """Validate basic file access"""
        if not file_path.exists():
            result.add_error(f"File does not exist: {file_path}")
            return False
        
        if not file_path.is_file():
            result.add_error(f"Path is not a file: {file_path}")
            return False
        
        if file_path.stat().st_size == 0:
            result.add_error(f"File is empty: {file_path}")
            return False
        
        try:
            # Test read access
            with open(file_path, 'rb') as f:
                f.read(1024)  # Read first 1KB
        except PermissionError:
            result.add_error(f"No read permission: {file_path}")
            return False
        except Exception as e:
            result.add_error(f"File access error: {str(e)}")
            return False
        
        return True
    
    def _validate_duration(self, media_info: MediaInfo, result: ValidationResult) -> None:
        """Validate media duration"""
        if media_info.duration_seconds is None:
            result.add_warning("Duration information not available")
            return
        
        if media_info.duration_seconds < self.min_duration:
            result.add_error(f"Video too short: {media_info.duration_seconds}s < {self.min_duration}s")
        elif media_info.duration_seconds > self.max_duration:
            result.add_error(f"Video too long: {media_info.duration_seconds}s > {self.max_duration}s")
    
    def _validate_codecs(self, media_info: MediaInfo, result: ValidationResult) -> None:
        """Validate video and audio codecs"""
        # Check for audio stream
        if not media_info.audio_codec:
            result.add_error("No audio stream found")
        else:
            # Warn about problematic audio codecs
            problematic_audio = ['pcm_mulaw', 'pcm_alaw', 'adpcm']
            if any(codec in media_info.audio_codec.lower() for codec in problematic_audio):
                result.add_warning(f"Potentially problematic audio codec: {media_info.audio_codec}")
        
        # Check for video stream
        if not media_info.video_codec:
            result.add_warning("No video stream found")
    
    def _validate_file_integrity(self, file_path: Path, result: ValidationResult) -> None:
        """Basic file integrity validation"""
        try:
            # Try to read file header and footer
            with open(file_path, 'rb') as f:
                # Read first 1KB
                header = f.read(1024)
                if len(header) < 1024:
                    result.add_warning("File smaller than expected")
                
                # Seek to end and read last 1KB
                f.seek(-min(1024, file_path.stat().st_size), 2)
                footer = f.read(1024)
                
                # Basic checks for common video file signatures
                if not any(sig in header for sig in [b'ftyp', b'RIFF', b'AVI ', b'\x1aE\xdf\xa3']):
                    result.add_warning("File may not be a valid video file")
                    
        except Exception as e:
            result.add_warning(f"File integrity check failed: {str(e)}")


class MediaHealthChecker:
    """
    Advanced media health checking and diagnostic reporting
    """
    
    def __init__(self):
        """Initialize media health checker"""
        logger.info("Media health checker initialized")
    
    def comprehensive_health_check(self, file_path: Union[str, Path]) -> ValidationResult:
        """
        Perform comprehensive health check on media file
        
        Args:
            file_path: Path to media file
            
        Returns:
            ValidationResult: Comprehensive health check results
        """
        file_path = Path(file_path)
        result = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        logger.info("Starting comprehensive health check", file_path=str(file_path))
        
        # Basic file validation
        if not self._validate_file_system(file_path, result):
            return result
        
        # Media format validation
        self._validate_media_format(file_path, result)
        
        # Stream integrity validation
        self._validate_stream_integrity(file_path, result)
        
        # Quality assessment
        self._assess_media_quality(file_path, result)
        
        # Performance metrics
        self._collect_performance_metrics(file_path, result)
        
        logger.info("Comprehensive health check completed", 
                   file_path=str(file_path),
                   is_valid=result.is_valid,
                   errors=len(result.errors),
                   warnings=len(result.warnings))
        
        return result
    
    def validate_processing_readiness(self, file_path: Union[str, Path]) -> ValidationResult:
        """
        Validate if file is ready for processing pipeline
        
        Args:
            file_path: Path to media file
            
        Returns:
            ValidationResult: Processing readiness validation
        """
        file_path = Path(file_path)
        result = ValidationResult(is_valid=True, errors=[], warnings=[], metrics={})
        
        logger.debug("Validating processing readiness", file_path=str(file_path))
        
        try:
            # Check file stability (not being written to)
            if not self._is_file_stable(file_path):
                result.add_error("File is still being written to or modified")
                return result
            
            # Check file locks
            if self._is_file_locked(file_path):
                result.add_error("File is locked by another process")
                return result
            
            # Validate media streams for processing
            self._validate_processing_streams(file_path, result)
            
            # Check disk space for processing
            self._validate_disk_space(file_path, result)
            
            result.add_metric('processing_ready', result.is_valid)
            
        except Exception as e:
            result.add_error(f"Processing readiness check failed: {str(e)}")
        
        return result
    
    def generate_diagnostic_report(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Generate detailed diagnostic report for media file
        
        Args:
            file_path: Path to media file
            
        Returns:
            Dict[str, Any]: Comprehensive diagnostic report
        """
        file_path = Path(file_path)
        
        logger.info("Generating diagnostic report", file_path=str(file_path))
        
        report = {
            'file_path': str(file_path),
            'timestamp': datetime.now().isoformat(),
            'file_info': {},
            'media_info': {},
            'validation_results': {},
            'health_metrics': {},
            'recommendations': []
        }
        
        try:
            # File system information
            report['file_info'] = self._collect_file_info(file_path)
            
            # Media information
            prep_engine = MediaPreparationEngine()
            media_info = prep_engine.get_media_info(file_path)
            report['media_info'] = media_info.to_dict()
            
            # Validation results
            validator = MediaValidator()
            validation = validator.validate_video_file(file_path, media_info)
            report['validation_results'] = {
                'is_valid': validation.is_valid,
                'errors': validation.errors,
                'warnings': validation.warnings,
                'metrics': validation.metrics
            }
            
            # Health check results
            health_check = self.comprehensive_health_check(file_path)
            report['health_metrics'] = health_check.metrics
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(
                media_info, validation, health_check
            )
            
        except Exception as e:
            report['error'] = str(e)
            logger.error("Failed to generate diagnostic report", 
                        file_path=str(file_path),
                        error=str(e))
        
        return report
    
    def _validate_file_system(self, file_path: Path, result: ValidationResult) -> bool:
        """Validate file system level properties"""
        try:
            stat = file_path.stat()
            
            # Check file size
            file_size_mb = stat.st_size / (1024 * 1024)
            result.add_metric('file_size_mb', file_size_mb)
            
            if stat.st_size == 0:
                result.add_error("File is empty")
                return False
            
            if file_size_mb < 1:
                result.add_warning("File is very small (< 1MB)")
            elif file_size_mb > 10000:  # 10GB
                result.add_warning("File is very large (> 10GB)")
            
            # Check file permissions
            if not os.access(file_path, os.R_OK):
                result.add_error("File is not readable")
                return False
            
            # Check file age
            file_age_hours = (datetime.now().timestamp() - stat.st_mtime) / 3600
            result.add_metric('file_age_hours', file_age_hours)
            
            return True
            
        except Exception as e:
            result.add_error(f"File system validation failed: {str(e)}")
            return False
    
    def _validate_media_format(self, file_path: Path, result: ValidationResult) -> None:
        """Validate media format and container"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path)
            ]
            
            probe_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if probe_result.returncode != 0:
                result.add_error("Cannot read media format")
                return
            
            format_data = json.loads(probe_result.stdout)
            format_info = format_data.get('format', {})
            
            # Validate container format
            format_name = format_info.get('format_name', '')
            result.add_metric('container_format', format_name)
            
            supported_formats = ['mp4', 'mkv', 'avi', 'mov', 'webm']
            if not any(fmt in format_name.lower() for fmt in supported_formats):
                result.add_warning(f"Uncommon container format: {format_name}")
            
            # Check for metadata
            tags = format_info.get('tags', {})
            if tags:
                result.add_metric('has_metadata', True)
                result.add_metric('metadata_keys', list(tags.keys()))
            else:
                result.add_metric('has_metadata', False)
            
        except Exception as e:
            result.add_warning(f"Media format validation failed: {str(e)}")
    
    def _validate_stream_integrity(self, file_path: Path, result: ValidationResult) -> None:
        """Validate integrity of media streams"""
        try:
            # Use ffmpeg to validate streams
            cmd = [
                "ffmpeg",
                "-v", "error",
                "-i", str(file_path),
                "-f", "null",
                "-"
            ]
            
            integrity_result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if integrity_result.returncode == 0:
                result.add_metric('stream_integrity', 'valid')
            else:
                error_output = integrity_result.stderr
                if error_output:
                    result.add_warning(f"Stream integrity issues: {error_output[:200]}")
                    result.add_metric('stream_integrity', 'issues_detected')
                else:
                    result.add_metric('stream_integrity', 'unknown')
            
        except subprocess.TimeoutExpired:
            result.add_warning("Stream integrity check timed out")
            result.add_metric('stream_integrity', 'timeout')
        except Exception as e:
            result.add_warning(f"Stream integrity check failed: {str(e)}")
            result.add_metric('stream_integrity', 'error')
    
    def _assess_media_quality(self, file_path: Path, result: ValidationResult) -> None:
        """Assess media quality metrics"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=bit_rate,width,height,r_frame_rate,pix_fmt",
                "-print_format", "json",
                str(file_path)
            ]
            
            quality_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if quality_result.returncode == 0:
                data = json.loads(quality_result.stdout)
                streams = data.get('streams', [])
                
                if streams:
                    stream = streams[0]
                    
                    # Resolution assessment
                    width = stream.get('width')
                    height = stream.get('height')
                    if width and height:
                        resolution = width * height
                        result.add_metric('resolution_pixels', resolution)
                        
                        if resolution < 480 * 360:
                            result.add_warning("Low resolution video")
                        elif resolution >= 1920 * 1080:
                            result.add_metric('hd_quality', True)
                    
                    # Bitrate assessment
                    bitrate = stream.get('bit_rate')
                    if bitrate:
                        bitrate_mbps = int(bitrate) / 1000000
                        result.add_metric('video_bitrate_mbps', bitrate_mbps)
                        
                        if bitrate_mbps < 1:
                            result.add_warning("Low bitrate video")
                        elif bitrate_mbps > 50:
                            result.add_warning("Very high bitrate video")
                    
                    # Pixel format
                    pix_fmt = stream.get('pix_fmt')
                    if pix_fmt:
                        result.add_metric('pixel_format', pix_fmt)
            
        except Exception as e:
            result.add_warning(f"Quality assessment failed: {str(e)}")
    
    def _collect_performance_metrics(self, file_path: Path, result: ValidationResult) -> None:
        """Collect performance-related metrics"""
        try:
            # File I/O performance test
            start_time = datetime.now()
            
            with open(file_path, 'rb') as f:
                # Read first 10MB or entire file if smaller
                chunk_size = min(10 * 1024 * 1024, file_path.stat().st_size)
                f.read(chunk_size)
            
            read_time = (datetime.now() - start_time).total_seconds()
            read_speed_mbps = (chunk_size / (1024 * 1024)) / read_time if read_time > 0 else 0
            
            result.add_metric('read_speed_mbps', read_speed_mbps)
            
            if read_speed_mbps < 10:
                result.add_warning("Slow file I/O performance")
            
        except Exception as e:
            result.add_warning(f"Performance metrics collection failed: {str(e)}")
    
    def _is_file_stable(self, file_path: Path, stability_seconds: int = 5) -> bool:
        """Check if file is stable (not being written to)"""
        try:
            initial_stat = file_path.stat()
            
            # Wait and check again
            import time
            time.sleep(min(stability_seconds, 2))
            
            current_stat = file_path.stat()
            
            # Compare size and modification time
            return (initial_stat.st_size == current_stat.st_size and 
                   initial_stat.st_mtime == current_stat.st_mtime)
            
        except Exception:
            return False
    
    def _is_file_locked(self, file_path: Path) -> bool:
        """Check if file is locked by another process"""
        try:
            # Try to open file in exclusive mode
            with open(file_path, 'r+b') as f:
                pass
            return False
        except (PermissionError, OSError):
            return True
        except Exception:
            return False
    
    def _validate_processing_streams(self, file_path: Path, result: ValidationResult) -> None:
        """Validate streams are suitable for processing"""
        try:
            prep_engine = MediaPreparationEngine()
            media_info = prep_engine.get_media_info(file_path)
            
            # Check for required audio stream
            if not media_info.audio_codec:
                result.add_error("No audio stream available for transcription")
            
            # Check duration for processing
            if media_info.duration_seconds and media_info.duration_seconds > 14400:  # 4 hours
                result.add_warning("Very long video may require extended processing time")
            
            result.add_metric('processing_duration_estimate', 
                            media_info.duration_seconds * 0.1 if media_info.duration_seconds else 0)
            
        except Exception as e:
            result.add_warning(f"Processing stream validation failed: {str(e)}")
    
    def _validate_disk_space(self, file_path: Path, result: ValidationResult) -> None:
        """Validate sufficient disk space for processing"""
        try:
            file_size = file_path.stat().st_size
            
            # Check available space in staging directory
            staging_path = Path("staging")
            if staging_path.exists():
                statvfs = os.statvfs(staging_path)
                available_bytes = statvfs.f_frsize * statvfs.f_bavail
            else:
                # Check space in current directory
                statvfs = os.statvfs(file_path.parent)
                available_bytes = statvfs.f_frsize * statvfs.f_bavail
            
            # Estimate space needed (original + audio extraction + temp files)
            estimated_needed = file_size * 1.5  # 50% overhead
            
            result.add_metric('available_space_gb', available_bytes / (1024**3))
            result.add_metric('estimated_space_needed_gb', estimated_needed / (1024**3))
            
            if available_bytes < estimated_needed:
                result.add_error("Insufficient disk space for processing")
            elif available_bytes < estimated_needed * 2:
                result.add_warning("Low disk space for processing")
            
        except Exception as e:
            result.add_warning(f"Disk space validation failed: {str(e)}")
    
    def _collect_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Collect comprehensive file information"""
        try:
            stat = file_path.stat()
            
            return {
                'name': file_path.name,
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'accessed': datetime.fromtimestamp(stat.st_atime).isoformat(),
                'extension': file_path.suffix.lower(),
                'directory': str(file_path.parent),
                'permissions': oct(stat.st_mode)[-3:]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _generate_recommendations(self, media_info: MediaInfo, 
                                validation: ValidationResult,
                                health_check: ValidationResult) -> List[str]:
        """Generate processing recommendations based on analysis"""
        recommendations = []
        
        # Duration-based recommendations
        if media_info.duration_seconds:
            if media_info.duration_seconds > 7200:  # 2 hours
                recommendations.append("Consider splitting long video for faster processing")
            elif media_info.duration_seconds < 60:  # 1 minute
                recommendations.append("Very short video may not provide meaningful content")
        
        # Quality-based recommendations
        if 'resolution_pixels' in health_check.metrics:
            resolution = health_check.metrics['resolution_pixels']
            if resolution < 480 * 360:
                recommendations.append("Low resolution may affect visual content analysis")
        
        # Audio-based recommendations
        if not media_info.audio_codec:
            recommendations.append("No audio stream - transcription will not be possible")
        elif 'problematic' in str(media_info.audio_codec).lower():
            recommendations.append("Audio codec may cause transcription issues")
        
        # Performance recommendations
        if 'read_speed_mbps' in health_check.metrics:
            if health_check.metrics['read_speed_mbps'] < 10:
                recommendations.append("Slow file I/O - consider moving to faster storage")
        
        # Error-based recommendations
        if validation.errors:
            recommendations.append("Resolve validation errors before processing")
        
        if len(validation.warnings) > 3:
            recommendations.append("Multiple warnings detected - review file quality")
        
        return recommendations


class MediaPreparationPipeline:
    """
    Complete media preparation pipeline integrating all components
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize media preparation pipeline
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Initialize components
        staging_path = self.config.get('staging_path', 'staging')
        cleanup_enabled = self.config.get('cleanup_enabled', True)
        
        self.preparation_engine = MediaPreparationEngine(staging_path, cleanup_enabled)
        self.validator = MediaValidator(
            min_duration_seconds=self.config.get('min_duration', 10.0),
            max_duration_seconds=self.config.get('max_duration', 14400.0)
        )
        self.health_checker = MediaHealthChecker()
        
        logger.info("Media preparation pipeline initialized", config=self.config)
    
    def prepare_episode(self, episode: EpisodeObject) -> Tuple[EpisodeObject, AudioFile, ValidationResult]:
        """
        Complete preparation of episode for processing
        
        Args:
            episode: Episode object to prepare
            
        Returns:
            Tuple[EpisodeObject, AudioFile, ValidationResult]: Updated episode, audio file, and validation results
            
        Raises:
            ProcessingError: If preparation fails
        """
        logger.info("Starting episode preparation", episode_id=episode.episode_id)
        
        try:
            # Update episode stage
            episode.update_stage(ProcessingStage.PREPPED)
            
            # Comprehensive health check
            health_result = self.health_checker.comprehensive_health_check(episode.source.path)
            
            if not health_result.is_valid:
                error_msg = f"Health check failed: {'; '.join(health_result.errors)}"
                episode.add_error(error_msg)
                raise ProcessingError(error_msg)
            
            # Extract media info if not present
            if not episode.media.duration_seconds:
                media_info = self.preparation_engine.get_media_info(episode.source.path)
                episode.media = media_info
            
            # Validate video file
            validation_result = self.validator.validate_video_file(episode.source.path, episode.media)
            
            if not validation_result.is_valid:
                error_msg = f"Validation failed: {'; '.join(validation_result.errors)}"
                episode.add_error(error_msg)
                raise ProcessingError(error_msg)
            
            # Extract audio
            audio_file = self.preparation_engine.extract_audio(episode.source.path)
            
            # Validate audio
            audio_validation = self.validator.validate_audio_file(audio_file)
            
            if not audio_validation.is_valid:
                error_msg = f"Audio validation failed: {'; '.join(audio_validation.errors)}"
                episode.add_error(error_msg)
                raise ProcessingError(error_msg)
            
            # Validate duration match
            duration_validation = self.validator.validate_duration_match(
                episode.media.duration_seconds or 0,
                audio_file.duration_seconds
            )
            
            if not duration_validation.is_valid:
                logger.warning("Duration mismatch detected", 
                             episode_id=episode.episode_id,
                             errors=duration_validation.errors)
            
            # Combine validation results
            combined_validation = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=validation_result.warnings + audio_validation.warnings + duration_validation.warnings,
                metrics={**validation_result.metrics, **audio_validation.metrics, **duration_validation.metrics}
            )
            
            logger.info("Episode preparation completed successfully", 
                       episode_id=episode.episode_id,
                       audio_duration=audio_file.duration_seconds,
                       warnings=len(combined_validation.warnings))
            
            return episode, audio_file, combined_validation
            
        except Exception as e:
            error_msg = f"Episode preparation failed: {str(e)}"
            episode.add_error(error_msg)
            logger.error(error_msg, episode_id=episode.episode_id)
            raise ProcessingError(error_msg)
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        self.preparation_engine.cleanup_temp_files()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()