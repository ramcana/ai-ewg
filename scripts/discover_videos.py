#!/usr/bin/env python3
"""
Quick script to discover and register videos from a folder
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import hashlib

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core import (
    ConfigurationManager,
    setup_logging,
    get_logger
)
from src.core.database import DatabaseManager
from src.core.registry import EpisodeRegistry
from src.core.models import (
    EpisodeObject,
    ProcessingStage,
    SourceInfo,
    MediaInfo,
    EpisodeMetadata
)

# Setup logging
setup_logging({'logging': {'level': 'INFO', 'console': True, 'structured': False}})
logger = get_logger('discover_videos')


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def discover_and_register(folder_path: str, show_name: str = "newsroom"):
    """Discover videos in folder and register them"""
    
    folder = Path(folder_path)
    if not folder.exists():
        logger.error(f"Folder not found: {folder_path}")
        return
    
    # Load config and initialize database
    config_path = Path(__file__).parent / 'config' / 'pipeline.yaml'
    config_mgr = ConfigurationManager(config_path)
    config = config_mgr.load_config()
    
    db_manager = DatabaseManager(config.database)
    db_manager.initialize()
    
    registry = EpisodeRegistry(db_manager)
    
    # Find all video files
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov']
    video_files = []
    for ext in video_extensions:
        video_files.extend(folder.glob(f'*{ext}'))
    
    logger.info(f"Found {len(video_files)} video files in {folder_path}")
    
    registered_count = 0
    duplicate_count = 0
    
    for video_file in video_files:
        try:
            # Get file stats
            stats = video_file.stat()
            file_size = stats.st_size
            last_modified = datetime.fromtimestamp(stats.st_mtime)
            
            # Generate episode ID
            base_name = video_file.stem
            episode_id = f"{show_name}-2024-{base_name.lower().replace('_', '-')}"
            
            logger.info(f"Processing: {video_file.name} -> {episode_id}")
            
            # Calculate file hash
            logger.info(f"  Calculating hash...")
            content_hash = calculate_file_hash(video_file)
            
            # Create episode object
            source_info = SourceInfo(
                path=str(video_file.absolute()),
                file_size=file_size,
                last_modified=last_modified
            )
            
            media_info = MediaInfo(
                duration_seconds=None,  # Will be populated during processing
                resolution="1920x1080",  # Default, will be updated
                frame_rate=30.0,
                video_codec=None,
                audio_codec=None,
                bitrate=None
            )
            
            metadata = EpisodeMetadata(
                show_name=show_name,
                show_slug=show_name.lower().replace(' ', '-'),
                season=None,
                episode=None,
                date=last_modified.strftime('%Y-%m-%d'),
                topic=base_name,
                topic_slug=base_name.lower().replace('_', '-'),
                title=f"{show_name.title()} - {base_name}",
                description=f"Episode {base_name}"
            )
            
            episode = EpisodeObject(
                episode_id=episode_id,
                content_hash=content_hash,
                source=source_info,
                media=media_info,
                metadata=metadata,
                processing_stage=ProcessingStage.DISCOVERED,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Register episode
            if registry.register_episode(episode):
                logger.info(f"  [OK] Registered: {episode_id}")
                registered_count += 1
            else:
                logger.info(f"  [SKIP] Duplicate: {episode_id}")
                duplicate_count += 1
                
        except Exception as e:
            logger.error(f"  [ERROR] Processing {video_file.name}: {e}")
    
    logger.info(f"\n" + "="*60)
    logger.info(f"Discovery complete!")
    logger.info(f"  Total files: {len(video_files)}")
    logger.info(f"  Registered: {registered_count}")
    logger.info(f"  Duplicates: {duplicate_count}")
    logger.info(f"="*60)
    
    db_manager.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover and register videos')
    parser.add_argument('folder', help='Folder containing videos')
    parser.add_argument('--show', default='newsroom', help='Show name (default: newsroom)')
    
    args = parser.parse_args()
    
    discover_and_register(args.folder, args.show)
