"""
Video Discovery Engine for the Video Processing Pipeline

Handles multi-source video file discovery with pattern matching, stability checking,
and concurrent scanning capabilities. Supports local drives, UNC shares, and external drives.
"""

import os
import time
import fnmatch
import asyncio
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import SourceConfig, DiscoveryConfig
from .models import SourceInfo, MediaInfo, EpisodeMetadata, EpisodeObject, ContentHasher
from .exceptions import DiscoveryError, ConfigurationError
from .logging import get_logger

logger = get_logger('pipeline.discovery')


@dataclass
class VideoFile:
    """Represents a discovered video file"""
    path: str
    size: int
    modified_time: datetime
    source_type: str = "local"
    is_stable: bool = False
    
    def to_source_info(self) -> SourceInfo:
        """Convert to SourceInfo object"""
        return SourceInfo(
            path=self.path,
            file_size=self.size,
            last_modified=self.modified_time,
            source_type=self.source_type
        )


@dataclass
class DiscoveryResult:
    """Result of a discovery scan"""
    files_found: List[VideoFile]
    files_skipped: int
    errors: List[str]
    scan_duration: float
    source_path: str


class FileStabilityChecker:
    """Manages file stability checking with configurable time windows"""
    
    def __init__(self, stability_minutes: int = 5):
        self.stability_minutes = stability_minutes
        self._file_cache: Dict[str, Tuple[int, datetime]] = {}
        self._lock = threading.Lock()
    
    def is_file_stable(self, file_path: Union[str, Path]) -> bool:
        """
        Check if a file has been stable (unchanged) for the configured duration
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            bool: True if file is stable, False otherwise
        """
        file_path = str(file_path)
        
        try:
            stat = os.stat(file_path)
            current_size = stat.st_size
            current_mtime = datetime.fromtimestamp(stat.st_mtime)
            
            with self._lock:
                if file_path in self._file_cache:
                    cached_size, cached_mtime = self._file_cache[file_path]
                    
                    # Check if file has changed
                    if cached_size != current_size or cached_mtime != current_mtime:
                        # File changed, update cache
                        self._file_cache[file_path] = (current_size, current_mtime)
                        return False
                    
                    # File unchanged, check if enough time has passed
                    time_since_change = datetime.now() - current_mtime
                    is_stable = time_since_change >= timedelta(minutes=self.stability_minutes)
                    
                    if is_stable:
                        logger.debug("File is stable", 
                                   file=file_path, 
                                   stability_minutes=self.stability_minutes)
                    
                    return is_stable
                else:
                    # First time seeing this file
                    self._file_cache[file_path] = (current_size, current_mtime)
                    return False
        
        except (OSError, IOError) as e:
            logger.warning("Failed to check file stability", 
                         file=file_path, 
                         error=str(e))
            return False
    
    def clear_cache(self) -> None:
        """Clear the file stability cache"""
        with self._lock:
            self._file_cache.clear()
    
    def remove_from_cache(self, file_path: Union[str, Path]) -> None:
        """Remove a specific file from the stability cache"""
        file_path = str(file_path)
        with self._lock:
            self._file_cache.pop(file_path, None)


class PatternMatcher:
    """Handles include/exclude pattern matching for file discovery"""
    
    def __init__(self, include_patterns: List[str], exclude_patterns: List[str]):
        self.include_patterns = include_patterns or ["*"]
        self.exclude_patterns = exclude_patterns or []
    
    def matches(self, file_path: Union[str, Path]) -> bool:
        """
        Check if a file path matches the include/exclude patterns
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if file should be included, False otherwise
        """
        file_path = Path(file_path)
        filename = file_path.name.lower()
        
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern.lower()):
                logger.debug("File excluded by pattern", 
                           file=str(file_path), 
                           pattern=pattern)
                return False
        
        # Check include patterns
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(filename, pattern.lower()):
                logger.debug("File included by pattern", 
                           file=str(file_path), 
                           pattern=pattern)
                return True
        
        # No include pattern matched
        logger.debug("File not matched by include patterns", 
                   file=str(file_path), 
                   patterns=self.include_patterns)
        return False


