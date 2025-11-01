"""
Media Normalization Pipeline for Social Media Packages

Implements media asset processing for platform-specific requirements including
video transcoding, audio normalization, thumbnail generation, and caption processing.
"""

import subprocess
import json
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
import tempfile
import shutil

from .platform_profiles import PlatformProfile, MediaSpecValidator
from .publishing_models import (
    MediaAsset, AssetType, FormatSpecs, ValidationResult, 
    ValidationError, ErrorType, Severity
)


@dataclass
class MediaInfo:
    """Media file information from ffprobe"""
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[int] = None
    frame_rate: Optional[float] = None
    sample_rate: Optional[int] = None
    audio_bitrate: Optional[int] = None
    file_size: Optional[int] = None
    
    @property
    def resolution(self) -> Optional[str]:
        """Get resolution as string (e.g., '1920x1080')"""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None
    
    @property
    def aspect_ratio(self) -> Optional[str]:
        """Calculate aspect ratio as string (e.g., '16:9')"""
        if not self.width or not self.height:
            return None
        
        # Calculate GCD for aspect ratio
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        
        divisor = gcd(self.width, self.height)
        ratio_w = self.width // divisor
        ratio_h = self.height // divisor
        
        return f"{ratio_w}:{ratio_h}"


@dataclass
class NormalizationJob:
    """Media normalization job specification"""
    input_path: str
    output_path: str
    platform_profile: PlatformProfile
    target_specs: Dict[str, Any]  # Specific target specifications
    asset_type: AssetType = AssetType.VIDEO
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_path': self.input_path,
            'output_path': self.output_path,
            'platform_profile': self.platform_profile.to_dict(),
            'target_specs': self.target_specs,
            'asset_type': self.asset_type.value
        }


@dataclass
class NormalizationResult:
    """Result of media normalization operation"""
    success: bool
    output_path: Optional[str] = None
    media_asset: Optional[MediaAsset] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    processing_log: List[str] = None
    
    def __post_init__(self):
        if self.processing_log is None:
            self.processing_log = []


