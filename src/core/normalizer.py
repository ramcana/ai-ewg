"""
Episode Normalization and ID Generation for the Video Processing Pipeline

Handles intelligent parsing of video file paths to extract show metadata,
generates stable episode IDs with collision detection, and ensures global uniqueness.
"""

import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple, Union
from datetime import datetime
from dataclasses import dataclass

from .models import EpisodeMetadata, EpisodeObject, MediaInfo, ContentHasher, SourceInfo
from .discovery import VideoFile
from .exceptions import NormalizationError
from .logging import get_logger
from .naming_service import get_naming_service

logger = get_logger('pipeline.normalizer')


@dataclass
class ParsedMetadata:
    """Intermediate parsed metadata before normalization"""
    show_name: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    date: Optional[str] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    raw_filename: Optional[str] = None
    confidence: float = 0.0


class FilenameParser:
    """Parses video filenames to extract show metadata"""
    
    def __init__(self):
        # Common patterns for TV show episodes
        self.tv_patterns = [
            # Show.Name.S01E01.Episode.Title.ext
            r'(?P<show>.*?)\.S(?P<season>\d+)E(?P<episode>\d+)\.?(?P<title>.*?)\.(?P<ext>\w+)$',
            # Show Name - S01E01 - Episode Title.ext
            r'(?P<show>.*?)\s*-\s*S(?P<season>\d+)E(?P<episode>\d+)\s*-\s*(?P<title>.*?)\.(?P<ext>\w+)$',
            # Show Name S01E01 Episode Title.ext
            r'(?P<show>.*?)\s+S(?P<season>\d+)E(?P<episode>\d+)\s+(?P<title>.*?)\.(?P<ext>\w+)$',
            # Show_Name_1x01_Episode_Title.ext
            r'(?P<show>.*?)_(?P<season>\d+)x(?P<episode>\d+)_(?P<title>.*?)\.(?P<ext>\w+)$',
            # Show Name 1x01 Episode Title.ext
            r'(?P<show>.*?)\s+(?P<season>\d+)x(?P<episode>\d+)\s+(?P<title>.*?)\.(?P<ext>\w+)$',
        ]
        
        # Patterns for date-based episodes (news shows, podcasts)
        self.date_patterns = [
            # Show Name - 2024-01-15 - Topic.ext
            r'(?P<show>.*?)\s*-\s*(?P<date>\d{4}-\d{2}-\d{2})\s*-\s*(?P<topic>.*?)\.(?P<ext>\w+)$',
            # Show Name 2024-01-15 Topic.ext
            r'(?P<show>.*?)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<topic>.*?)\.(?P<ext>\w+)$',
            # Show_Name_20240115_Topic.ext
            r'(?P<show>.*?)_(?P<date>\d{8})_(?P<topic>.*?)\.(?P<ext>\w+)$',
            # Show Name - Jan 15 2024 - Topic.ext
            r'(?P<show>.*?)\s*-\s*(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})\s*-\s*(?P<topic>.*?)\.(?P<ext>\w+)$',
        ]
        
        # Patterns for simple show episodes without season/episode numbers
        self.simple_patterns = [
            # Show Name - Episode Title.ext
            r'(?P<show>.*?)\s*-\s*(?P<title>.*?)\.(?P<ext>\w+)$',
            # Show Name Episode Title.ext
            r'(?P<show>.*?)\s+(?P<title>.*?)\.(?P<ext>\w+)$',
        ]
        
        # Month name to number mapping
        self.month_names = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
    
    def parse_filename(self, file_path: Union[str, Path]) -> ParsedMetadata:
        """
        Parse a video filename to extract metadata
        
        Args:
            file_path: Path to the video file
            
        Returns:
            ParsedMetadata: Parsed metadata with confidence score
        """
        file_path = Path(file_path)
        filename = file_path.name
        
        logger.debug("Parsing filename", filename=filename)
        
        # Try TV show patterns first (highest confidence)
        for pattern in self.tv_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                return self._parse_tv_match(match, filename)
        
        # Try date-based patterns
        for pattern in self.date_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                return self._parse_date_match(match, filename)
        
        # Try simple patterns (lowest confidence)
        for pattern in self.simple_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                return self._parse_simple_match(match, filename)
        
        # Fallback: extract show name from directory structure
        return self._parse_fallback(file_path)
    
    def _parse_tv_match(self, match: re.Match, filename: str) -> ParsedMetadata:
        """Parse TV show pattern match"""
        groups = match.groupdict()
        
        show_name = self._clean_show_name(groups.get('show', ''))
        season = int(groups.get('season', 0)) if groups.get('season') else None
        episode = int(groups.get('episode', 0)) if groups.get('episode') else None
        title = self._clean_title(groups.get('title', ''))
        
        return ParsedMetadata(
            show_name=show_name,
            season=season,
            episode=episode,
            title=title,
            raw_filename=filename,
            confidence=0.9
        )
    
    def _parse_date_match(self, match: re.Match, filename: str) -> ParsedMetadata:
        """Parse date-based pattern match"""
        groups = match.groupdict()
        
        show_name = self._clean_show_name(groups.get('show', ''))
        topic = self._clean_title(groups.get('topic', ''))
        
        # Handle different date formats
        date_str = None
        if 'date' in groups and groups['date']:
            if len(groups['date']) == 8:  # YYYYMMDD
                date_str = f"{groups['date'][:4]}-{groups['date'][4:6]}-{groups['date'][6:8]}"
            else:  # YYYY-MM-DD
                date_str = groups['date']
        elif 'year' in groups and 'month' in groups and 'day' in groups:
            # Convert month name to number
            month_num = self.month_names.get(groups['month'].lower()[:3], '01')
            day = groups['day'].zfill(2)
            date_str = f"{groups['year']}-{month_num}-{day}"
        
        return ParsedMetadata(
            show_name=show_name,
            date=date_str,
            topic=topic,
            raw_filename=filename,
            confidence=0.8
        )
    
    def _parse_simple_match(self, match: re.Match, filename: str) -> ParsedMetadata:
        """Parse simple pattern match"""
        groups = match.groupdict()
        
        show_name = self._clean_show_name(groups.get('show', ''))
        title = self._clean_title(groups.get('title', ''))
        
        return ParsedMetadata(
            show_name=show_name,
            title=title,
            raw_filename=filename,
            confidence=0.5
        )
    
    def _parse_fallback(self, file_path: Path) -> ParsedMetadata:
        """Fallback parsing using directory structure"""
        # Try to extract show name from parent directory
        parent_dir = file_path.parent.name
        show_name = self._clean_show_name(parent_dir)
        
        # Use filename without extension as title
        title = self._clean_title(file_path.stem)
        
        return ParsedMetadata(
            show_name=show_name,
            title=title,
            raw_filename=file_path.name,
            confidence=0.3
        )
    
    def _clean_show_name(self, raw_name: str) -> str:
        """Clean and normalize show name"""
        if not raw_name:
            return "Unknown Show"
        
        # Replace common separators with spaces
        cleaned = re.sub(r'[._-]+', ' ', raw_name)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Title case
        cleaned = cleaned.title()
        
        return cleaned or "Unknown Show"
    
    def _clean_title(self, raw_title: str) -> str:
        """Clean and normalize episode title"""
        if not raw_title:
            return ""
        
        # Replace common separators with spaces
        cleaned = re.sub(r'[._-]+', ' ', raw_title)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Title case
        cleaned = cleaned.title()
        
        return cleaned


