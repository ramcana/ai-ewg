"""
Unit tests for Feed Generator

Tests RSS feed generation, XML sitemap creation, feed validation,
and caching mechanisms for the Content Publishing Platform.
"""

import pytest
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.feed_generator import (
    FeedGenerator, RSSFeed, XMLSitemap, FeedCache,
    create_feed_generator, validate_feed_xml
)
from src.core.publishing_models import (
    Episode, Series, Host, ValidationResult, ErrorType, Severity
)
from src.core.content_registry import ContentRegistry


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
        bio="AI researcher and technology expert",
        headshot_url="https://example.com/images/jane-smith.jpg",
        same_as_links=["https://en.wikipedia.org/wiki/Jane_Smith"],
        affiliation="Example University",
        shows=["tech-talk"]
    )


@pytest.fixture
def sample_series(sample_host):
    """Create a sample series for testing"""
    return Series(
        series_id="tech-talk",
        title="Tech Talk Weekly",
        description="Weekly discussions on technology trends",
        slug="tech-talk-weekly",
        primary_host=sample_host,
        artwork_url="https://example.com/images/tech-talk-artwork.jpg",
        topics=["Technology", "AI", "Innovation"],
        live_series_url="https://example.com/series/tech-talk"
    )


@pytest.fixture
def sample_episodes(sample_series, sample_host):
    """Create sample episodes for testing"""
    episodes = []
    
    for i in range(3):
        episode = Episode(
            episode_id=f"tech-talk-2024-{i+1:03d}",
            title=f"Episode {i+1}: AI Technology Trends",
            description=f"Discussion about AI trends in episode {i+1}",
            upload_date=datetime(2024, 1, 15 + i, 10, 0, 0),
            duration=timedelta(hours=1, minutes=30),
            series=sample_series,
            hosts=[sample_host],
            transcript_path=f"data/transcripts/tech-talk-2024-{i+1:03d}.vtt",
            thumbnail_url=f"https://example.com/images/tech-talk-2024-{i+1:03d}-thumb.jpg",
            content_url=f"https://example.com/videos/tech-talk-2024-{i+1:03d}.mp4",
            tags=["AI", "Technology", f"Episode{i+1}"],
            social_links={
                "youtube": f"https://youtube.com/watch?v=abc{i+1}23",
                "instagram": f"https://instagram.com/p/def{i+1}56"
            },
            episode_number=i+1,
            season_number=2024
        )
        episodes.append(episode)
    
    return episodes


@pytest.fixture
def mock_content_registry(sample_episodes, sample_series, sample_host):
    """Create a mock content registry for testing"""
    registry = Mock(spec=ContentRegistry)
    registry.get_episodes.return_value = sample_episodes
    registry.get_all_series.return_value = [sample_series]
    registry.get_all_hosts.return_value = [sample_host]
    return registry


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def feed_generator(mock_content_registry, temp_cache_dir):
    """Create a FeedGenerator instance for testing"""
    return FeedGenerator(
        content_registry=mock_content_registry,
        base_url="https://example.com",
        site_name="Test Site",
        site_description="Test site description",
        cache_dir=str(temp_cache_dir)
    )


# ========================================
# RSS Feed Tests
# ========================================

