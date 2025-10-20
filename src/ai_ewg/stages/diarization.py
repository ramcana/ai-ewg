"""Stage 4: Speaker diarization."""

from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.models import EpisodeState, ArtifactKind
from ..core.logger import get_logger

logger = get_logger(__name__)


def diarize_episodes(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Perform speaker diarization."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.TRANSCRIBED)
    
    count = 0
    for episode in episodes:
        if not force and episode.state != EpisodeState.TRANSCRIBED:
            continue
        
        try:
            # Placeholder: actual diarization logic
            # - Load pyannote model
            # - Perform diarization
            # - Merge with transcript
            # - Save diarized transcript
            
            diar_path = settings.data_dir / "transcripts" / "txt" / f"{episode.episode_id}_diarized.txt"
            
            registry.register_artifact(
                episode.episode_id,
                ArtifactKind.DIARIZATION,
                diar_path,
                model_version=settings.diarization.model
            )
            
            registry.update_episode_state(episode.episode_id, EpisodeState.DIARIZED)
            count += 1
            
            if verbose:
                logger.info(f"Diarized: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Diarization failed for {episode.episode_id}: {e}")
            registry.update_episode_state(episode.episode_id, EpisodeState.ERROR, str(e))
    
    logger.info(f"Diarization complete: {count} episodes")
    
    return {"count": count}
