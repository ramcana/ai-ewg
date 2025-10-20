"""Stage 2: Metadata normalization."""

from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.models import EpisodeState
from ..core.logger import get_logger

logger = get_logger(__name__)


def normalize_metadata(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Normalize episode metadata."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.NEW)
    
    count = 0
    for episode in episodes:
        if not force and episode.state != EpisodeState.NEW:
            continue
        
        # Normalize metadata (placeholder for actual logic)
        # - Parse episode title from filename
        # - Extract date
        # - Validate paths
        
        registry.update_episode_state(episode.episode_id, EpisodeState.NORMALIZED)
        count += 1
        
        if verbose:
            logger.info(f"Normalized: {episode.episode_id}")
    
    logger.info(f"Normalization complete: {count} episodes")
    
    return {"count": count}