class TestRSSFeed:
    """Test RSSFeed data structure and XML generation"""
    
    def test_rss_feed_creation(self):
        """Test basic RSS feed creation"""
        rss_feed = RSSFeed(
            title="Test Feed",
            description="Test feed description",
            link="https://example.com"
        )
        
        assert rss_feed.title == "Test Feed"
        assert rss_feed.description == "Test feed description"
        assert rss_feed.link == "https://example.com"
        assert rss_feed.language == "en-US"
        assert rss_feed.items == []
    
    def test_rss_feed_xml_generation(self):
        """Test RSS feed XML generation"""
        rss_feed = RSSFeed(
            title="Test Feed",
            description="Test feed description",
            link="https://example.com",
            pub_date=datetime(2024, 1, 15, 12, 0, 0),
            last_build_date=datetime(2024, 1, 15, 12, 30, 0)
        )
        
        # Add a test item
        rss_feed.items.append({
            "title": "Test Episode",
            "description": "Test episode description",
            "link": "https://example.com/episodes/test",
            "guid": "https://example.com/episodes/test",
            "pub_date": datetime(2024, 1, 15, 10, 0, 0),
            "category": ["Technology", "AI"]
        })
        
        xml_content = rss_feed.to_xml()
        
        # Parse XML to verify structure
        root = ET.fromstring(xml_content)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"
        
        channel = root.find("channel")
        assert channel is not None
        
        # Check channel metadata
        assert channel.find("title").text == "Test Feed"
        assert channel.find("description").text == "Test feed description"
        assert channel.find("link").text == "https://example.com"
        
        # Check items
        items = channel.findall("item")
        assert len(items) == 1
        
        item = items[0]
        assert item.find("title").text == "Test Episode"
        assert item.find("description").text == "Test episode description"
        
        # Check categories
        categories = item.findall("category")
        assert len(categories) == 2
        category_texts = [cat.text for cat in categories]
        assert "Technology" in category_texts
        assert "AI" in category_texts
    
    def test_rss_feed_with_media_content(self):
        """Test RSS feed with media enclosures"""
        rss_feed = RSSFeed(
            title="Video Feed",
            description="Video content feed",
            link="https://example.com"
        )
        
        # Add item with media content
        rss_feed.items.append({
            "title": "Video Episode",
            "description": "Video episode description",
            "link": "https://example.com/episodes/video",
            "guid": "https://example.com/episodes/video",
            "enclosure": {
                "url": "https://example.com/videos/episode.mp4",
                "type": "video/mp4",
                "length": 52428800
            },
            "media_content": {
                "url": "https://example.com/videos/episode.mp4",
                "type": "video/mp4",
                "duration": 3600
            },
            "media_thumbnail": "https://example.com/images/thumb.jpg"
        })
        
        xml_content = rss_feed.to_xml()
        root = ET.fromstring(xml_content)
        
        # Check enclosure
        item = root.find(".//item")
        enclosure = item.find("enclosure")
        assert enclosure is not None
        assert enclosure.get("url") == "https://example.com/videos/episode.mp4"
        assert enclosure.get("type") == "video/mp4"
        assert enclosure.get("length") == "52428800"
        
        # Check media namespace elements
        media_content = item.find("media:content", {"media": "http://search.yahoo.com/mrss/"})
        assert media_content is not None
        assert media_content.get("duration") == "3600"


# ========================================
# XML Sitemap Tests
# ========================================

class TestXMLSitemap:
    """Test XMLSitemap data structure and XML generation"""
    
    def test_sitemap_creation(self):
        """Test basic sitemap creation"""
        sitemap = XMLSitemap()
        assert sitemap.urls == []
    
    def test_sitemap_add_url(self):
        """Test adding URLs to sitemap"""
        sitemap = XMLSitemap()
        
        sitemap.add_url(
            loc="https://example.com/page1",
            lastmod=datetime(2024, 1, 15),
            changefreq="weekly",
            priority=0.8
        )
        
        assert len(sitemap.urls) == 1
        url_data = sitemap.urls[0]
        assert url_data["loc"] == "https://example.com/page1"
        assert url_data["lastmod"] == "2024-01-15"
        assert url_data["changefreq"] == "weekly"
        assert url_data["priority"] == "0.8"
    
    def test_sitemap_xml_generation(self):
        """Test sitemap XML generation"""
        sitemap = XMLSitemap()
        
        sitemap.add_url(
            loc="https://example.com/page1",
            lastmod=datetime(2024, 1, 15),
            changefreq="weekly",
            priority=0.8
        )
        
        sitemap.add_url(
            loc="https://example.com/page2",
            changefreq="monthly",
            priority=0.6
        )
        
        xml_content = sitemap.to_xml()
        root = ET.fromstring(xml_content)
        
        # Handle namespace in tag name
        assert root.tag.endswith("urlset")
        # Check namespace is in the XML content
        assert "xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\"" in xml_content
        
        # Define namespace for finding elements
        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sitemap:url", ns)
        assert len(urls) == 2
        
        # Check first URL
        url1 = urls[0]
        assert url1.find("sitemap:loc", ns).text == "https://example.com/page1"
        assert url1.find("sitemap:lastmod", ns).text == "2024-01-15"
        assert url1.find("sitemap:changefreq", ns).text == "weekly"
        assert url1.find("sitemap:priority", ns).text == "0.8"
        
        # Check second URL (no lastmod)
        url2 = urls[1]
        assert url2.find("sitemap:loc", ns).text == "https://example.com/page2"
        assert url2.find("sitemap:lastmod", ns) is None
    
    def test_video_sitemap_generation(self):
        """Test video sitemap with video metadata"""
        sitemap = XMLSitemap()
        
        video_data = {
            "thumbnail_loc": "https://example.com/thumb.jpg",
            "title": "Test Video",
            "description": "Test video description",
            "content_loc": "https://example.com/video.mp4",
            "duration": 3600,
            "publication_date": "2024-01-15T10:00:00",
            "tags": ["technology", "ai"]
        }
        
        sitemap.add_url(
            loc="https://example.com/video-page",
            video=video_data
        )
        
        xml_content = sitemap.to_xml()
        root = ET.fromstring(xml_content)
        
        # Check video namespace (it's in the XML but not in attrib due to namespace handling)
        assert "xmlns:video" in xml_content
        
        # Check video elements
        video_elem = root.find(".//video:video", {"video": "http://www.google.com/schemas/sitemap-video/1.1"})
        assert video_elem is not None
        
        # Check required video fields
        assert video_elem.find("video:thumbnail_loc", {"video": "http://www.google.com/schemas/sitemap-video/1.1"}).text == "https://example.com/thumb.jpg"
        assert video_elem.find("video:title", {"video": "http://www.google.com/schemas/sitemap-video/1.1"}).text == "Test Video"
        assert video_elem.find("video:description", {"video": "http://www.google.com/schemas/sitemap-video/1.1"}).text == "Test video description"


