"""
Platform Profile System for Social Media Package Generation

Implements platform-specific media specifications, validation rules,
and configuration management for social media content normalization.
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from .publishing_models import ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity


class DurationUnit(Enum):
    """Duration units for platform specifications"""
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"


@dataclass
class VideoSpecs:
    """Video specifications for a platform"""
    max_duration: Optional[str] = None  # ISO 8601 duration format (PT60S, PT12H)
    min_duration: Optional[str] = None
    resolutions: List[str] = field(default_factory=list)  # ["1920x1080", "1280x720"]
    codecs: List[str] = field(default_factory=list)  # ["h264", "h265"]
    max_bitrate: Optional[str] = None  # "50Mbps"
    min_bitrate: Optional[str] = None
    max_file_size: Optional[str] = None  # "2GB"
    aspect_ratios: List[str] = field(default_factory=list)  # ["16:9", "9:16", "1:1"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_duration': self.max_duration,
            'min_duration': self.min_duration,
            'resolutions': self.resolutions,
            'codecs': self.codecs,
            'max_bitrate': self.max_bitrate,
            'min_bitrate': self.min_bitrate,
            'max_file_size': self.max_file_size,
            'aspect_ratios': self.aspect_ratios
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoSpecs':
        return cls(
            max_duration=data.get('max_duration'),
            min_duration=data.get('min_duration'),
            resolutions=data.get('resolutions', []),
            codecs=data.get('codecs', []),
            max_bitrate=data.get('max_bitrate'),
            min_bitrate=data.get('min_bitrate'),
            max_file_size=data.get('max_file_size'),
            aspect_ratios=data.get('aspect_ratios', [])
        )


@dataclass
class AudioSpecs:
    """Audio specifications for a platform"""
    codecs: List[str] = field(default_factory=list)  # ["aac", "mp3"]
    loudness_target: Optional[str] = None  # "-14 LUFS"
    loudness_range: Optional[str] = None  # "-23 to -14 LUFS"
    sample_rates: List[int] = field(default_factory=list)  # [44100, 48000]
    bitrates: List[str] = field(default_factory=list)  # ["128kbps", "320kbps"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'codecs': self.codecs,
            'loudness_target': self.loudness_target,
            'loudness_range': self.loudness_range,
            'sample_rates': self.sample_rates,
            'bitrates': self.bitrates
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioSpecs':
        return cls(
            codecs=data.get('codecs', []),
            loudness_target=data.get('loudness_target'),
            loudness_range=data.get('loudness_range'),
            sample_rates=data.get('sample_rates', []),
            bitrates=data.get('bitrates', [])
        )


@dataclass
class MetadataSpecs:
    """Metadata specifications for a platform"""
    title_max_length: Optional[int] = None
    title_min_length: Optional[int] = None
    description_max_length: Optional[int] = None
    description_min_length: Optional[int] = None
    tags_max_count: Optional[int] = None
    tag_max_length: Optional[int] = None
    supports_captions: bool = True
    supports_thumbnails: bool = True
    thumbnail_formats: List[str] = field(default_factory=list)  # ["jpg", "png"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title_max_length': self.title_max_length,
            'title_min_length': self.title_min_length,
            'description_max_length': self.description_max_length,
            'description_min_length': self.description_min_length,
            'tags_max_count': self.tags_max_count,
            'tag_max_length': self.tag_max_length,
            'supports_captions': self.supports_captions,
            'supports_thumbnails': self.supports_thumbnails,
            'thumbnail_formats': self.thumbnail_formats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetadataSpecs':
        return cls(
            title_max_length=data.get('title_max_length'),
            title_min_length=data.get('title_min_length'),
            description_max_length=data.get('description_max_length'),
            description_min_length=data.get('description_min_length'),
            tags_max_count=data.get('tags_max_count'),
            tag_max_length=data.get('tag_max_length'),
            supports_captions=data.get('supports_captions', True),
            supports_thumbnails=data.get('supports_thumbnails', True),
            thumbnail_formats=data.get('thumbnail_formats', [])
        )


@dataclass
class PlatformProfile:
    """Complete platform profile with all specifications"""
    platform_name: str
    platform_id: str
    video: VideoSpecs
    audio: AudioSpecs
    metadata: MetadataSpecs
    enabled: bool = True
    api_version: Optional[str] = None
    upload_endpoint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'platform_name': self.platform_name,
            'platform_id': self.platform_id,
            'video': self.video.to_dict(),
            'audio': self.audio.to_dict(),
            'metadata': self.metadata.to_dict(),
            'enabled': self.enabled,
            'api_version': self.api_version,
            'upload_endpoint': self.upload_endpoint
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlatformProfile':
        return cls(
            platform_name=data['platform_name'],
            platform_id=data['platform_id'],
            video=VideoSpecs.from_dict(data['video']),
            audio=AudioSpecs.from_dict(data['audio']),
            metadata=MetadataSpecs.from_dict(data['metadata']),
            enabled=data.get('enabled', True),
            api_version=data.get('api_version'),
            upload_endpoint=data.get('upload_endpoint')
        )


class PlatformProfileLoader:
    """Loads and manages platform profiles from YAML configuration"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize profile loader
        
        Args:
            config_path: Path to platform profiles YAML file
        """
        self.config_path = Path(config_path) if config_path else None
        self._profiles: Dict[str, PlatformProfile] = {}
        self._loaded = False
    
    def load_profiles(self, config_path: Optional[Union[str, Path]] = None) -> Dict[str, PlatformProfile]:
        """
        Load platform profiles from YAML configuration
        
        Args:
            config_path: Optional path to override default config path
            
        Returns:
            Dictionary of platform_id -> PlatformProfile
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If profile validation fails
        """
        if config_path:
            self.config_path = Path(config_path)
        
        if not self.config_path or not self.config_path.exists():
            raise FileNotFoundError(f"Platform profiles config not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse platform profiles YAML: {e}")
        
        if not isinstance(config_data, dict) or 'platforms' not in config_data:
            raise ValueError("Invalid platform profiles format: missing 'platforms' key")
        
        profiles = {}
        for platform_id, platform_data in config_data['platforms'].items():
            try:
                # Add platform_id to the data if not present
                if 'platform_id' not in platform_data:
                    platform_data['platform_id'] = platform_id
                
                profile = PlatformProfile.from_dict(platform_data)
                profiles[platform_id] = profile
            except Exception as e:
                raise ValueError(f"Failed to load profile for platform '{platform_id}': {e}")
        
        self._profiles = profiles
        self._loaded = True
        return profiles
    
    def get_profile(self, platform_id: str) -> Optional[PlatformProfile]:
        """
        Get platform profile by ID
        
        Args:
            platform_id: Platform identifier
            
        Returns:
            PlatformProfile if found, None otherwise
        """
        if not self._loaded:
            raise RuntimeError("Profiles not loaded. Call load_profiles() first.")
        
        return self._profiles.get(platform_id)
    
    def get_enabled_profiles(self) -> Dict[str, PlatformProfile]:
        """
        Get all enabled platform profiles
        
        Returns:
            Dictionary of enabled platform profiles
        """
        if not self._loaded:
            raise RuntimeError("Profiles not loaded. Call load_profiles() first.")
        
        return {
            platform_id: profile 
            for platform_id, profile in self._profiles.items() 
            if profile.enabled
        }
    
    def list_platforms(self) -> List[str]:
        """
        List all available platform IDs
        
        Returns:
            List of platform identifiers
        """
        if not self._loaded:
            raise RuntimeError("Profiles not loaded. Call load_profiles() first.")
        
        return list(self._profiles.keys())


class MediaSpecValidator:
    """Validates media assets against platform specifications"""
    
    def __init__(self, profile: PlatformProfile):
        """
        Initialize validator with platform profile
        
        Args:
            profile: Platform profile to validate against
        """
        self.profile = profile
    
    def validate_video_specs(self, 
                           duration_seconds: Optional[float] = None,
                           resolution: Optional[str] = None,
                           codec: Optional[str] = None,
                           bitrate: Optional[str] = None,
                           file_size_bytes: Optional[int] = None,
                           aspect_ratio: Optional[str] = None) -> ValidationResult:
        """
        Validate video specifications against platform profile
        
        Args:
            duration_seconds: Video duration in seconds
            resolution: Video resolution (e.g., "1920x1080")
            codec: Video codec (e.g., "h264")
            bitrate: Video bitrate (e.g., "5Mbps")
            file_size_bytes: File size in bytes
            aspect_ratio: Aspect ratio (e.g., "16:9")
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate duration
        if duration_seconds is not None:
            duration_errors = self._validate_duration(duration_seconds)
            errors.extend(duration_errors)
        
        # Validate resolution
        if resolution and self.profile.video.resolutions:
            if resolution not in self.profile.video.resolutions:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Resolution {resolution} not supported. Supported: {self.profile.video.resolutions}",
                    location="video.resolution",
                    severity=Severity.ERROR
                ))
        
        # Validate codec
        if codec and self.profile.video.codecs:
            if codec.lower() not in [c.lower() for c in self.profile.video.codecs]:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Codec {codec} not supported. Supported: {self.profile.video.codecs}",
                    location="video.codec",
                    severity=Severity.ERROR
                ))
        
        # Validate aspect ratio
        if aspect_ratio and self.profile.video.aspect_ratios:
            if aspect_ratio not in self.profile.video.aspect_ratios:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Aspect ratio {aspect_ratio} not supported. Supported: {self.profile.video.aspect_ratios}",
                    location="video.aspect_ratio",
                    severity=Severity.ERROR
                ))
        
        # Validate bitrate
        if bitrate and self.profile.video.max_bitrate:
            bitrate_errors = self._validate_bitrate(bitrate, self.profile.video.max_bitrate)
            errors.extend(bitrate_errors)
        
        # Validate file size
        if file_size_bytes and self.profile.video.max_file_size:
            file_size_errors = self._validate_file_size(file_size_bytes, self.profile.video.max_file_size)
            errors.extend(file_size_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'platform': self.profile.platform_id}
        )
    
    def validate_audio_specs(self,
                           codec: Optional[str] = None,
                           loudness: Optional[str] = None,
                           sample_rate: Optional[int] = None,
                           bitrate: Optional[str] = None) -> ValidationResult:
        """
        Validate audio specifications against platform profile
        
        Args:
            codec: Audio codec (e.g., "aac")
            loudness: Loudness level (e.g., "-14 LUFS")
            sample_rate: Sample rate in Hz (e.g., 48000)
            bitrate: Audio bitrate (e.g., "128kbps")
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate codec
        if codec and self.profile.audio.codecs:
            if codec.lower() not in [c.lower() for c in self.profile.audio.codecs]:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Audio codec {codec} not supported. Supported: {self.profile.audio.codecs}",
                    location="audio.codec",
                    severity=Severity.ERROR
                ))
        
        # Validate sample rate
        if sample_rate and self.profile.audio.sample_rates:
            if sample_rate not in self.profile.audio.sample_rates:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Sample rate {sample_rate}Hz not supported. Supported: {self.profile.audio.sample_rates}",
                    location="audio.sample_rate",
                    severity=Severity.ERROR
                ))
        
        # Validate loudness target
        if loudness and self.profile.audio.loudness_target:
            loudness_warnings = self._validate_loudness(loudness, self.profile.audio.loudness_target)
            warnings.extend(loudness_warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'platform': self.profile.platform_id}
        )
    
    def validate_metadata_specs(self,
                              title: Optional[str] = None,
                              description: Optional[str] = None,
                              tags: Optional[List[str]] = None) -> ValidationResult:
        """
        Validate metadata specifications against platform profile
        
        Args:
            title: Content title
            description: Content description
            tags: List of content tags
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate title length
        if title:
            if self.profile.metadata.title_max_length and len(title) > self.profile.metadata.title_max_length:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Title too long: {len(title)} chars (max: {self.profile.metadata.title_max_length})",
                    location="metadata.title",
                    severity=Severity.ERROR
                ))
            
            if self.profile.metadata.title_min_length and len(title) < self.profile.metadata.title_min_length:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Title too short: {len(title)} chars (min: {self.profile.metadata.title_min_length})",
                    location="metadata.title",
                    severity=Severity.ERROR
                ))
        
        # Validate description length
        if description:
            if self.profile.metadata.description_max_length and len(description) > self.profile.metadata.description_max_length:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Description too long: {len(description)} chars (max: {self.profile.metadata.description_max_length})",
                    location="metadata.description",
                    severity=Severity.ERROR
                ))
        
        # Validate tags
        if tags:
            if self.profile.metadata.tags_max_count and len(tags) > self.profile.metadata.tags_max_count:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Too many tags: {len(tags)} (max: {self.profile.metadata.tags_max_count})",
                    location="metadata.tags",
                    severity=Severity.ERROR
                ))
            
            if self.profile.metadata.tag_max_length:
                for i, tag in enumerate(tags):
                    if len(tag) > self.profile.metadata.tag_max_length:
                        errors.append(ValidationError(
                            error_type=ErrorType.MEDIA_VALIDATION,
                            message=f"Tag {i+1} too long: {len(tag)} chars (max: {self.profile.metadata.tag_max_length})",
                            location=f"metadata.tags[{i}]",
                            severity=Severity.ERROR
                        ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'platform': self.profile.platform_id}
        )
    
    def _validate_duration(self, duration_seconds: float) -> List[ValidationError]:
        """Validate video duration against platform limits"""
        errors = []
        
        if self.profile.video.max_duration:
            max_seconds = self._parse_duration_to_seconds(self.profile.video.max_duration)
            if duration_seconds > max_seconds:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Duration {duration_seconds}s exceeds maximum {max_seconds}s",
                    location="video.duration",
                    severity=Severity.ERROR
                ))
        
        if self.profile.video.min_duration:
            min_seconds = self._parse_duration_to_seconds(self.profile.video.min_duration)
            if duration_seconds < min_seconds:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Duration {duration_seconds}s below minimum {min_seconds}s",
                    location="video.duration",
                    severity=Severity.ERROR
                ))
        
        return errors
    
    def _parse_duration_to_seconds(self, duration_str: str) -> float:
        """Parse ISO 8601 duration string to seconds"""
        import re
        
        # Handle ISO 8601 format (PT1H30M45S)
        if duration_str.startswith('PT'):
            pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?'
            match = re.match(pattern, duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = float(match.group(3) or 0)
                return hours * 3600 + minutes * 60 + seconds
        
        # Handle simple seconds format
        try:
            return float(duration_str.rstrip('s'))
        except ValueError:
            return 0.0
    
    def _validate_bitrate(self, bitrate: str, max_bitrate: str) -> List[ValidationError]:
        """Validate bitrate against maximum"""
        errors = []
        
        try:
            # Parse bitrate values (e.g., "5Mbps" -> 5000000)
            current_bps = self._parse_bitrate_to_bps(bitrate)
            max_bps = self._parse_bitrate_to_bps(max_bitrate)
            
            if current_bps > max_bps:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"Bitrate {bitrate} exceeds maximum {max_bitrate}",
                    location="video.bitrate",
                    severity=Severity.ERROR
                ))
        except ValueError as e:
            errors.append(ValidationError(
                error_type=ErrorType.MEDIA_VALIDATION,
                message=f"Invalid bitrate format: {e}",
                location="video.bitrate",
                severity=Severity.ERROR
            ))
        
        return errors
    
    def _parse_bitrate_to_bps(self, bitrate_str: str) -> int:
        """Parse bitrate string to bits per second"""
        import re
        
        # Match number and unit (e.g., "5Mbps", "128kbps")
        match = re.match(r'(\d+(?:\.\d+)?)\s*([kmg]?bps)', bitrate_str.lower())
        if not match:
            raise ValueError(f"Invalid bitrate format: {bitrate_str}")
        
        value = float(match.group(1))
        unit = match.group(2)
        
        multipliers = {
            'bps': 1,
            'kbps': 1000,
            'mbps': 1000000,
            'gbps': 1000000000
        }
        
        return int(value * multipliers[unit])
    
    def _validate_file_size(self, file_size_bytes: int, max_size_str: str) -> List[ValidationError]:
        """Validate file size against maximum"""
        errors = []
        
        try:
            max_bytes = self._parse_size_to_bytes(max_size_str)
            if file_size_bytes > max_bytes:
                errors.append(ValidationError(
                    error_type=ErrorType.MEDIA_VALIDATION,
                    message=f"File size {file_size_bytes} bytes exceeds maximum {max_size_str}",
                    location="video.file_size",
                    severity=Severity.ERROR
                ))
        except ValueError as e:
            errors.append(ValidationError(
                error_type=ErrorType.MEDIA_VALIDATION,
                message=f"Invalid file size format: {e}",
                location="video.file_size",
                severity=Severity.ERROR
            ))
        
        return errors
    
    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Parse size string to bytes"""
        import re
        
        # Match number and unit (e.g., "2GB", "500MB")
        match = re.match(r'(\d+(?:\.\d+)?)\s*([kmgt]?b)', size_str.lower())
        if not match:
            raise ValueError(f"Invalid size format: {size_str}")
        
        value = float(match.group(1))
        unit = match.group(2)
        
        multipliers = {
            'b': 1,
            'kb': 1024,
            'mb': 1024**2,
            'gb': 1024**3,
            'tb': 1024**4
        }
        
        return int(value * multipliers[unit])
    
    def _validate_loudness(self, loudness: str, target_loudness: str) -> List[ValidationWarning]:
        """Validate loudness against target (warnings only)"""
        warnings = []
        
        try:
            # Parse LUFS values (e.g., "-14 LUFS" -> -14.0)
            current_lufs = self._parse_lufs(loudness)
            target_lufs = self._parse_lufs(target_loudness)
            
            # Allow some tolerance (±2 LUFS)
            tolerance = 2.0
            if abs(current_lufs - target_lufs) > tolerance:
                warnings.append(ValidationWarning(
                    message=f"Loudness {loudness} differs from target {target_loudness} by more than {tolerance} LUFS",
                    location="audio.loudness"
                ))
        except ValueError:
            warnings.append(ValidationWarning(
                message=f"Could not parse loudness values: {loudness} vs {target_loudness}",
                location="audio.loudness"
            ))
        
        return warnings
    
    def _parse_lufs(self, lufs_str: str) -> float:
        """Parse LUFS string to float value"""
        import re
        
        # Match LUFS value (e.g., "-14 LUFS", "-14.5LUFS")
        match = re.match(r'(-?\d+(?:\.\d+)?)\s*lufs', lufs_str.lower())
        if not match:
            raise ValueError(f"Invalid LUFS format: {lufs_str}")
        
        return float(match.group(1))


def create_default_profiles_config() -> Dict[str, Any]:
    """
    Create default platform profiles configuration
    
    Returns:
        Dictionary with default platform configurations
    """
    return {
        'platforms': {
            'youtube': {
                'platform_name': 'YouTube',
                'platform_id': 'youtube',
                'enabled': True,
                'api_version': 'v3',
                'video': {
                    'max_duration': 'PT12H',  # 12 hours
                    'min_duration': 'PT1S',   # 1 second
                    'resolutions': ['1920x1080', '1280x720', '854x480', '640x360'],
                    'codecs': ['h264', 'h265'],
                    'max_bitrate': '50Mbps',
                    'max_file_size': '256GB',
                    'aspect_ratios': ['16:9', '9:16', '1:1', '4:3']
                },
                'audio': {
                    'codecs': ['aac', 'mp3'],
                    'loudness_target': '-14 LUFS',
                    'loudness_range': '-23 to -14 LUFS',
                    'sample_rates': [44100, 48000],
                    'bitrates': ['128kbps', '192kbps', '320kbps']
                },
                'metadata': {
                    'title_max_length': 100,
                    'title_min_length': 1,
                    'description_max_length': 5000,
                    'tags_max_count': 500,
                    'tag_max_length': 30,
                    'supports_captions': True,
                    'supports_thumbnails': True,
                    'thumbnail_formats': ['jpg', 'png']
                }
            },
            'instagram': {
                'platform_name': 'Instagram',
                'platform_id': 'instagram',
                'enabled': True,
                'video': {
                    'max_duration': 'PT60S',  # 60 seconds for reels
                    'min_duration': 'PT3S',   # 3 seconds
                    'resolutions': ['1080x1920', '1080x1080', '1080x608'],
                    'codecs': ['h264'],
                    'max_bitrate': '10Mbps',
                    'max_file_size': '4GB',
                    'aspect_ratios': ['9:16', '1:1', '16:9']
                },
                'audio': {
                    'codecs': ['aac'],
                    'loudness_target': '-16 LUFS',
                    'sample_rates': [44100, 48000],
                    'bitrates': ['128kbps', '192kbps']
                },
                'metadata': {
                    'title_max_length': 150,
                    'description_max_length': 2200,
                    'tags_max_count': 30,
                    'tag_max_length': 100,
                    'supports_captions': False,  # Burn-in required
                    'supports_thumbnails': True,
                    'thumbnail_formats': ['jpg']
                }
            },
            'tiktok': {
                'platform_name': 'TikTok',
                'platform_id': 'tiktok',
                'enabled': False,  # Optional platform
                'video': {
                    'max_duration': 'PT180S',  # 3 minutes
                    'min_duration': 'PT15S',   # 15 seconds
                    'resolutions': ['1080x1920', '720x1280'],
                    'codecs': ['h264'],
                    'max_bitrate': '8Mbps',
                    'max_file_size': '287MB',
                    'aspect_ratios': ['9:16']
                },
                'audio': {
                    'codecs': ['aac'],
                    'loudness_target': '-16 LUFS',
                    'sample_rates': [44100, 48000],
                    'bitrates': ['128kbps']
                },
                'metadata': {
                    'title_max_length': 150,
                    'description_max_length': 2200,
                    'tags_max_count': 100,
                    'supports_captions': False,
                    'supports_thumbnails': True,
                    'thumbnail_formats': ['jpg']
                }
            }
        }
    }


def save_default_profiles_config(config_path: Union[str, Path]) -> None:
    """
    Save default platform profiles configuration to YAML file
    
    Args:
        config_path: Path where to save the configuration
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config_data = create_default_profiles_config()
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, indent=2)