class SlugGenerator:
    """Generates URL-friendly slugs from text"""
    
    @staticmethod
    def generate_slug(text: str, max_length: int = 50) -> str:
        """
        Generate a URL-friendly slug from text
        
        Args:
            text: Input text
            max_length: Maximum length of slug
            
        Returns:
            str: URL-friendly slug
        """
        if not text:
            return ""
        
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces and special characters with hyphens
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        # Truncate if too long
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip('-')
        
        return slug or "unknown"


class EpisodeIDGenerator:
    """Generates stable episode IDs with collision detection"""
    
    def __init__(self):
        self.slug_generator = SlugGenerator()
    
    def generate_episode_id(self, metadata: EpisodeMetadata) -> str:
        """
        Generate episode ID in format: {show-slug}-s{season}e{episode}-{date}-{topic-slug}
        
        Args:
            metadata: Episode metadata
            
        Returns:
            str: Generated episode ID
        """
        parts = []
        
        # Show slug (required)
        show_slug = metadata.show_slug or self.slug_generator.generate_slug(metadata.show_name)
        parts.append(show_slug)
        
        # Season and episode
        if metadata.season is not None and metadata.episode is not None:
            parts.append(f"s{metadata.season}e{metadata.episode}")
        
        # Date
        if metadata.date:
            # Normalize date format
            date_slug = self._normalize_date_slug(metadata.date)
            if date_slug:
                parts.append(date_slug)
        
        # Topic slug
        if metadata.topic_slug:
            parts.append(metadata.topic_slug)
        elif metadata.topic:
            topic_slug = self.slug_generator.generate_slug(metadata.topic)
            parts.append(topic_slug)
        
        episode_id = "-".join(parts)
        
        logger.debug("Generated episode ID", 
                   episode_id=episode_id,
                   show=metadata.show_name,
                   season=metadata.season,
                   episode=metadata.episode,
                   date=metadata.date,
                   topic=metadata.topic)
        
        return episode_id
    
    def ensure_unique_id(self, base_id: str, existing_ids: Set[str]) -> str:
        """
        Ensure episode ID is unique by adding suffix if needed
        
        Args:
            base_id: Base episode ID
            existing_ids: Set of existing episode IDs
            
        Returns:
            str: Unique episode ID
        """
        if base_id not in existing_ids:
            return base_id
        
        # Add numeric suffix to make unique
        counter = 1
        while True:
            unique_id = f"{base_id}-{counter}"
            if unique_id not in existing_ids:
                logger.info("Episode ID collision resolved", 
                          original_id=base_id,
                          unique_id=unique_id)
                return unique_id
            counter += 1
    
    def _normalize_date_slug(self, date_str: str) -> str:
        """Normalize date string to consistent format"""
        if not date_str:
            return ""
        
        # Try to parse various date formats
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
            r'(\d{4})(\d{2})(\d{2})',    # YYYYMMDD
            r'(\d{2})/(\d{2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{2})-(\d{2})-(\d{4})',  # MM-DD-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.match(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if len(groups[0]) == 4:  # Year first
                        year, month, day = groups
                    else:  # Month/day first
                        month, day, year = groups
                    
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Fallback: return as-is if can't parse
        return self.slug_generator.generate_slug(date_str)