# ========================================
# Feed Cache Tests
# ========================================

class TestFeedCache:
    """Test feed caching mechanism"""
    
    def test_cache_creation(self, temp_cache_dir):
        """Test cache directory creation"""
        cache = FeedCache(temp_cache_dir)
        assert cache.cache_dir == temp_cache_dir
        assert cache.cache_dir.exists()
    
    def test_cache_key_generation(self, temp_cache_dir):
        """Test cache key generation"""
        cache = FeedCache(temp_cache_dir)
        
        key1 = cache.get_cache_key("rss", "site")
        key2 = cache.get_cache_key("rss", "series_123")
        key3 = cache.get_cache_key("sitemap")
        
        assert len(key1) == 32  # MD5 hash length
        assert key1 != key2
        assert key2 != key3
    
    def test_cache_operations(self, temp_cache_dir):
        """Test cache store and retrieve operations"""
        cache = FeedCache(temp_cache_dir)
        cache_key = "test_key"
        content = "<rss><channel><title>Test</title></channel></rss>"
        
        # Initially not cached
        assert not cache.is_cached(cache_key)
        assert cache.get_cached_feed(cache_key) is None
        
        # Cache content
        cache.cache_feed(cache_key, content)
        
        # Should now be cached
        assert cache.is_cached(cache_key)
        cached_content = cache.get_cached_feed(cache_key)
        assert cached_content == content
    
    def test_cache_expiration(self, temp_cache_dir):
        """Test cache TTL expiration"""
        # Create cache with very short TTL
        cache = FeedCache(temp_cache_dir, cache_ttl=timedelta(milliseconds=1))
        cache_key = "test_key"
        content = "<rss><channel><title>Test</title></channel></rss>"
        
        # Cache content
        cache.cache_feed(cache_key, content)
        assert cache.is_cached(cache_key)
        
        # Wait for expiration
        import time
        time.sleep(0.002)  # 2ms
        
        # Should be expired
        assert not cache.is_cached(cache_key)
    
    def test_cache_invalidation(self, temp_cache_dir):
        """Test cache invalidation"""
        cache = FeedCache(temp_cache_dir)
        
        # Cache multiple items
        cache.cache_feed("key1", "content1")
        cache.cache_feed("key2", "content2")
        
        assert cache.is_cached("key1")
        assert cache.is_cached("key2")
        
        # Invalidate specific key
        cache.invalidate_cache("key1")
        assert not cache.is_cached("key1")
        assert cache.is_cached("key2")
        
        # Invalidate all
        cache.invalidate_cache()
        assert not cache.is_cached("key2")


# ========================================
# Feed Generator Tests
# ========================================

