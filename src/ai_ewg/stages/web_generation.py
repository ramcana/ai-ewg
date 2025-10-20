"""Stage 9: Web artifact generation."""

from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.models import EpisodeState, ArtifactKind
from ..core.logger import get_logger

logger = get_logger(__name__)


def build_web_artifacts(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Build HTML pages with JSON-LD."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.ENRICHED)
    
    count = 0
    for episode in episodes:
        try:
            # Placeholder: web generation logic
            # - Load Jinja2 templates
            # - Render episode page
            # - Embed JSON-LD (Episode, Person, Organization)
            # - Save to public/shows/{show}/{episode}.html
            
            html_path = settings.web.output_dir / "shows" / episode.show_slug / f"{episode.episode_id}.html"
            html_path.parent.mkdir(parents=True, exist_ok=True)
            
            registry.register_artifact(
                episode.episode_id,
                ArtifactKind.HTML,
                html_path,
            )
            
            registry.update_episode_state(episode.episode_id, EpisodeState.RENDERED)
            count += 1
            
            if verbose:
                logger.info(f"Built web page: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Web generation failed for {episode.episode_id}: {e}")
    
    logger.info(f"Web generation complete: {count} pages")
    
    return {"count": count}
