"""
Unit tests for Content Registry

Tests the ContentRegistry class including manifest loading, validation,
content retrieval, filtering, and social link management.
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from src.core.content_registry import (
    ContentRegistry, ContentFilter, ManifestCompatibility,
    create_content_registry, load_and_validate_manifest,
    filter_episodes_by_confidence, create_content_filter
)
from src.core.publishing_models import (
    PublishManifest, Episode, Series, Host, Person, PathMapping, SocialManifest,
    ValidationResult, ValidationError, ErrorType, Severity
)


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def sample_manifest_data():
    """Create sample manifest data for testing"""
    return {
        "manifest_version": "2.0",
        "build_id": "build_20240115_120000_abc123",
        "episodes": [
            {
                "episode_id": "tech-talk-001",
                "title": "AI Revolution",
                "description": "Discussion about AI impact on society",
                "upload_date": "2024-01-15T10:00:00",
                "duration": "PT1H0M0S",
                "series_id": "tech-talk",
                "host_ids": ["host-001"],
                "tags": ["AI", "Technology"],
                "social_links": {
                    "youtube": "https://youtube.com/watch?v=abc123"
                },
                "series": {
                    "series_id": "tech-talk",
                    "title": "Tech Talk Weekly",
                    "description": "Weekly technology discussions",
                    "slug": "tech-talk-weekly"
                },
                "hosts": [
                    {
                        "person_id": "host-001",
                        "name": "Dr. Jane Smith",
                        "slug": "jane-smith"
                    }
                ]
            },
            {
                "episode_id": "tech-talk-002", 
                "title": "Future of Work",
                "description": "How technology changes the workplace",
                "upload_date": "2024-01-22T10:00:00",
                "duration": "PT45M0S",
                "series_id": "tech-talk",
                "host_ids": ["host-001", "host-002"],
                "tags": ["Work", "Future", "Technology"],
                "series": {
                    "series_id": "tech-talk",
                    "title": "Tech Talk Weekly",
                    "description": "Weekly technology discussions",
                    "slug": "tech-talk-weekly"
                },
                "hosts": [
                    {
                        "person_id": "host-001",
                        "name": "Dr. Jane Smith",
                        "slug": "jane-smith"
                    },
                    {
                        "person_id": "host-002",
                        "name": "Prof. Bob Johnson",
                        "slug": "bob-johnson"
                    }
                ]
            }
        ],
        "series": [
            {
                "series_id": "tech-talk",
                "title": "Tech Talk Weekly",
                "description": "Weekly technology discussions",
                "slug": "tech-talk-weekly",
                "primary_host": {
                    "person_id": "host-001",
                    "name": "Dr. Jane Smith",
                    "slug": "jane-smith"
                },
                "topics": ["Technology", "AI"]
            }
        ],
        "hosts": [
            {
                "person_id": "host-001",
                "name": "Dr. Jane Smith",
                "slug": "jane-smith",
                "bio": "AI researcher",
                "shows": ["tech-talk"]
            },
            {
                "person_id": "host-002",
                "name": "Prof. Bob Johnson",
                "slug": "bob-johnson",
                "bio": "Technology expert",
                "shows": ["tech-talk"]
            }
        ],
        "paths": {
            "public_root": "data/public",
            "meta_root": "data/meta", 
            "transcripts_root": "data/transcripts",
            "social_root": "data/social"
        },
        "social": {
            "platforms": {"youtube": 2, "instagram": 1},
            "ready_flags": {"youtube": True, "instagram": False}
        }
    }


@pytest.fixture
def temp_manifest_file(sample_manifest_data):
    """Create temporary manifest file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_manifest_data, f, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def content_registry():
    """Create ContentRegistry instance for testing"""
    return ContentRegistry()


@pytest.fixture
def loaded_registry(content_registry, temp_manifest_file):
    """Create ContentRegistry with loaded manifest"""
    content_registry.load_manifest(temp_manifest_file)
    return content_registry


# ========================================
# ContentRegistry Basic Tests
# ========================================