class TestFeedGenerator:
    """Test FeedGenerator main functionality"""
    
    def test_feed_generator_creation(self, mock_content_registry, temp_cache_dir):
        """Test feed generator initialization"""
        generator = FeedGenerator(
            content_registry=mock_content_registry,
            base_url="https://example.com",
            site_name="Test Site",
            cache_dir=str(temp_cache_dir)
        )
        
        assert generator.base_url == "https://example.com"
        assert generator.site_name == "Test Site"
        assert generator.cache.cache_dir == temp_cache_dir
    
    def test_site_rss_generation(self, feed_generator, sample_episodes):
        """Test site-wide RSS feed generation"""
        # Mock the content registry to return our sample episodes
        feed_generator.content_registry.get_episodes.return_value = sample_episodes
        
        rss_feed = feed_generator.generate_site_rss()
        
        assert rss_feed.title == "Test Site"
        assert rss_feed.link == "https://example.com"
        assert len(rss_feed.items) == 3
        
        # Check first item
        first_item = rss_feed.items[0]
        assert "Episode 3" in first_item["title"]  # Should be newest first
        assert first_item["link"] == "https://example.com/episodes/tech-talk-2024-003"
        assert "category" in first_item
    
    def test_series_rss_generation(self, feed_generator, sample_episodes, sample_series):
        """Test per-series RSS feed generation"""
        # Mock content registry for series episodes
        from src.core.content_registry import ContentFilter
        
        def mock_get_episodes(filters=None):
            if filters and filters.series_ids:
                return [ep for ep in sample_episodes if ep.series.series_id in filters.series_ids]
            return sample_episodes
        
        feed_generator.content_registry.get_episodes.side_effect = mock_get_episodes
        
        rss_feed = feed_generator.generate_series_rss(sample_series)
        
        assert sample_series.title in rss_feed.title
        assert len(rss_feed.items) == 3
        assert rss_feed.managing_editor is not None
        assert "Dr. Jane Smith" in rss_feed.managing_editor
    
    def test_sitemap_generation(self, feed_generator, sample_episodes, sample_series, sample_host):
        """Test standard XML sitemap generation"""
        sitemap = feed_generator.generate_sitemap()
        
        # Should include homepage, series index, hosts index, episodes, series pages, host profiles
        expected_urls = (
            1 +  # homepage
            1 +  # series index
            1 +  # hosts index
            len(sample_episodes) +  # episode pages
            1 +  # series page
            1    # host profile
        )
        
        assert len(sitemap.urls) == expected_urls
        
        # Check homepage
        homepage_url = next(url for url in sitemap.urls if url["loc"] == "https://example.com")
        assert homepage_url["priority"] == "1.0"
        assert homepage_url["changefreq"] == "daily"
    
    def test_video_sitemap_generation(self, feed_generator, sample_episodes):
        """Test video sitemap generation"""
        video_sitemap = feed_generator.generate_video_sitemap(sample_episodes)
        
        # Should include all episodes with video content
        assert len(video_sitemap.urls) == len(sample_episodes)
        
        # Check video metadata
        first_url = video_sitemap.urls[0]
        assert "video" in first_url
        
        video_data = first_url["video"]
        assert "thumbnail_loc" in video_data
        assert "title" in video_data
        assert "description" in video_data
        assert "content_loc" in video_data
        assert "duration" in video_data
    
    def test_news_sitemap_generation(self, feed_generator):
        """Test news sitemap for recent episodes"""
        # Create recent episodes (within 48 hours)
        recent_time = datetime.now() - timedelta(hours=24)
        recent_episodes = [
            Episode(
                episode_id="recent-001",
                title="Recent Episode",
                description="Recent episode description",
                upload_date=recent_time,
                duration=timedelta(hours=1),
                series=Mock(),
                hosts=[Mock()]
            )
        ]
        
        # Mock content registry for recent episodes
        from src.core.content_registry import ContentFilter
        
        def mock_get_episodes(filters=None):
            if filters and filters.date_from:
                return recent_episodes
            return []
        
        feed_generator.content_registry.get_episodes.side_effect = mock_get_episodes
        
        news_sitemap = feed_generator.generate_news_sitemap()
        
        assert len(news_sitemap.urls) == 1
        
        # Check news metadata
        news_url = news_sitemap.urls[0]
        assert "news" in news_url
        
        news_data = news_url["news"]
        assert news_data["publication_name"] == "Test Site"
        assert news_data["language"] == "en"
        assert news_data["title"] == "Recent Episode"


