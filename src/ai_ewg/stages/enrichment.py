"""Stage 5: Entity enrichment."""

from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.models import EpisodeState, ArtifactKind
from ..core.logger import get_logger

logger = get_logger(__name__)


def extract_entities(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Extract named entities from transcripts."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.DIARIZED)
    
    count = 0
    for episode in episodes:
        try:
            # Placeholder: entity extraction logic
            # - Load SpaCy model
            # - Extract PERSON, ORG, GPE entities
            # - Optional: LLM-based extraction
            # - Save to enriched JSON
            
            enriched_path = settings.data_dir / "enriched" / f"{episode.episode_id}.json"
            
            registry.register_artifact(
                episode.episode_id,
                ArtifactKind.ENTITIES,
                enriched_path,
            )
            
            count += 1
            
            if verbose:
                logger.info(f"Extracted entities: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Entity extraction failed for {episode.episode_id}: {e}")
    
    logger.info(f"Entity extraction complete: {count} episodes")
    
    return {"count": count}


def disambiguate_entities(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Disambiguate entities against Wikidata."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.DIARIZED)
    
    count = 0
    for episode in episodes:
        try:
            # Placeholder: disambiguation logic
            # - Load entities from enriched JSON
            # - Query Wikidata/Wikipedia
            # - Use cache for repeated lookups
            # - Update enriched JSON with links
            
            count += 1
            
            if verbose:
                logger.info(f"Disambiguated: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Disambiguation failed for {episode.episode_id}: {e}")
    
    logger.info(f"Disambiguation complete: {count} episodes")
    
    return {"count": count}


def score_entities(
    settings: Settings,
    episode_id: Optional[str] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Score and rank entities by relevance."""
    registry = Registry(settings.registry_db_path)
    
    if episode_id:
        episodes = [registry.get_episode(episode_id)]
        episodes = [e for e in episodes if e]
    else:
        episodes = registry.get_episodes_by_state(EpisodeState.DIARIZED)
    
    count = 0
    for episode in episodes:
        try:
            # Placeholder: scoring logic
            # - Calculate mention frequency
            # - Apply role-based weights (host > guest)
            # - Consider context and co-occurrence
            # - Update enriched JSON with scores
            
            registry.update_episode_state(episode.episode_id, EpisodeState.ENRICHED)
            count += 1
            
            if verbose:
                logger.info(f"Scored entities: {episode.episode_id}")
        
        except Exception as e:
            logger.error(f"Entity scoring failed for {episode.episode_id}: {e}")
    
    logger.info(f"Entity scoring complete: {count} episodes")
    
    return {"count": count}
