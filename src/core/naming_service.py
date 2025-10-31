"""
Naming Service - Episode ID and Path Generation

Handles:
1. Episode ID generation from templates
2. Folder structure organization by show
3. Show name mapping and slugification
4. Fallback naming for uncategorized content
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import re
import json
from dataclasses import dataclass

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class NamingConfig:
    """Configuration for naming conventions"""
    folder_structure: str = "{show_folder}/{year}"
    episode_template: str = "{show_folder}_ep{episode_number}_{date}"
    date_format: str = "%Y-%m-%d"
    fallback_template: str = "{source_name}_{timestamp}"
    uncategorized_folder: str = "_uncategorized"


# Show name mapping - AI extracted name → folder name
SHOW_NAME_MAPPING = {
    # The News Forum shows
    "the news forum": "thenewsforum",
    "news forum": "thenewsforum",
    "newsroom": "thenewsforum",
    "the newsroom": "thenewsforum",
    
    # Individual shows
    "forum daily news": "ForumDailyNews",
    "daily news": "ForumDailyNews",
    
    "boom and bust": "BoomAndBust",
    "boom & bust": "BoomAndBust",
    
    "canadian justice": "CanadianJustice",
    
    "counterpoint": "Counterpoint",
    
    "canadian innovators": "CanadianInnovators",
    "innovators": "CanadianInnovators",
    
    "the ledrew show": "TheLeDrewShow",
    "ledrew show": "TheLeDrewShow",
    "ledrew": "TheLeDrewShow",
    
    "my generation": "MyGeneration",
    
    "forum focus": "ForumFocus",
    
    "empowered": "Empowered",
}


class NamingService:
    """
    Service for generating episode IDs and organizing file paths
    
    Provides consistent naming across the pipeline based on:
    - AI-extracted show names
    - Episode numbers
    - Dates
    - Configurable templates
    """
    
    def __init__(self, config: Optional[NamingConfig] = None):
        """
        Initialize naming service
        
        Args:
            config: Naming configuration (uses defaults if not provided)
        """
        self.config = config or NamingConfig()
        self.show_mappings = self._load_show_mappings()
        logger.info("NamingService initialized",
                   folder_structure=self.config.folder_structure,
                   episode_template=self.config.episode_template,
                   show_mappings_count=len(self.show_mappings))
    
    def _load_show_mappings(self) -> Dict[str, str]:
        """
        Load show name mappings from config file, fallback to defaults
        
        Returns:
            Dictionary mapping AI-extracted names to folder names
        """
        config_file = Path("config/show_mappings.json")
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)
                logger.info("Loaded show mappings from config file",
                           count=len(mappings),
                           path=str(config_file))
                return mappings
            except Exception as e:
                logger.warning("Failed to load show mappings from config, using defaults",
                              error=str(e))
        
        # Return default mappings
        return SHOW_NAME_MAPPING.copy()
    
    def generate_episode_id(self, 
                           show_name: Optional[str] = None,
                           episode_number: Optional[str] = None,
                           date: Optional[datetime] = None,
                           source_filename: Optional[str] = None) -> str:
        """
        Generate episode ID based on available metadata
        
        Args:
            show_name: AI-extracted show name
            episode_number: Episode number (can be string like "140" or "S01E05")
            date: Episode date
            source_filename: Original filename for fallback
            
        Returns:
            Generated episode ID (e.g., "ForumDailyNews_ep140_2024-10-27")
        """
        # Use current date if not provided
        if date is None:
            date = datetime.now()
        
        # If we have show name, use structured naming
        if show_name:
            show_folder = self.map_show_name(show_name)
            episode_num = self._format_episode_number(episode_number) if episode_number else "000"
            date_str = date.strftime(self.config.date_format)
            
            episode_id = self.config.episode_template.format(
                show_folder=show_folder,
                episode_number=episode_num,
                date=date_str,
                date_compact=date.strftime("%Y%m%d")
            )
            
            logger.info("Generated structured episode ID",
                       episode_id=episode_id,
                       show_name=show_name,
                       show_folder=show_folder)
            
            return episode_id
        
        # Fallback to filename-based naming
        if source_filename:
            source_name = self._slugify(Path(source_filename).stem)
            timestamp = date.strftime("%Y%m%d_%H%M%S")
            
            episode_id = self.config.fallback_template.format(
                source_name=source_name,
                timestamp=timestamp
            )
            
            logger.warning("Using fallback episode ID (no show name)",
                          episode_id=episode_id,
                          source_filename=source_filename)
            
            return episode_id
        
        # Last resort: timestamp only
        timestamp = date.strftime("%Y%m%d_%H%M%S")
        episode_id = f"episode_{timestamp}"
        
        logger.warning("Using timestamp-only episode ID",
                      episode_id=episode_id)
        
        return episode_id
    
    def get_episode_folder_path(self,
                                episode_id: str,
                                show_name: Optional[str] = None,
                                date: Optional[datetime] = None,
                                base_path: str = "data/outputs") -> Path:
        """
        Generate full folder path for episode
        
        Args:
            episode_id: Episode identifier
            show_name: Show name for folder organization
            date: Episode date for year/month folders
            base_path: Base output directory
            
        Returns:
            Full path (e.g., "data/outputs/ForumDailyNews/2024/episode_id/")
        """
        if date is None:
            date = datetime.now()
        
        # Build folder structure
        if show_name:
            show_folder = self.map_show_name(show_name)
            year = date.strftime("%Y")
            month = date.strftime("%m")
            
            folder_path = self.config.folder_structure.format(
                show_folder=show_folder,
                year=year,
                month=month
            )
        else:
            # Uncategorized
            folder_path = self.config.uncategorized_folder
        
        # Combine with base path and episode ID
        full_path = Path(base_path) / folder_path / episode_id
        
        logger.debug("Generated episode folder path",
                    episode_id=episode_id,
                    path=str(full_path))
        
        return full_path
    
    def map_show_name(self, show_name: str) -> str:
        """
        Map AI-extracted show name to folder name
        
        Args:
            show_name: Raw show name from AI (e.g., "The News Forum")
            
        Returns:
            Folder name (e.g., "thenewsforum")
        """
        # Normalize for lookup
        normalized = show_name.lower().strip()
        
        # Check mapping (use loaded mappings instead of hardcoded)
        if normalized in self.show_mappings:
            folder_name = self.show_mappings[normalized]
            logger.debug("Mapped show name",
                        input=show_name,
                        output=folder_name)
            return folder_name
        
        # Fallback: slugify the show name
        folder_name = self._slugify(show_name)
        logger.warning("No mapping found for show name, using slugified version",
                      show_name=show_name,
                      folder_name=folder_name)
        
        return folder_name
    
    def _format_episode_number(self, episode_number: Any) -> str:
        """
        Format episode number consistently
        
        Args:
            episode_number: Raw episode number (int, string, etc.)
            
        Returns:
            Formatted episode number (e.g., "140", "S01E05")
        """
        if episode_number is None:
            return "000"
        
        # Convert to string
        ep_str = str(episode_number).strip()
        
        # If it's already formatted (e.g., "S01E05"), keep it
        if re.match(r'[Ss]\d+[Ee]\d+', ep_str):
            return ep_str.upper()
        
        # If it's a number, pad it
        try:
            ep_num = int(re.sub(r'\D', '', ep_str))  # Extract digits
            return f"{ep_num:03d}"  # Pad to 3 digits
        except (ValueError, TypeError):
            return "000"
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug
        
        Args:
            text: Input text
            
        Returns:
            Slugified text (lowercase, no spaces, alphanumeric + hyphens)
        """
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces and underscores with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        
        # Remove non-alphanumeric characters (except hyphens)
        text = re.sub(r'[^a-z0-9-]', '', text)
        
        # Remove multiple consecutive hyphens
        text = re.sub(r'-+', '-', text)
        
        # Strip leading/trailing hyphens
        text = text.strip('-')
        
        return text
    
    def parse_episode_id(self, episode_id: str) -> Dict[str, Any]:
        """
        Parse episode ID back into components
        
        Args:
            episode_id: Episode ID to parse
            
        Returns:
            Dict with show_folder, episode_number, date (if parseable)
        """
        parts = episode_id.split('_')
        
        result = {
            'episode_id': episode_id,
            'show_folder': None,
            'episode_number': None,
            'date': None
        }
        
        # Try to parse structured format: show_epXXX_date
        if len(parts) >= 3:
            result['show_folder'] = parts[0]
            
            # Extract episode number
            if parts[1].startswith('ep'):
                result['episode_number'] = parts[1][2:]
            
            # Parse date
            try:
                result['date'] = datetime.strptime(parts[2], self.config.date_format)
            except (ValueError, IndexError):
                pass
        
        return result
    
    def get_show_list(self) -> list[str]:
        """
        Get list of all configured show folders
        
        Returns:
            List of show folder names
        """
        # Get unique folder names from mapping
        show_folders = sorted(set(SHOW_NAME_MAPPING.values()))
        return show_folders
    
    def add_show_mapping(self, show_name: str, folder_name: str):
        """
        Add a new show name mapping at runtime
        
        Args:
            show_name: AI-extracted show name (normalized to lowercase)
            folder_name: Desired folder name
        """
        normalized = show_name.lower().strip()
        SHOW_NAME_MAPPING[normalized] = folder_name
        
        logger.info("Added show mapping",
                   show_name=show_name,
                   folder_name=folder_name)


# Global instance
_naming_service = None


def get_naming_service(config: Optional[NamingConfig] = None) -> NamingService:
    """
    Get global naming service instance
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        NamingService instance
    """
    global _naming_service
    
    if _naming_service is None:
        _naming_service = NamingService(config)
    
    return _naming_service
