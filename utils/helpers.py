"""
Common utility functions for GUI Control Panel

Provides helper functions for data formatting, time calculations,
and other common operations used throughout the dashboard.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import re


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.5 MB", "2.3 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def format_duration(duration: Union[float, int]) -> str:
    """
    Format duration in human-readable format
    
    Args:
        duration: Duration in seconds (float) or milliseconds (int > 1000)
        
    Returns:
        str: Formatted duration string (e.g., "2m 30s", "1h 15m")
    """
    # Auto-detect if input is milliseconds (assume values > 1000 are ms)
    if isinstance(duration, int) and duration > 1000:
        seconds = duration / 1000.0
    else:
        seconds = float(duration)
    
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds:.0f}s"
        else:
            return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    else:
        return f"{hours}h"


def format_timestamp(timestamp: Union[datetime, str, float]) -> str:
    """
    Format timestamp for display
    
    Args:
        timestamp: Timestamp as datetime, ISO string, or Unix timestamp
        
    Returns:
        str: Formatted timestamp string
    """
    try:
        if isinstance(timestamp, str):
            # Try parsing ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        elif isinstance(timestamp, (int, float)):
            # Unix timestamp
            dt = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            return "Unknown"
        
        # Format as relative time if recent, otherwise absolute
        now = datetime.now()
        diff = now - dt.replace(tzinfo=None) if dt.tzinfo else now - dt
        
        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() // 60)
            return f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() // 3600)
            return f"{hours}h ago"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime("%Y-%m-%d %H:%M")
            
    except Exception:
        return "Invalid timestamp"


def format_clip_time(milliseconds: int) -> str:
    """
    Format clip time from milliseconds to readable format
    
    Args:
        milliseconds: Time in milliseconds
        
    Returns:
        str: Formatted time string (e.g., "1:23", "12:34")
    """
    seconds = milliseconds / 1000
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    return f"{minutes}:{remaining_seconds:02d}"


def calculate_success_rate(successful: int, total: int) -> float:
    """
    Calculate success rate percentage
    
    Args:
        successful: Number of successful operations
        total: Total number of operations
        
    Returns:
        float: Success rate as percentage (0.0 to 100.0)
    """
    if total == 0:
        return 0.0
    
    return (successful / total) * 100.0


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system usage
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    # Ensure not empty
    if not sanitized:
        sanitized = "untitled"
    
    return sanitized


def extract_episode_id_from_path(path: str) -> Optional[str]:
    """
    Extract episode ID from file path
    
    Args:
        path: File path containing episode ID
        
    Returns:
        str or None: Episode ID if found
    """
    # Common patterns for episode IDs in paths
    patterns = [
        r'/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/',  # UUID
        r'/([a-zA-Z0-9_-]+)\.mp4',  # Filename without extension
        r'/([a-zA-Z0-9_-]+)/',  # Directory name
    ]
    
    for pattern in patterns:
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    
    return None


def validate_episode_id(episode_id: str) -> bool:
    """
    Validate episode ID format
    
    Args:
        episode_id: Episode ID to validate
        
    Returns:
        bool: True if valid format
    """
    if not episode_id or not isinstance(episode_id, str):
        return False
    
    # Check for reasonable length and characters
    if len(episode_id) < 3 or len(episode_id) > 100:
        return False
    
    # Allow alphanumeric, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', episode_id):
        return False
    
    return True


def parse_aspect_ratio(aspect_ratio: str) -> Optional[tuple]:
    """
    Parse aspect ratio string to width/height tuple
    
    Args:
        aspect_ratio: Aspect ratio string (e.g., "16x9", "9:16")
        
    Returns:
        tuple or None: (width, height) if valid
    """
    try:
        # Handle different separators
        if 'x' in aspect_ratio:
            parts = aspect_ratio.split('x')
        elif ':' in aspect_ratio:
            parts = aspect_ratio.split(':')
        else:
            return None
        
        if len(parts) != 2:
            return None
        
        width = int(parts[0])
        height = int(parts[1])
        
        return (width, height)
        
    except (ValueError, IndexError):
        return None


def get_standard_resolutions() -> Dict[str, tuple]:
    """
    Get standard video resolutions for different aspect ratios
    
    Returns:
        Dict: Mapping of aspect ratio to (width, height)
    """
    return {
        "16x9": (1920, 1080),  # Landscape/Horizontal
        "9x16": (1080, 1920),  # Portrait/Vertical
        "1x1": (1080, 1080),   # Square
        "4x3": (1440, 1080),   # Traditional TV
        "21x9": (2560, 1080)   # Ultra-wide
    }


def estimate_processing_time(
    file_size_mb: float, 
    processing_stage: str = "rendered"
) -> float:
    """
    Estimate processing time based on file size and target stage
    
    Args:
        file_size_mb: File size in megabytes
        processing_stage: Target processing stage
        
    Returns:
        float: Estimated time in seconds
    """
    # Base processing rates (MB per second) for different stages
    stage_rates = {
        "transcribed": 2.0,    # Transcription is relatively fast
        "enriched": 1.0,       # Enrichment takes longer
        "editorial": 0.5,      # Editorial processing is slower
        "rendered": 0.3        # Full rendering is slowest
    }
    
    rate = stage_rates.get(processing_stage, 0.5)
    
    # Add base overhead time
    base_time = 30  # 30 seconds base overhead
    
    return base_time + (file_size_mb / rate)


def create_social_hashtags(
    topic: Optional[str] = None,
    guests: Optional[List[str]] = None,
    show_name: Optional[str] = None
) -> List[str]:
    """
    Create relevant hashtags for social media posts
    
    Args:
        topic: Episode topic
        guests: List of guest names
        show_name: Show name
        
    Returns:
        List[str]: Generated hashtags
    """
    hashtags = []
    
    # Add show-specific hashtag
    if show_name:
        show_tag = re.sub(r'[^a-zA-Z0-9]', '', show_name)
        if show_tag:
            hashtags.append(f"#{show_tag}")
    
    # Add topic-based hashtags
    if topic:
        topic_lower = topic.lower()
        
        # Technology topics
        if any(word in topic_lower for word in ['ai', 'artificial intelligence', 'machine learning', 'tech']):
            hashtags.extend(['#AI', '#Technology', '#Innovation'])
        
        # Business topics
        if any(word in topic_lower for word in ['business', 'startup', 'entrepreneur', 'leadership']):
            hashtags.extend(['#Business', '#Leadership', '#Entrepreneurship'])
        
        # Health topics
        if any(word in topic_lower for word in ['health', 'wellness', 'fitness', 'medical']):
            hashtags.extend(['#Health', '#Wellness'])
        
        # Education topics
        if any(word in topic_lower for word in ['education', 'learning', 'teaching', 'school']):
            hashtags.extend(['#Education', '#Learning'])
    
    # Add guest-based hashtags (if they're notable)
    if guests:
        for guest in guests[:2]:  # Limit to first 2 guests
            guest_tag = re.sub(r'[^a-zA-Z0-9]', '', guest.replace(' ', ''))
            if len(guest_tag) > 3:  # Only add if meaningful length
                hashtags.append(f"#{guest_tag}")
    
    # Add generic podcast hashtags
    hashtags.extend(['#Podcast', '#Interview'])
    
    # Remove duplicates and limit count
    unique_hashtags = list(dict.fromkeys(hashtags))  # Preserve order
    return unique_hashtags[:8]  # Limit to 8 hashtags


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    truncated_length = max_length - len(suffix)
    if truncated_length <= 0:
        return suffix[:max_length]
    
    return text[:truncated_length] + suffix


def safe_get(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value using dot notation
    
    Args:
        data: Dictionary to search
        key_path: Dot-separated key path (e.g., "metadata.title")
        default: Default value if key not found
        
    Returns:
        Any: Value if found, default otherwise
    """
    try:
        keys = key_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
        
    except Exception:
        return default