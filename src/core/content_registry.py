"""
Content Registry for Content Publishing Platform

Implements centralized metadata management and content contract enforcement.
Provides manifest loading, validation, content retrieval, and social link management.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field

from .publishing_models import (
    PublishManifest, Episode, Series, Host, Person, PathMapping, SocialManifest,
    ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity,
    create_episode_from_metadata, RightsMetadata, SocialPackage, PackageStatus
)
from .structured_data_contract import (
    StructuredDataContract, ManifestValidator, SchemaType,
    create_manifest_validator, validate_complete_manifest
)
from .social_generator import SocialPackageValidator
from .platform_profiles import PlatformProfileLoader
from .social_queue_manager import SocialQueueManager, SchedulingConfig, QueueItemStatus


@dataclass
class ContentFilter:
    """Filter criteria for content retrieval"""
    series_ids: Optional[List[str]] = None
    host_ids: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    confidence_threshold: Optional[float] = None
    tags: Optional[List[str]] = None
    episode_ids: Optional[List[str]] = None
    
    def matches_episode(self, episode: Episode) -> bool:
        """Check if episode matches filter criteria"""
        # Series filter
        if self.series_ids and episode.series.series_id not in self.series_ids:
            return False
        
        # Host filter
        if self.host_ids:
            episode_host_ids = [host.person_id for host in episode.hosts]
            if not any(host_id in episode_host_ids for host_id in self.host_ids):
                return False
        
        # Date range filter
        if self.date_from and episode.upload_date < self.date_from:
            return False
        
        if self.date_to and episode.upload_date > self.date_to:
            return False
        
        # Episode ID filter
        if self.episode_ids and episode.episode_id not in self.episode_ids:
            return False
        
        # Tags filter
        if self.tags:
            if not any(tag in episode.tags for tag in self.tags):
                return False
        
        return True


@dataclass
class ManifestCompatibility:
    """Manifest version compatibility information"""
    supported_versions: List[str] = field(default_factory=lambda: ["1.0", "1.1", "2.0"])
    current_version: str = "2.0"
    
    def is_compatible(self, version: str) -> bool:
        """Check if manifest version is compatible"""
        return version in self.supported_versions
    
    def get_migration_path(self, from_version: str) -> Optional[List[str]]:
        """Get migration path from old version to current"""
        if from_version == "1.0":
            return ["1.0", "1.1", "2.0"]
        elif from_version == "1.1":
            return ["1.1", "2.0"]
        elif from_version == "2.0":
            return []
        return None


class ContentRegistry:
    """
    Central repository for processed episodes, series, and host information
    
    Provides manifest loading, validation, content retrieval, filtering,
    and social link management capabilities.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize Content Registry
        
        Args:
            base_path: Base directory path for content files (defaults to 'data')
        """
        self.base_path = Path(base_path or "data")
        self.manifest: Optional[PublishManifest] = None
        self.episodes_cache: Dict[str, Episode] = {}
        self.series_cache: Dict[str, Series] = {}
        self.hosts_cache: Dict[str, Host] = {}
        self.social_packages_cache: Dict[str, List[SocialPackage]] = {}  # episode_id -> packages
        
        # Initialize validators
        self.manifest_validator = create_manifest_validator()
        self.compatibility = ManifestCompatibility()
        
        # Content contract validator
        self.video_contract = StructuredDataContract(SchemaType.VIDEO_OBJECT)
        self.tv_episode_contract = StructuredDataContract(SchemaType.TV_EPISODE)
        
        # Social package support
        self.platform_loader = PlatformProfileLoader()
        self.social_validators: Dict[str, SocialPackageValidator] = {}
        
        # Queue management
        queue_root = self.base_path / "social" / "queue"
        self.queue_manager = SocialQueueManager(str(queue_root))
    
    def load_manifest(self, manifest_path: Optional[str] = None) -> PublishManifest:
        """
        Load and validate publishing manifest
        
        Args:
            manifest_path: Path to manifest file (defaults to base_path/publish_manifest.json)
            
        Returns:
            Loaded and validated PublishManifest
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid or incompatible
        """
        if manifest_path is None:
            manifest_path = self.base_path / "publish_manifest.json"
        else:
            manifest_path = Path(manifest_path)
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest file: {e}")
        
        # Validate basic manifest structure (not full content contract yet)
        validation_result = self._validate_manifest_structure(manifest_data)
        if not validation_result.is_valid:
            error_messages = [error.message for error in validation_result.errors]
            raise ValueError(f"Manifest validation failed: {'; '.join(error_messages)}")
        
        # Check version compatibility
        manifest_version = manifest_data.get("manifest_version", "1.0")
        if not self.compatibility.is_compatible(manifest_version):
            raise ValueError(f"Unsupported manifest version: {manifest_version}")
        
        # Create manifest object
        self.manifest = PublishManifest.from_dict(manifest_data)
        
        # Clear caches to force reload
        self.episodes_cache.clear()
        self.series_cache.clear()
        self.hosts_cache.clear()
        self.social_packages_cache.clear()
        
        # Update social manifest with discovered packages
        try:
            self.update_social_manifest()
        except Exception as e:
            print(f"Warning: Failed to update social manifest: {e}")
        
        return self.manifest
    
    def _validate_manifest_structure(self, manifest_data: Dict[str, Any]) -> ValidationResult:
        """Validate basic manifest structure without full content contract validation"""
        errors = []
        warnings = []
        
        # Required manifest fields
        required_manifest_fields = [
            "manifest_version", "build_id", "episodes", "series", "hosts", "paths"
        ]
        
        for field in required_manifest_fields:
            if field not in manifest_data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Required manifest field '{field}' is missing",
                    location=f"manifest.{field}",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_manifest(self, manifest_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate manifest against content contract
        
        Args:
            manifest_data: Raw manifest data to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        return self.manifest_validator.validate_publish_manifest(manifest_data)
    
    def validate_content_contract(self, manifest: PublishManifest) -> ValidationResult:
        """
        Validate content contract compliance for all episodes
        
        Args:
            manifest: PublishManifest to validate
            
        Returns:
            ValidationResult with comprehensive validation information
        """
        errors = []
        warnings = []
        
        # Validate each episode against structured data contract
        for i, episode_data in enumerate(manifest.episodes):
            try:
                # Create episode object for validation
                series_data = next((s for s in manifest.series if s['series_id'] == episode_data.get('series_id')), None)
                if not series_data:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Episode {i} references unknown series: {episode_data.get('series_id')}",
                        location=f"episodes[{i}].series_id",
                        severity=Severity.ERROR
                    ))
                    continue
                
                # Get host data
                host_ids = episode_data.get('host_ids', [])
                hosts_data = [h for h in manifest.hosts if h['person_id'] in host_ids]
                
                if not hosts_data:
                    warnings.append(ValidationWarning(
                        message=f"Episode {i} has no valid hosts",
                        location=f"episodes[{i}].host_ids"
                    ))
                
                # Create episode for validation
                episode = create_episode_from_metadata(episode_data, series_data, hosts_data)
                
                # Validate against structured data contract
                schema_result = self.video_contract.validate_schema(
                    self.video_contract.generate_schema_from_episode(episode)
                )
                
                # Add location context to errors
                for error in schema_result.errors:
                    error.location = f"episodes[{i}].{error.location}"
                    errors.append(error)
                
                for warning in schema_result.warnings:
                    warning.location = f"episodes[{i}].{warning.location}"
                    warnings.append(warning)
                
            except Exception as e:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Failed to validate episode {i}: {str(e)}",
                    location=f"episodes[{i}]",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_episodes_validated": len(manifest.episodes),
                "validation_timestamp": datetime.now().isoformat()
            }
        )
    
    def get_episodes(self, filters: Optional[ContentFilter] = None) -> List[Episode]:
        """
        Retrieve episodes with optional filtering
        
        Args:
            filters: Optional ContentFilter for filtering results
            
        Returns:
            List of Episode objects matching filter criteria
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        episodes = []
        
        for episode_data in self.manifest.episodes:
            episode_id = episode_data['episode_id']
            
            # Check cache first
            if episode_id in self.episodes_cache:
                episode = self.episodes_cache[episode_id]
            else:
                # Create episode object
                episode = self._create_episode_from_data(episode_data)
                self.episodes_cache[episode_id] = episode
            
            # Apply filters
            if filters is None or filters.matches_episode(episode):
                episodes.append(episode)
        
        return episodes
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """
        Get specific episode by ID
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Episode object or None if not found
        """
        episodes = self.get_episodes(ContentFilter(episode_ids=[episode_id]))
        return episodes[0] if episodes else None
    
    def get_series(self, series_id: str) -> Optional[Series]:
        """
        Get series information by ID
        
        Args:
            series_id: Series identifier
            
        Returns:
            Series object or None if not found
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        # Check cache first
        if series_id in self.series_cache:
            return self.series_cache[series_id]
        
        # Find series data
        series_data = next((s for s in self.manifest.series if s['series_id'] == series_id), None)
        if not series_data:
            return None
        
        # Create series object
        series = Series.from_dict(series_data)
        self.series_cache[series_id] = series
        
        return series
    
    def get_all_series(self) -> List[Series]:
        """
        Get all series from manifest
        
        Returns:
            List of all Series objects
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        series_list = []
        for series_data in self.manifest.series:
            series_id = series_data['series_id']
            series = self.get_series(series_id)
            if series:
                series_list.append(series)
        
        return series_list
    
    def get_hosts(self, host_ids: List[str]) -> List[Host]:
        """
        Get host information by IDs
        
        Args:
            host_ids: List of host identifiers
            
        Returns:
            List of Host objects (may be shorter than input if some not found)
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        hosts = []
        
        for host_id in host_ids:
            # Check cache first
            if host_id in self.hosts_cache:
                hosts.append(self.hosts_cache[host_id])
                continue
            
            # Find host data
            host_data = next((h for h in self.manifest.hosts if h['person_id'] == host_id), None)
            if host_data:
                host = Host.from_dict(host_data)
                self.hosts_cache[host_id] = host
                hosts.append(host)
        
        return hosts
    
    def get_host(self, host_id: str) -> Optional[Host]:
        """
        Get specific host by ID
        
        Args:
            host_id: Host identifier
            
        Returns:
            Host object or None if not found
        """
        hosts = self.get_hosts([host_id])
        return hosts[0] if hosts else None
    
    def get_all_hosts(self) -> List[Host]:
        """
        Get all hosts from manifest
        
        Returns:
            List of all Host objects
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        host_ids = [host_data['person_id'] for host_data in self.manifest.hosts]
        return self.get_hosts(host_ids)
    
    def _create_episode_from_data(self, episode_data: Dict[str, Any]) -> Episode:
        """Create Episode object from episode data in manifest"""
        # Get series data
        series_id = episode_data.get('series_id')
        series_data = next((s for s in self.manifest.series if s['series_id'] == series_id), None)
        if not series_data:
            raise ValueError(f"Series not found for episode: {series_id}")
        
        # Get host data
        host_ids = episode_data.get('host_ids', [])
        hosts_data = [h for h in self.manifest.hosts if h['person_id'] in host_ids]
        
        return create_episode_from_metadata(episode_data, series_data, hosts_data)
    
    def validate_cross_references(self) -> ValidationResult:
        """
        Validate cross-reference integrity between episodes, series, and hosts
        
        Returns:
            ValidationResult with cross-reference validation status
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        errors = []
        warnings = []
        
        # Track referenced IDs
        referenced_series_ids = set()
        referenced_host_ids = set()
        
        # Available IDs
        available_series_ids = {s['series_id'] for s in self.manifest.series}
        available_host_ids = {h['person_id'] for h in self.manifest.hosts}
        
        # Check episode references
        for i, episode_data in enumerate(self.manifest.episodes):
            episode_id = episode_data.get('episode_id', f'episode_{i}')
            
            # Check series reference
            series_id = episode_data.get('series_id')
            if series_id:
                referenced_series_ids.add(series_id)
                if series_id not in available_series_ids:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Episode '{episode_id}' references unknown series: {series_id}",
                        location=f"episodes[{i}].series_id",
                        severity=Severity.ERROR
                    ))
            
            # Check host references
            host_ids = episode_data.get('host_ids', [])
            for host_id in host_ids:
                referenced_host_ids.add(host_id)
                if host_id not in available_host_ids:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Episode '{episode_id}' references unknown host: {host_id}",
                        location=f"episodes[{i}].host_ids",
                        severity=Severity.ERROR
                    ))
        
        # Check for unreferenced series
        unreferenced_series = available_series_ids - referenced_series_ids
        for series_id in unreferenced_series:
            warnings.append(ValidationWarning(
                message=f"Series '{series_id}' is defined but not referenced by any episodes",
                location=f"series.{series_id}"
            ))
        
        # Check for unreferenced hosts
        unreferenced_hosts = available_host_ids - referenced_host_ids
        for host_id in unreferenced_hosts:
            warnings.append(ValidationWarning(
                message=f"Host '{host_id}' is defined but not referenced by any episodes",
                location=f"hosts.{host_id}"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_episodes": len(self.manifest.episodes),
                "total_series": len(self.manifest.series),
                "total_hosts": len(self.manifest.hosts),
                "referenced_series": len(referenced_series_ids),
                "referenced_hosts": len(referenced_host_ids)
            }
        )    

    def update_social_links(self, episode_id: str, platform_urls: Dict[str, str]) -> None:
        """
        Update social media URLs for an episode
        
        Args:
            episode_id: Episode identifier
            platform_urls: Dictionary mapping platform names to URLs
            
        Raises:
            ValueError: If episode not found or URLs are invalid
        """
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        # Find episode data in manifest
        episode_data = None
        episode_index = None
        
        for i, ep_data in enumerate(self.manifest.episodes):
            if ep_data.get('episode_id') == episode_id:
                episode_data = ep_data
                episode_index = i
                break
        
        if episode_data is None:
            raise ValueError(f"Episode not found: {episode_id}")
        
        # Validate and normalize URLs
        validated_urls = {}
        for platform, url in platform_urls.items():
            if not self._is_valid_social_url(url, platform):
                raise ValueError(f"Invalid {platform} URL: {url}")
            
            validated_urls[platform] = self._normalize_social_url(url, platform)
        
        # Update episode data
        if 'social_links' not in episode_data:
            episode_data['social_links'] = {}
        
        episode_data['social_links'].update(validated_urls)
        
        # Update cache if episode is cached
        if episode_id in self.episodes_cache:
            self.episodes_cache[episode_id].social_links.update(validated_urls)
    
    def get_social_links(self, episode_id: str) -> Dict[str, str]:
        """
        Get social media links for an episode
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Dictionary mapping platform names to URLs
        """
        episode = self.get_episode(episode_id)
        if episode:
            return episode.social_links.copy()
        return {}
    
    def populate_same_as_fields(self, episode_id: str) -> List[str]:
        """
        Generate sameAs field values for JSON-LD from social links
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            List of URLs for sameAs field in JSON-LD
        """
        social_links = self.get_social_links(episode_id)
        
        # Filter to valid sameAs URLs (exclude internal/temporary links)
        same_as_urls = []
        for platform, url in social_links.items():
            if self._is_valid_same_as_url(url, platform):
                same_as_urls.append(url)
        
        return same_as_urls
    
    def _is_valid_social_url(self, url: str, platform: str) -> bool:
        """
        Validate social media URL format for specific platform
        
        Args:
            url: URL to validate
            platform: Platform name (youtube, instagram, etc.)
            
        Returns:
            True if URL is valid for the platform
        """
        if not url or not isinstance(url, str):
            return False
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Platform-specific validation
        platform_patterns = {
            'youtube': [
                r'https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
                r'https?://(www\.)?youtu\.be/[\w-]+',
                r'https?://(www\.)?youtube\.com/embed/[\w-]+',
            ],
            'instagram': [
                r'https?://(www\.)?instagram\.com/p/[\w-]+',
                r'https?://(www\.)?instagram\.com/reel/[\w-]+',
                r'https?://(www\.)?instagram\.com/tv/[\w-]+',
            ],
            'twitter': [
                r'https?://(www\.)?twitter\.com/\w+/status/\d+',
                r'https?://(www\.)?x\.com/\w+/status/\d+',
            ],
            'facebook': [
                r'https?://(www\.)?facebook\.com/\w+/videos/\d+',
                r'https?://(www\.)?facebook\.com/watch/\?v=\d+',
            ],
            'tiktok': [
                r'https?://(www\.)?tiktok\.com/@[\w.]+/video/\d+',
            ]
        }
        
        if platform.lower() in platform_patterns:
            import re
            patterns = platform_patterns[platform.lower()]
            return any(re.match(pattern, url) for pattern in patterns)
        
        # For unknown platforms, just check basic URL format
        return True
    
    def _normalize_social_url(self, url: str, platform: str) -> str:
        """
        Normalize social media URL to canonical format
        
        Args:
            url: URL to normalize
            platform: Platform name
            
        Returns:
            Normalized URL
        """
        # Basic normalization - remove tracking parameters
        import re
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed = urlparse(url)
        
        # Platform-specific normalization
        if platform.lower() == 'youtube':
            # Convert youtu.be to youtube.com format
            if parsed.netloc == 'youtu.be':
                video_id = parsed.path.lstrip('/')
                return f"https://www.youtube.com/watch?v={video_id}"
            
            # Clean up youtube.com URLs
            if 'youtube.com' in parsed.netloc:
                query_params = parse_qs(parsed.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    return f"https://www.youtube.com/watch?v={video_id}"
        
        elif platform.lower() == 'instagram':
            # Ensure www prefix for Instagram
            if parsed.netloc == 'instagram.com':
                return url.replace('instagram.com', 'www.instagram.com')
        
        # Default: return original URL with https
        if url.startswith('http://'):
            return url.replace('http://', 'https://')
        
        return url
    
    def _is_valid_same_as_url(self, url: str, platform: str) -> bool:
        """
        Check if URL is suitable for sameAs field in JSON-LD
        
        Args:
            url: URL to check
            platform: Platform name
            
        Returns:
            True if URL should be included in sameAs field
        """
        # Exclude temporary or internal URLs
        excluded_patterns = [
            r'localhost',
            r'127\.0\.0\.1',
            r'\.local',
            r'staging\.',
            r'test\.',
            r'dev\.',
        ]
        
        import re
        for pattern in excluded_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about loaded content
        
        Returns:
            Dictionary with content statistics
        """
        if not self.manifest:
            return {"error": "No manifest loaded"}
        
        episodes = self.get_episodes()
        
        # Calculate statistics
        total_duration = sum((ep.duration.total_seconds() for ep in episodes), 0)
        
        # Series statistics
        series_episode_counts = {}
        for episode in episodes:
            series_id = episode.series.series_id
            series_episode_counts[series_id] = series_episode_counts.get(series_id, 0) + 1
        
        # Host statistics
        host_episode_counts = {}
        for episode in episodes:
            for host in episode.hosts:
                host_id = host.person_id
                host_episode_counts[host_id] = host_episode_counts.get(host_id, 0) + 1
        
        # Social links statistics
        social_platform_counts = {}
        for episode in episodes:
            for platform in episode.social_links.keys():
                social_platform_counts[platform] = social_platform_counts.get(platform, 0) + 1
        
        return {
            "manifest_version": self.manifest.manifest_version,
            "build_id": self.manifest.build_id,
            "total_episodes": len(episodes),
            "total_series": len(self.manifest.series),
            "total_hosts": len(self.manifest.hosts),
            "total_duration_hours": round(total_duration / 3600, 2),
            "average_episode_duration_minutes": round((total_duration / len(episodes)) / 60, 2) if episodes else 0,
            "series_episode_counts": series_episode_counts,
            "host_episode_counts": host_episode_counts,
            "social_platform_counts": social_platform_counts,
            "episodes_with_social_links": sum(1 for ep in episodes if ep.social_links),
            "cache_stats": {
                "episodes_cached": len(self.episodes_cache),
                "series_cached": len(self.series_cache),
                "hosts_cached": len(self.hosts_cache)
            }
        }
    
    def clear_caches(self) -> None:
        """Clear all internal caches"""
        self.episodes_cache.clear()
        self.series_cache.clear()
        self.hosts_cache.clear()
        self.social_packages_cache.clear()
        self.social_validators.clear()
    
    def discover_social_packages(self) -> Dict[str, Dict[str, int]]:
        """
        Discover social packages in the social directory
        
        Returns:
            Dictionary mapping episode_id -> {platform: package_count}
        """
        if not self.manifest or not self.manifest.paths.social_root:
            return {}
        
        social_root = Path(self.manifest.paths.social_root)
        if not social_root.exists():
            return {}
        
        discovered_packages = {}
        
        # Scan platform directories
        for platform_dir in social_root.iterdir():
            if not platform_dir.is_dir() or platform_dir.name == 'queue':
                continue
            
            platform_name = platform_dir.name
            
            # Scan episode directories within platform
            for episode_dir in platform_dir.iterdir():
                if not episode_dir.is_dir():
                    continue
                
                episode_id = episode_dir.name
                
                # Count packages in episode directory
                package_files = list(episode_dir.glob('upload.json'))
                if package_files:
                    if episode_id not in discovered_packages:
                        discovered_packages[episode_id] = {}
                    discovered_packages[episode_id][platform_name] = len(package_files)
        
        return discovered_packages
    
    def update_social_manifest(self) -> None:
        """
        Update social manifest with discovered packages and validation status
        """
        if not self.manifest:
            raise ValueError("No manifest loaded")
        
        # Discover packages
        discovered_packages = self.discover_social_packages()
        
        # Initialize social manifest if not present
        if not self.manifest.social:
            self.manifest.social = SocialManifest()
        
        # Update platform counts
        self.manifest.social.platforms.clear()
        self.manifest.social.ready_flags.clear()
        
        for episode_id, platforms in discovered_packages.items():
            for platform, count in platforms.items():
                # Update platform counts
                if platform not in self.manifest.social.platforms:
                    self.manifest.social.platforms[platform] = 0
                self.manifest.social.platforms[platform] += count
                
                # Validate packages to determine ready status
                packages = self.load_social_packages(episode_id, platform)
                is_ready = all(pkg.status == PackageStatus.VALID for pkg in packages)
                
                if platform not in self.manifest.social.ready_flags:
                    self.manifest.social.ready_flags[platform] = True
                
                # If any episode's packages are not ready, mark platform as not ready
                if not is_ready:
                    self.manifest.social.ready_flags[platform] = False
        
        # Set queue path
        queue_dir = Path(self.manifest.paths.social_root) / "queue"
        if queue_dir.exists():
            self.manifest.social.queue_path = str(queue_dir)
        
        # Check for existing queue file for this build
        queue_file = queue_dir / f"{self.manifest.build_id}.json"
        if queue_file.exists():
            self.manifest.social.queue_path = str(queue_file)
    
    def load_social_packages(self, episode_id: str, platform: Optional[str] = None) -> List[SocialPackage]:
        """
        Load social packages for an episode
        
        Args:
            episode_id: Episode identifier
            platform: Optional platform filter
            
        Returns:
            List of SocialPackage objects
        """
        if not self.manifest or not self.manifest.paths.social_root:
            return []
        
        # Check cache first
        cache_key = f"{episode_id}:{platform or 'all'}"
        if cache_key in self.social_packages_cache:
            return self.social_packages_cache[cache_key]
        
        social_root = Path(self.manifest.paths.social_root)
        packages = []
        
        # Determine platforms to scan
        platforms_to_scan = [platform] if platform else []
        if not platforms_to_scan:
            # Scan all platform directories
            for platform_dir in social_root.iterdir():
                if platform_dir.is_dir() and platform_dir.name != 'queue':
                    platforms_to_scan.append(platform_dir.name)
        
        for platform_name in platforms_to_scan:
            platform_dir = social_root / platform_name / episode_id
            if not platform_dir.exists():
                continue
            
            # Look for upload.json files
            upload_manifest_path = platform_dir / "upload.json"
            if upload_manifest_path.exists():
                try:
                    package = self._load_social_package_from_path(
                        episode_id, platform_name, platform_dir
                    )
                    if package:
                        packages.append(package)
                except Exception as e:
                    # Log error but continue processing
                    print(f"Warning: Failed to load social package {platform_dir}: {e}")
        
        # Cache results
        self.social_packages_cache[cache_key] = packages
        return packages
    
    def _load_social_package_from_path(self, episode_id: str, platform: str, package_dir: Path) -> Optional[SocialPackage]:
        """Load a social package from directory path"""
        upload_manifest_path = package_dir / "upload.json"
        
        if not upload_manifest_path.exists():
            return None
        
        try:
            # Load upload manifest
            with open(upload_manifest_path, 'r', encoding='utf-8') as f:
                upload_data = json.load(f)
            
            from .publishing_models import UploadManifest
            upload_manifest = UploadManifest.from_dict(upload_data)
            
            # Load media assets
            media_assets = []
            for media_path in upload_manifest.media_paths:
                asset_path = package_dir / media_path
                if asset_path.exists():
                    # Create basic media asset (full metadata would require file inspection)
                    from .publishing_models import MediaAsset, AssetType, FormatSpecs
                    
                    # Determine asset type from file extension
                    suffix = asset_path.suffix.lower()
                    if suffix in ['.mp4', '.mov', '.avi', '.mkv']:
                        asset_type = AssetType.VIDEO
                    elif suffix in ['.mp3', '.wav', '.aac', '.m4a']:
                        asset_type = AssetType.AUDIO
                    elif suffix in ['.jpg', '.jpeg', '.png', '.webp']:
                        asset_type = AssetType.THUMBNAIL
                    elif suffix in ['.vtt', '.srt']:
                        asset_type = AssetType.CAPTIONS
                    else:
                        continue  # Skip unknown file types
                    
                    media_asset = MediaAsset(
                        asset_path=str(asset_path),
                        asset_type=asset_type,
                        format_specs=FormatSpecs(),
                        file_size=asset_path.stat().st_size if asset_path.exists() else None
                    )
                    media_assets.append(media_asset)
            
            # Load or create rights metadata
            rights_path = package_dir / "rights.json"
            if rights_path.exists():
                with open(rights_path, 'r', encoding='utf-8') as f:
                    rights_data = json.load(f)
                rights = RightsMetadata.from_dict(rights_data)
            else:
                rights = RightsMetadata()
            
            # Determine package status
            status = PackageStatus.PENDING
            status_path = package_dir / "status.json"
            if status_path.exists():
                with open(status_path, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                status = PackageStatus(status_data.get('status', 'pending'))
            
            # Create social package
            social_package = SocialPackage(
                episode_id=episode_id,
                platform=platform,
                status=status,
                media_assets=media_assets,
                upload_manifest=upload_manifest,
                rights=rights
            )
            
            return social_package
            
        except Exception as e:
            print(f"Error loading social package from {package_dir}: {e}")
            return None
    
    def validate_social_packages(self, episode_id: Optional[str] = None, 
                               platform: Optional[str] = None,
                               failure_threshold: float = 0.1) -> ValidationResult:
        """
        Validate social packages with configurable failure thresholds
        
        Args:
            episode_id: Optional episode filter
            platform: Optional platform filter  
            failure_threshold: Maximum allowed failure rate (0.0 to 1.0)
            
        Returns:
            ValidationResult with social package validation status
        """
        errors = []
        warnings = []
        
        # Get packages to validate
        if episode_id:
            packages = self.load_social_packages(episode_id, platform)
        else:
            # Validate all packages
            packages = []
            discovered = self.discover_social_packages()
            for ep_id in discovered.keys():
                packages.extend(self.load_social_packages(ep_id, platform))
        
        if not packages:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                metadata={"total_packages": 0, "validation_skipped": True}
            )
        
        # Validate each package
        validation_results = []
        failed_packages = 0
        
        for package in packages:
            try:
                # Get platform validator
                validator = self._get_social_validator(package.platform)
                if not validator:
                    warnings.append(ValidationWarning(
                        message=f"No validator available for platform: {package.platform}",
                        location=f"{package.episode_id}.{package.platform}"
                    ))
                    continue
                
                # Validate package
                result = validator.validate_package(package)
                validation_results.append(result)
                
                if not result.is_valid:
                    failed_packages += 1
                    
                    # Add package-specific context to errors
                    for error in result.errors:
                        error.location = f"{package.episode_id}.{package.platform}.{error.location}"
                        errors.append(error)
                    
                    for warning in result.warnings:
                        warning.location = f"{package.episode_id}.{package.platform}.{warning.location}"
                        warnings.append(warning)
                
            except Exception as e:
                failed_packages += 1
                errors.append(ValidationError(
                    error_type=ErrorType.PLATFORM_COMPLIANCE,
                    message=f"Validation failed for {package.episode_id}.{package.platform}: {str(e)}",
                    location=f"{package.episode_id}.{package.platform}",
                    severity=Severity.ERROR
                ))
        
        # Check failure threshold
        failure_rate = failed_packages / len(packages) if packages else 0
        threshold_exceeded = failure_rate > failure_threshold
        
        if threshold_exceeded:
            errors.append(ValidationError(
                error_type=ErrorType.PLATFORM_COMPLIANCE,
                message=f"Social package failure rate ({failure_rate:.2%}) exceeds threshold ({failure_threshold:.2%})",
                location="social_packages",
                severity=Severity.ERROR
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_packages": len(packages),
                "failed_packages": failed_packages,
                "failure_rate": failure_rate,
                "failure_threshold": failure_threshold,
                "threshold_exceeded": threshold_exceeded
            }
        )
    
    def _get_social_validator(self, platform: str) -> Optional[SocialPackageValidator]:
        """Get or create social package validator for platform"""
        if platform in self.social_validators:
            return self.social_validators[platform]
        
        try:
            # Load platform profile
            profile = self.platform_loader.load_profile(platform)
            if profile:
                validator = SocialPackageValidator(profile)
                self.social_validators[platform] = validator
                return validator
        except Exception as e:
            print(f"Warning: Failed to create validator for platform {platform}: {e}")
        
        return None
    
    def validate_web_content_independently(self) -> ValidationResult:
        """
        Validate web content independently of social packages
        
        Returns:
            ValidationResult for web content only
        """
        if not self.manifest:
            raise ValueError("No manifest loaded")
        
        # Validate content contract (web content)
        content_validation = self.validate_content_contract(self.manifest)
        
        # Validate cross-references
        cross_ref_validation = self.validate_cross_references()
        
        # Combine results
        all_errors = content_validation.errors + cross_ref_validation.errors
        all_warnings = content_validation.warnings + cross_ref_validation.warnings
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "validation_type": "web_content_only",
                "content_validation": content_validation.metadata,
                "cross_reference_validation": cross_ref_validation.metadata
            }
        )
    
    def validate_social_content_independently(self, failure_threshold: float = 0.1) -> ValidationResult:
        """
        Validate social content independently of web content
        
        Args:
            failure_threshold: Maximum allowed failure rate for social packages
            
        Returns:
            ValidationResult for social content only
        """
        if not self.manifest:
            raise ValueError("No manifest loaded")
        
        # Run social package validation
        social_validation = self.validate_social_packages(failure_threshold=failure_threshold)
        
        # Add validation type metadata
        social_validation.metadata["validation_type"] = "social_content_only"
        
        return social_validation
    
    def validate_with_independent_gates(self, 
                                      social_failure_threshold: float = 0.1,
                                      strict_mode: bool = False) -> Dict[str, ValidationResult]:
        """
        Run independent validation gates for web and social content
        
        Args:
            social_failure_threshold: Failure threshold for social packages
            strict_mode: If True, social failures affect overall validation
            
        Returns:
            Dictionary with separate validation results for web and social content
        """
        results = {}
        
        # Web content validation (always required)
        results["web"] = self.validate_web_content_independently()
        
        # Social content validation (optional/independent)
        results["social"] = self.validate_social_content_independently(social_failure_threshold)
        
        # Overall validation result
        if strict_mode:
            # In strict mode, both web and social must pass
            overall_valid = results["web"].is_valid and results["social"].is_valid
        else:
            # In non-strict mode, only web content must pass
            overall_valid = results["web"].is_valid
        
        # Create combined result
        all_errors = results["web"].errors + results["social"].errors
        all_warnings = results["web"].warnings + results["social"].warnings
        
        results["overall"] = ValidationResult(
            is_valid=overall_valid,
            errors=all_errors if strict_mode else results["web"].errors,
            warnings=all_warnings,
            metadata={
                "validation_mode": "independent_gates",
                "strict_mode": strict_mode,
                "web_validation": results["web"].metadata,
                "social_validation": results["social"].metadata,
                "social_failure_threshold": social_failure_threshold
            }
        )
        
        return results

    def get_social_package_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about social packages
        
        Returns:
            Dictionary with social package statistics
        """
        if not self.manifest or not self.manifest.paths.social_root:
            return {"error": "No social packages configured"}
        
        discovered = self.discover_social_packages()
        
        # Platform statistics
        platform_stats = {}
        total_packages = 0
        
        for episode_id, platforms in discovered.items():
            for platform, count in platforms.items():
                if platform not in platform_stats:
                    platform_stats[platform] = {
                        'total_packages': 0,
                        'episodes_with_packages': 0,
                        'ready_episodes': 0
                    }
                
                platform_stats[platform]['total_packages'] += count
                platform_stats[platform]['episodes_with_packages'] += 1
                total_packages += count
                
                # Check if episode packages are ready
                packages = self.load_social_packages(episode_id, platform)
                if all(pkg.status == PackageStatus.VALID for pkg in packages):
                    platform_stats[platform]['ready_episodes'] += 1
        
        # Status distribution
        status_counts = {}
        for episode_id in discovered.keys():
            packages = self.load_social_packages(episode_id)
            for package in packages:
                status = package.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_packages": total_packages,
            "total_episodes_with_packages": len(discovered),
            "platform_statistics": platform_stats,
            "status_distribution": status_counts,
            "social_manifest": self.manifest.social.to_dict() if self.manifest.social else None
        }
    
    def generate_social_queue(self, scheduling_config: Optional[SchedulingConfig] = None) -> Optional[str]:
        """
        Generate social posting queue for current build
        
        Args:
            scheduling_config: Optional scheduling configuration
            
        Returns:
            Build ID of generated queue, or None if no packages available
        """
        if not self.manifest:
            raise ValueError("No manifest loaded")
        
        # Get all valid social packages
        all_packages = []
        discovered = self.discover_social_packages()
        
        for episode_id in discovered.keys():
            packages = self.load_social_packages(episode_id)
            valid_packages = [pkg for pkg in packages if pkg.status == PackageStatus.VALID]
            all_packages.extend(valid_packages)
        
        if not all_packages:
            return None
        
        # Generate queue
        queue = self.queue_manager.generate_queue_file(
            build_id=self.manifest.build_id,
            social_packages=all_packages,
            scheduling_config=scheduling_config
        )
        
        # Save queue file
        queue_path = self.queue_manager.save_queue_file(queue)
        
        # Update social manifest with queue path
        if self.manifest.social:
            self.manifest.social.queue_path = str(queue_path)
        
        return self.manifest.build_id
    
    def get_social_queue_status(self, build_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of social posting queue
        
        Args:
            build_id: Optional build ID, uses current manifest build_id if not provided
            
        Returns:
            Dictionary with queue status information
        """
        if build_id is None:
            if not self.manifest:
                raise ValueError("No manifest loaded and no build_id provided")
            build_id = self.manifest.build_id
        
        return self.queue_manager.get_queue_statistics(build_id)
    
    def update_queue_item_status(self, item_id: str, status: QueueItemStatus,
                                external_id: Optional[str] = None,
                                error_message: Optional[str] = None,
                                build_id: Optional[str] = None) -> bool:
        """
        Update status of a queue item
        
        Args:
            item_id: Queue item identifier
            status: New status
            external_id: Optional external platform ID
            error_message: Optional error message
            build_id: Optional build ID, uses current manifest build_id if not provided
            
        Returns:
            True if update successful
        """
        if build_id is None:
            if not self.manifest:
                raise ValueError("No manifest loaded and no build_id provided")
            build_id = self.manifest.build_id
        
        return self.queue_manager.update_queue_item_status(
            build_id=build_id,
            item_id=item_id,
            status=status,
            external_id=external_id,
            error_message=error_message
        )
    
    def get_pending_queue_items(self, build_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get pending items from social posting queue
        
        Args:
            build_id: Optional build ID, if None returns from all queues
            
        Returns:
            List of pending queue items as dictionaries
        """
        pending_items = self.queue_manager.get_pending_items(build_id)
        return [item.to_dict() for item in pending_items]
    
    def cleanup_old_social_queues(self, days_old: int = 30) -> int:
        """
        Clean up old social posting queues
        
        Args:
            days_old: Remove queues older than this many days
            
        Returns:
            Number of queues removed
        """
        return self.queue_manager.cleanup_old_queues(days_old)

    def save_manifest(self, output_path: Optional[str] = None) -> None:
        """
        Save current manifest to file
        
        Args:
            output_path: Path to save manifest (defaults to original location)
        """
        if not self.manifest:
            raise ValueError("No manifest loaded to save")
        
        if output_path is None:
            output_path = self.base_path / "publish_manifest.json"
        else:
            output_path = Path(output_path)
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save manifest
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.manifest.to_dict(), f, indent=2, ensure_ascii=False)


# Utility functions for working with Content Registry

def create_content_registry(base_path: Optional[str] = None) -> ContentRegistry:
    """
    Create a new ContentRegistry instance
    
    Args:
        base_path: Base directory path for content files
        
    Returns:
        Configured ContentRegistry instance
    """
    return ContentRegistry(base_path)


def load_and_validate_manifest(manifest_path: str, base_path: Optional[str] = None) -> tuple[ContentRegistry, ValidationResult]:
    """
    Load manifest and perform comprehensive validation
    
    Args:
        manifest_path: Path to manifest file
        base_path: Base directory path for content files
        
    Returns:
        Tuple of (ContentRegistry, ValidationResult)
    """
    registry = create_content_registry(base_path)
    
    try:
        manifest = registry.load_manifest(manifest_path)
        
        # Perform comprehensive validation
        content_validation = registry.validate_content_contract(manifest)
        cross_ref_validation = registry.validate_cross_references()
        
        # Combine validation results
        all_errors = content_validation.errors + cross_ref_validation.errors
        all_warnings = content_validation.warnings + cross_ref_validation.warnings
        
        combined_result = ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "content_validation": content_validation.metadata,
                "cross_reference_validation": cross_ref_validation.metadata,
                "total_validations": 2
            }
        )
        
        return registry, combined_result
        
    except Exception as e:
        # Return registry with error result
        error_result = ValidationResult(
            is_valid=False,
            errors=[ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Failed to load manifest: {str(e)}",
                location="manifest",
                severity=Severity.ERROR
            )],
            warnings=[],
            metadata={"exception": str(e)}
        )
        
        return registry, error_result


def filter_episodes_by_confidence(episodes: List[Episode], threshold: float = 0.8) -> List[Episode]:
    """
    Filter episodes by confidence threshold (placeholder for future confidence scoring)
    
    Args:
        episodes: List of episodes to filter
        threshold: Confidence threshold (0.0 to 1.0)
        
    Returns:
        Filtered list of episodes
    """
    # For now, return all episodes since confidence scoring is not implemented
    # This is a placeholder for future confidence-based filtering
    return episodes


def create_content_filter(
    series_ids: Optional[List[str]] = None,
    host_ids: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
    episode_ids: Optional[List[str]] = None
) -> ContentFilter:
    """
    Create a ContentFilter with specified criteria
    
    Args:
        series_ids: Filter by series IDs
        host_ids: Filter by host IDs  
        date_from: Filter episodes from this date
        date_to: Filter episodes to this date
        tags: Filter by tags
        episode_ids: Filter by specific episode IDs
        
    Returns:
        Configured ContentFilter
    """
    return ContentFilter(
        series_ids=series_ids,
        host_ids=host_ids,
        date_from=date_from,
        date_to=date_to,
        tags=tags,
        episode_ids=episode_ids
    )