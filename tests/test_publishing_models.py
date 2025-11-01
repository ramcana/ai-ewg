"""
Unit tests for Content Publishing Platform data models

Tests the core data structures including episodes, series, hosts, social packages,
and publishing manifests with comprehensive validation and serialization testing.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from src.core.publishing_models import (
    Episode, Series, Host, Person, PublishManifest, PathMapping, SocialManifest,
    RightsMetadata, SocialPackage, UploadManifest, MediaAsset, FormatSpecs,
    ValidationResult, ValidationError, ValidationWarning,
    PackageStatus, PrivacyLevel, AssetType, ErrorType, Severity,
    create_episode_from_metadata, generate_build_id
)


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def sample_host():
    """Create a sample host for testing"""
    return Host(
        person_id="host-001",
        name="Dr. Jane Smith",
        slug="jane-smith",
        bio="AI researcher and technology expert with 15 years of experience",
        headshot_url="https://example.com/images/jane-smith.jpg",
        same_as_links=[
            "https://en.wikipedia.org/wiki/Jane_Smith",
            "https://www.wikidata.org/wiki/Q12345"
        ],
        affiliation="Example University",
        shows=["tech-talk", "ai-insights"]
    )


@pytest.fixture
def sample_series(sample_host):
    """Create a sample series for testing"""
    return Series(
        series_id="tech-talk",
        title="Tech Talk Weekly",
        description="Weekly discussions on the latest technology trends and innovations",
        slug="tech-talk-weekly",
        primary_host=sample_host,
        artwork_url="https://example.com/images/tech-talk-artwork.jpg",
        topics=["Technology", "AI", "Innovation", "Software"],
        live_series_url="https://example.com/series/tech-talk"
    )


@pytest.fixture
def sample_guest():
    """Create a sample guest for testing"""
    return Person(
        person_id="guest-001",
        name="Prof. John Doe",
        slug="john-doe",
        bio="Machine learning expert and author",
        headshot_url="https://example.com/images/john-doe.jpg",
        same_as_links=["https://en.wikipedia.org/wiki/John_Doe"],
        affiliation="Tech Institute"
    )


@pytest.fixture
def sample_rights_metadata():
    """Create sample rights metadata for testing"""
    return RightsMetadata(
        music_clearance=True,
        third_party_assets=["intro-music.mp3", "background-image.jpg"],
        licensing_notes="All content licensed under Creative Commons",
        copyright_holder="Example Media Corp",
        license_url="https://creativecommons.org/licenses/by/4.0/"
    )


@pytest.fixture
def sample_episode(sample_series, sample_host, sample_guest, sample_rights_metadata):
    """Create a sample episode for testing"""
    return Episode(
        episode_id="tech-talk-2024-001",
        title="The Future of Artificial Intelligence",
        description="An in-depth discussion about the current state and future prospects of AI technology, covering machine learning, neural networks, and ethical considerations.",
        upload_date=datetime(2024, 1, 15, 10, 0, 0),
        duration=timedelta(hours=1, minutes=30, seconds=45),
        series=sample_series,
        hosts=[sample_host],
        guests=[sample_guest],
        transcript_path="data/transcripts/tech-talk-2024-001.vtt",
        thumbnail_url="https://example.com/images/tech-talk-2024-001-thumb.jpg",
        content_url="https://example.com/videos/tech-talk-2024-001.mp4",
        tags=["AI", "Machine Learning", "Technology", "Future"],
        social_links={
            "youtube": "https://youtube.com/watch?v=abc123",
            "instagram": "https://instagram.com/p/def456"
        },
        rights=sample_rights_metadata,
        episode_number=1,
        season_number=2024
    )


@pytest.fixture
def sample_path_mapping():
    """Create sample path mapping for testing"""
    return PathMapping(
        public_root="data/public",
        meta_root="data/meta",
        transcripts_root="data/transcripts",
        social_root="data/social"
    )


@pytest.fixture
def sample_social_manifest():
    """Create sample social manifest for testing"""
    return SocialManifest(
        platforms={"youtube": 5, "instagram": 3},
        ready_flags={"youtube": True, "instagram": False},
        queue_path="data/social/queue/build_20240115.json"
    )


@pytest.fixture
def sample_publish_manifest(sample_episode, sample_series, sample_host, sample_path_mapping, sample_social_manifest):
    """Create sample publish manifest for testing"""
    return PublishManifest(
        manifest_version="1.0",
        build_id="build_20240115_120000_abc123",
        episodes=[sample_episode.to_dict()],
        series=[sample_series.to_dict()],
        hosts=[sample_host.to_dict()],
        paths=sample_path_mapping,
        social=sample_social_manifest,
        created_at=datetime(2024, 1, 15, 12, 0, 0)
    )


@pytest.fixture
def sample_format_specs():
    """Create sample format specifications for testing"""
    return FormatSpecs(
        resolution="1920x1080",
        codec="h264",
        bitrate="5000k",
        frame_rate=30.0,
        loudness_target="-14 LUFS"
    )


@pytest.fixture
def sample_media_asset(sample_format_specs):
    """Create sample media asset for testing"""
    return MediaAsset(
        asset_path="data/social/youtube/tech-talk-2024-001/video.mp4",
        asset_type=AssetType.VIDEO,
        format_specs=sample_format_specs,
        duration=timedelta(minutes=5, seconds=30),
        file_size=52428800,  # 50MB
        checksum="sha256:abc123def456"
    )


@pytest.fixture
def sample_upload_manifest():
    """Create sample upload manifest for testing"""
    return UploadManifest(
        title="AI Future Discussion - Tech Talk Weekly",
        description="Join us for an exciting discussion about the future of AI technology and its impact on society.",
        tags=["AI", "Technology", "Future", "TechTalk"],
        publish_at=datetime(2024, 1, 16, 9, 0, 0),
        privacy=PrivacyLevel.PUBLIC,
        age_restriction=False,
        made_for_kids=False,
        captions_url="data/social/youtube/tech-talk-2024-001/captions.vtt",
        thumbnail_url="data/social/youtube/tech-talk-2024-001/thumbnail.jpg",
        media_paths=["data/social/youtube/tech-talk-2024-001/video.mp4"]
    )


@pytest.fixture
def sample_social_package(sample_media_asset, sample_upload_manifest, sample_rights_metadata):
    """Create sample social package for testing"""
    return SocialPackage(
        episode_id="tech-talk-2024-001",
        platform="youtube",
        status=PackageStatus.VALID,
        media_assets=[sample_media_asset],
        upload_manifest=sample_upload_manifest,
        rights=sample_rights_metadata,
        created_at=datetime(2024, 1, 15, 14, 0, 0)
    )


# ========================================
# Person and Host Model Tests
# ========================================

class TestPersonModel:
    """Test Person data model"""
    
    def test_person_creation(self):
        """Test basic person creation"""
        person = Person(
            person_id="person-001",
            name="Test Person",
            slug="test-person"
        )
        
        assert person.person_id == "person-001"
        assert person.name == "Test Person"
        assert person.slug == "test-person"
        assert person.bio is None
        assert person.same_as_links == []
    
    def test_person_serialization(self, sample_guest):
        """Test person to_dict and from_dict methods"""
        person_dict = sample_guest.to_dict()
        
        # Verify dictionary structure
        assert person_dict["person_id"] == "guest-001"
        assert person_dict["name"] == "Prof. John Doe"
        assert person_dict["slug"] == "john-doe"
        assert person_dict["bio"] == "Machine learning expert and author"
        
        # Test round-trip serialization
        restored_person = Person.from_dict(person_dict)
        assert restored_person.person_id == sample_guest.person_id
        assert restored_person.name == sample_guest.name
        assert restored_person.same_as_links == sample_guest.same_as_links


class TestHostModel:
    """Test Host data model extending Person"""
    
    def test_host_creation(self, sample_host):
        """Test host creation with all fields"""
        assert sample_host.person_id == "host-001"
        assert sample_host.name == "Dr. Jane Smith"
        assert sample_host.shows == ["tech-talk", "ai-insights"]
        assert len(sample_host.same_as_links) == 2
    
    def test_host_serialization(self, sample_host):
        """Test host serialization includes shows field"""
        host_dict = sample_host.to_dict()
        
        assert "shows" in host_dict
        assert host_dict["shows"] == ["tech-talk", "ai-insights"]
        
        # Test round-trip
        restored_host = Host.from_dict(host_dict)
        assert restored_host.shows == sample_host.shows
        assert restored_host.affiliation == sample_host.affiliation


# ========================================
# Series Model Tests
# ========================================

class TestSeriesModel:
    """Test Series data model"""
    
    def test_series_creation(self, sample_series):
        """Test series creation with all fields"""
        assert sample_series.series_id == "tech-talk"
        assert sample_series.title == "Tech Talk Weekly"
        assert sample_series.primary_host.name == "Dr. Jane Smith"
        assert "Technology" in sample_series.topics
    
    def test_series_serialization(self, sample_series):
        """Test series serialization includes nested host"""
        series_dict = sample_series.to_dict()
        
        assert "primary_host" in series_dict
        assert series_dict["primary_host"]["name"] == "Dr. Jane Smith"
        assert series_dict["topics"] == ["Technology", "AI", "Innovation", "Software"]
        
        # Test round-trip
        restored_series = Series.from_dict(series_dict)
        assert restored_series.series_id == sample_series.series_id
        assert restored_series.primary_host.name == sample_series.primary_host.name


# ========================================
# Episode Model Tests
# ========================================

class TestEpisodeModel:
    """Test Episode data model"""
    
    def test_episode_creation(self, sample_episode):
        """Test episode creation with all fields"""
        assert sample_episode.episode_id == "tech-talk-2024-001"
        assert sample_episode.title == "The Future of Artificial Intelligence"
        assert sample_episode.duration == timedelta(hours=1, minutes=30, seconds=45)
        assert len(sample_episode.hosts) == 1
        assert len(sample_episode.guests) == 1
        assert len(sample_episode.tags) == 4
    
    def test_episode_serialization(self, sample_episode):
        """Test episode serialization with complex nested objects"""
        episode_dict = sample_episode.to_dict()
        
        # Check basic fields
        assert episode_dict["episode_id"] == "tech-talk-2024-001"
        assert episode_dict["title"] == "The Future of Artificial Intelligence"
        
        # Check datetime serialization
        assert episode_dict["upload_date"] == "2024-01-15T10:00:00"
        
        # Check nested objects
        assert "series" in episode_dict
        assert episode_dict["series"]["title"] == "Tech Talk Weekly"
        assert len(episode_dict["hosts"]) == 1
        assert len(episode_dict["guests"]) == 1
        
        # Check social links
        assert episode_dict["social_links"]["youtube"] == "https://youtube.com/watch?v=abc123"
    
    def test_episode_from_dict_duration_parsing(self):
        """Test episode creation from dict with different duration formats"""
        episode_data = {
            "episode_id": "test-001",
            "title": "Test Episode",
            "description": "Test description",
            "upload_date": "2024-01-15T10:00:00",
            "duration": "PT1H30M45S",  # ISO 8601 format
            "series": {
                "series_id": "test-series",
                "title": "Test Series",
                "description": "Test series description",
                "slug": "test-series",
                "primary_host": {
                    "person_id": "host-001",
                    "name": "Test Host",
                    "slug": "test-host"
                }
            },
            "hosts": [{
                "person_id": "host-001",
                "name": "Test Host",
                "slug": "test-host"
            }]
        }
        
        episode = Episode.from_dict(episode_data)
        assert episode.duration == timedelta(hours=1, minutes=30, seconds=45)


# ========================================
# Rights Metadata Tests
# ========================================

class TestRightsMetadata:
    """Test RightsMetadata model"""
    
    def test_rights_creation(self, sample_rights_metadata):
        """Test rights metadata creation"""
        assert sample_rights_metadata.music_clearance is True
        assert len(sample_rights_metadata.third_party_assets) == 2
        assert sample_rights_metadata.copyright_holder == "Example Media Corp"
    
    def test_rights_serialization(self, sample_rights_metadata):
        """Test rights metadata serialization"""
        rights_dict = sample_rights_metadata.to_dict()
        
        assert rights_dict["music_clearance"] is True
        assert "intro-music.mp3" in rights_dict["third_party_assets"]
        
        # Test round-trip
        restored_rights = RightsMetadata.from_dict(rights_dict)
        assert restored_rights.music_clearance == sample_rights_metadata.music_clearance
        assert restored_rights.third_party_assets == sample_rights_metadata.third_party_assets


# ========================================
# Publishing Manifest Tests
# ========================================

class TestPublishManifest:
    """Test PublishManifest model"""
    
    def test_manifest_creation(self, sample_publish_manifest):
        """Test publish manifest creation"""
        assert sample_publish_manifest.manifest_version == "1.0"
        assert sample_publish_manifest.build_id.startswith("build_")
        assert len(sample_publish_manifest.episodes) == 1
        assert len(sample_publish_manifest.series) == 1
        assert len(sample_publish_manifest.hosts) == 1
    
    def test_manifest_serialization(self, sample_publish_manifest):
        """Test manifest serialization with nested objects"""
        manifest_dict = sample_publish_manifest.to_dict()
        
        assert manifest_dict["manifest_version"] == "1.0"
        assert "episodes" in manifest_dict
        assert "series" in manifest_dict
        assert "hosts" in manifest_dict
        assert "paths" in manifest_dict
        assert "social" in manifest_dict
        
        # Test round-trip
        restored_manifest = PublishManifest.from_dict(manifest_dict)
        assert restored_manifest.manifest_version == sample_publish_manifest.manifest_version
        assert restored_manifest.build_id == sample_publish_manifest.build_id
    
    def test_manifest_auto_created_at(self):
        """Test that created_at is automatically set if not provided"""
        manifest = PublishManifest(
            manifest_version="1.0",
            build_id="test-build",
            episodes=[],
            series=[],
            hosts=[],
            paths=PathMapping("public", "meta", "transcripts")
        )
        
        assert manifest.created_at is not None
        assert isinstance(manifest.created_at, datetime)


# ========================================
# Social Media Models Tests
# ========================================

class TestSocialMediaModels:
    """Test social media related models"""
    
    def test_format_specs(self, sample_format_specs):
        """Test format specifications model"""
        assert sample_format_specs.resolution == "1920x1080"
        assert sample_format_specs.codec == "h264"
        assert sample_format_specs.frame_rate == 30.0
        
        # Test serialization
        specs_dict = sample_format_specs.to_dict()
        restored_specs = FormatSpecs.from_dict(specs_dict)
        assert restored_specs.resolution == sample_format_specs.resolution
    
    def test_media_asset(self, sample_media_asset):
        """Test media asset model"""
        assert sample_media_asset.asset_type == AssetType.VIDEO
        assert sample_media_asset.duration == timedelta(minutes=5, seconds=30)
        assert sample_media_asset.file_size == 52428800
        
        # Test serialization
        asset_dict = sample_media_asset.to_dict()
        assert asset_dict["asset_type"] == "video"
        
        restored_asset = MediaAsset.from_dict(asset_dict)
        assert restored_asset.asset_type == sample_media_asset.asset_type
        assert restored_asset.duration == sample_media_asset.duration
    
    def test_upload_manifest(self, sample_upload_manifest):
        """Test upload manifest model"""
        assert sample_upload_manifest.privacy == PrivacyLevel.PUBLIC
        assert sample_upload_manifest.age_restriction is False
        assert len(sample_upload_manifest.tags) == 4
        
        # Test serialization
        upload_dict = sample_upload_manifest.to_dict()
        assert upload_dict["privacy"] == "public"
        
        restored_upload = UploadManifest.from_dict(upload_dict)
        assert restored_upload.privacy == sample_upload_manifest.privacy
    
    def test_social_package(self, sample_social_package):
        """Test social package model"""
        assert sample_social_package.platform == "youtube"
        assert sample_social_package.status == PackageStatus.VALID
        assert len(sample_social_package.media_assets) == 1
        
        # Test auto-created timestamp
        assert sample_social_package.created_at is not None
        
        # Test serialization
        package_dict = sample_social_package.to_dict()
        assert package_dict["status"] == "valid"
        
        restored_package = SocialPackage.from_dict(package_dict)
        assert restored_package.platform == sample_social_package.platform
        assert restored_package.status == sample_social_package.status


# ========================================
# Validation Models Tests
# ========================================

class TestValidationModels:
    """Test validation result models"""
    
    def test_validation_error(self):
        """Test validation error model"""
        error = ValidationError(
            error_type=ErrorType.SCHEMA_VALIDATION,
            message="Required field missing",
            location="root.title",
            severity=Severity.ERROR
        )
        
        assert error.error_type == ErrorType.SCHEMA_VALIDATION
        assert error.severity == Severity.ERROR
        
        # Test serialization
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "schema_validation"
        
        restored_error = ValidationError.from_dict(error_dict)
        assert restored_error.error_type == error.error_type
    
    def test_validation_result(self):
        """Test validation result model"""
        errors = [ValidationError(
            error_type=ErrorType.SCHEMA_VALIDATION,
            message="Test error",
            location="test.field",
            severity=Severity.ERROR
        )]
        
        warnings = [ValidationWarning(
            message="Test warning",
            location="test.field"
        )]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            metadata={"test": "data"}
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        
        # Test serialization
        result_dict = result.to_dict()
        restored_result = ValidationResult.from_dict(result_dict)
        assert restored_result.is_valid == result.is_valid
        assert len(restored_result.errors) == len(result.errors)


# ========================================
# Utility Functions Tests
# ========================================

class TestUtilityFunctions:
    """Test utility functions for model creation"""
    
    def test_create_episode_from_metadata(self):
        """Test episode creation from metadata dictionaries"""
        episode_data = {
            "episode_id": "test-001",
            "title": "Test Episode",
            "description": "Test description",
            "upload_date": "2024-01-15T10:00:00",
            "duration_seconds": 3600,
            "tags": ["test", "episode"],
            "social_links": {"youtube": "https://youtube.com/test"}
        }
        
        series_data = {
            "series_id": "test-series",
            "title": "Test Series",
            "description": "Test series description",
            "slug": "test-series"
        }
        
        hosts_data = [{
            "person_id": "host-001",
            "name": "Test Host",
            "slug": "test-host"
        }]
        
        episode = create_episode_from_metadata(episode_data, series_data, hosts_data)
        
        assert episode.episode_id == "test-001"
        assert episode.title == "Test Episode"
        assert episode.duration == timedelta(seconds=3600)
        assert episode.series.title == "Test Series"
        assert len(episode.hosts) == 1
        assert episode.social_links["youtube"] == "https://youtube.com/test"
    
    def test_generate_build_id(self):
        """Test build ID generation"""
        build_id = generate_build_id()
        
        assert build_id.startswith("build_")
        assert len(build_id) > 20  # Should include timestamp and hash
        
        # Generate another to ensure uniqueness
        build_id2 = generate_build_id()
        assert build_id != build_id2


# ========================================
# Edge Cases and Error Handling Tests
# ========================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_episode_with_minimal_data(self):
        """Test episode creation with minimal required data"""
        host = Host(person_id="host-001", name="Test Host", slug="test-host")
        series = Series(
            series_id="test-series",
            title="Test Series", 
            description="Test description",
            slug="test-series",
            primary_host=host
        )
        
        episode = Episode(
            episode_id="test-001",
            title="Test Episode",
            description="Test description",
            upload_date=datetime.now(),
            duration=timedelta(minutes=30),
            series=series,
            hosts=[host]
        )
        
        assert episode.guests == []
        assert episode.tags == []
        assert episode.social_links == {}
        assert episode.rights is None
    
    def test_empty_social_manifest(self):
        """Test social manifest with empty data"""
        social_manifest = SocialManifest()
        
        assert social_manifest.platforms == {}
        assert social_manifest.ready_flags == {}
        assert social_manifest.queue_path is None
        
        # Test serialization of empty manifest
        manifest_dict = social_manifest.to_dict()
        restored_manifest = SocialManifest.from_dict(manifest_dict)
        assert restored_manifest.platforms == {}
    
    def test_media_asset_duration_parsing(self):
        """Test media asset duration parsing from different formats"""
        asset_data = {
            "asset_path": "test.mp4",
            "asset_type": "video",
            "format_specs": {
                "resolution": "1920x1080",
                "codec": "h264"
            },
            "duration": "0:05:30"  # MM:SS format
        }
        
        asset = MediaAsset.from_dict(asset_data)
        assert asset.duration == timedelta(minutes=5, seconds=30)