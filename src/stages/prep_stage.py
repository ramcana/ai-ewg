"""
Media Preparation Stage Processor

Extracts audio from video files and validates media properties.
Creates: data/audio/{episode_id}.wav
"""

import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from fractions import Fraction
import json

from ..core.logging import get_logger
from ..core.exceptions import ProcessingError
from ..core.models import EpisodeObject

logger = get_logger('pipeline.prep_stage')


class PrepStageProcessor:
    """Processes media preparation stage - audio extraction and validation"""
    
    def __init__(self, output_dir: str = "data/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def process(self, episode: EpisodeObject) -> Dict[str, Any]:
        """
        Extract audio from video and validate media properties
        
        Args:
            episode: Episode object with source video path
            
        Returns:
            Dict with audio_path and media info
        """
        try:
            logger.info("Starting media preparation", episode_id=episode.episode_id)
            
            # Verify source file exists (resolve relative paths to absolute)
            source_path = episode.source.get_absolute_path()
            if not source_path.exists():
                raise ProcessingError(f"Source file not found: {source_path}")
            
            # Extract media info first
            media_info = await self._get_media_info(source_path)
            logger.info("Media info extracted", 
                       duration=media_info.get('duration'),
                       resolution=media_info.get('resolution'))
            
            # Extract audio to WAV
            audio_path = self.output_dir / f"{episode.episode_id}.wav"
            await self._extract_audio(source_path, audio_path)
            
            logger.info("Audio extraction completed", 
                       audio_path=str(audio_path),
                       size=audio_path.stat().st_size)
            
            return {
                'audio_path': str(audio_path),
                'media_info': media_info,
                'success': True
            }
            
        except Exception as e:
            logger.error("Media preparation failed", 
                        episode_id=episode.episode_id,
                        error=str(e))
            raise ProcessingError(f"Prep stage failed: {e}")
    
    async def _get_media_info(self, video_path: Path) -> Dict[str, Any]:
        """Extract media information using ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            # Offload blocking subprocess to thread executor
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            # Extract relevant info
            format_data = data.get('format', {})
            video_stream = next(
                (s for s in data.get('streams', []) if s.get('codec_type') == 'video'),
                {}
            )
            audio_stream = next(
                (s for s in data.get('streams', []) if s.get('codec_type') == 'audio'),
                {}
            )
            
            # Safely parse frame rate using Fraction instead of eval()
            frame_rate_str = video_stream.get('r_frame_rate', '0/1')
            try:
                frame_rate = float(Fraction(frame_rate_str))
            except (ValueError, ZeroDivisionError):
                logger.warning(f"Invalid frame rate format: {frame_rate_str}, defaulting to 0")
                frame_rate = 0.0
            
            return {
                'duration': float(format_data.get('duration', 0)),
                'bitrate': int(format_data.get('bit_rate', 0)),
                'video_codec': video_stream.get('codec_name'),
                'audio_codec': audio_stream.get('codec_name'),
                'resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                'frame_rate': frame_rate
            }
            
        except subprocess.CalledProcessError as e:
            raise ProcessingError(f"ffprobe failed: {e.stderr}")
        except Exception as e:
            raise ProcessingError(f"Failed to get media info: {e}")
    
    async def _extract_audio(self, video_path: Path, audio_path: Path) -> None:
        """Extract audio to WAV format using ffmpeg"""
        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '16000',  # 16kHz sample rate (good for speech)
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                str(audio_path)
            ]
            
            logger.debug("Running ffmpeg", command=' '.join(cmd))
            
            # Offload blocking subprocess to thread executor
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            if not audio_path.exists():
                raise ProcessingError("Audio file was not created")
            
            logger.debug("Audio extraction successful", size=audio_path.stat().st_size)
            
        except subprocess.CalledProcessError as e:
            raise ProcessingError(f"ffmpeg failed: {e.stderr}")
        except Exception as e:
            raise ProcessingError(f"Audio extraction failed: {e}")
