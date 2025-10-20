"""Stage 1: Video discovery."""

from pathlib import Path
from typing import Optional, Dict, Any
from ..core.settings import Settings
from ..core.registry import Registry
from ..core.logger import get_logger

logger = get_logger(__name__)


def discover_videos(
    settings: Settings,
    source: Optional[Path] = None,
    pattern: str = "**/*.mp4",
    dry_run: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Discover video files from configured sources."""
    registry = Registry(settings.registry_db_path)
    
    sources = [source] if source else settings.source_paths
    discovered = []
    new_count = 0
    
    for source_path in sources:
        if not source_path.exists():
            logger.warning(f"Source path does not exist: {source_path}")
            continue
        
        logger.info(f"Scanning {source_path} with pattern {pattern}")
        
        for video_path in source_path.glob(pattern):
            if not video_path.is_file():
                continue
            
            # Extract metadata from path
            show, episode_id = _extract_metadata(video_path, source_path)
            
            discovered.append({
                "path": video_path,
                "show": show,
                "episode_id": episode_id,
            })
            
            if not dry_run:
                # Check if new
                existing = registry.get_episode(episode_id)
                if not existing:
                    new_count += 1
                
                # Register in database
                registry.register_episode(
                    abs_path=video_path,
                    show=show,
                    show_slug=_slugify(show),
                    episode_id=episode_id,
                )
                
                if verbose:
                    logger.info(f"Registered: {episode_id}")
    
    logger.info(f"Discovery complete: {len(discovered)} total, {new_count} new")
    
    return {
        "count": len(discovered),
        "new_count": new_count,
        "files": [str(d["path"]) for d in discovered],
    }


def _extract_metadata(video_path: Path, source_root: Path) -> tuple[str, str]:
    """Extract show and episode ID from path."""
    # Example: test_videos/newsroom/2024/newsroom-2024-bb580.mp4
    # Show: newsroom, Episode: newsroom-2024-bb580
    
    rel_path = video_path.relative_to(source_root)
    parts = rel_path.parts
    
    if len(parts) >= 2:
        show = parts[0]
    else:
        show = "unknown"
    
    episode_id = video_path.stem  # Filename without extension
    
    return show, episode_id


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')
