"""
Data models for the Content Publishing Platform

Defines the core data structures for content publishing, including episodes,
series, hosts, social packages, and publishing manifests.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import uuid


class PackageStatus(Enum):
    """Status of social media package processing"""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    QUEUED = "queued"
    POSTED = "posted"
    FAILED = "failed"


class PrivacyLevel(Enum):
    """Privacy levels for social media posts"""
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class AssetType(Enum):
    """Types of media assets"""
    VIDEO = "video"
    AUDIO = "audio"
    THUMBNAIL = "thumbnail"
    CAPTIONS = "captions"


class ErrorType(Enum):
    """Types of validation errors"""
    SCHEMA_VALIDATION = "schema_validation"
    LINK_VALIDATION = "link_validation"
    MEDIA_VALIDATION = "media_validation"
    RIGHTS_VALIDATION = "rights_validation"
    PLATFORM_COMPLIANCE = "platform_compliance"


class Severity(Enum):
    """Error severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Person:
    """Person entity (host, guest, etc.)"""
    person_id: str
    name: str
    slug: str
    bio: Optional[str] = None
    headshot_url: Optional[str] = None
    same_as_links: List[str] = field(default_factory=list)  # Wikidata, Wikipedia, etc.
    affiliation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'person_id': self.person_id,
            'name': self.name,
            'slug': self.slug,
            'bio': self.bio,
            'headshot_url': self.headshot_url,
            'same_as_links': self.same_as_links,
            'affiliation': self.affiliation
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Person':
        return cls(
            person_id=data['person_id'],
            name=data['name'],
            slug=data['slug'],
            bio=data.get('bio'),
            headshot_url=data.get('headshot_url'),
            same_as_links=data.get('same_as_links', []),
            affiliation=data.get('affiliation')
        )


@dataclass
class Host(Person):
    """Host entity extending Person with host-specific fields"""
    shows: List[str] = field(default_factory=list)  # series IDs
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['shows'] = self.shows
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Host':
        return cls(
            person_id=data['person_id'],
            name=data['name'],
            slug=data['slug'],
            bio=data.get('bio'),
            headshot_url=data.get('headshot_url'),
            same_as_links=data.get('same_as_links', []),
            affiliation=data.get('affiliation'),
            shows=data.get('shows', [])
        )


@dataclass
class Series:
    """Series/show information"""
    series_id: str
    title: str
    description: str
    slug: str
    primary_host: Host
    artwork_url: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    live_series_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'series_id': self.series_id,
            'title': self.title,
            'description': self.description,
            'slug': self.slug,
            'primary_host': self.primary_host.to_dict(),
            'artwork_url': self.artwork_url,
            'topics': self.topics,
            'live_series_url': self.live_series_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Series':
        return cls(
            series_id=data['series_id'],
            title=data['title'],
            description=data['description'],
            slug=data['slug'],
            primary_host=Host.from_dict(data['primary_host']),
            artwork_url=data.get('artwork_url'),
            topics=data.get('topics', []),
            live_series_url=data.get('live_series_url')
        )


@dataclass
class RightsMetadata:
    """Rights and licensing information"""
    music_clearance: bool = False
    third_party_assets: List[str] = field(default_factory=list)
    licensing_notes: Optional[str] = None
    copyright_holder: Optional[str] = None
    license_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'music_clearance': self.music_clearance,
            'third_party_assets': self.third_party_assets,
            'licensing_notes': self.licensing_notes,
            'copyright_holder': self.copyright_holder,
            'license_url': self.license_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RightsMetadata':
        return cls(
            music_clearance=data.get('music_clearance', False),
            third_party_assets=data.get('third_party_assets', []),
            licensing_notes=data.get('licensing_notes'),
            copyright_holder=data.get('copyright_holder'),
            license_url=data.get('license_url')
        )


@dataclass
class Episode:
    """Episode content model for publishing"""
    episode_id: str
    title: str
    description: str
    upload_date: datetime
    duration: timedelta
    series: Series
    hosts: List[Host]
    guests: List[Person] = field(default_factory=list)
    transcript_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    content_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    social_links: Dict[str, str] = field(default_factory=dict)  # platform -> URL
    rights: Optional[RightsMetadata] = None
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'title': self.title,
            'description': self.description,
            'upload_date': self.upload_date.isoformat(),
            'duration': str(self.duration),
            'series': self.series.to_dict(),
            'hosts': [host.to_dict() for host in self.hosts],
            'guests': [guest.to_dict() for guest in self.guests],
            'transcript_path': self.transcript_path,
            'thumbnail_url': self.thumbnail_url,
            'content_url': self.content_url,
            'tags': self.tags,
            'social_links': self.social_links,
            'rights': self.rights.to_dict() if self.rights else None,
            'episode_number': self.episode_number,
            'season_number': self.season_number
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Episode':
        # Parse duration from string format
        duration_str = data['duration']
        if isinstance(duration_str, str):
            # Handle ISO 8601 duration format or simple seconds
            if duration_str.startswith('PT'):
                # Parse ISO 8601 duration (PT1H30M45S)
                import re
                pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?'
                match = re.match(pattern, duration_str)
                if match:
                    hours = int(match.group(1) or 0)
                    minutes = int(match.group(2) or 0)
                    seconds = float(match.group(3) or 0)
                    duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                else:
                    duration = timedelta(seconds=0)
            else:
                # Assume it's a timedelta string representation
                duration = timedelta(seconds=float(duration_str))
        else:
            duration = timedelta(seconds=data['duration'])
        
        return cls(
            episode_id=data['episode_id'],
            title=data['title'],
            description=data['description'],
            upload_date=datetime.fromisoformat(data['upload_date']),
            duration=duration,
            series=Series.from_dict(data['series']),
            hosts=[Host.from_dict(host_data) for host_data in data['hosts']],
            guests=[Person.from_dict(guest_data) for guest_data in data.get('guests', [])],
            transcript_path=data.get('transcript_path'),
            thumbnail_url=data.get('thumbnail_url'),
            content_url=data.get('content_url'),
            tags=data.get('tags', []),
            social_links=data.get('social_links', {}),
            rights=RightsMetadata.from_dict(data['rights']) if data.get('rights') else None,
            episode_number=data.get('episode_number'),
            season_number=data.get('season_number')
        )


