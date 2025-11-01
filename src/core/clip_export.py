"""
Clip Export System

Handles multi-format video export with subtitles and thumbnails.
Generates clips in multiple aspect ratios with both clean and subtitled variants.
"""

import subprocess
import json
import os
import shutil
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import ClipAsset, TranscriptionResult
from .clip_specification import ClipSpecification, ClipVariantSpec
from .logging import get_logger
from .exceptions import ProcessingError, FFmpegError, ExportError
from .clip_resource_manager import with_clip_resource_management
from .intelligent_crop import (
    IntelligentCropAnalyzer,
    IntelligentCropConfig,
    CropStrategy,
    CropRegion,
    create_crop_filter_string
)

logger = get_logger('clip_generation.clip_export')


@dataclass
class VideoEncodingSettings:
    """Video encoding configuration"""
    codec: str = "libx264"
    preset: str = "veryfast"
    crf: int = 20
    pixel_format: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "160k"
    audio_sample_rate: str = "48000"
    preserve_frame_rate: bool = True
    
    def to_ffmpeg_args(self) -> List[str]:
        """Convert settings to ffmpeg arguments"""
        args = [
            "-c:v", self.codec,
            "-preset", self.preset,
            "-crf", str(self.crf),
            "-pix_fmt", self.pixel_format,
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
            "-ar", self.audio_sample_rate
        ]
        
        if not self.preserve_frame_rate:
            args.extend(["-r", "30"])  # Default to 30fps if not preserving
        
        return args


@dataclass
class AspectRatioConfig:
    """Aspect ratio configuration for video output"""
    name: str
    width: int
    height: int
    crop_filter: str
    
    @property
    def resolution(self) -> str:
        """Get resolution string"""
        return f"{self.width}x{self.height}"


@dataclass
class SubtitleStyle:
    """Subtitle styling configuration"""
    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2
    background_color: str = "black@0.5"
    alignment: str = "center"
    margin_bottom: int = 50
    
    def to_ffmpeg_style(self) -> str:
        """Convert to ffmpeg subtitle style string"""
        return (
            f"FontName={self.font_family},"
            f"FontSize={self.font_size},"
            f"PrimaryColour=&H{self._color_to_hex(self.font_color)},"
            f"OutlineColour=&H{self._color_to_hex(self.outline_color)},"
            f"Outline={self.outline_width},"
            f"BackColour=&H{self._color_to_hex(self.background_color)},"
            f"Alignment={self._alignment_to_number()},"
            f"MarginV={self.margin_bottom}"
        )
    
    def _color_to_hex(self, color: str) -> str:
        """Convert color name to hex format for ffmpeg"""
        color_map = {
            "white": "FFFFFF",
            "black": "000000",
            "red": "FF0000",
            "green": "00FF00",
            "blue": "0000FF",
            "yellow": "FFFF00",
            "black@0.5": "80000000"  # Semi-transparent black
        }
        return color_map.get(color, "FFFFFF")
    
    def _alignment_to_number(self) -> int:
        """Convert alignment to ffmpeg number"""
        alignment_map = {
            "left": 1,
            "center": 2,
            "right": 3
        }
        return alignment_map.get(self.alignment, 2)


