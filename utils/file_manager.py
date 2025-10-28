"""
File management utilities for GUI Control Panel

Provides file system operations for organized output directories,
file validation, and path management functions with comprehensive
error handling, caching, and logging.
"""

import os
import shutil
import json
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """File information structure"""
    path: str
    name: str
    size_bytes: int
    size_mb: float
    exists: bool
    is_valid: bool
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class DirectoryInfo:
    """Directory information structure"""
    path: str
    exists: bool
    file_count: int
    total_size_bytes: int
    total_size_mb: float
    files: List[FileInfo]
    subdirectories: List[str]


@dataclass
class EpisodeFileStructure:
    """Episode file organization structure"""
    episode_id: str
    clips_dir: DirectoryInfo
    social_dir: DirectoryInfo
    public_dir: DirectoryInfo
    meta_file: Optional[FileInfo]
    transcript_files: List[FileInfo]
    total_files: int
    total_size_mb: float
    is_complete: bool
    missing_components: List[str]


class FileManager:
    """
    File management utilities for GUI Control Panel
    
    Handles file system operations, validation, organization, and caching
    for the video processing pipeline outputs.
    """
    
    def __init__(self, base_data_dir: str = "data", enable_cache: bool = True):
        """
        Initialize file manager
        
        Args:
            base_data_dir: Base directory for all data files (default: "data")
            enable_cache: Enable file operation caching for performance
        """
        self.base_data_dir = Path(base_data_dir)
        self.enable_cache = enable_cache
        
        # Standard directory structure
        self.clips_dir = self.base_data_dir / "clips"
        self.social_dir = self.base_data_dir / "social"
        self.public_dir = self.base_data_dir / "public"
        self.meta_dir = self.base_data_dir / "meta"
        self.transcripts_dir = self.base_data_dir / "transcripts"
        self.outputs_dir = self.base_data_dir / "outputs"
        
        # Cache configuration
        self.cache_ttl = {
            'file_info': 60,        # File info cached for 1 minute
            'directory_scan': 120,  # Directory scans cached for 2 minutes
            'episode_structure': 180, # Episode structure cached for 3 minutes
        }
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """Generate cache key for file operations"""
        key_data = f"{operation}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str, cache_type: str) -> Optional[Any]:
        """Get cached result if valid"""
        if not self.enable_cache or 'file_cache' not in st.session_state:
            return None
        
        cache = st.session_state['file_cache']
        timestamps = st.session_state.get('file_cache_timestamps', {})
        
        if cache_key not in cache or cache_key not in timestamps:
            return None
        
        # Check if cache is still valid
        cache_time = timestamps[cache_key]
        ttl = self.cache_ttl.get(cache_type, 60)
        
        if (datetime.now() - cache_time).total_seconds() > ttl:
            # Cache expired, remove it
            del cache[cache_key]
            del timestamps[cache_key]
            return None
        
        return cache[cache_key]
    
    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Cache result for future use"""
        if not self.enable_cache:
            return
        
        if 'file_cache' not in st.session_state:
            st.session_state['file_cache'] = {}
        if 'file_cache_timestamps' not in st.session_state:
            st.session_state['file_cache_timestamps'] = {}
        
        st.session_state['file_cache'][cache_key] = result
        st.session_state['file_cache_timestamps'][cache_key] = datetime.now()
        
        # Limit cache size
        if len(st.session_state['file_cache']) > 50:
            # Remove oldest entries
            timestamps = st.session_state['file_cache_timestamps']
            oldest_keys = sorted(timestamps.keys(), key=lambda k: timestamps[k])[:10]
            
            for key in oldest_keys:
                if key in st.session_state['file_cache']:
                    del st.session_state['file_cache'][key]
                if key in timestamps:
                    del timestamps[key]
    
    def ensure_directory_structure(self) -> bool:
        """
        Ensure all required directories exist
        
        Returns:
            bool: True if all directories were created/exist successfully
        """
        directories = [
            self.clips_dir,
            self.social_dir,
            self.public_dir,
            self.meta_dir,
            self.transcripts_dir,
            self.outputs_dir
        ]
        
        try:
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {directory}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            return False
    
    def create_episode_directories(self, episode_id: str) -> bool:
        """
        Create organized directory structure for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            bool: True if directories were created successfully
        """
        try:
            # Create episode-specific directories
            episode_clips_dir = self.clips_dir / episode_id
            episode_social_dir = self.social_dir / episode_id
            
            directories = [episode_clips_dir, episode_social_dir]
            
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created episode directory: {directory}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating episode directories for {episode_id}: {e}")
            return False
    
    def validate_file(self, file_path: Union[str, Path], min_size_bytes: int = 1, use_cache: bool = True) -> FileInfo:
        """
        Validate a file exists and has non-zero size (like process_clips.py check_clip_files)
        
        Args:
            file_path: Path to file to validate
            min_size_bytes: Minimum file size in bytes (default: 1)
            use_cache: Use cached result if available
            
        Returns:
            FileInfo: File validation results
        """
        path = Path(file_path)
        
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key('validate_file', str(path), min_size_bytes)
            cached_result = self._get_cached_result(cache_key, 'file_info')
            if cached_result:
                return cached_result
        
        try:
            if not path.exists():
                return FileInfo(
                    path=str(path),
                    name=path.name,
                    size_bytes=0,
                    size_mb=0.0,
                    exists=False,
                    is_valid=False,
                    error="File does not exist"
                )
            
            if not path.is_file():
                return FileInfo(
                    path=str(path),
                    name=path.name,
                    size_bytes=0,
                    size_mb=0.0,
                    exists=True,
                    is_valid=False,
                    error="Path is not a file"
                )
            
            stat = path.stat()
            size_bytes = stat.st_size
            size_mb = size_bytes / (1024 * 1024)
            
            is_valid = size_bytes >= min_size_bytes
            error = None if is_valid else f"File too small ({size_bytes} bytes < {min_size_bytes} bytes)"
            
            result = FileInfo(
                path=str(path),
                name=path.name,
                size_bytes=size_bytes,
                size_mb=size_mb,
                exists=True,
                is_valid=is_valid,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                error=error
            )
            
            # Cache the result
            if use_cache:
                cache_key = self._get_cache_key('validate_file', str(path), min_size_bytes)
                self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating file {path}: {e}")
            result = FileInfo(
                path=str(path),
                name=path.name,
                size_bytes=0,
                size_mb=0.0,
                exists=False,
                is_valid=False,
                error=f"Validation error: {str(e)}"
            )
            
            # Cache error results too (with shorter TTL)
            if use_cache:
                cache_key = self._get_cache_key('validate_file', str(path), min_size_bytes)
                self._cache_result(cache_key, result)
            
            return result
    
    def scan_directory(self, directory_path: Union[str, Path], recursive: bool = False) -> DirectoryInfo:
        """
        Scan directory and return file information
        
        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            DirectoryInfo: Directory scan results
        """
        path = Path(directory_path)
        
        if not path.exists():
            return DirectoryInfo(
                path=str(path),
                exists=False,
                file_count=0,
                total_size_bytes=0,
                total_size_mb=0.0,
                files=[],
                subdirectories=[]
            )
        
        try:
            files = []
            subdirectories = []
            total_size = 0
            
            # Scan directory contents
            for item in path.iterdir():
                if item.is_file():
                    file_info = self.validate_file(item)
                    files.append(file_info)
                    if file_info.is_valid:
                        total_size += file_info.size_bytes
                elif item.is_dir():
                    subdirectories.append(item.name)
                    
                    # Recursive scanning if requested
                    if recursive:
                        subdir_info = self.scan_directory(item, recursive=True)
                        files.extend(subdir_info.files)
                        total_size += subdir_info.total_size_bytes
            
            return DirectoryInfo(
                path=str(path),
                exists=True,
                file_count=len(files),
                total_size_bytes=total_size,
                total_size_mb=total_size / (1024 * 1024),
                files=files,
                subdirectories=subdirectories
            )
            
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
            return DirectoryInfo(
                path=str(path),
                exists=True,
                file_count=0,
                total_size_bytes=0,
                total_size_mb=0.0,
                files=[],
                subdirectories=[]
            )
    
    def check_clip_files(self, episode_id: str) -> DirectoryInfo:
        """
        Check clip files for an episode (similar to process_clips.py check_clip_files)
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            DirectoryInfo: Clip files information
        """
        clips_dir = self.clips_dir / episode_id
        return self.scan_directory(clips_dir, recursive=True)
    
    def get_episode_file_structure(self, episode_id: str) -> EpisodeFileStructure:
        """
        Get complete file structure for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            EpisodeFileStructure: Complete episode file organization
        """
        # Scan clips directory
        clips_dir = self.check_clip_files(episode_id)
        
        # Scan social media directory
        social_dir = self.scan_directory(self.social_dir / episode_id)
        
        # Scan public directory (HTML pages)
        public_dir = self.scan_directory(self.public_dir, recursive=True)
        
        # Check metadata file
        meta_file_path = self.meta_dir / f"{episode_id}.json"
        meta_file = self.validate_file(meta_file_path) if meta_file_path.exists() else None
        
        # Check transcript files
        transcript_files = []
        for ext in ['.txt', '.vtt']:
            transcript_path = self.transcripts_dir / f"{episode_id}{ext}"
            if transcript_path.exists():
                transcript_files.append(self.validate_file(transcript_path))
        
        # Calculate totals
        total_files = clips_dir.file_count + social_dir.file_count + public_dir.file_count
        total_files += len(transcript_files)
        if meta_file and meta_file.is_valid:
            total_files += 1
        
        total_size_mb = clips_dir.total_size_mb + social_dir.total_size_mb + public_dir.total_size_mb
        total_size_mb += sum(f.size_mb for f in transcript_files if f.is_valid)
        if meta_file and meta_file.is_valid:
            total_size_mb += meta_file.size_mb
        
        # Check completeness
        missing_components = []
        if clips_dir.file_count == 0:
            missing_components.append("clips")
        if social_dir.file_count == 0:
            missing_components.append("social_packages")
        if not transcript_files:
            missing_components.append("transcripts")
        if not meta_file or not meta_file.is_valid:
            missing_components.append("metadata")
        
        is_complete = len(missing_components) == 0
        
        return EpisodeFileStructure(
            episode_id=episode_id,
            clips_dir=clips_dir,
            social_dir=social_dir,
            public_dir=public_dir,
            meta_file=meta_file,
            transcript_files=transcript_files,
            total_files=total_files,
            total_size_mb=total_size_mb,
            is_complete=is_complete,
            missing_components=missing_components
        )
    
    def save_social_package(
        self, 
        episode_id: str, 
        platform: str, 
        package_data: Dict[str, Any]
    ) -> bool:
        """
        Save social media package to organized directory structure
        
        Args:
            episode_id: Episode identifier
            platform: Social media platform (twitter, instagram, etc.)
            package_data: Package data to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Ensure episode social directory exists
            episode_social_dir = self.social_dir / episode_id
            episode_social_dir.mkdir(parents=True, exist_ok=True)
            
            # Save package as JSON file
            package_file = episode_social_dir / f"{platform}.json"
            
            with open(package_file, 'w', encoding='utf-8') as f:
                json.dump(package_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved social package: {package_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving social package for {episode_id}/{platform}: {e}")
            return False
    
    def load_social_package(self, episode_id: str, platform: str) -> Optional[Dict[str, Any]]:
        """
        Load social media package from file
        
        Args:
            episode_id: Episode identifier
            platform: Social media platform
            
        Returns:
            Dict or None: Package data if found and valid
        """
        try:
            package_file = self.social_dir / episode_id / f"{platform}.json"
            
            if not package_file.exists():
                return None
            
            with open(package_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading social package for {episode_id}/{platform}: {e}")
            return None
    
    def get_html_page_path(self, episode_id: str, show_slug: Optional[str] = None) -> Optional[str]:
        """
        Find HTML page path for an episode
        
        Args:
            episode_id: Episode identifier
            show_slug: Show slug for path construction (optional)
            
        Returns:
            str or None: Path to HTML page if found
        """
        # Try multiple possible HTML paths
        possible_paths = []
        
        if show_slug:
            possible_paths.extend([
                self.public_dir / "shows" / show_slug / episode_id / "index.html",
                self.public_dir / show_slug / episode_id / "index.html"
            ])
        
        possible_paths.extend([
            self.public_dir / episode_id / "index.html",
            self.public_dir / f"{episode_id}.html"
        ])
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def cleanup_episode_files(self, episode_id: str, keep_transcripts: bool = True) -> bool:
        """
        Clean up episode files (useful for re-processing)
        
        Args:
            episode_id: Episode identifier
            keep_transcripts: Whether to keep transcript files
            
        Returns:
            bool: True if cleanup was successful
        """
        try:
            # Remove clips directory
            clips_dir = self.clips_dir / episode_id
            if clips_dir.exists():
                shutil.rmtree(clips_dir)
                logger.info(f"Removed clips directory: {clips_dir}")
            
            # Remove outputs directory
            outputs_dir = self.outputs_dir / episode_id
            if outputs_dir.exists():
                shutil.rmtree(outputs_dir)
                logger.info(f"Removed outputs directory: {outputs_dir}")
            
            # Remove social packages
            social_dir = self.social_dir / episode_id
            if social_dir.exists():
                shutil.rmtree(social_dir)
                logger.info(f"Removed social directory: {social_dir}")
            
            # Remove transcripts if requested
            if not keep_transcripts:
                for ext in ['.txt', '.vtt']:
                    transcript_path = self.transcripts_dir / f"{episode_id}{ext}"
                    if transcript_path.exists():
                        transcript_path.unlink()
                        logger.info(f"Removed transcript: {transcript_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up episode files for {episode_id}: {e}")
            return False
    
    def get_file_organization_status(self) -> Dict[str, Any]:
        """
        Get overall file organization status
        
        Returns:
            Dict: Organization status summary
        """
        try:
            # Scan all main directories
            clips_info = self.scan_directory(self.clips_dir)
            social_info = self.scan_directory(self.social_dir)
            public_info = self.scan_directory(self.public_dir, recursive=True)
            meta_info = self.scan_directory(self.meta_dir)
            transcripts_info = self.scan_directory(self.transcripts_dir)
            
            # Count episodes with files
            episodes_with_clips = len(clips_info.subdirectories)
            episodes_with_social = len(social_info.subdirectories)
            
            total_files = (clips_info.file_count + social_info.file_count + 
                          public_info.file_count + meta_info.file_count + 
                          transcripts_info.file_count)
            
            total_size_mb = (clips_info.total_size_mb + social_info.total_size_mb + 
                           public_info.total_size_mb + meta_info.total_size_mb + 
                           transcripts_info.total_size_mb)
            
            return {
                "total_files": total_files,
                "total_size_mb": total_size_mb,
                "episodes_with_clips": episodes_with_clips,
                "episodes_with_social": episodes_with_social,
                "directories": {
                    "clips": {
                        "files": clips_info.file_count,
                        "size_mb": clips_info.total_size_mb,
                        "episodes": len(clips_info.subdirectories)
                    },
                    "social": {
                        "files": social_info.file_count,
                        "size_mb": social_info.total_size_mb,
                        "episodes": len(social_info.subdirectories)
                    },
                    "public": {
                        "files": public_info.file_count,
                        "size_mb": public_info.total_size_mb
                    },
                    "meta": {
                        "files": meta_info.file_count,
                        "size_mb": meta_info.total_size_mb
                    },
                    "transcripts": {
                        "files": transcripts_info.file_count,
                        "size_mb": transcripts_info.total_size_mb
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting file organization status: {e}")
            return {
                "total_files": 0,
                "total_size_mb": 0.0,
                "episodes_with_clips": 0,
                "episodes_with_social": 0,
                "directories": {},
                "error": str(e)
            }


# Convenience function for creating file manager instance
def create_file_manager(base_data_dir: str = "data", enable_cache: bool = True) -> FileManager:
    """
    Create and return a configured file manager instance with caching
    
    Args:
        base_data_dir: Base directory for data files
        enable_cache: Enable file operation caching for performance
        
    Returns:
        FileManager: Configured file manager instance
    """
    return FileManager(base_data_dir=base_data_dir, enable_cache=enable_cache)