class MediaProber:
    """Utility for probing media file information using ffprobe"""
    
    @staticmethod
    def probe_media(file_path: Union[str, Path]) -> MediaInfo:
        """
        Probe media file and extract information
        
        Args:
            file_path: Path to media file
            
        Returns:
            MediaInfo object with file information
            
        Raises:
            subprocess.CalledProcessError: If ffprobe fails
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")
        
        # Run ffprobe to get media information
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode, e.cmd, 
                f"ffprobe failed: {e.stderr}"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse ffprobe output: {e}")
        
        # Extract media information
        media_info = MediaInfo()
        
        # Get format information
        if 'format' in probe_data:
            format_info = probe_data['format']
            media_info.duration = float(format_info.get('duration', 0))
            media_info.bitrate = int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
            media_info.file_size = int(format_info.get('size', 0)) if format_info.get('size') else None
        
        # Get stream information
        if 'streams' in probe_data:
            for stream in probe_data['streams']:
                if stream.get('codec_type') == 'video':
                    media_info.width = stream.get('width')
                    media_info.height = stream.get('height')
                    media_info.video_codec = stream.get('codec_name')
                    
                    # Parse frame rate
                    if 'r_frame_rate' in stream:
                        frame_rate_str = stream['r_frame_rate']
                        if '/' in frame_rate_str:
                            num, den = frame_rate_str.split('/')
                            if int(den) > 0:
                                media_info.frame_rate = float(num) / float(den)
                
                elif stream.get('codec_type') == 'audio':
                    media_info.audio_codec = stream.get('codec_name')
                    media_info.sample_rate = int(stream.get('sample_rate', 0)) if stream.get('sample_rate') else None
                    media_info.audio_bitrate = int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None
        
        return media_info


class VideoTranscoder:
    """Video transcoding operations using ffmpeg"""
    
    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize video transcoder
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def transcode_video(self, 
                       input_path: Union[str, Path],
                       output_path: Union[str, Path],
                       target_specs: Dict[str, Any],
                       platform_profile: PlatformProfile) -> NormalizationResult:
        """
        Transcode video to meet platform specifications
        
        Args:
            input_path: Source video file
            output_path: Target output file
            target_specs: Target specifications (resolution, codec, etc.)
            platform_profile: Platform profile for validation
            
        Returns:
            NormalizationResult with success status and details
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        processing_log = []
        
        try:
            # Probe input media
            processing_log.append(f"Probing input media: {input_path}")
            input_info = MediaProber.probe_media(input_path)
            processing_log.append(f"Input: {input_info.resolution}, {input_info.duration}s, {input_info.video_codec}")
            
            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(input_path, output_path, target_specs, input_info)
            processing_log.append(f"FFmpeg command: {' '.join(cmd)}")
            
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Run transcoding
            processing_log.append("Starting transcoding...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"FFmpeg failed: {result.stderr}"
                processing_log.append(error_msg)
                return NormalizationResult(
                    success=False,
                    error_message=error_msg,
                    processing_log=processing_log
                )
            
            processing_log.append("Transcoding completed successfully")
            
            # Probe output media
            output_info = MediaProber.probe_media(output_path)
            processing_log.append(f"Output: {output_info.resolution}, {output_info.duration}s, {output_info.video_codec}")
            
            # Create media asset
            media_asset = self._create_media_asset(output_path, output_info, target_specs)
            
            # Validate against platform profile
            validator = MediaSpecValidator(platform_profile)
            validation_result = validator.validate_video_specs(
                duration_seconds=output_info.duration,
                resolution=output_info.resolution,
                codec=output_info.video_codec,
                file_size_bytes=output_info.file_size,
                aspect_ratio=output_info.aspect_ratio
            )
            
            return NormalizationResult(
                success=True,
                output_path=str(output_path),
                media_asset=media_asset,
                validation_result=validation_result,
                processing_log=processing_log
            )
            
        except Exception as e:
            error_msg = f"Transcoding failed: {str(e)}"
            processing_log.append(error_msg)
            return NormalizationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log
            )
    
    def _build_ffmpeg_command(self, 
                             input_path: Path, 
                             output_path: Path,
                             target_specs: Dict[str, Any],
                             input_info: MediaInfo) -> List[str]:
        """Build ffmpeg command for transcoding"""
        cmd = ['ffmpeg', '-i', str(input_path)]
        
        # Video codec
        if 'codec' in target_specs:
            if target_specs['codec'].lower() == 'h264':
                cmd.extend(['-c:v', 'libx264'])
            elif target_specs['codec'].lower() == 'h265':
                cmd.extend(['-c:v', 'libx265'])
        
        # Resolution
        if 'resolution' in target_specs:
            cmd.extend(['-s', target_specs['resolution']])
        
        # Bitrate
        if 'bitrate' in target_specs:
            cmd.extend(['-b:v', target_specs['bitrate']])
        
        # Frame rate
        if 'frame_rate' in target_specs:
            cmd.extend(['-r', str(target_specs['frame_rate'])])
        
        # Audio codec
        if 'audio_codec' in target_specs:
            if target_specs['audio_codec'].lower() == 'aac':
                cmd.extend(['-c:a', 'aac'])
            elif target_specs['audio_codec'].lower() == 'mp3':
                cmd.extend(['-c:a', 'libmp3lame'])
        
        # Audio bitrate
        if 'audio_bitrate' in target_specs:
            cmd.extend(['-b:a', target_specs['audio_bitrate']])
        
        # Quality settings
        cmd.extend(['-preset', 'medium', '-crf', '23'])
        
        # Overwrite output
        cmd.extend(['-y', str(output_path)])
        
        return cmd
    
    def _create_media_asset(self, 
                           output_path: Path, 
                           media_info: MediaInfo,
                           target_specs: Dict[str, Any]) -> MediaAsset:
        """Create MediaAsset from transcoded output"""
        # Calculate file checksum
        checksum = self._calculate_file_checksum(output_path)
        
        # Create format specs
        format_specs = FormatSpecs(
            resolution=media_info.resolution,
            codec=media_info.video_codec,
            bitrate=f"{media_info.bitrate}bps" if media_info.bitrate else None,
            frame_rate=media_info.frame_rate,
            loudness_target=target_specs.get('loudness_target')
        )
        
        return MediaAsset(
            asset_path=str(output_path),
            asset_type=AssetType.VIDEO,
            format_specs=format_specs,
            duration=timedelta(seconds=media_info.duration) if media_info.duration else None,
            file_size=media_info.file_size,
            checksum=checksum
        )
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class AudioNormalizer:
    """Audio normalization operations using ffmpeg"""
    
    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize audio normalizer
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def normalize_audio(self,
                       input_path: Union[str, Path],
                       output_path: Union[str, Path],
                       target_loudness: str = "-16 LUFS") -> NormalizationResult:
        """
        Normalize audio loudness to target level
        
        Args:
            input_path: Source audio/video file
            output_path: Target output file
            target_loudness: Target loudness level (e.g., "-16 LUFS")
            
        Returns:
            NormalizationResult with success status and details
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        processing_log = []
        
        try:
            # Parse target loudness
            target_lufs = self._parse_lufs(target_loudness)
            processing_log.append(f"Target loudness: {target_lufs} LUFS")
            
            # Analyze current loudness
            processing_log.append("Analyzing current loudness...")
            current_lufs = self._analyze_loudness(input_path)
            processing_log.append(f"Current loudness: {current_lufs} LUFS")
            
            # Calculate adjustment needed
            adjustment = target_lufs - current_lufs
            processing_log.append(f"Loudness adjustment: {adjustment:+.1f} dB")
            
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Apply loudness normalization
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-af', f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11',
                '-c:v', 'copy',  # Copy video stream unchanged
                '-y', str(output_path)
            ]
            
            processing_log.append(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Audio normalization failed: {result.stderr}"
                processing_log.append(error_msg)
                return NormalizationResult(
                    success=False,
                    error_message=error_msg,
                    processing_log=processing_log
                )
            
            processing_log.append("Audio normalization completed successfully")
            
            # Verify output
            output_info = MediaProber.probe_media(output_path)
            
            # Create media asset
            format_specs = FormatSpecs(
                loudness_target=target_loudness,
                codec=output_info.audio_codec
            )
            
            media_asset = MediaAsset(
                asset_path=str(output_path),
                asset_type=AssetType.AUDIO,
                format_specs=format_specs,
                duration=timedelta(seconds=output_info.duration) if output_info.duration else None,
                file_size=output_info.file_size,
                checksum=self._calculate_file_checksum(output_path)
            )
            
            return NormalizationResult(
                success=True,
                output_path=str(output_path),
                media_asset=media_asset,
                processing_log=processing_log
            )
            
        except Exception as e:
            error_msg = f"Audio normalization failed: {str(e)}"
            processing_log.append(error_msg)
            return NormalizationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log
            )
    
    def _parse_lufs(self, lufs_str: str) -> float:
        """Parse LUFS string to float value"""
        import re
        match = re.match(r'(-?\d+(?:\.\d+)?)\s*lufs', lufs_str.lower())
        if not match:
            raise ValueError(f"Invalid LUFS format: {lufs_str}")
        return float(match.group(1))
    
    def _analyze_loudness(self, input_path: Path) -> float:
        """Analyze current loudness of audio/video file"""
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-af', 'loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json',
            '-f', 'null', '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse loudness from stderr (ffmpeg outputs to stderr)
        import re
        match = re.search(r'"input_i"\s*:\s*"(-?\d+(?:\.\d+)?)"', result.stderr)
        if match:
            return float(match.group(1))
        
        # Fallback: assume reasonable default
        return -23.0
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class ThumbnailGenerator:
    """Thumbnail generation from video files"""
    
    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize thumbnail generator
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_thumbnail(self,
                          input_path: Union[str, Path],
                          output_path: Union[str, Path],
                          timestamp: Optional[float] = None,
                          resolution: str = "1920x1080",
                          format: str = "jpg") -> NormalizationResult:
        """
        Generate thumbnail from video file
        
        Args:
            input_path: Source video file
            output_path: Target thumbnail file
            timestamp: Time position for thumbnail (seconds, default: 10% of duration)
            resolution: Thumbnail resolution
            format: Output format (jpg, png)
            
        Returns:
            NormalizationResult with success status and details
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        processing_log = []
        
        try:
            # Probe input video
            processing_log.append(f"Probing input video: {input_path}")
            input_info = MediaProber.probe_media(input_path)
            
            # Determine timestamp for thumbnail
            if timestamp is None:
                # Use 10% of video duration, minimum 5 seconds
                timestamp = max(5.0, (input_info.duration or 60) * 0.1)
            
            processing_log.append(f"Generating thumbnail at {timestamp}s")
            
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build ffmpeg command for thumbnail generation
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-ss', str(timestamp),
                '-vframes', '1',
                '-s', resolution,
                '-q:v', '2',  # High quality
                '-y', str(output_path)
            ]
            
            processing_log.append(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Thumbnail generation failed: {result.stderr}"
                processing_log.append(error_msg)
                return NormalizationResult(
                    success=False,
                    error_message=error_msg,
                    processing_log=processing_log
                )
            
            processing_log.append("Thumbnail generated successfully")
            
            # Get output file info
            file_size = output_path.stat().st_size if output_path.exists() else None
            
            # Create media asset
            format_specs = FormatSpecs(
                resolution=resolution,
                codec=format
            )
            
            media_asset = MediaAsset(
                asset_path=str(output_path),
                asset_type=AssetType.THUMBNAIL,
                format_specs=format_specs,
                file_size=file_size,
                checksum=self._calculate_file_checksum(output_path)
            )
            
            return NormalizationResult(
                success=True,
                output_path=str(output_path),
                media_asset=media_asset,
                processing_log=processing_log
            )
            
        except Exception as e:
            error_msg = f"Thumbnail generation failed: {str(e)}"
            processing_log.append(error_msg)
            return NormalizationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log
            )
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class CaptionProcessor:
    """Caption and subtitle processing for social media"""
    
    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize caption processor
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def process_captions(self,
                        input_path: Union[str, Path],
                        output_path: Union[str, Path],
                        format: str = "srt") -> NormalizationResult:
        """
        Process captions for social media platforms
        
        Args:
            input_path: Source caption file (VTT, SRT, etc.)
            output_path: Target caption file
            format: Output format (srt, vtt, txt)
            
        Returns:
            NormalizationResult with success status and details
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        processing_log = []
        
        try:
            processing_log.append(f"Processing captions: {input_path} -> {output_path}")
            
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # For now, just copy the file (could add format conversion later)
            shutil.copy2(input_path, output_path)
            processing_log.append("Captions copied successfully")
            
            # Get file info
            file_size = output_path.stat().st_size if output_path.exists() else None
            
            # Create media asset
            format_specs = FormatSpecs(codec=format)
            
            media_asset = MediaAsset(
                asset_path=str(output_path),
                asset_type=AssetType.CAPTIONS,
                format_specs=format_specs,
                file_size=file_size,
                checksum=self._calculate_file_checksum(output_path)
            )
            
            return NormalizationResult(
                success=True,
                output_path=str(output_path),
                media_asset=media_asset,
                processing_log=processing_log
            )
            
        except Exception as e:
            error_msg = f"Caption processing failed: {str(e)}"
            processing_log.append(error_msg)
            return NormalizationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log
            )
    
    def burn_in_captions(self,
                        video_path: Union[str, Path],
                        caption_path: Union[str, Path],
                        output_path: Union[str, Path],
                        style: Optional[Dict[str, Any]] = None) -> NormalizationResult:
        """
        Burn captions into video for platforms that don't support separate captions
        
        Args:
            video_path: Source video file
            caption_path: Caption file (SRT, VTT)
            output_path: Target video with burned-in captions
            style: Caption styling options
            
        Returns:
            NormalizationResult with success status and details
        """
        video_path = Path(video_path)
        caption_path = Path(caption_path)
        output_path = Path(output_path)
        processing_log = []
        
        try:
            processing_log.append(f"Burning captions into video: {video_path}")
            
            # Default caption style
            if style is None:
                style = {
                    'font_size': 24,
                    'font_color': 'white',
                    'outline_color': 'black',
                    'outline_width': 2,
                    'position': 'bottom'
                }
            
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build ffmpeg command for caption burn-in
            subtitle_filter = f"subtitles={caption_path}:force_style='FontSize={style['font_size']},PrimaryColour=&H{self._color_to_hex(style['font_color'])},OutlineColour=&H{self._color_to_hex(style['outline_color'])},Outline={style['outline_width']}'"
            
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-y', str(output_path)
            ]
            
            processing_log.append(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Caption burn-in failed: {result.stderr}"
                processing_log.append(error_msg)
                return NormalizationResult(
                    success=False,
                    error_message=error_msg,
                    processing_log=processing_log
                )
            
            processing_log.append("Caption burn-in completed successfully")
            
            # Probe output video
            output_info = MediaProber.probe_media(output_path)
            
            # Create media asset
            format_specs = FormatSpecs(
                resolution=output_info.resolution,
                codec=output_info.video_codec
            )
            
            media_asset = MediaAsset(
                asset_path=str(output_path),
                asset_type=AssetType.VIDEO,
                format_specs=format_specs,
                duration=timedelta(seconds=output_info.duration) if output_info.duration else None,
                file_size=output_info.file_size,
                checksum=self._calculate_file_checksum(output_path)
            )
            
            return NormalizationResult(
                success=True,
                output_path=str(output_path),
                media_asset=media_asset,
                processing_log=processing_log
            )
            
        except Exception as e:
            error_msg = f"Caption burn-in failed: {str(e)}"
            processing_log.append(error_msg)
            return NormalizationResult(
                success=False,
                error_message=error_msg,
                processing_log=processing_log
            )
    
    def _color_to_hex(self, color_name: str) -> str:
        """Convert color name to hex for ffmpeg"""
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': 'FF0000',
            'green': '00FF00',
            'blue': '0000FF',
            'yellow': 'FFFF00'
        }
        return color_map.get(color_name.lower(), 'FFFFFF')
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class MediaNormalizationPipeline:
    """Complete media normalization pipeline for social media packages"""
    
    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        """
        Initialize media normalization pipeline
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize processors
        self.video_transcoder = VideoTranscoder(self.temp_dir)
        self.audio_normalizer = AudioNormalizer(self.temp_dir)
        self.thumbnail_generator = ThumbnailGenerator(self.temp_dir)
        self.caption_processor = CaptionProcessor(self.temp_dir)
    
    def normalize_for_platform(self,
                              input_video_path: Union[str, Path],
                              output_dir: Union[str, Path],
                              platform_profile: PlatformProfile,
                              episode_id: str,
                              caption_path: Optional[Union[str, Path]] = None) -> List[NormalizationResult]:
        """
        Normalize media assets for a specific platform
        
        Args:
            input_video_path: Source video file
            output_dir: Directory for normalized outputs
            platform_profile: Platform profile with specifications
            episode_id: Episode identifier for file naming
            caption_path: Optional caption file
            
        Returns:
            List of NormalizationResult for each processed asset
        """
        input_video_path = Path(input_video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        # Determine target specifications from platform profile
        target_specs = self._determine_target_specs(platform_profile)
        
        # 1. Transcode video
        video_output = output_dir / f"{episode_id}_video.mp4"
        video_result = self.video_transcoder.transcode_video(
            input_video_path, video_output, target_specs, platform_profile
        )
        results.append(video_result)
        
        # 2. Normalize audio (if video transcoding succeeded)
        if video_result.success and video_result.output_path:
            audio_output = output_dir / f"{episode_id}_normalized.mp4"
            audio_result = self.audio_normalizer.normalize_audio(
                video_result.output_path, audio_output, 
                target_specs.get('loudness_target', '-16 LUFS')
            )
            results.append(audio_result)
            
            # Use audio-normalized version for further processing
            final_video_path = audio_output if audio_result.success else video_result.output_path
        else:
            final_video_path = input_video_path
        
        # 3. Generate thumbnail
        thumbnail_output = output_dir / f"{episode_id}_thumbnail.jpg"
        thumbnail_result = self.thumbnail_generator.generate_thumbnail(
            final_video_path, thumbnail_output,
            resolution=target_specs.get('thumbnail_resolution', '1920x1080')
        )
        results.append(thumbnail_result)
        
        # 4. Process captions (if provided)
        if caption_path:
            caption_path = Path(caption_path)
            
            # Check if platform supports separate captions
            if platform_profile.metadata.supports_captions:
                # Copy/convert captions
                caption_output = output_dir / f"{episode_id}_captions.srt"
                caption_result = self.caption_processor.process_captions(
                    caption_path, caption_output, format="srt"
                )
                results.append(caption_result)
            else:
                # Burn captions into video
                captioned_output = output_dir / f"{episode_id}_captioned.mp4"
                burnin_result = self.caption_processor.burn_in_captions(
                    final_video_path, caption_path, captioned_output
                )
                results.append(burnin_result)
        
        return results
    
    def _determine_target_specs(self, platform_profile: PlatformProfile) -> Dict[str, Any]:
        """Determine target specifications from platform profile"""
        specs = {}
        
        # Video specifications
        if platform_profile.video.resolutions:
            # Use highest resolution available
            specs['resolution'] = platform_profile.video.resolutions[0]
        
        if platform_profile.video.codecs:
            # Prefer H.264 for compatibility
            if 'h264' in [c.lower() for c in platform_profile.video.codecs]:
                specs['codec'] = 'h264'
            else:
                specs['codec'] = platform_profile.video.codecs[0]
        
        if platform_profile.video.max_bitrate:
            # Use 80% of max bitrate for safety margin
            max_bitrate = platform_profile.video.max_bitrate
            if 'mbps' in max_bitrate.lower():
                bitrate_val = float(max_bitrate.lower().replace('mbps', '')) * 0.8
                specs['bitrate'] = f"{bitrate_val}M"
        
        # Audio specifications
        if platform_profile.audio.codecs:
            # Prefer AAC for compatibility
            if 'aac' in [c.lower() for c in platform_profile.audio.codecs]:
                specs['audio_codec'] = 'aac'
            else:
                specs['audio_codec'] = platform_profile.audio.codecs[0]
        
        if platform_profile.audio.loudness_target:
            specs['loudness_target'] = platform_profile.audio.loudness_target
        
        # Thumbnail specifications
        if platform_profile.video.resolutions:
            specs['thumbnail_resolution'] = platform_profile.video.resolutions[0]
        
        return specs


def create_normalization_pipeline(temp_dir: Optional[Union[str, Path]] = None) -> MediaNormalizationPipeline:
    """
    Factory function to create media normalization pipeline
    
    Args:
        temp_dir: Optional temporary directory
        
    Returns:
        MediaNormalizationPipeline instance
    """
    return MediaNormalizationPipeline(temp_dir)