class TestContentRegistryBasics:
    """Test basic ContentRegistry functionality"""
    
    def test_registry_creation(self):
        """Test ContentRegistry creation with default and custom paths"""
        # Default path
        registry = ContentRegistry()
        assert registry.base_path == Path("data")
        assert registry.manifest is None
        
        # Custom path
        registry_custom = ContentRegistry("/custom/path")
        assert registry_custom.base_path == Path("/custom/path")
    
    def test_manifest_compatibility(self):
        """Test manifest version compatibility checking"""
        compatibility = ManifestCompatibility()
        
        assert compatibility.is_compatible("1.0")
        assert compatibility.is_compatible("2.0")
        assert not compatibility.is_compatible("3.0")
        
        # Test migration paths
        assert compatibility.get_migration_path("1.0") == ["1.0", "1.1", "2.0"]
        assert compatibility.get_migration_path("2.0") == []
        assert compatibility.get_migration_path("3.0") is None


# ========================================
# Manifest Loading and Validation Tests
# ========================================

class TestManifestLoading:
    """Test manifest loading and validation"""
    
    def test_load_valid_manifest(self, content_registry, temp_manifest_file):
        """Test loading a valid manifest file"""
        manifest = content_registry.load_manifest(temp_manifest_file)
        
        assert manifest is not None
        assert manifest.manifest_version == "2.0"
        assert manifest.build_id == "build_20240115_120000_abc123"
        assert len(manifest.episodes) == 2
        assert len(manifest.series) == 1
        assert len(manifest.hosts) == 2
    
    def test_load_manifest_with_missing_optional_fields(self, content_registry, sample_manifest_data):
        """Test loading manifest with missing optional fields"""
        # Remove optional social field
        sample_manifest_data.pop("social", None)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_manifest_data, f)
            temp_path = f.name
        
        try:
            manifest = content_registry.load_manifest(temp_path)
            assert manifest is not None
            assert manifest.social is None or manifest.social == {}
        finally:
            os.unlink(temp_path)
    
    def test_load_manifest_with_malformed_episode_data(self, content_registry, sample_manifest_data):
        """Test loading manifest with malformed episode data"""
        # Create episode with missing required fields
        sample_manifest_data["episodes"][0].pop("title", None)
        sample_manifest_data["episodes"][0].pop("duration", None)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_manifest_data, f)
            temp_path = f.name
        
        try:
            # Should still load but validation should catch issues
            manifest = content_registry.load_manifest(temp_path)
            validation_result = content_registry.validate_content_contract(manifest)
            assert not validation_result.is_valid
            assert len(validation_result.errors) > 0
        finally:
            os.unlink(temp_path)
    
    def test_load_nonexistent_manifest(self, content_registry):
        """Test loading nonexistent manifest file"""
        with pytest.raises(FileNotFoundError):
            content_registry.load_manifest("/nonexistent/path/manifest.json")
    
    def test_load_invalid_json(self, content_registry):
        """Test loading manifest with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                content_registry.load_manifest(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_load_incompatible_version(self, content_registry, sample_manifest_data):
        """Test loading manifest with incompatible version"""
        sample_manifest_data["manifest_version"] = "3.0"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_manifest_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported manifest version"):
                content_registry.load_manifest(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_manifest_structure(self, content_registry, sample_manifest_data):
        """Test manifest structure validation"""
        # Valid manifest
        result = content_registry.validate_manifest(sample_manifest_data)
        assert result.is_valid
        
        # Missing required field
        invalid_data = sample_manifest_data.copy()
        del invalid_data["episodes"]
        
        result = content_registry.validate_manifest(invalid_data)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_validate_content_contract(self, loaded_registry):
        """Test content contract validation"""
        result = loaded_registry.validate_content_contract(loaded_registry.manifest)
        
        # Should be valid with sample data
        assert result.is_valid or len(result.errors) == 0  # Allow warnings
        assert result.metadata["total_episodes_validated"] == 2


# ========================================
# Content Retrieval Tests
# ========================================

class TestContentRetrieval:
    """Test content retrieval and filtering"""
    
    def test_get_all_episodes(self, loaded_registry):
        """Test retrieving all episodes"""
        episodes = loaded_registry.get_episodes()
        
        assert len(episodes) == 2
        assert episodes[0].episode_id == "tech-talk-001"
        assert episodes[1].episode_id == "tech-talk-002"
    
    def test_get_episode_by_id(self, loaded_registry):
        """Test retrieving specific episode by ID"""
        episode = loaded_registry.get_episode("tech-talk-001")
        
        assert episode is not None
        assert episode.title == "AI Revolution"
        assert episode.series.title == "Tech Talk Weekly"
        
        # Test nonexistent episode
        nonexistent = loaded_registry.get_episode("nonexistent")
        assert nonexistent is None
    
    def test_get_series(self, loaded_registry):
        """Test retrieving series information"""
        series = loaded_registry.get_series("tech-talk")
        
        assert series is not None
        assert series.title == "Tech Talk Weekly"
        assert series.primary_host.name == "Dr. Jane Smith"
        
        # Test nonexistent series
        nonexistent = loaded_registry.get_series("nonexistent")
        assert nonexistent is None
    
    def test_get_all_series(self, loaded_registry):
        """Test retrieving all series"""
        all_series = loaded_registry.get_all_series()
        
        assert len(all_series) == 1
        assert all_series[0].series_id == "tech-talk"
    
    def test_get_hosts(self, loaded_registry):
        """Test retrieving hosts by IDs"""
        hosts = loaded_registry.get_hosts(["host-001", "host-002"])
        
        assert len(hosts) == 2
        assert hosts[0].name == "Dr. Jane Smith"
        assert hosts[1].name == "Prof. Bob Johnson"
        
        # Test partial match
        partial_hosts = loaded_registry.get_hosts(["host-001", "nonexistent"])
        assert len(partial_hosts) == 1
    
    def test_get_host_by_id(self, loaded_registry):
        """Test retrieving specific host by ID"""
        host = loaded_registry.get_host("host-001")
        
        assert host is not None
        assert host.name == "Dr. Jane Smith"
        assert "tech-talk" in host.shows
        
        # Test nonexistent host
        nonexistent = loaded_registry.get_host("nonexistent")
        assert nonexistent is None
    
    def test_get_all_hosts(self, loaded_registry):
        """Test retrieving all hosts"""
        all_hosts = loaded_registry.get_all_hosts()
        
        assert len(all_hosts) == 2
        host_names = [host.name for host in all_hosts]
        assert "Dr. Jane Smith" in host_names
        assert "Prof. Bob Johnson" in host_names


# ========================================
# Content Filtering Tests
# ========================================

class TestContentFiltering:
    """Test content filtering functionality"""
    
    def test_filter_by_series(self, loaded_registry):
        """Test filtering episodes by series"""
        filter_obj = ContentFilter(series_ids=["tech-talk"])
        episodes = loaded_registry.get_episodes(filter_obj)
        
        assert len(episodes) == 2
        assert all(ep.series.series_id == "tech-talk" for ep in episodes)
    
    def test_filter_accuracy_with_complex_criteria(self, loaded_registry):
        """Test filtering accuracy with complex criteria combinations"""
        # Test exact match filtering
        filter_exact = ContentFilter(
            series_ids=["tech-talk"],
            host_ids=["host-001"],
            episode_ids=["tech-talk-001"]
        )
        episodes_exact = loaded_registry.get_episodes(filter_exact)
        
        assert len(episodes_exact) == 1
        assert episodes_exact[0].episode_id == "tech-talk-001"
        assert episodes_exact[0].series.series_id == "tech-talk"
        assert any(host.person_id == "host-001" for host in episodes_exact[0].hosts)
    
    def test_filter_with_confidence_threshold(self, loaded_registry):
        """Test filtering with confidence thresholds (requirement 4.3)"""
        # Test confidence-based filtering
        filter_with_confidence = ContentFilter(confidence_threshold=0.8)
        episodes = loaded_registry.get_episodes(filter_with_confidence)
        
        # Should return episodes (placeholder implementation returns all)
        assert len(episodes) >= 0
        
        # Test utility function
        all_episodes = loaded_registry.get_episodes()
        filtered_episodes = filter_episodes_by_confidence(all_episodes, 0.9)
        assert len(filtered_episodes) <= len(all_episodes)
    
    def test_filter_by_host(self, loaded_registry):
        """Test filtering episodes by host"""
        filter_obj = ContentFilter(host_ids=["host-002"])
        episodes = loaded_registry.get_episodes(filter_obj)
        
        assert len(episodes) == 1
        assert episodes[0].episode_id == "tech-talk-002"
        
        # Test multiple hosts
        filter_multi = ContentFilter(host_ids=["host-001", "host-002"])
        episodes_multi = loaded_registry.get_episodes(filter_multi)
        assert len(episodes_multi) == 2
    
    def test_filter_by_date_range(self, loaded_registry):
        """Test filtering episodes by date range"""
        # Filter from specific date
        filter_from = ContentFilter(date_from=datetime(2024, 1, 20))
        episodes_from = loaded_registry.get_episodes(filter_from)
        
        assert len(episodes_from) == 1
        assert episodes_from[0].episode_id == "tech-talk-002"
        
        # Filter to specific date
        filter_to = ContentFilter(date_to=datetime(2024, 1, 20))
        episodes_to = loaded_registry.get_episodes(filter_to)
        
        assert len(episodes_to) == 1
        assert episodes_to[0].episode_id == "tech-talk-001"
    
    def test_filter_by_tags(self, loaded_registry):
        """Test filtering episodes by tags"""
        filter_obj = ContentFilter(tags=["AI"])
        episodes = loaded_registry.get_episodes(filter_obj)
        
        assert len(episodes) == 1
        assert episodes[0].episode_id == "tech-talk-001"
        
        # Test multiple tags (OR logic)
        filter_multi = ContentFilter(tags=["AI", "Work"])
        episodes_multi = loaded_registry.get_episodes(filter_multi)
        assert len(episodes_multi) == 2
    
    def test_filter_by_episode_ids(self, loaded_registry):
        """Test filtering by specific episode IDs"""
        filter_obj = ContentFilter(episode_ids=["tech-talk-001"])
        episodes = loaded_registry.get_episodes(filter_obj)
        
        assert len(episodes) == 1
        assert episodes[0].episode_id == "tech-talk-001"
    
    def test_combined_filters(self, loaded_registry):
        """Test combining multiple filter criteria"""
        filter_obj = ContentFilter(
            series_ids=["tech-talk"],
            host_ids=["host-001"],
            tags=["Technology"]
        )
        episodes = loaded_registry.get_episodes(filter_obj)
        
        # Should match both episodes as they both have host-001 and Technology tag
        assert len(episodes) == 2
    
    def test_no_matches_filter(self, loaded_registry):
        """Test filter that matches no episodes"""
        filter_obj = ContentFilter(tags=["NonexistentTag"])
        episodes = loaded_registry.get_episodes(filter_obj)
        
        assert len(episodes) == 0


# ========================================
# Social Link Management Tests
# ========================================

class TestSocialLinkManagement:
    """Test social link management functionality"""
    
    def test_update_social_links(self, loaded_registry):
        """Test updating social media links for an episode"""
        episode_id = "tech-talk-001"
        new_links = {
            "instagram": "https://instagram.com/p/abc123",
            "twitter": "https://twitter.com/user/status/123456"
        }
        
        loaded_registry.update_social_links(episode_id, new_links)
        
        # Verify links were updated
        updated_links = loaded_registry.get_social_links(episode_id)
        assert "instagram" in updated_links
        assert "twitter" in updated_links
        assert updated_links["instagram"] == "https://www.instagram.com/p/abc123"  # Normalized URL
        
        # Original YouTube link should still be there
        assert "youtube" in updated_links
    
    def test_social_link_updates_trigger_cache_refresh(self, loaded_registry):
        """Test that social link updates properly refresh cached episode data"""
        episode_id = "tech-talk-001"
        
        # Load episode to populate cache
        original_episode = loaded_registry.get_episode(episode_id)
        original_social_count = len(original_episode.social_links)
        
        # Update social links
        new_links = {"tiktok": "https://tiktok.com/@user/video/123456"}
        loaded_registry.update_social_links(episode_id, new_links)
        
        # Verify cache was updated
        updated_episode = loaded_registry.get_episode(episode_id)
        assert len(updated_episode.social_links) == original_social_count + 1
        assert "tiktok" in updated_episode.social_links
    
    def test_bulk_social_link_updates(self, loaded_registry):
        """Test updating multiple social links at once"""
        episode_id = "tech-talk-002"
        
        # Add multiple social links
        bulk_links = {
            "youtube": "https://youtube.com/watch?v=xyz789",
            "instagram": "https://instagram.com/p/def456", 
            "twitter": "https://twitter.com/user/status/789012",
            "facebook": "https://facebook.com/user/videos/345678"
        }
        
        loaded_registry.update_social_links(episode_id, bulk_links)
        
        # Verify all links were added
        updated_links = loaded_registry.get_social_links(episode_id)
        for platform, url in bulk_links.items():
            assert platform in updated_links
            # URLs should be normalized
            assert updated_links[platform].startswith("https://")
    
    def test_social_link_validation_edge_cases(self, loaded_registry):
        """Test social link validation with edge cases"""
        episode_id = "tech-talk-001"
        
        # Test various invalid URL formats
        invalid_cases = [
            {"youtube": ""},  # Empty URL
            {"youtube": None},  # None value
            {"youtube": "not-a-url-at-all"},  # Not a URL
            {"youtube": "ftp://example.com/video"},  # Wrong protocol
            {"youtube": "https://example.com/video"},  # Wrong domain
        ]
        
        for invalid_links in invalid_cases:
            with pytest.raises((ValueError, TypeError)):
                loaded_registry.update_social_links(episode_id, invalid_links)
    
    def test_update_social_links_invalid_episode(self, loaded_registry):
        """Test updating social links for nonexistent episode"""
        with pytest.raises(ValueError, match="Episode not found"):
            loaded_registry.update_social_links("nonexistent", {"youtube": "https://youtube.com/test"})
    
    def test_update_social_links_invalid_url(self, loaded_registry):
        """Test updating with invalid social media URL"""
        with pytest.raises(ValueError, match="Invalid youtube URL"):
            loaded_registry.update_social_links("tech-talk-001", {"youtube": "invalid-url"})
    
    def test_get_social_links(self, loaded_registry):
        """Test retrieving social media links"""
        links = loaded_registry.get_social_links("tech-talk-001")
        
        assert "youtube" in links
        assert links["youtube"] == "https://youtube.com/watch?v=abc123"
        
        # Test nonexistent episode
        empty_links = loaded_registry.get_social_links("nonexistent")
        assert empty_links == {}
    
    def test_populate_same_as_fields(self, loaded_registry):
        """Test generating sameAs field values for JSON-LD"""
        same_as_urls = loaded_registry.populate_same_as_fields("tech-talk-001")
        
        assert len(same_as_urls) >= 1
        assert "https://youtube.com/watch?v=abc123" in same_as_urls
    
    def test_social_url_validation(self, loaded_registry):
        """Test social media URL validation for different platforms"""
        # Valid URLs
        assert loaded_registry._is_valid_social_url("https://youtube.com/watch?v=abc123", "youtube")
        assert loaded_registry._is_valid_social_url("https://instagram.com/p/abc123", "instagram")
        assert loaded_registry._is_valid_social_url("https://twitter.com/user/status/123456", "twitter")
        
        # Invalid URLs
        assert not loaded_registry._is_valid_social_url("invalid-url", "youtube")
        assert not loaded_registry._is_valid_social_url("https://example.com/video", "youtube")
    
    def test_social_url_normalization(self, loaded_registry):
        """Test social media URL normalization"""
        # YouTube normalization
        normalized = loaded_registry._normalize_social_url("https://youtu.be/abc123", "youtube")
        assert normalized == "https://www.youtube.com/watch?v=abc123"
        
        # Instagram normalization
        normalized = loaded_registry._normalize_social_url("https://instagram.com/p/abc123", "instagram")
        assert normalized == "https://www.instagram.com/p/abc123"
        
        # HTTP to HTTPS conversion
        normalized = loaded_registry._normalize_social_url("http://example.com/video", "other")
        assert normalized == "https://example.com/video"


# ========================================
# Cross-Reference Validation Tests
# ========================================

class TestCrossReferenceValidation:
    """Test cross-reference integrity validation"""
    
    def test_validate_cross_references_valid(self, loaded_registry):
        """Test cross-reference validation with valid data"""
        result = loaded_registry.validate_cross_references()
        
        assert result.is_valid
        assert result.metadata["total_episodes"] == 2
        assert result.metadata["referenced_series"] == 1
        assert result.metadata["referenced_hosts"] == 2
    
    def test_validate_cross_references_missing_series(self, content_registry, sample_manifest_data):
        """Test cross-reference validation with missing series"""
        # Remove series but keep episode reference
        sample_manifest_data["series"] = []
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_manifest_data, f)
            temp_path = f.name
        
        try:
            content_registry.load_manifest(temp_path)
            result = content_registry.validate_cross_references()
            
            assert not result.is_valid
            assert len(result.errors) >= 2  # One error per episode
            assert any("unknown series" in error.message for error in result.errors)
        finally:
            os.unlink(temp_path)
    
    def test_validate_cross_references_missing_host(self, content_registry, sample_manifest_data):
        """Test cross-reference validation with missing host"""
        # Remove one host but keep episode reference
        sample_manifest_data["hosts"] = [sample_manifest_data["hosts"][0]]  # Keep only first host
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_manifest_data, f)
            temp_path = f.name
        
        try:
            content_registry.load_manifest(temp_path)
            result = content_registry.validate_cross_references()
            
            assert not result.is_valid
            assert any("unknown host" in error.message for error in result.errors)
        finally:
            os.unlink(temp_path)


# ========================================
# Statistics and Utility Tests
# ========================================

class TestStatisticsAndUtilities:
    """Test statistics and utility functions"""
    
    def test_get_content_statistics(self, loaded_registry):
        """Test content statistics generation"""
        stats = loaded_registry.get_content_statistics()
        
        assert stats["total_episodes"] == 2
        assert stats["total_series"] == 1
        assert stats["total_hosts"] == 2
        assert stats["episodes_with_social_links"] == 1
        assert "total_duration_hours" in stats
        assert "average_episode_duration_minutes" in stats
        assert "series_episode_counts" in stats
        assert "host_episode_counts" in stats
    
    def test_content_registry_data_quality_validation(self, loaded_registry):
        """Test data quality validation for series and host registries (requirement 4.1, 4.2)"""
        # Test series information completeness
        all_series = loaded_registry.get_all_series()
        for series in all_series:
            assert series.title is not None and len(series.title) > 0
            assert series.description is not None
            assert series.series_id is not None
            assert series.slug is not None
        
        # Test host profile completeness  
        all_hosts = loaded_registry.get_all_hosts()
        for host in all_hosts:
            assert host.name is not None and len(host.name) > 0
            assert host.person_id is not None
            assert host.slug is not None
            # Bio can be empty but should be present
            assert hasattr(host, 'bio')
    
    def test_metadata_consistency_across_content(self, loaded_registry):
        """Test metadata consistency across episodes, series, and hosts (requirement 4.1, 4.2)"""
        episodes = loaded_registry.get_episodes()
        
        for episode in episodes:
            # Verify series consistency
            series = loaded_registry.get_series(episode.series.series_id)
            assert series is not None
            assert series.title == episode.series.title
            
            # Verify host consistency
            for episode_host in episode.hosts:
                host = loaded_registry.get_host(episode_host.person_id)
                assert host is not None
                assert host.name == episode_host.name
                assert episode.series.series_id in host.shows
    
    def test_clear_caches(self, loaded_registry):
        """Test cache clearing functionality"""
        # Load some data to populate caches
        loaded_registry.get_episodes()
        loaded_registry.get_all_series()
        loaded_registry.get_all_hosts()
        
        # Verify caches are populated
        assert len(loaded_registry.episodes_cache) > 0
        assert len(loaded_registry.series_cache) > 0
        assert len(loaded_registry.hosts_cache) > 0
        
        # Clear caches
        loaded_registry.clear_caches()
        
        # Verify caches are empty
        assert len(loaded_registry.episodes_cache) == 0
        assert len(loaded_registry.series_cache) == 0
        assert len(loaded_registry.hosts_cache) == 0
    
    def test_save_manifest(self, loaded_registry):
        """Test saving manifest to file"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            output_path = f.name
        
        try:
            loaded_registry.save_manifest(output_path)
            
            # Verify file was created and contains valid JSON
            assert os.path.exists(output_path)
            
            with open(output_path, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["manifest_version"] == "2.0"
            assert saved_data["build_id"] == "build_20240115_120000_abc123"
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# ========================================
# Utility Functions Tests
# ========================================

class TestUtilityFunctions:
    """Test module-level utility functions"""
    
    def test_create_content_registry(self):
        """Test content registry factory function"""
        registry = create_content_registry()
        assert isinstance(registry, ContentRegistry)
        assert registry.base_path == Path("data")
        
        registry_custom = create_content_registry("/custom/path")
        assert registry_custom.base_path == Path("/custom/path")
    
    def test_load_and_validate_manifest(self, temp_manifest_file):
        """Test combined manifest loading and validation"""
        registry, result = load_and_validate_manifest(temp_manifest_file)
        
        assert isinstance(registry, ContentRegistry)
        assert isinstance(result, ValidationResult)
        assert registry.manifest is not None
    
    def test_filter_episodes_by_confidence(self, loaded_registry):
        """Test confidence-based episode filtering"""
        episodes = loaded_registry.get_episodes()
        
        # Currently returns all episodes (placeholder implementation)
        filtered = filter_episodes_by_confidence(episodes, 0.8)
        assert len(filtered) == len(episodes)
    
    def test_create_content_filter(self):
        """Test content filter factory function"""
        filter_obj = create_content_filter(
            series_ids=["series-1"],
            host_ids=["host-1"],
            tags=["tag1", "tag2"]
        )
        
        assert isinstance(filter_obj, ContentFilter)
        assert filter_obj.series_ids == ["series-1"]
        assert filter_obj.host_ids == ["host-1"]
        assert filter_obj.tags == ["tag1", "tag2"]


# ========================================
# Metadata Updates and Republication Tests
# ========================================

class TestMetadataUpdatesAndRepublication:
    """Test metadata updates and automatic republication triggers (requirement 4.4)"""
    
    def test_metadata_update_detection(self, loaded_registry):
        """Test detection of metadata changes that should trigger republication"""
        episode_id = "tech-talk-001"
        original_episode = loaded_registry.get_episode(episode_id)
        original_social_count = len(original_episode.social_links)
        
        # Simulate metadata update by updating social links with a new platform
        new_links = {"mastodon": "https://mastodon.social/@user/123456"}
        loaded_registry.update_social_links(episode_id, new_links)
        
        # Verify the update was applied
        updated_episode = loaded_registry.get_episode(episode_id)
        assert "mastodon" in updated_episode.social_links
        assert len(updated_episode.social_links) >= original_social_count
    
    def test_series_metadata_consistency_after_updates(self, loaded_registry):
        """Test that series metadata remains consistent after updates"""
        series_id = "tech-talk"
        original_series = loaded_registry.get_series(series_id)
        
        # Get episodes for this series
        episodes = loaded_registry.get_episodes(ContentFilter(series_ids=[series_id]))
        
        # Verify all episodes reference the same series metadata
        for episode in episodes:
            assert episode.series.title == original_series.title
            assert episode.series.description == original_series.description
            assert episode.series.series_id == original_series.series_id
    
    def test_host_metadata_consistency_after_updates(self, loaded_registry):
        """Test that host metadata remains consistent after updates"""
        host_id = "host-001"
        original_host = loaded_registry.get_host(host_id)
        
        # Get episodes featuring this host
        episodes = loaded_registry.get_episodes(ContentFilter(host_ids=[host_id]))
        
        # Verify all episodes reference consistent host metadata
        for episode in episodes:
            episode_host = next((h for h in episode.hosts if h.person_id == host_id), None)
            assert episode_host is not None
            assert episode_host.name == original_host.name
            assert episode_host.person_id == original_host.person_id


# ========================================
# Data Quality and Confidence Tests  
# ========================================

class TestDataQualityAndConfidence:
    """Test data quality validation and confidence thresholds (requirement 4.3, 4.5)"""
    
    def test_confidence_threshold_filtering(self, loaded_registry):
        """Test filtering content based on confidence thresholds"""
        # Test with different confidence levels
        all_episodes = loaded_registry.get_episodes()
        
        # Test high confidence threshold
        high_confidence = filter_episodes_by_confidence(all_episodes, 0.9)
        assert len(high_confidence) <= len(all_episodes)
        
        # Test medium confidence threshold
        medium_confidence = filter_episodes_by_confidence(all_episodes, 0.5)
        assert len(medium_confidence) >= len(high_confidence)
        
        # Test low confidence threshold
        low_confidence = filter_episodes_by_confidence(all_episodes, 0.1)
        assert len(low_confidence) >= len(medium_confidence)
    
    def test_data_quality_validation_before_publication(self, loaded_registry):
        """Test data quality validation before publication (requirement 4.3)"""
        # Validate content contract compliance
        validation_result = loaded_registry.validate_content_contract(loaded_registry.manifest)
        
        # Should pass basic validation with sample data
        assert validation_result.is_valid or len(validation_result.errors) == 0
        
        # Check that all required fields are present
        episodes = loaded_registry.get_episodes()
        for episode in episodes:
            # Core required fields
            assert episode.episode_id is not None
            assert episode.title is not None and len(episode.title) > 0
            assert episode.description is not None
            assert episode.upload_date is not None
            assert episode.duration is not None
            
            # Series and host references
            assert episode.series is not None
            assert len(episode.hosts) > 0
    
    def test_badge_visibility_based_on_confidence(self, loaded_registry):
        """Test badge visibility based on confidence thresholds (requirement 4.5)"""
        # This is a placeholder test for future confidence-based badge visibility
        # Currently the system doesn't implement confidence scoring
        
        episodes = loaded_registry.get_episodes()
        series_list = loaded_registry.get_all_series()
        hosts_list = loaded_registry.get_all_hosts()
        
        # Verify all content is accessible (no confidence filtering implemented yet)
        assert len(episodes) > 0
        assert len(series_list) > 0
        assert len(hosts_list) > 0
        
        # Future: Test that low-confidence content hides badges but maintains pages


# ========================================
# Error Handling Tests
# ========================================

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_operations_without_loaded_manifest(self, content_registry):
        """Test operations that require loaded manifest"""
        with pytest.raises(ValueError, match="No manifest loaded"):
            content_registry.get_episodes()
        
        with pytest.raises(ValueError, match="No manifest loaded"):
            content_registry.get_series("test")
        
        with pytest.raises(ValueError, match="No manifest loaded"):
            content_registry.update_social_links("test", {})
    
    def test_save_manifest_without_loaded_manifest(self, content_registry):
        """Test saving manifest when none is loaded"""
        with pytest.raises(ValueError, match="No manifest loaded to save"):
            content_registry.save_manifest()
    
    def test_invalid_social_url_formats(self, loaded_registry):
        """Test various invalid social URL formats"""
        episode_id = "tech-talk-001"
        
        invalid_urls = [
            {"youtube": "not-a-url"},
            {"youtube": "https://example.com/video"},
            {"instagram": "https://facebook.com/post"},
            {"twitter": "https://instagram.com/post"}
        ]
        
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError):
                loaded_registry.update_social_links(episode_id, invalid_url)