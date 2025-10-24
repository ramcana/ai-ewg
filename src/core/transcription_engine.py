"""
Faster-Whisper transcription engine with concurrency control

Provides GPU-safe transcription with automatic device management and
VRAM concurrency guards to prevent OOM errors.
"""

import asyncio
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Literal
from dataclasses import dataclass
from contextlib import asynccontextmanager

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment

from .logging import get_logger
from .exceptions import TranscriptionError

logger = get_logger('pipeline.transcription')


@dataclass
class TranscriptionSegment:
    """Single transcription segment"""
    start: float
    end: float
    text: str
    confidence: float
    
    def to_vtt_timestamp(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def to_vtt(self) -> str:
        """Format segment as VTT cue"""
        start_ts = self.to_vtt_timestamp(self.start)
        end_ts = self.to_vtt_timestamp(self.end)
        return f"{start_ts} --> {end_ts}\n{self.text}\n"


@dataclass
class TranscriptionResult:
    """Complete transcription result"""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float
    
    def to_vtt(self) -> str:
        """Export as WebVTT format"""
        vtt_lines = ["WEBVTT\n"]
        for i, segment in enumerate(self.segments, 1):
            vtt_lines.append(f"\n{i}\n")
            vtt_lines.append(segment.to_vtt())
        return "".join(vtt_lines)
    
    def to_plain_text(self) -> str:
        """Export as plain text"""
        return self.text


class TranscriptionEngine:
    """
    Faster-Whisper transcription engine with GPU concurrency control
    
    Features:
    - Automatic device selection (CUDA/CPU)
    - VRAM concurrency semaphore to prevent OOM
    - Compute type optimization (fp16/int8)
    - Thread-safe model loading
    """
    
    # Class-level semaphore for GPU concurrency control
    _gpu_semaphore: Optional[asyncio.Semaphore] = None
    _semaphore_lock = threading.Lock()
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: Literal["auto", "cuda", "cpu"] = "auto",
        compute_type: str = "float16",
        max_gpu_concurrent: int = 1
    ):
        """
        Initialize transcription engine
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large, large-v3)
            device: Device to use (auto, cuda, cpu)
            compute_type: Compute precision (int8, int8_float16, float16, float32)
            max_gpu_concurrent: Max concurrent GPU transcriptions (prevents OOM)
        """
        self.model_size = model_size
        self.device = self._resolve_device(device)
        self.compute_type = compute_type
        self.max_gpu_concurrent = max_gpu_concurrent
        
        # Initialize GPU semaphore if needed
        if self.device == "cuda":
            self._init_gpu_semaphore(max_gpu_concurrent)
        
        self._model: Optional[WhisperModel] = None
        self._model_lock = threading.Lock()
        
        logger.info(
            "Transcription engine initialized",
            model=model_size,
            device=self.device,
            compute_type=compute_type,
            max_concurrent=max_gpu_concurrent if self.device == "cuda" else "unlimited"
        )
    
    def _resolve_device(self, device: str) -> str:
        """Resolve device string to actual device"""
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                logger.warning("PyTorch not available, falling back to CPU")
                return "cpu"
        return device
    
    @classmethod
    def _init_gpu_semaphore(cls, max_concurrent: int) -> None:
        """Initialize class-level GPU semaphore"""
        with cls._semaphore_lock:
            if cls._gpu_semaphore is None:
                cls._gpu_semaphore = asyncio.Semaphore(max_concurrent)
                logger.info(f"GPU semaphore initialized with limit: {max_concurrent}")
    
    @asynccontextmanager
    async def _gpu_lock(self):
        """Context manager for GPU concurrency control"""
        if self.device == "cuda" and self._gpu_semaphore:
            async with self._gpu_semaphore:
                logger.debug("GPU slot acquired")
                yield
                logger.debug("GPU slot released")
        else:
            yield
    
    def _load_model(self) -> WhisperModel:
        """Load Whisper model (thread-safe)"""
        if self._model is None:
            with self._model_lock:
                if self._model is None:  # Double-check pattern
                    logger.info(
                        "Loading Whisper model",
                        model=self.model_size,
                        device=self.device,
                        compute_type=self.compute_type
                    )
                    
                    try:
                        self._model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            download_root=None,  # Use default cache
                            local_files_only=False
                        )
                        logger.info("Whisper model loaded successfully")
                    except Exception as e:
                        logger.error(f"Failed to load Whisper model: {e}")
                        raise TranscriptionError(f"Model loading failed: {e}")
        
        return self._model
    
    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        vad_filter: bool = True,
        beam_size: int = 5
    ) -> TranscriptionResult:
        """
        Transcribe audio file
        
        Args:
            audio_path: Path to audio file
            language: Language code (None for auto-detect)
            initial_prompt: Initial prompt to guide transcription
            vad_filter: Enable VAD filtering for better accuracy
            beam_size: Beam search size (higher = more accurate but slower)
            
        Returns:
            TranscriptionResult with text and segments
            
        Raises:
            TranscriptionError: If transcription fails
        """
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")
        
        logger.info(
            "Starting transcription",
            file=str(audio_path),
            language=language or "auto",
            device=self.device
        )
        
        try:
            # Acquire GPU slot if needed
            async with self._gpu_lock():
                # Load model in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                model = await loop.run_in_executor(None, self._load_model)
                
                # Run transcription in thread pool
                segments_raw, info = await loop.run_in_executor(
                    None,
                    lambda: model.transcribe(
                        str(audio_path),
                        language=language,
                        initial_prompt=initial_prompt,
                        vad_filter=vad_filter,
                        beam_size=beam_size,
                        word_timestamps=False
                    )
                )
                
                # Process segments
                segments = []
                full_text = []
                
                for segment in segments_raw:
                    segments.append(TranscriptionSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                        confidence=segment.avg_logprob
                    ))
                    full_text.append(segment.text.strip())
                
                result = TranscriptionResult(
                    text=" ".join(full_text),
                    segments=segments,
                    language=info.language,
                    duration=info.duration
                )
                
                logger.info(
                    "Transcription completed",
                    file=str(audio_path),
                    language=result.language,
                    duration=result.duration,
                    segments=len(result.segments)
                )
                
                return result
        
        except Exception as e:
            logger.error(
                "Transcription failed",
                file=str(audio_path),
                error=str(e)
            )
            raise TranscriptionError(f"Transcription failed: {e}")
    
    def unload_model(self) -> None:
        """Unload model to free memory"""
        with self._model_lock:
            if self._model is not None:
                del self._model
                self._model = None
                logger.info("Whisper model unloaded")


# Factory function
def create_transcription_engine(
    model_size: str = "large-v3",
    device: str = "auto",
    compute_type: str = "float16",
    max_gpu_concurrent: int = 1
) -> TranscriptionEngine:
    """Create transcription engine with settings"""
    return TranscriptionEngine(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        max_gpu_concurrent=max_gpu_concurrent
    )