@dataclass
class PathMapping:
    """Directory structure mapping for content"""
    public_root: str
    meta_root: str
    transcripts_root: str
    social_root: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'public_root': self.public_root,
            'meta_root': self.meta_root,
            'transcripts_root': self.transcripts_root,
            'social_root': self.social_root
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PathMapping':
        return cls(
            public_root=data['public_root'],
            meta_root=data['meta_root'],
            transcripts_root=data['transcripts_root'],
            social_root=data.get('social_root')
        )


@dataclass
class SocialManifest:
    """Social media package manifest"""
    platforms: Dict[str, int] = field(default_factory=dict)  # platform -> item count
    ready_flags: Dict[str, bool] = field(default_factory=dict)  # platform -> ready status
    queue_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'platforms': self.platforms,
            'ready_flags': self.ready_flags,
            'queue_path': self.queue_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialManifest':
        return cls(
            platforms=data.get('platforms', {}),
            ready_flags=data.get('ready_flags', {}),
            queue_path=data.get('queue_path')
        )


@dataclass
class PublishManifest:
    """Publishing manifest defining content contract"""
    manifest_version: str
    build_id: str
    episodes: List[Dict[str, Any]]  # Episode metadata
    series: List[Dict[str, Any]]    # Series registry
    hosts: List[Dict[str, Any]]     # Host registry
    paths: PathMapping
    social: Optional[SocialManifest] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'manifest_version': self.manifest_version,
            'build_id': self.build_id,
            'episodes': self.episodes,
            'series': self.series,
            'hosts': self.hosts,
            'paths': self.paths.to_dict(),
            'social': self.social.to_dict() if self.social else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PublishManifest':
        return cls(
            manifest_version=data['manifest_version'],
            build_id=data['build_id'],
            episodes=data['episodes'],
            series=data['series'],
            hosts=data['hosts'],
            paths=PathMapping.from_dict(data['paths']),
            social=SocialManifest.from_dict(data['social']) if data.get('social') else None,
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )


@dataclass
class FormatSpecs:
    """Media format specifications"""
    resolution: Optional[str] = None
    codec: Optional[str] = None
    bitrate: Optional[str] = None
    frame_rate: Optional[float] = None
    loudness_target: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'resolution': self.resolution,
            'codec': self.codec,
            'bitrate': self.bitrate,
            'frame_rate': self.frame_rate,
            'loudness_target': self.loudness_target
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FormatSpecs':
        return cls(
            resolution=data.get('resolution'),
            codec=data.get('codec'),
            bitrate=data.get('bitrate'),
            frame_rate=data.get('frame_rate'),
            loudness_target=data.get('loudness_target')
        )


@dataclass
class MediaAsset:
    """Media asset for social packages"""
    asset_path: str
    asset_type: AssetType
    format_specs: FormatSpecs
    duration: Optional[timedelta] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'asset_path': self.asset_path,
            'asset_type': self.asset_type.value,
            'format_specs': self.format_specs.to_dict(),
            'duration': str(self.duration) if self.duration else None,
            'file_size': self.file_size,
            'checksum': self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MediaAsset':
        duration = None
        if data.get('duration'):
            # Parse duration string back to timedelta
            duration_str = data['duration']
            if ':' in duration_str:
                # Handle HH:MM:SS format
                parts = duration_str.split(':')
                hours = int(parts[0]) if len(parts) > 2 else 0
                minutes = int(parts[1]) if len(parts) > 1 else 0
                seconds = float(parts[-1])
                duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            else:
                duration = timedelta(seconds=float(duration_str))
        
        return cls(
            asset_path=data['asset_path'],
            asset_type=AssetType(data['asset_type']),
            format_specs=FormatSpecs.from_dict(data['format_specs']),
            duration=duration,
            file_size=data.get('file_size'),
            checksum=data.get('checksum')
        )


