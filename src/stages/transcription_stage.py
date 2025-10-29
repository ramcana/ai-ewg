"""
Transcription Stage Processor

Uses Whisper to generate transcripts and VTT captions.
Creates:
- data/transcripts/txt/{episode_id}.txt
- data/transcripts/vtt/{episode_id}.vtt
"""

from pathlib import Path
from typing import Dict, Any
import asyncio
import torch

from ..core.logging import get_logger
from ..core.exceptions import ProcessingError
from ..core.models import EpisodeObject

logger = get_logger('pipeline.transcription_stage')


class TranscriptionStageProcessor:
    """Processes transcription stage using Whisper with multilingual support"""
    
    def __init__(self, model_name: str = "base", output_dir: str = "data/transcripts", config: Dict[str, Any] = None):
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.txt_dir = self.output_dir / "txt"
        self.vtt_dir = self.output_dir / "vtt"
        
        # Multilingual configuration
        self.config = config or {}
        self.transcription_config = self.config.get('transcription', {})
        self.language = self.transcription_config.get('language', 'auto')
        self.translate_to_english = self.transcription_config.get('translate_to_english', False)
        self.task = self.transcription_config.get('task', 'transcribe')
        self.supported_languages = self.transcription_config.get('supported_languages', ['en'])
        self.fallback_language = self.transcription_config.get('fallback_language', 'en')
        
        # Create output directories
        self.txt_dir.mkdir(parents=True, exist_ok=True)
        self.vtt_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Whisper model (lazy import)
        try:
            import whisper
            import torch
            
            # Detect device (CUDA if available)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading Whisper model: {model_name} on {device}")
            
            self.model = whisper.load_model(model_name, device=device)
            
            if device == "cuda":
                logger.info(f"Whisper model loaded successfully on GPU: {torch.cuda.get_device_name(0)}")
            else:
                logger.warning("CUDA not available, using CPU (this will be slower)")
                
        except ImportError:
            raise ProcessingError("Whisper is not installed. Run: pip install openai-whisper")
    
    async def process(self, episode: EpisodeObject, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe audio using Whisper
        
        Args:
            episode: Episode object
            audio_path: Path to audio WAV file
            
        Returns:
            Dict with transcript paths and metadata
        """
        try:
            logger.info("Starting transcription", 
                       episode_id=episode.episode_id,
                       audio_path=audio_path)
            
            # Verify audio file exists
            audio_file = Path(audio_path)
            if not audio_file.exists():
                raise ProcessingError(f"Audio file not found: {audio_path}")
            
            # Determine language and task settings
            whisper_language = None if self.language == 'auto' else self.language
            whisper_task = 'translate' if self.translate_to_english else 'transcribe'
            
            logger.info(f"Running Whisper transcription on {'GPU' if torch.cuda.is_available() else 'CPU'}...",
                       language=whisper_language or 'auto-detect',
                       task=whisper_task,
                       translate_to_english=self.translate_to_english)
            
            # Set FP16 for GPU acceleration
            fp16 = torch.cuda.is_available()
            
            # Offload blocking Whisper inference to thread executor
            result = await asyncio.to_thread(
                self.model.transcribe,
                str(audio_file),
                language=whisper_language,  # Auto-detect or specified language
                task=whisper_task,  # transcribe or translate
                verbose=False,
                word_timestamps=True,  # Enable word-level timestamps for clip generation
                fp16=fp16  # Use FP16 on GPU for faster processing
            )
            
            # Get detected language
            detected_language = result.get('language', self.fallback_language)
            
            # Validate detected language is supported
            if detected_language not in self.supported_languages:
                logger.warning(f"Detected language '{detected_language}' not in supported list, using fallback",
                             detected=detected_language,
                             supported=self.supported_languages,
                             fallback=self.fallback_language)
                detected_language = self.fallback_language
            
            # Save plain text transcript
            txt_path = self.txt_dir / f"{episode.episode_id}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(result['text'])
            
            logger.info("Text transcript saved", path=str(txt_path))
            
            # Generate VTT captions
            vtt_path = self.vtt_dir / f"{episode.episode_id}.vtt"
            self._save_vtt(result['segments'], vtt_path)
            
            logger.info("VTT captions saved", path=str(vtt_path))
            
            # Extract word-level timestamps for clip generation
            words = []
            for segment in result['segments']:
                if 'words' in segment:
                    words.extend(segment['words'])
            
            # Calculate statistics
            segment_count = len(result['segments'])
            word_count = len(words) if words else len(result['text'].split())
            
            logger.info("Transcription completed",
                       episode_id=episode.episode_id,
                       segments=segment_count,
                       words=word_count,
                       word_timestamps=len(words) > 0,
                       detected_language=detected_language,
                       task_performed=whisper_task)
            
            return {
                'txt_path': str(txt_path),
                'vtt_path': str(vtt_path),
                'text': result['text'],
                'segments': result['segments'],
                'words': words,  # Word-level timestamps for clip generation
                'language': detected_language,  # Use validated detected language
                'detected_language': detected_language,  # Explicit field for detected language
                'original_language': result.get('language', detected_language),  # Raw Whisper detection
                'task_performed': whisper_task,  # Track if transcribed or translated
                'translated_to_english': whisper_task == 'translate',
                'segment_count': segment_count,
                'word_count': word_count,
                'success': True
            }
            
        except Exception as e:
            logger.error("Transcription failed",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise ProcessingError(f"Transcription stage failed: {e}")
    
    def _save_vtt(self, segments: list, vtt_path: Path) -> None:
        """Convert Whisper segments to VTT format"""
        try:
            with open(vtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for i, segment in enumerate(segments):
                    start_time = self._format_timestamp(segment['start'])
                    end_time = self._format_timestamp(segment['end'])
                    text = segment['text'].strip()
                    
                    f.write(f"{i + 1}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")
                    
        except Exception as e:
            raise ProcessingError(f"Failed to save VTT: {e}")
    
    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp format (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