class ClipExportSystem:
    """
    Handles multi-format video export with subtitles
    
    Generates clips in multiple aspect ratios with both clean and subtitled
    variants using ffmpeg with optimized settings.
    """
    
    # Aspect ratio configurations
    ASPECT_RATIOS = {
        "9x16": AspectRatioConfig(
            name="9x16",
            width=1080,
            height=1920,
            crop_filter="crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        ),
        "16x9": AspectRatioConfig(
            name="16x9", 
            width=1920,
            height=1080,
            crop_filter="crop=iw:iw*9/16:0:(ih-iw*9/16)/2,scale=1920:1080"
        ),
        "1x1": AspectRatioConfig(
            name="1x1",
            width=1080,
            height=1080,
            crop_filter="crop=min(iw\\,ih):min(iw\\,ih):(iw-min(iw\\,ih))/2:(ih-min(iw\\,ih))/2,scale=1080:1080"
        )
    }
    
    def __init__(self, 
                 encoding_settings: Optional[VideoEncodingSettings] = None,
                 safe_padding_ms: int = 500,
                 temp_dir: Optional[str] = None,
                 subtitle_style: Optional[SubtitleStyle] = None,
                 intelligent_crop_config: Optional[IntelligentCropConfig] = None,
                 enable_intelligent_crop: bool = False):
        """
        Initialize clip export system
        
        Args:
            encoding_settings: Video encoding configuration
            safe_padding_ms: Safe padding around cut points in milliseconds
            temp_dir: Temporary directory for intermediate files
            subtitle_style: Subtitle styling configuration
            intelligent_crop_config: Intelligent crop configuration
            enable_intelligent_crop: Enable intelligent crop features
        """
        self.encoding_settings = encoding_settings or VideoEncodingSettings()
        self.safe_padding_ms = safe_padding_ms
        self.temp_dir = Path(temp_dir) if temp_dir else Path("temp/clip_export")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_style = subtitle_style or SubtitleStyle()
        self.enable_intelligent_crop = enable_intelligent_crop
        self.intelligent_crop_config = intelligent_crop_config or IntelligentCropConfig()
        self.intelligent_crop_analyzer = None
        
        if self.enable_intelligent_crop:
            self.intelligent_crop_analyzer = IntelligentCropAnalyzer(self.intelligent_crop_config)
            logger.info("Intelligent crop enabled", strategy=self.intelligent_crop_config.strategy.value)
        
        logger.info("ClipExportSystem initialized",
                   encoding_settings=self.encoding_settings.__dict__,
                   safe_padding_ms=safe_padding_ms,
                   temp_dir=str(self.temp_dir),
                   subtitle_style=self.subtitle_style.__dict__,
                   intelligent_crop_enabled=self.enable_intelligent_crop)
    
    @with_clip_resource_management("ffmpeg")
    def render_clip(self, clip_spec: ClipSpecification, source_path: str, transcript: TranscriptionResult = None) -> List[ClipAsset]:
        """
        Generate all variants for a clip specification
        
        Args:
            clip_spec: Complete clip specification with variants
            source_path: Path to source video file
            transcript: Episode transcription result (optional, for subtitles)
            
        Returns:
            List of generated clip assets
            
        Raises:
            ProcessingError: If clip rendering fails
        """
        try:
            logger.info("Starting clip rendering",
                       clip_id=clip_spec.clip_id,
                       episode_id=clip_spec.episode_id,
                       variants=len(clip_spec.variants),
                       source_path=source_path,
                       has_transcript=transcript is not None)
            
            # Validate source file
            source_file = Path(source_path)
            if not source_file.exists():
                raise ProcessingError(f"Source video file not found: {source_path}")
            
            # Apply safe padding to timing
            padded_start_ms, padded_end_ms = self._apply_safe_padding(
                clip_spec.start_ms, clip_spec.end_ms, source_path
            )
            
            assets = []
            
            # Group variants by aspect ratio for efficient processing
            variants_by_ratio = self._group_variants_by_aspect_ratio(clip_spec.variants)
            
            for aspect_ratio, variants in variants_by_ratio.items():
                try:
                    # Generate base clip for this aspect ratio
                    base_clip_path = self._render_base_clip(
                        source_path, padded_start_ms, padded_end_ms, aspect_ratio
                    )
                    
                    # Generate variants from base clip
                    for variant_spec in variants:
                        try:
                            asset = self._render_variant(
                                base_clip_path, variant_spec, clip_spec, transcript
                            )
                            assets.append(asset)
                            
                            logger.debug("Clip variant rendered",
                                       clip_id=clip_spec.clip_id,
                                       aspect_ratio=aspect_ratio,
                                       variant=variant_spec.variant,
                                       output_path=asset.path)
                            
                        except Exception as e:
                            logger.error("Failed to render clip variant",
                                       clip_id=clip_spec.clip_id,
                                       aspect_ratio=aspect_ratio,
                                       variant=variant_spec.variant,
                                       error=str(e))
                            # Continue with other variants
                            continue
                    
                    # Clean up base clip
                    if base_clip_path.exists():
                        base_clip_path.unlink()
                    
                except Exception as e:
                    logger.error("Failed to render base clip for aspect ratio",
                               clip_id=clip_spec.clip_id,
                               aspect_ratio=aspect_ratio,
                               error=str(e))
                    # Continue with other aspect ratios
                    continue
            
            if not assets:
                raise ProcessingError(f"No clip variants were successfully rendered for clip {clip_spec.clip_id}")
            
            logger.info("Clip rendering completed",
                       clip_id=clip_spec.clip_id,
                       assets_generated=len(assets),
                       total_variants=len(clip_spec.variants))
            
            # Generate thumbnail for the clip
            try:
                thumbnail_path = self.create_thumbnail(clip_spec, source_path)
                if thumbnail_path:
                    logger.debug("Thumbnail generated",
                               clip_id=clip_spec.clip_id,
                               thumbnail_path=thumbnail_path)
            except Exception as e:
                logger.warning("Failed to generate thumbnail",
                             clip_id=clip_spec.clip_id,
                             error=str(e))
            
            return assets
            
        except Exception as e:
            logger.error("Clip rendering failed",
                        clip_id=clip_spec.clip_id,
                        error=str(e))
            raise ProcessingError(f"Failed to render clip {clip_spec.clip_id}: {e}")
    
    def _apply_safe_padding(self, start_ms: int, end_ms: int, source_path: str) -> Tuple[int, int]:
        """
        Apply safe padding around cut points
        
        Args:
            start_ms: Original start time in milliseconds
            end_ms: Original end time in milliseconds
            source_path: Path to source video for duration validation
            
        Returns:
            Tuple of (padded_start_ms, padded_end_ms)
        """
        try:
            # Get source video duration
            source_duration_ms = self._get_video_duration_ms(source_path)
            
            # Apply padding
            padded_start_ms = max(0, start_ms - self.safe_padding_ms)
            padded_end_ms = min(source_duration_ms, end_ms + self.safe_padding_ms)
            
            logger.debug("Applied safe padding",
                        original_start_ms=start_ms,
                        original_end_ms=end_ms,
                        padded_start_ms=padded_start_ms,
                        padded_end_ms=padded_end_ms,
                        padding_ms=self.safe_padding_ms)
            
            return padded_start_ms, padded_end_ms
            
        except Exception as e:
            logger.warning("Failed to apply safe padding, using original times",
                          error=str(e))
            return start_ms, end_ms
    
    def _get_video_duration_ms(self, video_path: str) -> int:
        """
        Get video duration in milliseconds using ffprobe
        
        Args:
            video_path: Path to video file
            
        Returns:
            Duration in milliseconds
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise ProcessingError(f"ffprobe failed: {result.stderr}")
            
            probe_data = json.loads(result.stdout)
            duration_seconds = float(probe_data['format']['duration'])
            
            return int(duration_seconds * 1000)
            
        except Exception as e:
            logger.error("Failed to get video duration", video_path=video_path, error=str(e))
            # Return a large default value to avoid clipping
            return 24 * 60 * 60 * 1000  # 24 hours in ms
    
    def _group_variants_by_aspect_ratio(self, variants: List[ClipVariantSpec]) -> Dict[str, List[ClipVariantSpec]]:
        """
        Group variants by aspect ratio for efficient processing
        
        Args:
            variants: List of variant specifications
            
        Returns:
            Dictionary mapping aspect ratio to list of variants
        """
        grouped = {}
        
        for variant in variants:
            aspect_ratio = variant.aspect_ratio
            if aspect_ratio not in grouped:
                grouped[aspect_ratio] = []
            grouped[aspect_ratio].append(variant)
        
        return grouped
    
    def _render_base_clip(self, source_path: str, start_ms: int, end_ms: int, aspect_ratio: str) -> Path:
        """
        Render base clip for specific aspect ratio with retry mechanism
        
        Args:
            source_path: Path to source video
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            aspect_ratio: Target aspect ratio
            
        Returns:
            Path to rendered base clip
            
        Raises:
            ExportError: If all retry attempts fail
        """
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug("Attempting base clip render", 
                           attempt=attempt + 1, 
                           max_attempts=max_retries + 1,
                           aspect_ratio=aspect_ratio)
                
                # Get aspect ratio configuration
                if aspect_ratio not in self.ASPECT_RATIOS:
                    raise ExportError(f"Unsupported aspect ratio: {aspect_ratio}", 
                                    aspect_ratio=aspect_ratio)
                
                ratio_config = self.ASPECT_RATIOS[aspect_ratio]
                
                # Generate temporary output path
                temp_filename = f"base_{aspect_ratio}_{start_ms}_{end_ms}_attempt{attempt}.mp4"
                output_path = self.temp_dir / temp_filename
                
                # Convert milliseconds to seconds for ffmpeg
                start_seconds = start_ms / 1000.0
                duration_seconds = (end_ms - start_ms) / 1000.0
                
                # Build ffmpeg command with different parameters for retries
                cmd = self._build_ffmpeg_command_with_fallback(
                    source_path, start_seconds, duration_seconds, 
                    ratio_config, output_path, attempt,
                    start_ms=start_ms, end_ms=end_ms
                )
                
                logger.debug("Rendering base clip",
                            aspect_ratio=aspect_ratio,
                            start_seconds=start_seconds,
                            duration_seconds=duration_seconds,
                            attempt=attempt + 1,
                            command=' '.join(cmd))
                
                # Execute ffmpeg command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    error_msg = f"ffmpeg failed with return code {result.returncode}: {result.stderr}"
                    last_error = FFmpegError(error_msg, 
                                           command=' '.join(cmd),
                                           return_code=result.returncode,
                                           aspect_ratio=aspect_ratio)
                    logger.warning("ffmpeg command failed",
                                 attempt=attempt + 1,
                                 return_code=result.returncode,
                                 stderr=result.stderr)
                    continue
                
                if not output_path.exists():
                    error_msg = f"Output file was not created: {output_path}"
                    last_error = ExportError(error_msg, 
                                           export_stage="file_creation",
                                           aspect_ratio=aspect_ratio)
                    logger.warning("Output file not created",
                                 attempt=attempt + 1,
                                 output_path=str(output_path))
                    continue
                
                # Verify file size
                file_size = output_path.stat().st_size
                if file_size == 0:
                    error_msg = f"Output file is empty: {output_path}"
                    last_error = ExportError(error_msg,
                                           export_stage="file_validation",
                                           aspect_ratio=aspect_ratio)
                    logger.warning("Output file is empty",
                                 attempt=attempt + 1,
                                 output_path=str(output_path))
                    continue
                
                logger.debug("Base clip rendered successfully",
                            aspect_ratio=aspect_ratio,
                            output_path=str(output_path),
                            file_size=file_size,
                            attempt=attempt + 1)
                
                return output_path
                
            except subprocess.TimeoutExpired:
                error_msg = f"ffmpeg command timed out after 300 seconds"
                last_error = FFmpegError(error_msg,
                                       export_stage="timeout",
                                       aspect_ratio=aspect_ratio)
                logger.warning("ffmpeg command timed out",
                             attempt=attempt + 1)
                continue
            except Exception as e:
                error_msg = f"Unexpected error during base clip rendering: {str(e)}"
                last_error = ExportError(error_msg,
                                       export_stage="unexpected_error",
                                       aspect_ratio=aspect_ratio)
                logger.error("Unexpected error during base clip rendering",
                           attempt=attempt + 1,
                           error=str(e))
                continue
        
        # All attempts failed
        if last_error:
            logger.error("All base clip render attempts failed",
                       aspect_ratio=aspect_ratio,
                       max_attempts=max_retries + 1,
                       final_error=str(last_error))
            raise last_error
        else:
            raise ExportError(f"Failed to render base clip for {aspect_ratio} after {max_retries + 1} attempts",
                            aspect_ratio=aspect_ratio)
    
    def _get_intelligent_crop_filter(self, source_path: str, start_ms: int, end_ms: int, 
                                     ratio_config: AspectRatioConfig) -> Optional[str]:
        """
        Get intelligent crop filter for a clip segment
        
        Args:
            source_path: Path to source video
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            ratio_config: Aspect ratio configuration
            
        Returns:
            FFmpeg filter string or None if intelligent crop disabled/failed
        """
        if not self.enable_intelligent_crop or not self.intelligent_crop_analyzer:
            return None
        
        try:
            logger.info("Analyzing video for intelligent crop",
                       start_ms=start_ms,
                       end_ms=end_ms,
                       aspect_ratio=ratio_config.name)
            
            # Analyze video segment
            crop_regions = self.intelligent_crop_analyzer.analyze_video(
                video_path=Path(source_path),
                start_ms=start_ms,
                end_ms=end_ms,
                target_width=ratio_config.width,
                target_height=ratio_config.height
            )
            
            if not crop_regions:
                logger.warning("No crop regions generated, falling back to standard crop")
                return None
            
            # Get video FPS for filter generation
            fps = self._get_video_fps(source_path)
            
            # Create intelligent crop filter
            # For now, use the first region (static crop)
            # Full dynamic cropping would require more complex FFmpeg filters
            region = crop_regions[0]
            intelligent_filter = f"crop={region.width}:{region.height}:{region.x}:{region.y},scale={ratio_config.width}:{ratio_config.height}"
            
            logger.info("Intelligent crop filter generated",
                       strategy=region.strategy_used,
                       confidence=region.confidence,
                       crop_regions=len(crop_regions))
            
            return intelligent_filter
            
        except Exception as e:
            logger.warning(f"Intelligent crop analysis failed, using standard crop: {e}")
            return None
    
    def _get_video_fps(self, video_path: str) -> float:
        """Get video frame rate using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "v:0",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return 30.0  # Default fallback
            
            probe_data = json.loads(result.stdout)
            if 'streams' in probe_data and len(probe_data['streams']) > 0:
                fps_str = probe_data['streams'][0].get('r_frame_rate', '30/1')
                num, den = map(int, fps_str.split('/'))
                return num / den
            
            return 30.0
            
        except Exception as e:
            logger.warning(f"Failed to get video FPS: {e}")
            return 30.0
    
    def _build_ffmpeg_command_with_fallback(self, source_path: str, start_seconds: float, 
                                          duration_seconds: float, ratio_config: AspectRatioConfig,
                                          output_path: Path, attempt: int, 
                                          start_ms: int = None, end_ms: int = None) -> List[str]:
        """
        Build ffmpeg command with different parameters for retry attempts
        
        Args:
            source_path: Path to source video
            start_seconds: Start time in seconds
            duration_seconds: Duration in seconds
            ratio_config: Aspect ratio configuration
            output_path: Output file path
            attempt: Current attempt number (0-based)
            
        Returns:
            List of ffmpeg command arguments
        """
        # Try to get intelligent crop filter if enabled and timestamps provided
        crop_filter = ratio_config.crop_filter
        if start_ms is not None and end_ms is not None and attempt == 0:
            # Only try intelligent crop on first attempt
            intelligent_filter = self._get_intelligent_crop_filter(source_path, start_ms, end_ms, ratio_config)
            if intelligent_filter:
                crop_filter = intelligent_filter
                logger.info("Using intelligent crop filter")
        
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-ss", str(start_seconds),  # Start time
            "-i", source_path,  # Input file
            "-t", str(duration_seconds),  # Duration
            "-vf", crop_filter,  # Video filter for aspect ratio
        ]
        
        # Use different encoding parameters for retry attempts
        if attempt == 0:
            # First attempt: use standard settings
            cmd.extend(self.encoding_settings.to_ffmpeg_args())
        elif attempt == 1:
            # Second attempt: use more conservative settings
            fallback_settings = VideoEncodingSettings(
                codec="libx264",
                preset="medium",  # Slower but more reliable
                crf=23,  # Slightly lower quality for better compatibility
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="128k",  # Lower bitrate
                audio_sample_rate="44100",  # Standard sample rate
                preserve_frame_rate=True
            )
            cmd.extend(fallback_settings.to_ffmpeg_args())
        else:
            # Final attempt: use most conservative settings
            conservative_settings = VideoEncodingSettings(
                codec="libx264",
                preset="slow",  # Slowest but most reliable
                crf=25,  # Lower quality for maximum compatibility
                pixel_format="yuv420p",
                audio_codec="aac",
                audio_bitrate="96k",  # Lowest reasonable bitrate
                audio_sample_rate="44100",
                preserve_frame_rate=False  # Allow frame rate conversion
            )
            cmd.extend(conservative_settings.to_ffmpeg_args())
            # Add additional compatibility flags
            cmd.extend(["-movflags", "+faststart"])  # Optimize for streaming
        
        # Add output path
        cmd.append(str(output_path))
        
        return cmd
    
    def _render_variant(self, base_clip_path: Path, variant_spec: ClipVariantSpec, 
                       clip_spec: ClipSpecification, transcript: TranscriptionResult = None) -> ClipAsset:
        """
        Render specific variant from base clip
        
        Args:
            base_clip_path: Path to base clip file
            variant_spec: Variant specification
            clip_spec: Complete clip specification
            
        Returns:
            Generated clip asset
        """
        try:
            # Ensure output directory exists
            output_path = Path(variant_spec.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if variant_spec.variant == "clean":
                # For clean variant, just copy the base clip
                shutil.copy2(base_clip_path, output_path)
                
            elif variant_spec.variant == "subtitled":
                # For subtitled variant, burn subtitles into the video
                self._render_subtitled_variant(
                    base_clip_path, output_path, clip_spec, transcript
                )
            
            else:
                raise ProcessingError(f"Unknown variant type: {variant_spec.variant}")
            
            # Get file size
            file_size = output_path.stat().st_size
            
            # Create clip asset
            asset = ClipAsset.create_asset(
                clip_id=clip_spec.clip_id,
                path=str(output_path),
                variant=variant_spec.variant,
                aspect_ratio=variant_spec.aspect_ratio,
                size_bytes=file_size
            )
            
            logger.debug("Clip variant created",
                        clip_id=clip_spec.clip_id,
                        variant=variant_spec.variant,
                        aspect_ratio=variant_spec.aspect_ratio,
                        file_size=file_size)
            
            return asset
            
        except Exception as e:
            logger.error("Failed to render clip variant",
                        clip_id=clip_spec.clip_id,
                        variant=variant_spec.variant,
                        error=str(e))
            raise
    
    def _render_subtitled_variant(self, base_clip_path: Path, output_path: Path, 
                                 clip_spec: ClipSpecification, transcript: TranscriptionResult = None) -> None:
        """
        Render subtitled variant by burning subtitles into video
        
        Args:
            base_clip_path: Path to base clip file
            output_path: Path for output file
            clip_spec: Complete clip specification
            transcript: Episode transcription result (optional)
        """
        try:
            # Generate subtitle file for this clip
            subtitle_path = self._generate_clip_subtitles(clip_spec, transcript)
            
            if not subtitle_path or not subtitle_path.exists():
                logger.warning("No subtitles available, creating clean variant",
                             clip_id=clip_spec.clip_id)
                shutil.copy2(base_clip_path, output_path)
                return
            
            # Build ffmpeg command to burn subtitles
            # Convert Windows path to Unix-style for FFmpeg (replace backslashes with forward slashes)
            subtitle_path_ffmpeg = str(subtitle_path).replace('\\', '/')
            
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-i", str(base_clip_path),  # Input video
                "-vf", f"subtitles={subtitle_path_ffmpeg}:force_style='{self.subtitle_style.to_ffmpeg_style()}'",
                "-c:a", "copy",  # Copy audio without re-encoding
                str(output_path)
            ]
            
            logger.debug("Burning subtitles into video",
                        clip_id=clip_spec.clip_id,
                        subtitle_path=str(subtitle_path),
                        command=' '.join(cmd))
            
            # Execute ffmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error("Failed to burn subtitles, falling back to clean variant",
                           clip_id=clip_spec.clip_id,
                           ffmpeg_error=result.stderr[:500] if result.stderr else "No error output",
                           ffmpeg_command=' '.join(cmd))
                # Fallback to clean variant
                shutil.copy2(base_clip_path, output_path)
                return
            
            # Clean up temporary subtitle file
            if subtitle_path.exists():
                subtitle_path.unlink()
            
            logger.debug("Subtitles burned successfully",
                        clip_id=clip_spec.clip_id,
                        output_path=str(output_path))
            
        except Exception as e:
            logger.error("Failed to render subtitled variant, using clean variant",
                        clip_id=clip_spec.clip_id,
                        error=str(e))
            # Fallback to clean variant
            shutil.copy2(base_clip_path, output_path)
    
    def generate_subtitles(self, clip_spec: ClipSpecification, transcript: TranscriptionResult) -> str:
        """
        Create time-aligned subtitle file for clip
        
        Args:
            clip_spec: Clip specification with timing information
            transcript: Full episode transcription result
            
        Returns:
            SRT subtitle content for the clip
        """
        try:
            logger.info("Generating subtitles for clip",
                        clip_id=clip_spec.clip_id,
                        start_ms=clip_spec.start_ms,
                        end_ms=clip_spec.end_ms,
                        vtt_content_len=len(transcript.vtt_content) if transcript.vtt_content else 0)
            
            # Parse VTT content to extract segments
            segments = self._parse_vtt_segments(transcript.vtt_content)
            logger.info("VTT segments parsed", 
                       clip_id=clip_spec.clip_id,
                       segment_count=len(segments))
            
            # Filter segments that overlap with clip timing
            clip_segments = self._filter_segments_for_clip(
                segments, clip_spec.start_ms, clip_spec.end_ms
            )
            logger.info("Segments filtered for clip timing",
                       clip_id=clip_spec.clip_id,
                       filtered_count=len(clip_segments))
            
            if not clip_segments:
                logger.warning("No subtitle segments found for clip",
                             clip_id=clip_spec.clip_id)
                return ""
            
            # Adjust segment timing to clip timebase (start from 0)
            adjusted_segments = self._adjust_segment_timing(
                clip_segments, clip_spec.start_ms
            )
            
            # Generate SRT content
            srt_content = self._generate_srt_content(adjusted_segments)
            
            logger.debug("Subtitles generated",
                        clip_id=clip_spec.clip_id,
                        segments=len(adjusted_segments))
            
            return srt_content
            
        except Exception as e:
            logger.error("Failed to generate subtitles",
                        clip_id=clip_spec.clip_id,
                        error=str(e))
            return ""
    
    def _generate_clip_subtitles(self, clip_spec: ClipSpecification, transcript: TranscriptionResult = None) -> Optional[Path]:
        """
        Generate subtitle file for a specific clip
        
        Args:
            clip_spec: Clip specification
            transcript: Episode transcription result (if not provided, will attempt to load)
            
        Returns:
            Path to generated subtitle file or None if failed
        """
        try:
            logger.info("Starting subtitle generation",
                       clip_id=clip_spec.clip_id,
                       episode_id=clip_spec.episode_id,
                       has_transcript=transcript is not None)
            
            # If transcript not provided, try to load it
            if not transcript:
                logger.warning("No transcript provided to subtitle generation",
                             clip_id=clip_spec.clip_id,
                             episode_id=clip_spec.episode_id)
                return None
            
            # Check if transcript has VTT content, if not try to load from file
            vtt_content = None
            if hasattr(transcript, 'vtt_content') and transcript.vtt_content:
                vtt_content = transcript.vtt_content
            else:
                # Try to load VTT from file
                vtt_path = Path(f"data/transcripts/vtt/{clip_spec.episode_id}.vtt")
                if vtt_path.exists():
                    logger.info("Loading VTT content from file",
                               clip_id=clip_spec.clip_id,
                               vtt_path=str(vtt_path))
                    with open(vtt_path, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    # Update transcript object for future use
                    transcript.vtt_content = vtt_content
                else:
                    logger.warning("Transcript missing VTT content and file not found",
                                 clip_id=clip_spec.clip_id,
                                 episode_id=clip_spec.episode_id,
                                 vtt_path=str(vtt_path))
                    return None
            
            if not vtt_content:
                logger.warning("No VTT content available",
                             clip_id=clip_spec.clip_id)
                return None
            
            # Generate subtitles for this clip
            logger.info("Calling generate_subtitles",
                       clip_id=clip_spec.clip_id,
                       has_vtt=hasattr(transcript, 'vtt_content'),
                       vtt_len=len(transcript.vtt_content) if hasattr(transcript, 'vtt_content') and transcript.vtt_content else 0)
            
            srt_content = self.generate_subtitles(clip_spec, transcript)
            
            logger.info("generate_subtitles returned",
                       clip_id=clip_spec.clip_id,
                       srt_len=len(srt_content) if srt_content else 0)
            
            if not srt_content:
                logger.warning("No subtitle content generated",
                             clip_id=clip_spec.clip_id)
                return None
            
            # Write to temporary SRT file
            subtitle_path = Path(f"data/temp/{clip_spec.clip_id}_subtitles.srt")
            subtitle_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            logger.debug("Clip subtitles generated",
                        clip_id=clip_spec.clip_id,
                        subtitle_path=str(subtitle_path))
            
            return subtitle_path
            
        except Exception as e:
            logger.error("Failed to generate clip subtitles",
                        clip_id=clip_spec.clip_id,
                        error=str(e),
                        exc_info=True)
            return None
    
    def _parse_vtt_segments(self, vtt_content: str) -> List[Dict[str, Any]]:
        """
        Parse VTT content to extract timing and text segments
        
        Args:
            vtt_content: VTT file content
            
        Returns:
            List of segment dictionaries with start_ms, end_ms, and text
        """
        segments = []
        
        try:
            lines = vtt_content.strip().split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines and headers
                if not line or line == "WEBVTT":
                    i += 1
                    continue
                
                # Look for timestamp line (contains "-->")
                if "-->" in line:
                    # Parse timestamp line
                    timestamp_match = re.match(
                        r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})',
                        line
                    )
                    
                    if timestamp_match:
                        start_time = timestamp_match.group(1)
                        end_time = timestamp_match.group(2)
                        
                        # Convert to milliseconds
                        start_ms = self._vtt_timestamp_to_ms(start_time)
                        end_ms = self._vtt_timestamp_to_ms(end_time)
                        
                        # Get text from next line(s)
                        i += 1
                        text_lines = []
                        
                        while i < len(lines) and lines[i].strip():
                            text_lines.append(lines[i].strip())
                            i += 1
                        
                        if text_lines:
                            text = " ".join(text_lines)
                            segments.append({
                                'start_ms': start_ms,
                                'end_ms': end_ms,
                                'text': text
                            })
                
                i += 1
            
            logger.debug("Parsed VTT segments", segments=len(segments))
            return segments
            
        except Exception as e:
            logger.error("Failed to parse VTT content", error=str(e))
            return []
    
    def _vtt_timestamp_to_ms(self, timestamp: str) -> int:
        """
        Convert VTT timestamp (HH:MM:SS.mmm) to milliseconds
        
        Args:
            timestamp: VTT timestamp string
            
        Returns:
            Time in milliseconds
        """
        try:
            # Parse HH:MM:SS.mmm format
            time_parts = timestamp.split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds_parts = time_parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1])
            
            total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
            return total_ms
            
        except Exception as e:
            logger.error("Failed to parse VTT timestamp", timestamp=timestamp, error=str(e))
            return 0
    
    def _filter_segments_for_clip(self, segments: List[Dict[str, Any]], 
                                 clip_start_ms: int, clip_end_ms: int) -> List[Dict[str, Any]]:
        """
        Filter segments that overlap with clip timing
        
        Args:
            segments: List of all segments
            clip_start_ms: Clip start time in milliseconds
            clip_end_ms: Clip end time in milliseconds
            
        Returns:
            List of segments that overlap with the clip
        """
        clip_segments = []
        
        for segment in segments:
            seg_start = segment['start_ms']
            seg_end = segment['end_ms']
            
            # Check if segment overlaps with clip
            if seg_end > clip_start_ms and seg_start < clip_end_ms:
                # Trim segment to clip boundaries
                trimmed_segment = segment.copy()
                trimmed_segment['start_ms'] = max(seg_start, clip_start_ms)
                trimmed_segment['end_ms'] = min(seg_end, clip_end_ms)
                
                clip_segments.append(trimmed_segment)
        
        logger.debug("Filtered segments for clip",
                    total_segments=len(segments),
                    clip_segments=len(clip_segments),
                    clip_start_ms=clip_start_ms,
                    clip_end_ms=clip_end_ms)
        
        return clip_segments
    
    def _adjust_segment_timing(self, segments: List[Dict[str, Any]], 
                              clip_start_ms: int) -> List[Dict[str, Any]]:
        """
        Adjust segment timing to clip timebase (start from 0)
        
        Args:
            segments: List of segments with absolute timing
            clip_start_ms: Clip start time in milliseconds
            
        Returns:
            List of segments with timing adjusted to clip timebase
        """
        adjusted_segments = []
        
        for segment in segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start_ms'] = segment['start_ms'] - clip_start_ms
            adjusted_segment['end_ms'] = segment['end_ms'] - clip_start_ms
            
            # Ensure non-negative timing
            adjusted_segment['start_ms'] = max(0, adjusted_segment['start_ms'])
            adjusted_segment['end_ms'] = max(0, adjusted_segment['end_ms'])
            
            adjusted_segments.append(adjusted_segment)
        
        return adjusted_segments
    
    def _generate_srt_content(self, segments: List[Dict[str, Any]]) -> str:
        """
        Generate SRT subtitle content from segments
        
        Args:
            segments: List of segments with timing and text
            
        Returns:
            SRT subtitle content
        """
        srt_lines = []
        
        for i, segment in enumerate(segments, 1):
            # Format timestamps for SRT (HH:MM:SS,mmm)
            start_time = self._ms_to_srt_timestamp(segment['start_ms'])
            end_time = self._ms_to_srt_timestamp(segment['end_ms'])
            
            # Add SRT entry
            srt_lines.append(str(i))
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(segment['text'])
            srt_lines.append("")  # Empty line between entries
        
        return "\n".join(srt_lines)
    
    def _ms_to_srt_timestamp(self, ms: int) -> str:
        """
        Convert milliseconds to SRT timestamp format (HH:MM:SS,mmm)
        
        Args:
            ms: Time in milliseconds
            
        Returns:
            SRT timestamp string
        """
        hours = ms // (1000 * 60 * 60)
        minutes = (ms % (1000 * 60 * 60)) // (1000 * 60)
        seconds = (ms % (1000 * 60)) // 1000
        milliseconds = ms % 1000
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def create_thumbnail(self, clip_spec: ClipSpecification, source_path: str) -> Optional[str]:
        """
        Generate thumbnail from optimal frame
        
        Args:
            clip_spec: Clip specification with timing information
            source_path: Path to source video file
            
        Returns:
            Path to generated thumbnail file or None if failed
        """
        try:
            logger.debug("Generating thumbnail for clip",
                        clip_id=clip_spec.clip_id,
                        start_ms=clip_spec.start_ms,
                        end_ms=clip_spec.end_ms)
            
            # Determine optimal frame time for thumbnail
            optimal_time_ms = self._find_optimal_thumbnail_time(
                clip_spec.start_ms, clip_spec.end_ms, source_path
            )
            
            # Generate thumbnail output path
            thumbnail_dir = Path(clip_spec.variants[0].output_path).parent if clip_spec.variants else self.temp_dir
            thumbnail_path = thumbnail_dir / "thumb.jpg"
            
            # Ensure output directory exists
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract frame at optimal time
            success = self._extract_thumbnail_frame(
                source_path, optimal_time_ms, thumbnail_path
            )
            
            if success and thumbnail_path.exists():
                logger.info("Thumbnail generated successfully",
                           clip_id=clip_spec.clip_id,
                           thumbnail_path=str(thumbnail_path),
                           file_size=thumbnail_path.stat().st_size)
                return str(thumbnail_path)
            else:
                logger.warning("Thumbnail generation failed",
                             clip_id=clip_spec.clip_id)
                return None
            
        except Exception as e:
            logger.error("Failed to create thumbnail",
                        clip_id=clip_spec.clip_id,
                        error=str(e))
            return None
    
    def _find_optimal_thumbnail_time(self, start_ms: int, end_ms: int, source_path: str) -> int:
        """
        Find optimal time for thumbnail extraction
        
        Uses a simple heuristic: take frame at 1/3 into the clip to avoid
        potential fade-in effects and get a representative frame.
        
        Args:
            start_ms: Clip start time in milliseconds
            end_ms: Clip end time in milliseconds
            source_path: Path to source video (for future face detection)
            
        Returns:
            Optimal time in milliseconds for thumbnail extraction
        """
        try:
            # Simple heuristic: 1/3 into the clip
            duration_ms = end_ms - start_ms
            optimal_offset_ms = duration_ms // 3
            optimal_time_ms = start_ms + optimal_offset_ms
            
            logger.debug("Calculated optimal thumbnail time",
                        start_ms=start_ms,
                        end_ms=end_ms,
                        optimal_time_ms=optimal_time_ms)
            
            return optimal_time_ms
            
        except Exception as e:
            logger.error("Failed to find optimal thumbnail time", error=str(e))
            # Fallback to middle of clip
            return (start_ms + end_ms) // 2
    
    def _extract_thumbnail_frame(self, source_path: str, time_ms: int, output_path: Path) -> bool:
        """
        Extract frame at specific time for thumbnail
        
        Args:
            source_path: Path to source video file
            time_ms: Time in milliseconds to extract frame
            output_path: Path for output thumbnail
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert milliseconds to seconds for ffmpeg
            time_seconds = time_ms / 1000.0
            
            # Build ffmpeg command for frame extraction
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-ss", str(time_seconds),  # Seek to specific time
                "-i", source_path,  # Input file
                "-vframes", "1",  # Extract only one frame
                "-q:v", "2",  # High quality (1-31, lower is better)
                "-vf", "scale=1280:720",  # Scale to standard thumbnail size
                str(output_path)
            ]
            
            logger.debug("Extracting thumbnail frame",
                        time_seconds=time_seconds,
                        command=' '.join(cmd))
            
            # Execute ffmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )
            
            if result.returncode != 0:
                logger.error("ffmpeg thumbnail extraction failed",
                           error=result.stderr)
                return False
            
            # Verify output file was created
            if not output_path.exists():
                logger.error("Thumbnail file was not created", output_path=str(output_path))
                return False
            
            # Check file size (should be > 0)
            file_size = output_path.stat().st_size
            if file_size == 0:
                logger.error("Thumbnail file is empty", output_path=str(output_path))
                return False
            
            logger.debug("Thumbnail frame extracted successfully",
                        output_path=str(output_path),
                        file_size=file_size)
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Thumbnail extraction timed out")
            return False
        except Exception as e:
            logger.error("Failed to extract thumbnail frame", error=str(e))
            return False
    
    def _detect_faces_for_thumbnail(self, source_path: str, start_ms: int, end_ms: int) -> Optional[int]:
        """
        Detect faces in video segment to find optimal thumbnail time
        
        This is a placeholder for future face detection implementation.
        Would use OpenCV or similar library to detect faces and choose
        the frame with the best face visibility/composition.
        
        Args:
            source_path: Path to source video file
            start_ms: Clip start time in milliseconds
            end_ms: Clip end time in milliseconds
            
        Returns:
            Optimal time in milliseconds or None if no faces detected
        """
        # Placeholder for future implementation
        logger.debug("Face detection not implemented, using heuristic",
                    source_path=source_path)
        return None
    
    def _analyze_frame_contrast(self, source_path: str, time_ms: int) -> float:
        """
        Analyze frame contrast to help select optimal thumbnail
        
        This is a placeholder for future contrast analysis implementation.
        Would extract frame and calculate contrast metrics to prefer
        frames with good visual contrast.
        
        Args:
            source_path: Path to source video file
            time_ms: Time in milliseconds to analyze
            
        Returns:
            Contrast score (0.0 to 1.0, higher is better)
        """
        # Placeholder for future implementation
        logger.debug("Contrast analysis not implemented",
                    source_path=source_path,
                    time_ms=time_ms)
        return 0.5  # Default neutral score


# Utility functions
def create_clip_export_system(encoding_settings: Optional[VideoEncodingSettings] = None,
                            safe_padding_ms: int = 500,
                            temp_dir: Optional[str] = None,
                            subtitle_style: Optional[SubtitleStyle] = None) -> ClipExportSystem:
    """Factory function to create clip export system"""
    return ClipExportSystem(encoding_settings, safe_padding_ms, temp_dir, subtitle_style)