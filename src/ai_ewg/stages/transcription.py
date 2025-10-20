"""Stage 3: Audio transcription."""

from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.models import EpisodeState, ArtifactKind
from ..core.logger import get_logger

logger = get_logger(__name__)


def transcribe_episodes(
    settings: Settings,
    episode_id: Optional[str] = None,
    model: str = "large-v3",
    compute_type: str = "fp16",
    device: str = "auto",
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Transcribe episodes using Faster-Whisper."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.NORMALIZED)
    
    count = 0
    for episode in episodes:
        if not force and episode.state not in [EpisodeState.NORMALIZED, EpisodeState.NEW]:
            continue
        
        try:
            # Placeholder: actual transcription logic
            # - Load faster-whisper model
            # - Transcribe audio
            # - Generate TXT and VTT
            # - Save artifacts
            
            # Register artifacts
            txt_path = settings.data_dir / "transcripts" / "txt" / f"{episode.episode_id}.txt"
            vtt_path = settings.data_dir / "transcripts" / "vtt" / f"{episode.episode_id}.vtt"
            
            registry.register_artifact(
                episode.episode_id,
                ArtifactKind.TRANSCRIPT_TXT,
                txt_path,
                model_version=f"faster-whisper-{model}"
            )
            
            registry.register_artifact(
                episode.episode_id,
                ArtifactKind.TRANSCRIPT_VTT,
                vtt_path,
                model_version=f"faster-whisper-{model}"
            )
            
            registry.update_episode_state(episode.episode_id, EpisodeState.TRANSCRIBED)
            count += 1
            
            if verbose:
                logger.info(f"Transcribed: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Transcription failed for {episode.episode_id}: {e}")
            registry.update_episode_state(episode.episode_id, EpisodeState.ERROR, str(e))
    
    logger.info(f"Transcription complete: {count} episodes")
    
    return {"count": count}
