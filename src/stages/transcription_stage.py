"""
Transcription Stage Processor

Uses Whisper to generate transcripts and VTT captions.
Creates:
- data/transcripts/txt/{episode_id}.txt
- data/transcripts/vtt/{episode_id}.vtt
"""

from pathlib import Path
from typing import Dict, Any

from ..core.logging import get_logger
from ..core.exceptions import ProcessingError
from ..core.models import EpisodeObject

logger = get_logger('pipeline.transcription_stage')


class TranscriptionStageProcessor:
    """Processes transcription stage using Whisper"""
    
    def __init__(self, model_name: str = "base", output_dir: str = "data/transcripts"):
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.txt_dir = self.output_dir / "txt"
        self.vtt_dir = self.output_dir / "vtt"
        
        # Create output directories
        self.txt_dir.mkdir(parents=True, exist_ok=True)
        self.vtt_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Whisper model (lazy import)
        try:
            import whisper
            logger.info(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name)
            logger.info("Whisper model loaded successfully")
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
            
            # Run Whisper transcription
            logger.info("Running Whisper transcription...")
            result = self.model.transcribe(
                str(audio_file),
                language='en',  # Force English for now
                task='transcribe',
                verbose=False
            )
            
            # Save plain text transcript
            txt_path = self.txt_dir / f"{episode.episode_id}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(result['text'])
            
            logger.info("Text transcript saved", path=str(txt_path))
            
            # Generate VTT captions
            vtt_path = self.vtt_dir / f"{episode.episode_id}.vtt"
            self._save_vtt(result['segments'], vtt_path)
            
            logger.info("VTT captions saved", path=str(vtt_path))
            
            # Calculate statistics
            segment_count = len(result['segments'])
            word_count = len(result['text'].split())
            
            logger.info("Transcription completed",
                       episode_id=episode.episode_id,
                       segments=segment_count,
                       words=word_count)
            
            return {
                'txt_path': str(txt_path),
                'vtt_path': str(vtt_path),
                'text': result['text'],
                'segments': result['segments'],
                'language': result.get('language', 'en'),
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
