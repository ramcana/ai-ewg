"""
Path normalization utilities for cross-platform compatibility

Handles path conversions between:
- Docker container paths (Linux-style: /data/...)
- Windows host paths (relative to project root)
- UNC network paths (\\server\share\...)
"""

import os
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Optional, Union
from .logging import get_logger

logger = get_logger('pipeline.path_utils')

# Get project root dynamically (where this file is located: src/core/path_utils.py)
# Project root is 2 levels up from this file
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def normalize_path(path_str: str) -> Path:
    """
    Normalize a path string to a valid Path object for the current OS
    
    Handles:
    - Linux-style paths from Docker containers
    - Windows-style paths with backslashes
    - Mixed separators
    - Relative paths
    
    Args:
        path_str: Path string in any format
        
    Returns:
        Path: Normalized Path object
        
    Example:
        >>> normalize_path("/data/videos/test.mp4")
        WindowsPath('path/to/project/data/videos/test.mp4')  # Relative to project root
        
        >>> normalize_path("videos\\test.mp4")
        WindowsPath('path/to/project/videos/test.mp4')
    """
    if not path_str:
        raise ValueError("Path string cannot be empty")
    
    # Convert to Path object (handles most normalization)
    try:
        # First, try to resolve as-is
        path = Path(path_str)
        
        # If path exists, return it
        if path.exists():
            return path.resolve()
        
        # If path doesn't exist, try container-to-host mapping
        if path_str.startswith('/data'):
            # Map Docker container path to project root path
            # /data -> <project_root>/data
            relative_path = path_str[1:]  # Remove leading /
            mapped = _PROJECT_ROOT / relative_path
            
            if mapped.exists():
                logger.debug(f"Mapped container path to host: {path_str} -> {mapped}")
                return mapped.resolve()
            
            # Return the mapped path even if it doesn't exist yet
            return mapped
        
        # If it's a relative path, resolve from project root
        if not path.is_absolute():
            resolved = _PROJECT_ROOT / path
            if resolved.exists():
                return resolved.resolve()
            return resolved
        
        # Return the normalized path even if it doesn't exist
        # (might be created later)
        return path
        
    except Exception as e:
        logger.warning(f"Error normalizing path '{path_str}': {e}")
        return Path(path_str)


def get_filename_from_path(path_str: str) -> str:
    """
    Extract filename from any path format
    
    Args:
        path_str: Path string in any format
        
    Returns:
        str: Filename without directory
        
    Example:
        >>> get_filename_from_path("/data/videos/test.mp4")
        'test.mp4'
        
        >>> get_filename_from_path("D:\\videos\\test.mp4")
        'test.mp4'
    """
    # Handle both Windows and POSIX paths
    try:
        # Try Windows path first
        if '\\' in path_str:
            return PureWindowsPath(path_str).name
        else:
            return PurePosixPath(path_str).name
    except Exception:
        # Fallback: split by both separators
        return path_str.split('/')[-1].split('\\')[-1]


def paths_match(path1: str, path2: str, match_filename_only: bool = False) -> bool:
    """
    Check if two paths refer to the same file
    
    Supports:
    - Exact path matching
    - Filename-only matching (useful for cross-platform)
    - Case-insensitive matching on Windows
    
    Args:
        path1: First path
        path2: Second path
        match_filename_only: If True, only compare filenames
        
    Returns:
        bool: True if paths match
        
    Example:
        >>> paths_match("/data/test.mp4", "D:\\n8n\\ai-ewg\\data\\test.mp4")
        True  # After normalization
        
        >>> paths_match("/data/test.mp4", "D:\\other\\test.mp4", match_filename_only=True)
        True  # Same filename
    """
    if match_filename_only:
        # Compare only filenames
        file1 = get_filename_from_path(path1)
        file2 = get_filename_from_path(path2)
        
        # Case-insensitive on Windows
        if os.name == 'nt':
            return file1.lower() == file2.lower()
        return file1 == file2
    
    # Full path comparison
    try:
        norm1 = normalize_path(path1)
        norm2 = normalize_path(path2)
        
        # Resolve to absolute paths if they exist
        if norm1.exists() and norm2.exists():
            return norm1.resolve() == norm2.resolve()
        
        # Compare as strings (case-insensitive on Windows)
        if os.name == 'nt':
            return str(norm1).lower() == str(norm2).lower()
        return str(norm1) == str(norm2)
        
    except Exception as e:
        logger.warning(f"Error comparing paths: {e}")
        # Fallback to filename comparison
        return paths_match(path1, path2, match_filename_only=True)


def ensure_windows_path(path_str: str) -> str:
    """
    Convert any path format to Windows-style path
    
    Args:
        path_str: Path in any format
        
    Returns:
        str: Windows-style path with backslashes
    """
    normalized = normalize_path(path_str)
    return str(normalized).replace('/', '\\')


def ensure_posix_path(path_str: str) -> str:
    """
    Convert any path format to POSIX-style path (for APIs/URLs)
    
    Args:
        path_str: Path in any format
        
    Returns:
        str: POSIX-style path with forward slashes
    """
    return str(path_str).replace('\\', '/')