# ========================================
# Feed Validation Tests
# ========================================

class TestFeedValidation:
    """Test feed validation functionality"""
    
    def test_rss_feed_validation_success(self, feed_generator):
        """Test successful RSS feed validation"""
        rss_feed = RSSFeed(
            title="Valid Feed",
            description="Valid feed description",
            link="https://example.com"
        )
        
        rss_feed.items.append({
            "title": "Valid Item",
            "description": "Valid item description",
            "link": "https://example.com/item1",
            "guid": "https://example.com/item1"
        })
        
        result = feed_generator.validate_rss_feed(rss_feed)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.metadata["total_items"] == 1
    
    def test_rss_feed_validation_errors(self, feed_generator):
        """Test RSS feed validation with errors"""
        # Create invalid feed (missing required fields)
        rss_feed = RSSFeed(
            title="",  # Empty title
            description="Valid description",
            link=""    # Empty link
        )
        
        # Add invalid item
        rss_feed.items.append({
            "title": "",  # Empty title
            "description": "Valid description"
            # Missing link and guid
        })
        
        result = feed_generator.validate_rss_feed(rss_feed)
        
        assert result.is_valid is False
        assert len(result.errors) >= 3  # Missing title, link, and item issues
        
        # Check specific error types
        error_messages = [error.message for error in result.errors]
        assert any("title is required" in msg for msg in error_messages)
        assert any("link is required" in msg for msg in error_messages)
    
    def test_xml_sitemap_validation_success(self, feed_generator):
        """Test successful XML sitemap validation"""
        sitemap = XMLSitemap()
        
        sitemap.add_url(
            loc="https://example.com/page1",
            changefreq="weekly",
            priority=0.8
        )
        
        result = feed_generator.validate_xml_sitemap(sitemap)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.metadata["total_urls"] == 1
    
    def test_xml_sitemap_validation_errors(self, feed_generator):
        """Test XML sitemap validation with errors"""
        sitemap = XMLSitemap()
        
        # Add invalid URLs
        sitemap.urls.append({
            "loc": "",  # Empty location
            "changefreq": "invalid_freq",  # Invalid changefreq
            "priority": "2.0"  # Invalid priority (> 1.0)
        })
        
        result = feed_generator.validate_xml_sitemap(sitemap)
        
        assert result.is_valid is False
        assert len(result.errors) >= 3
        
        # Check specific error types
        error_messages = [error.message for error in result.errors]
        assert any("missing required loc" in msg for msg in error_messages)
        assert any("invalid changefreq" in msg for msg in error_messages)
        assert any("priority must be between" in msg for msg in error_messages)


# ========================================
# Feed Management Tests
# ========================================

class TestFeedManagement:
    """Test feed update and management functionality"""
    
    def test_feed_update_on_content_change(self, feed_generator):
        """Test automatic feed updates when content changes"""
        # Cache some feeds first
        feed_generator.cache.cache_feed("site_rss", "cached_content")
        feed_generator.cache.cache_feed("sitemap", "cached_sitemap")
        
        assert feed_generator.cache.is_cached("site_rss")
        assert feed_generator.cache.is_cached("sitemap")
        
        # Trigger content change
        feed_generator.update_feeds_on_content_change(["episode-001", "episode-002"])
        
        # Caches should be invalidated
        assert not feed_generator.cache.is_cached("site_rss")
        assert not feed_generator.cache.is_cached("sitemap")
    
    def test_feed_statistics(self, feed_generator, sample_episodes):
        """Test feed statistics generation"""
        feed_generator.content_registry.get_episodes.return_value = sample_episodes
        feed_generator.content_registry.get_all_series.return_value = [sample_episodes[0].series]
        
        stats = feed_generator.get_feed_statistics()
        
        assert stats["total_episodes"] == 3
        assert stats["total_series"] == 1
        assert stats["video_episodes"] == 3  # All sample episodes have video content
        assert "feeds_available" in stats
        assert "site_rss" in stats["feeds_available"]


# ========================================
# Utility Functions Tests
# ========================================

