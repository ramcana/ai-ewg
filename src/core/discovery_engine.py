"""
Integrated Discovery Engine for the Video Processing Pipeline

Combines video discovery and episode normalization into a unified interface
for discovering and processing video files from multiple sources.
"""

from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from .config import SourceConfig, DiscoveryConfig, PipelineConfig
from .discovery import DiscoveryEngine, VideoFile
from .normalizer import EpisodeNormalizer
from .models import EpisodeObject
from .registry import EpisodeRegistry
from .exceptions import DiscoveryError, NormalizationError
from .logging import get_logger

logger = get_logger('pipeline.discovery_engine')


class IntegratedDiscoveryEngine:
    """
    Integrated discovery engine that combines file discovery and episode normalization
    
    This class provides a high-level interface for discovering video files from
    multiple sources and converting them to normalized episode objects ready
    for processing.
    """
    
    def __init__(self, config: PipelineConfig, registry: Optional[EpisodeRegistry] = None):
        self.config = config
        self.registry = registry
        
        # Initialize components
        self.discovery_engine = DiscoveryEngine(config.discovery)
        self.normalizer = EpisodeNormalizer()
        
        logger.info("Integrated discovery engine initialized", 
                   sources_count=len(config.sources),
                   stability_minutes=config.discovery.stability_minutes)
    
    def discover_and_normalize(self, force_rescan: bool = False) -> List[EpisodeObject]:
        """
        Discover video files and normalize them to episode objects
        
        Args:
            force_rescan: If True, ignore stability cache and rescan all files
            
        Returns:
            List[EpisodeObject]: Discovered and normalized episodes
            
        Raises:
            DiscoveryError: If discovery fails
            NormalizationError: If normalization fails
        """
        logger.info("Starting integrated discovery and normalization", 
                   force_rescan=force_rescan)
        
        # Clear stability cache if force rescan
        if force_rescan:
            self.discovery_engine.clear_stability_cache()
        
        # Discover video files
        try:
            video_files = self.discovery_engine.discover_videos(self.config.sources)
            logger.info("Video discovery completed", 
                       files_found=len(video_files))
        except Exception as e:
            raise DiscoveryError(f"Video discovery failed: {e}") from e
        
        if not video_files:
            logger.warning("No video files discovered")
            return []
        
        # Get existing episode IDs for collision detection
        existing_ids = self._get_existing_episode_ids()
        
        # Normalize video files to episodes
        episodes = []
        normalization_errors = []
        
        for video_file in video_files:
            try:
                episode = self.normalizer.normalize_file(video_file, existing_ids)
                episodes.append(episode)
                existing_ids.add(episode.episode_id)
                
                logger.debug("Video file normalized", 
                           file=video_file.path,
                           episode_id=episode.episode_id)
            
            except NormalizationError as e:
                normalization_errors.append(str(e))
                logger.error("Failed to normalize video file", 
                           file=video_file.path,
                           error=str(e))
                continue
        
        logger.info("Episode normalization completed", 
                   episodes_created=len(episodes),
                   normalization_errors=len(normalization_errors))
        
        if normalization_errors:
            logger.warning("Some files failed normalization", 
                         error_count=len(normalization_errors),
                         sample_errors=normalization_errors[:3])
        
        return episodes
    
    def discover_new_episodes(self) -> List[EpisodeObject]:
        """
        Discover only new episodes that haven't been processed yet
        
        Returns:
            List[EpisodeObject]: New episodes not in registry
        """
        logger.info("Discovering new episodes")
        
        # Get all episodes
        all_episodes = self.discover_and_normalize()
        
        if not self.registry:
            logger.warning("No registry available, returning all discovered episodes")
            return all_episodes
        
        # Filter out episodes already in registry
        new_episodes = []
        for episode in all_episodes:
            if not self.registry.episode_exists(episode.episode_id):
                new_episodes.append(episode)
        
        logger.info("New episode discovery completed", 
                   total_discovered=len(all_episodes),
                   new_episodes=len(new_episodes))
        
        return new_episodes
    
    def get_discovery_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current discovery state
        
        Returns:
            Dict: Discovery summary with statistics
        """
        try:
            # Discover files (without normalization for speed)
            video_files = self.discovery_engine.discover_videos(self.config.sources)
            
            # Get basic file statistics
            from .discovery import get_discovery_summary
            file_summary = get_discovery_summary(video_files)
            
            # Get cache statistics
            cache_stats = self.discovery_engine.get_cache_stats()
            
            # Get registry statistics if available
            registry_stats = {}
            if self.registry:
                try:
                    registry_stats = {
                        'total_episodes_in_registry': len(self.registry.get_all_episodes()),
                        'processing_stages': self.registry.get_stage_counts()
                    }
                except Exception as e:
                    logger.warning("Failed to get registry stats", error=str(e))
            
            return {
                'discovery': file_summary,
                'cache': cache_stats,
                'registry': registry_stats,
                'sources': {
                    'total_sources': len(self.config.sources),
                    'enabled_sources': len([s for s in self.config.sources if s.enabled]),
                    'source_paths': [s.path for s in self.config.sources if s.enabled]
                }
            }
        
        except Exception as e:
            logger.error("Failed to generate discovery summary", error=str(e))
            return {'error': str(e)}
    
    def validate_sources(self) -> Dict[str, Any]:
        """
        Validate all configured sources
        
        Returns:
            Dict: Validation results for each source
        """
        logger.info("Validating discovery sources")
        
        results = {}
        
        for i, source in enumerate(self.config.sources):
            source_key = f"source_{i}_{Path(source.path).name}"
            
            try:
                source_path = Path(source.path)
                
                validation = {
                    'path': source.path,
                    'enabled': source.enabled,
                    'exists': source_path.exists(),
                    'is_directory': source_path.is_dir() if source_path.exists() else False,
                    'readable': False,
                    'file_count': 0,
                    'errors': []
                }
                
                if validation['exists'] and validation['is_directory']:
                    try:
                        # Test readability
                        list(source_path.iterdir())
                        validation['readable'] = True
                        
                        # Count video files (quick scan)
                        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}
                        file_count = 0
                        for file_path in source_path.rglob('*'):
                            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                                file_count += 1
                                if file_count >= 100:  # Limit for performance
                                    break
                        
                        validation['file_count'] = file_count
                        
                    except PermissionError:
                        validation['errors'].append("Permission denied")
                    except Exception as e:
                        validation['errors'].append(f"Access error: {e}")
                
                elif not validation['exists']:
                    validation['errors'].append("Path does not exist")
                elif not validation['is_directory']:
                    validation['errors'].append("Path is not a directory")
                
                results[source_key] = validation
                
            except Exception as e:
                results[source_key] = {
                    'path': source.path,
                    'enabled': source.enabled,
                    'errors': [f"Validation failed: {e}"]
                }
        
        # Summary
        total_sources = len(results)
        valid_sources = len([r for r in results.values() if not r.get('errors')])
        
        logger.info("Source validation completed", 
                   total_sources=total_sources,
                   valid_sources=valid_sources)
        
        return {
            'summary': {
                'total_sources': total_sources,
                'valid_sources': valid_sources,
                'invalid_sources': total_sources - valid_sources
            },
            'sources': results
        }
    
    def _get_existing_episode_ids(self) -> Set[str]:
        """Get set of existing episode IDs from registry"""
        if not self.registry:
            return set()
        
        try:
            episodes = self.registry.get_all_episodes()
            return {ep.episode_id for ep in episodes}
        except Exception as e:
            logger.warning("Failed to get existing episode IDs", error=str(e))
            return set()
    
    def clear_caches(self) -> None:
        """Clear all internal caches"""
        self.discovery_engine.clear_stability_cache()
        logger.info("Discovery caches cleared")


# Utility functions for working with the integrated discovery engine
def create_discovery_engine(config: PipelineConfig, 
                          registry: Optional[EpisodeRegistry] = None) -> IntegratedDiscoveryEngine:
    """
    Create and configure an integrated discovery engine
    
    Args:
        config: Pipeline configuration
        registry: Optional episode registry
        
    Returns:
        IntegratedDiscoveryEngine: Configured discovery engine
    """
    return IntegratedDiscoveryEngine(config, registry)


def quick_discovery_test(config: PipelineConfig) -> Dict[str, Any]:
    """
    Perform a quick discovery test without full processing
    
    Args:
        config: Pipeline configuration
        
    Returns:
        Dict: Test results
    """
    from datetime import datetime
    
    engine = IntegratedDiscoveryEngine(config)
    
    # Validate sources
    validation_results = engine.validate_sources()
    
    # Get discovery summary
    summary = engine.get_discovery_summary()
    
    return {
        'validation': validation_results,
        'summary': summary,
        'timestamp': str(datetime.now())
    }