class EpisodeNormalizer:
    """
    Main episode normalizer that converts video files to structured episode objects
    """
    
    def __init__(self):
        self.filename_parser = FilenameParser()
        self.id_generator = EpisodeIDGenerator()
        self.slug_generator = SlugGenerator()
    
    def normalize_file(self, video_file: VideoFile, existing_ids: Optional[Set[str]] = None) -> EpisodeObject:
        """
        Convert a VideoFile to a normalized EpisodeObject
        
        Args:
            video_file: Video file to normalize
            existing_ids: Set of existing episode IDs for collision detection
            
        Returns:
            EpisodeObject: Normalized episode object
            
        Raises:
            NormalizationError: If normalization fails
        """
        if existing_ids is None:
            existing_ids = set()
        
        try:
            logger.info("Normalizing video file", file=video_file.path)
            
            # Parse filename to extract metadata
            parsed = self.filename_parser.parse_filename(video_file.path)
            
            # Create episode metadata
            metadata = self._create_episode_metadata(parsed, video_file)
            
            # Generate episode ID using naming service (fallback naming at discovery)
            naming_service = get_naming_service()
            episode_id = naming_service.generate_episode_id(
                show_name=None,  # Will be set after AI enrichment
                episode_number=None,
                date=datetime.now(),
                source_filename=Path(video_file.path).name
            )
            
            # Ensure uniqueness
            unique_id = self.id_generator.ensure_unique_id(episode_id, existing_ids)
            
            # Create media info (will be populated later in pipeline)
            media_info = MediaInfo()
            
            # Calculate content hash
            content_hash = ContentHasher.calculate_metadata_hash(
                video_file.to_source_info(), 
                media_info
            )
            
            # Create episode object
            episode = EpisodeObject(
                episode_id=unique_id,
                content_hash=content_hash,
                source=video_file.to_source_info(),
                media=media_info,
                metadata=metadata
            )
            
            logger.info("Video file normalized successfully", 
                       file=video_file.path,
                       episode_id=unique_id,
                       show=metadata.show_name,
                       confidence=parsed.confidence)
            
            return episode
        
        except Exception as e:
            error_msg = f"Failed to normalize video file {video_file.path}: {e}"
            logger.error(error_msg)
            raise NormalizationError(error_msg) from e
    
    def _create_episode_metadata(self, parsed: ParsedMetadata, video_file: VideoFile) -> EpisodeMetadata:
        """Create EpisodeMetadata from parsed data"""
        
        # Generate slugs
        show_slug = self.slug_generator.generate_slug(parsed.show_name or "unknown-show")
        topic_slug = self.slug_generator.generate_slug(parsed.topic) if parsed.topic else None
        
        # Create description from available info
        description_parts = []
        if parsed.title:
            description_parts.append(parsed.title)
        if parsed.topic and parsed.topic != parsed.title:
            description_parts.append(parsed.topic)
        
        description = " - ".join(description_parts) if description_parts else None
        
        return EpisodeMetadata(
            show_name=parsed.show_name or "Unknown Show",
            show_slug=show_slug,
            season=parsed.season,
            episode=parsed.episode,
            date=parsed.date,
            topic=parsed.topic,
            topic_slug=topic_slug,
            title=parsed.title,
            description=description
        )
    
    def extract_metadata(self, file_path: Union[str, Path]) -> EpisodeMetadata:
        """
        Extract metadata from a file path without creating full episode object
        
        Args:
            file_path: Path to video file
            
        Returns:
            EpisodeMetadata: Extracted metadata
        """
        parsed = self.filename_parser.parse_filename(file_path)
        
        # Create a dummy VideoFile for metadata creation
        file_path = Path(file_path)
        if file_path.exists():
            stat = file_path.stat()
            video_file = VideoFile(
                path=str(file_path),
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime)
            )
        else:
            video_file = VideoFile(
                path=str(file_path),
                size=0,
                modified_time=datetime.now()
            )
        
        return self._create_episode_metadata(parsed, video_file)
    
    def validate_episode_id_uniqueness(self, episode_id: str, existing_episodes: List[EpisodeObject]) -> bool:
        """
        Validate that an episode ID is unique across existing episodes
        
        Args:
            episode_id: Episode ID to validate
            existing_episodes: List of existing episodes
            
        Returns:
            bool: True if ID is unique, False otherwise
        """
        existing_ids = {ep.episode_id for ep in existing_episodes}
        return episode_id not in existing_ids
    
    def get_normalization_stats(self, episodes: List[EpisodeObject]) -> Dict[str, Any]:
        """
        Get statistics about normalized episodes
        
        Args:
            episodes: List of normalized episodes
            
        Returns:
            Dict: Statistics about the episodes
        """
        if not episodes:
            return {
                'total_episodes': 0,
                'shows': {},
                'date_range': None,
                'season_episode_count': 0,
                'date_based_count': 0
            }
        
        # Group by show
        shows = {}
        date_based_count = 0
        season_episode_count = 0
        dates = []
        
        for episode in episodes:
            show_name = episode.get_show_name()
            if show_name not in shows:
                shows[show_name] = {
                    'count': 0,
                    'seasons': set(),
                    'has_dates': False
                }
            
            shows[show_name]['count'] += 1
            
            if episode.metadata.season is not None:
                shows[show_name]['seasons'].add(episode.metadata.season)
                season_episode_count += 1
            
            if episode.metadata.date:
                shows[show_name]['has_dates'] = True
                date_based_count += 1
                dates.append(episode.metadata.date)
        
        # Convert seasons sets to counts
        for show_data in shows.values():
            show_data['seasons'] = len(show_data['seasons'])
        
        # Date range
        date_range = None
        if dates:
            dates.sort()
            date_range = {
                'earliest': dates[0],
                'latest': dates[-1]
            }
        
        return {
            'total_episodes': len(episodes),
            'shows': shows,
            'date_range': date_range,
            'season_episode_count': season_episode_count,
            'date_based_count': date_based_count
        }