class SourceScanner:
    """Scans a single video source for files"""
    
    def __init__(self, 
                 source_config: SourceConfig,
                 stability_checker: FileStabilityChecker,
                 pattern_matcher: PatternMatcher):
        self.source_config = source_config
        self.stability_checker = stability_checker
        self.pattern_matcher = pattern_matcher
    
    def scan_source(self) -> DiscoveryResult:
        """
        Scan a video source for files
        
        Returns:
            DiscoveryResult: Results of the scan
        """
        start_time = time.time()
        files_found = []
        files_skipped = 0
        errors = []
        
        source_path = Path(self.source_config.path)
        
        logger.info("Starting source scan", 
                   source=str(source_path),
                   include_patterns=self.source_config.include,
                   exclude_patterns=self.source_config.exclude)
        
        try:
            if not source_path.exists():
                error_msg = f"Source path does not exist: {source_path}"
                logger.error(error_msg)
                errors.append(error_msg)
                return DiscoveryResult(
                    files_found=[],
                    files_skipped=0,
                    errors=errors,
                    scan_duration=time.time() - start_time,
                    source_path=str(source_path)
                )
            
            # Determine source type
            source_type = self._determine_source_type(source_path)
            
            # Recursively scan directory
            for file_path in self._scan_directory_recursive(source_path):
                try:
                    # Check if file matches patterns
                    if not self.pattern_matcher.matches(file_path):
                        files_skipped += 1
                        continue
                    
                    # Get file info
                    stat = file_path.stat()
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Check file stability
                    is_stable = self.stability_checker.is_file_stable(file_path)
                    
                    video_file = VideoFile(
                        path=str(file_path),
                        size=stat.st_size,
                        modified_time=modified_time,
                        source_type=source_type,
                        is_stable=is_stable
                    )
                    
                    files_found.append(video_file)
                    
                    if is_stable:
                        logger.debug("Stable video file found", 
                                   file=str(file_path),
                                   size=stat.st_size)
                    else:
                        logger.debug("Unstable video file found", 
                                   file=str(file_path),
                                   size=stat.st_size)
                
                except (OSError, IOError) as e:
                    error_msg = f"Error processing file {file_path}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
        
        except Exception as e:
            error_msg = f"Error scanning source {source_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        scan_duration = time.time() - start_time
        
        logger.info("Source scan completed", 
                   source=str(source_path),
                   files_found=len(files_found),
                   files_skipped=files_skipped,
                   errors=len(errors),
                   duration=f"{scan_duration:.2f}s")
        
        return DiscoveryResult(
            files_found=files_found,
            files_skipped=files_skipped,
            errors=errors,
            scan_duration=scan_duration,
            source_path=str(source_path)
        )
    
    def _determine_source_type(self, path: Path) -> str:
        """Determine the type of source (local, unc, external)"""
        path_str = str(path)
        
        if path_str.startswith('\\\\'):
            return "unc"
        elif path.is_mount() or self._is_external_drive(path):
            return "external"
        else:
            return "local"
    
    def _is_external_drive(self, path: Path) -> bool:
        """Check if path is on an external drive (Windows-specific logic)"""
        try:
            # On Windows, check if it's a removable drive
            import psutil
            
            # Get the drive letter
            drive = path.anchor
            
            # Check disk usage to see if it's a valid drive
            for partition in psutil.disk_partitions():
                if partition.mountpoint.upper() == drive.upper():
                    # Check if it's a removable drive
                    return 'removable' in partition.opts.lower()
            
            return False
        except ImportError:
            # psutil not available, use simple heuristic
            # Assume drives other than C: might be external
            drive_letter = path.anchor[0].upper()
            return drive_letter not in ['C']
        except Exception:
            return False
    
    def _scan_directory_recursive(self, directory: Path) -> List[Path]:
        """Recursively scan directory for video files"""
        video_files = []
        
        try:
            for item in directory.rglob('*'):
                if item.is_file() and self._is_video_file(item):
                    video_files.append(item)
        except (OSError, IOError) as e:
            logger.warning("Error scanning directory", 
                         directory=str(directory), 
                         error=str(e))
        
        return video_files
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video file based on extension"""
        video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', 
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv'
        }
        
        return file_path.suffix.lower() in video_extensions


class DiscoveryEngine:
    """
    Main discovery engine for multi-source video scanning
    
    Handles concurrent scanning of multiple video sources with pattern matching,
    stability checking, and rate limiting.
    """
    
    def __init__(self, discovery_config: DiscoveryConfig):
        self.config = discovery_config
        self.stability_checker = FileStabilityChecker(discovery_config.stability_minutes)
        self._scan_lock = threading.Lock()
    
    def discover_videos(self, sources: List[SourceConfig]) -> List[VideoFile]:
        """
        Discover video files from multiple sources
        
        Args:
            sources: List of source configurations to scan
            
        Returns:
            List[VideoFile]: All discovered video files
            
        Raises:
            DiscoveryError: If discovery fails
        """
        if not sources:
            logger.warning("No sources configured for discovery")
            return []
        
        # Filter enabled sources
        enabled_sources = [s for s in sources if s.enabled]
        if not enabled_sources:
            logger.warning("No enabled sources found")
            return []
        
        logger.info("Starting video discovery", 
                   total_sources=len(enabled_sources),
                   max_concurrent=self.config.max_concurrent_scans)
        
        all_files = []
        total_errors = []
        
        # Use ThreadPoolExecutor for concurrent scanning
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_scans) as executor:
            # Submit scan tasks
            future_to_source = {}
            for source in enabled_sources:
                pattern_matcher = PatternMatcher(source.include, source.exclude)
                scanner = SourceScanner(source, self.stability_checker, pattern_matcher)
                future = executor.submit(scanner.scan_source)
                future_to_source[future] = source
            
            # Collect results
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result()
                    all_files.extend(result.files_found)
                    total_errors.extend(result.errors)
                    
                    logger.info("Source scan result", 
                               source=result.source_path,
                               files_found=len(result.files_found),
                               files_skipped=result.files_skipped,
                               errors=len(result.errors))
                
                except Exception as e:
                    error_msg = f"Failed to scan source {source.path}: {e}"
                    logger.error(error_msg)
                    total_errors.append(error_msg)
        
        # Filter for stable files only
        stable_files = [f for f in all_files if f.is_stable]
        
        logger.info("Video discovery completed", 
                   total_files=len(all_files),
                   stable_files=len(stable_files),
                   total_errors=len(total_errors))
        
        if total_errors:
            logger.warning("Discovery completed with errors", 
                         error_count=len(total_errors),
                         errors=total_errors[:5])  # Log first 5 errors
        
        return stable_files
    
    def is_file_stable(self, file_path: Union[str, Path], stability_minutes: Optional[int] = None) -> bool:
        """
        Check if a specific file is stable
        
        Args:
            file_path: Path to the file
            stability_minutes: Override stability duration (uses config default if None)
            
        Returns:
            bool: True if file is stable
        """
        if stability_minutes is not None:
            # Create temporary checker with custom duration
            temp_checker = FileStabilityChecker(stability_minutes)
            return temp_checker.is_file_stable(file_path)
        else:
            return self.stability_checker.is_file_stable(file_path)
    
    def matches_patterns(self, file_path: Union[str, Path], 
                        include_patterns: List[str], 
                        exclude_patterns: List[str]) -> bool:
        """
        Check if a file matches the given patterns
        
        Args:
            file_path: Path to check
            include_patterns: Patterns to include
            exclude_patterns: Patterns to exclude
            
        Returns:
            bool: True if file matches patterns
        """
        matcher = PatternMatcher(include_patterns, exclude_patterns)
        return matcher.matches(file_path)
    
    def clear_stability_cache(self) -> None:
        """Clear the file stability cache"""
        self.stability_checker.clear_cache()
        logger.info("File stability cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the stability cache"""
        with self.stability_checker._lock:
            cache_size = len(self.stability_checker._file_cache)
        
        return {
            'cache_size': cache_size,
            'stability_minutes': self.stability_checker.stability_minutes
        }