@dataclass
class UploadManifest:
    """Upload manifest for social media packages"""
    title: str
    description: str
    tags: List[str]
    publish_at: datetime
    privacy: PrivacyLevel
    age_restriction: bool = False
    made_for_kids: bool = False
    captions_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_paths: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'description': self.description,
            'tags': self.tags,
            'publish_at': self.publish_at.isoformat(),
            'privacy': self.privacy.value,
            'age_restriction': self.age_restriction,
            'made_for_kids': self.made_for_kids,
            'captions_url': self.captions_url,
            'thumbnail_url': self.thumbnail_url,
            'media_paths': self.media_paths
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UploadManifest':
        return cls(
            title=data['title'],
            description=data['description'],
            tags=data['tags'],
            publish_at=datetime.fromisoformat(data['publish_at']),
            privacy=PrivacyLevel(data['privacy']),
            age_restriction=data.get('age_restriction', False),
            made_for_kids=data.get('made_for_kids', False),
            captions_url=data.get('captions_url'),
            thumbnail_url=data.get('thumbnail_url'),
            media_paths=data.get('media_paths', [])
        )


@dataclass
class SocialPackage:
    """Social media package for a platform"""
    episode_id: str
    platform: str
    status: PackageStatus
    media_assets: List[MediaAsset]
    upload_manifest: UploadManifest
    rights: RightsMetadata
    created_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    external_id: Optional[str] = None  # Platform-specific video/post ID
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'platform': self.platform,
            'status': self.status.value,
            'media_assets': [asset.to_dict() for asset in self.media_assets],
            'upload_manifest': self.upload_manifest.to_dict(),
            'rights': self.rights.to_dict(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None,
            'external_id': self.external_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialPackage':
        return cls(
            episode_id=data['episode_id'],
            platform=data['platform'],
            status=PackageStatus(data['status']),
            media_assets=[MediaAsset.from_dict(asset_data) for asset_data in data['media_assets']],
            upload_manifest=UploadManifest.from_dict(data['upload_manifest']),
            rights=RightsMetadata.from_dict(data['rights']),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            posted_at=datetime.fromisoformat(data['posted_at']) if data.get('posted_at') else None,
            external_id=data.get('external_id')
        )


@dataclass
class ValidationError:
    """Validation error details"""
    error_type: ErrorType
    message: str
    location: str  # file path, line number, field name
    severity: Severity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_type': self.error_type.value,
            'message': self.message,
            'location': self.location,
            'severity': self.severity.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationError':
        return cls(
            error_type=ErrorType(data['error_type']),
            message=data['message'],
            location=data['location'],
            severity=Severity(data['severity'])
        )


@dataclass
class ValidationWarning:
    """Validation warning details"""
    message: str
    location: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message': self.message,
            'location': self.location
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationWarning':
        return cls(
            message=data['message'],
            location=data['location']
        )


@dataclass
class ValidationResult:
    """Result of validation operations"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationResult':
        return cls(
            is_valid=data['is_valid'],
            errors=[ValidationError.from_dict(error_data) for error_data in data.get('errors', [])],
            warnings=[ValidationWarning.from_dict(warning_data) for warning_data in data.get('warnings', [])],
            metadata=data.get('metadata', {})
        )


# Utility functions for creating models
def create_episode_from_metadata(episode_data: Dict[str, Any], 
                               series_data: Dict[str, Any],
                               hosts_data: List[Dict[str, Any]]) -> Episode:
    """Create Episode object from metadata dictionaries"""
    # Create series object
    primary_host = Host.from_dict(hosts_data[0]) if hosts_data else Host(
        person_id="unknown", name="Unknown Host", slug="unknown"
    )
    
    series = Series(
        series_id=series_data['series_id'],
        title=series_data['title'],
        description=series_data['description'],
        slug=series_data['slug'],
        primary_host=primary_host,
        artwork_url=series_data.get('artwork_url'),
        topics=series_data.get('topics', []),
        live_series_url=series_data.get('live_series_url')
    )
    
    # Create host objects
    hosts = [Host.from_dict(host_data) for host_data in hosts_data]
    
    # Create episode
    return Episode(
        episode_id=episode_data['episode_id'],
        title=episode_data['title'],
        description=episode_data['description'],
        upload_date=datetime.fromisoformat(episode_data['upload_date']),
        duration=timedelta(seconds=episode_data.get('duration_seconds', 0)),
        series=series,
        hosts=hosts,
        guests=[Person.from_dict(guest_data) for guest_data in episode_data.get('guests', [])],
        transcript_path=episode_data.get('transcript_path'),
        thumbnail_url=episode_data.get('thumbnail_url'),
        content_url=episode_data.get('content_url'),
        tags=episode_data.get('tags', []),
        social_links=episode_data.get('social_links', {}),
        rights=RightsMetadata.from_dict(episode_data['rights']) if episode_data.get('rights') else None,
        episode_number=episode_data.get('episode_number'),
        season_number=episode_data.get('season_number')
    )


def generate_build_id() -> str:
    """Generate a unique build ID"""
    return f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"