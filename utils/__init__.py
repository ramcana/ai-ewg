"""
Utilities package for GUI Control Panel

Provides API client, file management, and helper utilities
for the Streamlit-based video processing dashboard.
"""

from .api_client import PipelineApiClient, create_api_client, ApiResponse, EpisodeInfo, ClipInfo
from .file_manager import FileManager, create_file_manager, FileInfo, DirectoryInfo, EpisodeFileStructure
from .helpers import (
    format_file_size,
    format_duration,
    format_timestamp,
    format_clip_time,
    calculate_success_rate,
    sanitize_filename,
    extract_episode_id_from_path,
    validate_episode_id,
    parse_aspect_ratio,
    get_standard_resolutions,
    estimate_processing_time,
    create_social_hashtags,
    truncate_text,
    safe_get
)

__all__ = [
    # API Client
    'PipelineApiClient',
    'create_api_client',
    'ApiResponse',
    'EpisodeInfo',
    'ClipInfo',
    
    # File Manager
    'FileManager',
    'create_file_manager',
    'FileInfo',
    'DirectoryInfo',
    'EpisodeFileStructure',
    
    # Helper Functions
    'format_file_size',
    'format_duration',
    'format_timestamp',
    'format_clip_time',
    'calculate_success_rate',
    'sanitize_filename',
    'extract_episode_id_from_path',
    'validate_episode_id',
    'parse_aspect_ratio',
    'get_standard_resolutions',
    'estimate_processing_time',
    'create_social_hashtags',
    'truncate_text',
    'safe_get'
]