# Utility functions for working with discovery results
def filter_video_files_by_extension(files: List[VideoFile], 
                                  extensions: List[str]) -> List[VideoFile]:
    """Filter video files by file extensions"""
    extensions_lower = [ext.lower() for ext in extensions]
    
    filtered_files = []
    for file in files:
        file_ext = Path(file.path).suffix.lower()
        if file_ext in extensions_lower:
            filtered_files.append(file)
    
    return filtered_files


def group_files_by_source_type(files: List[VideoFile]) -> Dict[str, List[VideoFile]]:
    """Group video files by their source type"""
    groups = {}
    
    for file in files:
        source_type = file.source_type
        if source_type not in groups:
            groups[source_type] = []
        groups[source_type].append(file)
    
    return groups


def get_discovery_summary(files: List[VideoFile]) -> Dict[str, Any]:
    """Get a summary of discovery results"""
    if not files:
        return {
            'total_files': 0,
            'total_size_gb': 0.0,
            'by_source_type': {},
            'largest_file': None,
            'oldest_file': None,
            'newest_file': None
        }
    
    total_size = sum(f.size for f in files)
    by_source_type = group_files_by_source_type(files)
    
    # Find extremes
    largest_file = max(files, key=lambda f: f.size)
    oldest_file = min(files, key=lambda f: f.modified_time)
    newest_file = max(files, key=lambda f: f.modified_time)
    
    return {
        'total_files': len(files),
        'total_size_gb': total_size / (1024**3),
        'by_source_type': {k: len(v) for k, v in by_source_type.items()},
        'largest_file': {
            'path': largest_file.path,
            'size_gb': largest_file.size / (1024**3)
        },
        'oldest_file': {
            'path': oldest_file.path,
            'modified': oldest_file.modified_time.isoformat()
        },
        'newest_file': {
            'path': newest_file.path,
            'modified': newest_file.modified_time.isoformat()
        }
    }