class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_feed_generator(self, mock_content_registry):
        """Test feed generator creation utility"""
        generator = create_feed_generator(
            content_registry=mock_content_registry,
            base_url="https://test.com",
            site_name="Test Site"
        )
        
        assert isinstance(generator, FeedGenerator)
        assert generator.base_url == "https://test.com"
        assert generator.site_name == "Test Site"
    
    def test_validate_feed_xml_rss(self):
        """Test XML feed validation utility for RSS"""
        valid_rss = '''<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <description>Test Description</description>
                <link>https://example.com</link>
            </channel>
        </rss>'''
        
        result = validate_feed_xml(valid_rss, "rss")
        assert result.is_valid is True
        
        # Test invalid RSS
        invalid_rss = '''<?xml version="1.0" encoding="UTF-8"?>
        <invalid>
            <channel>
                <title>Test</title>
            </channel>
        </invalid>'''
        
        result = validate_feed_xml(invalid_rss, "rss")
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_feed_xml_sitemap(self):
        """Test XML feed validation utility for sitemap"""
        valid_sitemap = '''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
            </url>
        </urlset>'''
        
        result = validate_feed_xml(valid_sitemap, "sitemap")
        assert result.is_valid is True
    
    def test_validate_feed_xml_malformed(self):
        """Test XML validation with malformed XML"""
        malformed_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <rss>
            <channel>
                <title>Unclosed tag
            </channel>
        </rss>'''
        
        result = validate_feed_xml(malformed_xml, "rss")
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "XML parsing error" in result.errors[0].message


# ========================================
# Integration Tests
# ========================================

class TestFeedGeneratorIntegration:
    """Integration tests for complete feed generation workflow"""
    
    def test_complete_rss_workflow(self, feed_generator, sample_episodes):
        """Test complete RSS generation and validation workflow"""
        # Generate RSS feed
        rss_feed = feed_generator.generate_site_rss(sample_episodes)
        
        # Validate the feed
        validation_result = feed_generator.validate_rss_feed(rss_feed)
        assert validation_result.is_valid is True
        
        # Generate XML and validate it
        xml_content = rss_feed.to_xml()
        xml_validation = validate_feed_xml(xml_content, "rss")
        assert xml_validation.is_valid is True
        
        # Verify XML structure
        root = ET.fromstring(xml_content)
        assert root.tag == "rss"
        
        channel = root.find("channel")
        assert channel.find("title").text == "Test Site"
        
        items = channel.findall("item")
        assert len(items) == len(sample_episodes)
    
    def test_complete_sitemap_workflow(self, feed_generator, sample_episodes):
        """Test complete sitemap generation and validation workflow"""
        # Generate sitemap
        sitemap = feed_generator.generate_sitemap()
        
        # Validate the sitemap
        validation_result = feed_generator.validate_xml_sitemap(sitemap)
        assert validation_result.is_valid is True
        
        # Generate XML and validate it
        xml_content = sitemap.to_xml()
        xml_validation = validate_feed_xml(xml_content, "sitemap")
        assert xml_validation.is_valid is True
        
        # Verify XML structure
        root = ET.fromstring(xml_content)
        assert root.tag.endswith("urlset")
        
        # Define namespace for finding elements
        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sitemap:url", ns)
        assert len(urls) > 0
        
        # Check that all URLs have required loc element
        for url in urls:
            loc_elem = url.find("sitemap:loc", ns)
            assert loc_elem is not None
            assert loc_elem.text.startswith("https://example.com")
    
    def test_caching_integration(self, feed_generator, sample_episodes):
        """Test feed caching integration"""
        # First generation should create cache
        rss_feed1 = feed_generator.generate_site_rss(sample_episodes)
        
        # Second generation should use cache (mock to verify)
        with patch.object(feed_generator.content_registry, 'get_episodes') as mock_get:
            rss_feed2 = feed_generator.generate_site_rss()
            # get_episodes should not be called due to caching
            mock_get.assert_not_called()
        
        # Content change should invalidate cache
        feed_generator.update_feeds_on_content_change(["episode-001"])
        
        # Next generation should call get_episodes again
        with patch.object(feed_generator.content_registry, 'get_episodes', return_value=sample_episodes) as mock_get:
            rss_feed3 = feed_generator.generate_site_rss()
            mock_get.assert_called_once()