# Utility functions
def batch_normalize_files(video_files: List[VideoFile], 
                         normalizer: Optional[EpisodeNormalizer] = None) -> List[EpisodeObject]:
    """
    Normalize a batch of video files
    
    Args:
        video_files: List of video files to normalize
        normalizer: Optional normalizer instance (creates new if None)
        
    Returns:
        List[EpisodeObject]: Normalized episodes
    """
    if normalizer is None:
        normalizer = EpisodeNormalizer()
    
    episodes = []
    existing_ids = set()
    
    for video_file in video_files:
        try:
            episode = normalizer.normalize_file(video_file, existing_ids)
            episodes.append(episode)
            existing_ids.add(episode.episode_id)
        except NormalizationError as e:
            logger.error("Failed to normalize file", 
                        file=video_file.path, 
                        error=str(e))
            continue
    
    return episodes


def find_duplicate_episode_ids(episodes: List[EpisodeObject]) -> List[Tuple[str, List[EpisodeObject]]]:
    """
    Find episodes with duplicate IDs
    
    Args:
        episodes: List of episodes to check
        
    Returns:
        List of tuples (episode_id, list_of_episodes_with_that_id)
    """
    id_groups = {}
    
    for episode in episodes:
        episode_id = episode.episode_id
        if episode_id not in id_groups:
            id_groups[episode_id] = []
        id_groups[episode_id].append(episode)
    
    # Return only groups with duplicates
    duplicates = [(id, eps) for id, eps in id_groups.items() if len(eps) > 1]
    
    return duplicates