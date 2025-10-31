"""
API client for GUI Control Panel communication with localhost:8000

Provides a robust API client with error handling, retry logic, caching,
and comprehensive methods for episode discovery, processing, and clip generation.
"""

import requests
import time
import streamlit as st
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class ApiResponse:
    """Standardized API response wrapper"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class EpisodeInfo:
    """Episode information from API responses"""
    episode_id: str
    title: Optional[str] = None
    show_name: Optional[str] = None
    status: Optional[str] = None
    processing_stage: Optional[str] = None
    source_path: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ClipInfo:
    """Clip information from API responses"""
    clip_id: str
    episode_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    score: float
    title: Optional[str] = None
    status: Optional[str] = None


@dataclass
class ProcessingProgress:
    """Processing progress information"""
    episode_id: str
    current_stage: str
    progress_percentage: float
    message: str
    estimated_remaining: Optional[float] = None


class PipelineApiClient:
    """
    API client for AI-EWG pipeline communication
    
    Provides methods for episode discovery, processing, status monitoring,
    and clip generation with built-in retry logic, caching, and error handling.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 600, enable_cache: bool = True):
        """
        Initialize API client
        
        Args:
            base_url: Base URL for the API (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 600 for long-running processes)
            enable_cache: Enable response caching for performance (default: True)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.enable_cache = enable_cache
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Cache configuration
        self.cache_ttl = {
            'health': 30,      # Health checks cached for 30 seconds
            'episodes': 60,    # Episode lists cached for 1 minute
            'status': 30,      # Status checks cached for 30 seconds
            'clips': 120,      # Clip discovery cached for 2 minutes
        }
    
    def _get_cache_key(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> str:
        """Generate cache key for request"""
        key_data = {
            'method': method,
            'endpoint': endpoint,
            'data': data,
            'params': params
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str, cache_type: str) -> Optional[ApiResponse]:
        """Get cached response if valid"""
        if not self.enable_cache or 'api_cache' not in st.session_state:
            return None
        
        cache = st.session_state['api_cache']
        timestamps = st.session_state.get('cache_timestamps', {})
        
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
    
    def _cache_response(self, cache_key: str, response: ApiResponse) -> None:
        """Cache response for future use"""
        if not self.enable_cache:
            return
        
        if 'api_cache' not in st.session_state:
            st.session_state['api_cache'] = {}
        if 'cache_timestamps' not in st.session_state:
            st.session_state['cache_timestamps'] = {}
        
        st.session_state['api_cache'][cache_key] = response
        st.session_state['cache_timestamps'][cache_key] = datetime.now()
        
        # Limit cache size to prevent memory issues
        if len(st.session_state['api_cache']) > 100:
            # Remove oldest entries
            timestamps = st.session_state['cache_timestamps']
            oldest_keys = sorted(timestamps.keys(), key=lambda k: timestamps[k])[:20]
            
            for key in oldest_keys:
                if key in st.session_state['api_cache']:
                    del st.session_state['api_cache'][key]
                if key in timestamps:
                    del timestamps[key]
    
    def clear_all_cache(self):
        """Clear all cached API responses"""
        if 'api_cache' in st.session_state:
            st.session_state['api_cache'].clear()
        if 'cache_timestamps' in st.session_state:
            st.session_state['cache_timestamps'].clear()
        logger.info("Cleared all API cache")
    
    def clear_episode_cache(self, episode_id: str):
        """Clear cached responses for a specific episode"""
        if 'api_cache' not in st.session_state:
            return
        
        cache = st.session_state['api_cache']
        timestamps = st.session_state.get('cache_timestamps', {})
        
        # Find and remove cache entries related to this episode
        keys_to_remove = []
        for cache_key in cache.keys():
            # Check if the cache key contains the episode ID
            if episode_id in cache_key:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in cache:
                del cache[key]
            if key in timestamps:
                del timestamps[key]
        
        logger.info(f"Cleared API cache for episode: {episode_id} ({len(keys_to_remove)} entries)")
    
    def clear_cache_by_type(self, cache_type: str):
        """Clear cached responses of a specific type"""
        if 'api_cache' not in st.session_state:
            return
        
        cache = st.session_state['api_cache']
        timestamps = st.session_state.get('cache_timestamps', {})
        
        # Find and remove cache entries of this type
        keys_to_remove = []
        for cache_key in cache.keys():
            # This is a simplified approach - in practice you might want to store cache type metadata
            if cache_type in cache_key:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in cache:
                del cache[key]
            if key in timestamps:
                del timestamps[key]
        
        logger.info(f"Cleared API cache for type: {cache_type} ({len(keys_to_remove)} entries)")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout))
    )
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        cache_type: Optional[str] = None,
        bypass_cache: bool = False
    ) -> ApiResponse:
        """
        Make HTTP request with retry logic and caching
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            cache_type: Type of cache to use (affects TTL)
            bypass_cache: Skip cache lookup and storage
            
        Returns:
            ApiResponse: Standardized response wrapper
        """
        # Check cache for GET requests (unless bypassed)
        if method == 'GET' and not bypass_cache and cache_type:
            cache_key = self._get_cache_key(method, endpoint, data, params)
            cached_response = self._get_cached_response(cache_key, cache_type)
            if cached_response:
                logger.debug(f"Using cached response for {endpoint}")
                return cached_response
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            # Handle successful responses
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    api_response = ApiResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status_code
                    )
                except ValueError:
                    # Non-JSON response
                    api_response = ApiResponse(
                        success=True,
                        data={"raw_response": response.text},
                        status_code=response.status_code
                    )
                
                # Cache successful GET responses
                if method == 'GET' and not bypass_cache and cache_type:
                    cache_key = self._get_cache_key(method, endpoint, data, params)
                    self._cache_response(cache_key, api_response)
                
                return api_response
            
            # Handle error responses
            error_message = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'detail' in error_data:
                    error_message = error_data['detail']
                elif 'error' in error_data:
                    error_message = error_data['error']
            except ValueError:
                error_message = response.text or error_message
            
            return ApiResponse(
                success=False,
                error=error_message,
                status_code=response.status_code
            )
            
        except requests.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return ApiResponse(
                success=False,
                error=f"Connection failed: {str(e)}"
            )
        except requests.Timeout as e:
            logger.error(f"Request timeout: {e}")
            return ApiResponse(
                success=False,
                error=f"Request timeout: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return ApiResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def check_health(self) -> ApiResponse:
        """
        Check API health status
        
        Returns:
            ApiResponse: Health status information
        """
        return self._make_request('GET', '/health', cache_type='health')
    
    def get_system_status(self) -> ApiResponse:
        """
        Get pipeline processing statistics
        
        Returns:
            ApiResponse: System status and statistics
        """
        return self._make_request('GET', '/status', cache_type='status')
    
    def discover_episodes(self) -> ApiResponse:
        """
        Discover new video episodes from configured source directories
        
        Returns:
            ApiResponse: Discovery results with episode list
        """
        response = self._make_request('POST', '/episodes/discover')
        logger.info(f"Discover episodes response: success={response.success}, data={response.data}")
        return response
    
    def list_episodes(
        self, 
        stage: Optional[str] = None, 
        limit: int = 20,
        force_refresh: bool = False
    ) -> ApiResponse:
        """
        List episodes with optional filtering
        
        Args:
            stage: Filter by processing stage (optional)
            limit: Maximum number of episodes to return
            force_refresh: Bypass cache and force fresh data
            
        Returns:
            ApiResponse: List of episodes with metadata
        """
        params = {'limit': limit}
        if stage:
            params['stage'] = stage
            
        return self._make_request(
            'GET', 
            '/episodes', 
            params=params, 
            cache_type='episodes',
            bypass_cache=force_refresh
        )
    
    def get_episode_status(self, episode_id: str, force_refresh: bool = False) -> ApiResponse:
        """
        Get status for a specific episode
        
        Args:
            episode_id: Episode identifier
            force_refresh: Bypass cache and force fresh data
            
        Returns:
            ApiResponse: Episode status and metadata
        """
        return self._make_request(
            'GET', 
            f'/episodes/{episode_id}', 
            cache_type='status',
            bypass_cache=force_refresh
        )
    
    def process_episode(
        self,
        episode_id: str,
        target_stage: str = "rendered",
        force_reprocess: bool = False,
        clear_cache: bool = False
    ) -> ApiResponse:
        """
        Process a single episode
        
        Args:
            episode_id: Episode identifier
            target_stage: Target processing stage (default: "rendered")
            force_reprocess: Force reprocessing even if already processed
            clear_cache: Clear cache before processing (like original process_episode.py)
            
        Returns:
            ApiResponse: Processing result with metadata and HTML outputs
        """
        data = {
            "episode_id": episode_id,
            "target_stage": target_stage,
            "force_reprocess": force_reprocess
        }
        
        # Add clear_cache if supported (for compatibility with original process_episode.py)
        if clear_cache:
            data["clear_cache"] = clear_cache
        
        return self._make_request('POST', '/episodes/process', data=data)
    
    def process_batch(
        self,
        episode_ids: List[str],
        target_stage: str = "rendered",
        max_concurrent: int = 2
    ) -> ApiResponse:
        """
        Process multiple episodes in batch
        
        Args:
            episode_ids: List of episode identifiers
            target_stage: Target processing stage
            max_concurrent: Maximum concurrent processing jobs
            
        Returns:
            ApiResponse: Batch processing results
        """
        data = {
            "episode_ids": episode_ids,
            "target_stage": target_stage,
            "max_concurrent": max_concurrent
        }
        
        return self._make_request('POST', '/episodes/batch', data=data)
    
    def delete_episode(
        self,
        episode_id: str,
        delete_files: bool = True
    ) -> ApiResponse:
        """
        Delete an episode and optionally all its generated files
        
        Args:
            episode_id: Episode identifier
            delete_files: Whether to delete all generated files (default: True)
            
        Returns:
            ApiResponse: Deletion result with list of deleted files
        """
        params = {
            "delete_files": delete_files
        }
        
        return self._make_request('DELETE', f'/episodes/{episode_id}', params=params)
    
    def discover_clips(
        self,
        episode_id: str,
        max_clips: int = 3,
        min_duration_ms: int = 20000,
        max_duration_ms: int = 120000,
        aspect_ratios: Optional[List[str]] = None,
        score_threshold: float = 0.3
    ) -> ApiResponse:
        """
        Discover clips for an episode
        
        Args:
            episode_id: Episode identifier
            max_clips: Maximum number of clips to discover
            min_duration_ms: Minimum clip duration in milliseconds
            max_duration_ms: Maximum clip duration in milliseconds
            aspect_ratios: List of aspect ratios (default: ["9x16", "16x9"])
            score_threshold: Minimum score threshold for clips
            
        Returns:
            ApiResponse: Discovered clips with metadata
        """
        if aspect_ratios is None:
            aspect_ratios = ["9x16", "16x9"]
            
        data = {
            "max_clips": max_clips,
            "min_duration_ms": min_duration_ms,
            "max_duration_ms": max_duration_ms,
            "aspect_ratios": aspect_ratios,
            "score_threshold": score_threshold
        }
        
        return self._make_request('POST', f'/episodes/{episode_id}/discover_clips', data=data)
    
    def render_clip(
        self,
        clip_id: str,
        variants: Optional[List[str]] = None,
        aspect_ratios: Optional[List[str]] = None,
        force_rerender: bool = False
    ) -> ApiResponse:
        """
        Render a specific clip
        
        Args:
            clip_id: Clip identifier
            variants: List of variants to render (default: ["clean", "subtitled"])
            aspect_ratios: List of aspect ratios (default: ["9x16", "16x9"])
            force_rerender: Force re-rendering even if assets exist
            
        Returns:
            ApiResponse: Render results with asset information
        """
        if variants is None:
            variants = ["clean", "subtitled"]
        if aspect_ratios is None:
            aspect_ratios = ["9x16", "16x9"]
            
        data = {
            "variants": variants,
            "aspect_ratios": aspect_ratios,
            "force_rerender": force_rerender
        }
        
        return self._make_request('POST', f'/clips/{clip_id}/render', data=data)
    
    def render_clips_bulk(
        self,
        episode_id: str,
        clip_ids: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        aspect_ratios: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
        status_filter: Optional[str] = None,
        force_rerender: bool = False
    ) -> ApiResponse:
        """
        Render multiple clips for an episode in batch
        
        Args:
            episode_id: Episode identifier
            clip_ids: Specific clip IDs to render (optional, renders all if None)
            variants: List of variants to render (default: ["clean", "subtitled"])
            aspect_ratios: List of aspect ratios (default: ["9x16", "16x9"])
            score_threshold: Minimum score threshold for clips
            status_filter: Filter clips by status
            force_rerender: Force re-rendering even if assets exist
            
        Returns:
            ApiResponse: Bulk render results
        """
        if variants is None:
            variants = ["clean", "subtitled"]
        if aspect_ratios is None:
            aspect_ratios = ["9x16", "16x9"]
            
        data = {
            "variants": variants,
            "aspect_ratios": aspect_ratios,
            "force_rerender": force_rerender
        }
        
        if clip_ids:
            data["clip_ids"] = clip_ids
        if score_threshold is not None:
            data["score_threshold"] = score_threshold
        if status_filter:
            data["status_filter"] = status_filter
        
        return self._make_request('POST', f'/episodes/{episode_id}/render_clips', data=data)
    
    def get_processing_progress(self, episode_id: str) -> ProcessingProgress:
        """
        Get processing progress for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            ProcessingProgress: Current processing status and progress
        """
        response = self.get_episode_status(episode_id)
        
        if not response.success or not response.data:
            return ProcessingProgress(
                episode_id=episode_id,
                current_stage="unknown",
                progress_percentage=0.0,
                message="Unable to get status"
            )
        
        data = response.data
        stage = data.get('stage', 'unknown')
        
        # Map stages to progress percentages
        stage_progress = {
            'discovered': 10.0,
            'transcribed': 30.0,
            'enriched': 60.0,
            'editorial': 80.0,
            'rendered': 100.0,
            'failed': 0.0
        }
        
        progress = stage_progress.get(stage, 0.0)
        
        return ProcessingProgress(
            episode_id=episode_id,
            current_stage=stage,
            progress_percentage=progress,
            message=f"Episode is in {stage} stage"
        )
    
    def parse_episode_info(self, episode_data: Dict[str, Any]) -> EpisodeInfo:
        """
        Parse episode data from API response into EpisodeInfo object
        
        Args:
            episode_data: Raw episode data from API
            
        Returns:
            EpisodeInfo: Parsed episode information
        """
        return EpisodeInfo(
            episode_id=episode_data.get('episode_id', ''),
            title=episode_data.get('title'),
            show_name=episode_data.get('show') or episode_data.get('show_name'),  # Try both field names
            status=episode_data.get('status'),
            processing_stage=episode_data.get('stage'),
            source_path=episode_data.get('source_path'),
            duration=episode_data.get('duration'),
            error=episode_data.get('error')
        )
    
    def parse_clip_info(self, clip_data: Dict[str, Any]) -> ClipInfo:
        """
        Parse clip data from API response into ClipInfo object
        
        Args:
            clip_data: Raw clip data from API
            
        Returns:
            ClipInfo: Parsed clip information
        """
        return ClipInfo(
            clip_id=clip_data.get('id', ''),
            episode_id=clip_data.get('episode_id', ''),
            start_ms=clip_data.get('start_ms', 0),
            end_ms=clip_data.get('end_ms', 0),
            duration_ms=clip_data.get('duration_ms', 0),
            score=clip_data.get('score', 0.0),
            title=clip_data.get('title'),
            status=clip_data.get('status')
        )


# Convenience function for creating client instance
def create_api_client(base_url: str = "http://localhost:8000", enable_cache: bool = True) -> PipelineApiClient:
    """
    Create and return a configured API client instance with caching
    
    Args:
        base_url: Base URL for the API
        enable_cache: Enable response caching for performance
        
    Returns:
        PipelineApiClient: Configured client instance
    """
    return PipelineApiClient(base_url=base_url, enable_cache=enable_cache)