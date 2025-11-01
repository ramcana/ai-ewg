"""
Tests for Web Generator

Tests HTML page generation, JSON-LD embedding, and SEO metadata functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.web_generator import (
    WebGenerator, HTMLPage, SEOMetadata, URLPattern,
    create_web_generator, generate_clean_slug, validate_url_patterns
)
from src.core.publishing_models import (
    Episode, Series, Host, Person, RightsMetadata
)
from src.core.structured_data_contract import SchemaType


@pytest.fixture
def sample_host():
    """Create a sample host for testing"""
    return Host(
        person_id="host_001",
        name="John Doe",
        slug="john-doe",
        bio="Experienced host and interviewer",
        headshot_url="https://example.com/images/john-doe.jpg",
        same_as_links=["https://wikipedia.org/wiki/John_Doe"],
        affiliation="Example University",
        shows=["series_001"]
    )


@pytest.fixture
def sample_series(sample_host):
    """Create a sample series for testing"""
    return Series(
        series_id="series_001",
        title="Tech Talk",
        description="Weekly technology discussions and interviews",
        slug="tech-talk",
        primary_host=sample_host,
        artwork_url="https://example.com/images/tech-talk.jpg",
        topics=["technology", "innovation", "interviews"],
        live_series_url="https://example.com/series/tech-talk"
    )


@pytest.fixture
def sample_episode(sample_series, sample_host):
    """Create a sample episode for testing"""
    return Episode(
        episode_id="ep_001",
        title="The Future of AI",
        description="A deep dive into artificial intelligence and its implications for society.",
        upload_date=datetime(2024, 1, 15, 10, 0, 0),
        duration=timedelta(hours=1, minutes=30),
        series=sample_series,
        hosts=[sample_host],
        guests=[Person(
            person_id="guest_001",
            name="Jane Smith",
            slug="jane-smith",
            bio="AI researcher and author",
            same_as_links=["https://wikipedia.org/wiki/Jane_Smith"]
        )],
        transcript_path="/transcripts/ep_001.vtt",
        thumbnail_url="https://example.com/images/ep_001_thumb.jpg",
        content_url="https://example.com/videos/ep_001.mp4",
        tags=["artificial intelligence", "machine learning", "future tech"],
        social_links={
            "youtube": "https://youtube.com/watch?v=abc123",
            "twitter": "https://twitter.com/example/status/123456"
        },
        rights=RightsMetadata(
            music_clearance=True,
            copyright_holder="Example Media Corp"
        ),
        episode_number=1,
        season_number=1
    )


@pytest.fixture
def web_generator():
    """Create a WebGenerator instance for testing"""
    return create_web_generator(
        base_url="https://example.com",
        site_name="Test Site",
        site_description="Test content platform"
    )


class TestWebGenerator:
    """Test WebGenerator functionality"""
    
    def test_initialization(self):
        """Test WebGenerator initialization"""
        generator = WebGenerator()
        
        assert generator.site_name == "Content Publishing Platform"
        assert generator.site_description == "Educational content archive and publishing platform"
        assert generator.url_patterns.base_url == "https://example.com"
        assert generator.video_contract.schema_type == SchemaType.VIDEO_OBJECT
        assert generator.tv_episode_contract.schema_type == SchemaType.TV_EPISODE
    
    def test_custom_initialization(self):
        """Test WebGenerator with custom parameters"""
        url_patterns = URLPattern(base_url="https://custom.com")
        generator = WebGenerator(
            url_patterns=url_patterns,
            site_name="Custom Site",
            site_description="Custom description"
        )
        
        assert generator.site_name == "Custom Site"
        assert generator.site_description == "Custom description"
        assert generator.url_patterns.base_url == "https://custom.com"
    
    def test_generate_episode_page(self, web_generator, sample_episode):
        """Test episode page generation"""
        page = web_generator.generate_episode_page(sample_episode)
        
        # Check basic page properties
        assert isinstance(page, HTMLPage)
        assert "The Future of AI" in page.title
        assert "Tech Talk" in page.title
        assert "Test Site" in page.title
        assert len(page.meta_description) <= 160
        assert page.canonical_url == "https://example.com/episodes/ep_001"
        
        # Check JSON-LD is present
        assert page.json_ld is not None
        assert page.json_ld["@type"] == "TVEpisode"
        assert page.json_ld["name"] == "The Future of AI"
        
        # Check Open Graph metadata
        assert "og:type" in page.open_graph
        assert page.open_graph["og:type"] == "video.episode"
        assert "og:title" in page.open_graph
        
        # Check Twitter Card metadata
        assert "twitter:card" in page.twitter_card
        assert "twitter:title" in page.twitter_card
        
        # Check content includes episode information
        assert "The Future of AI" in page.content
        assert "John Doe" in page.content
        assert "Jane Smith" in page.content
    
    def test_generate_episode_page_video_object_schema(self, web_generator, sample_episode):
        """Test episode page generation with VideoObject schema"""
        page = web_generator.generate_episode_page(sample_episode, use_tv_episode_schema=False)
        
        assert page.json_ld["@type"] == "VideoObject"
        assert "partOfSeries" in page.json_ld
    
    def test_generate_series_index(self, web_generator, sample_series, sample_episode):
        """Test series index page generation"""
        episodes = [sample_episode]
        page = web_generator.generate_series_index(sample_series, episodes)
        
        # Check basic page properties
        assert isinstance(page, HTMLPage)
        assert "Tech Talk" in page.title
        assert "Test Site" in page.title
        assert page.canonical_url == "https://example.com/series/tech-talk"
        
        # Check JSON-LD is present
        assert page.json_ld is not None
        assert page.json_ld["@type"] == "TVSeries"
        assert page.json_ld["name"] == "Tech Talk"
        assert page.json_ld["numberOfEpisodes"] == 1
        
        # Check content includes series and episode information
        assert "Tech Talk" in page.content
        assert "The Future of AI" in page.content
        assert "1 episodes" in page.content
    
    def test_generate_host_profile(self, web_generator, sample_host, sample_episode):
        """Test host profile page generation"""
        episodes = [sample_episode]
        page = web_generator.generate_host_profile(sample_host, episodes)
        
        # Check basic page properties
        assert isinstance(page, HTMLPage)
        assert "John Doe" in page.title
        assert "Host Profile" in page.title
        assert page.canonical_url == "https://example.com/hosts/john-doe"
        
        # Check JSON-LD is present
        assert page.json_ld is not None
        assert page.json_ld["@type"] == "Person"
        assert page.json_ld["name"] == "John Doe"
        
        # Check content includes host information
        assert "John Doe" in page.content
        assert "Experienced host" in page.content
        assert "1 episodes" in page.content
    
    def test_json_ld_episode_structure(self, web_generator, sample_episode):
        """Test JSON-LD structure for episodes"""
        page = web_generator.generate_episode_page(sample_episode)
        json_ld = page.json_ld
        
        # Check required Schema.org fields
        assert json_ld["@context"] == "https://schema.org"
        assert json_ld["@type"] == "TVEpisode"
        assert json_ld["@id"] == "https://example.com/episodes/ep_001"
        assert json_ld["name"] == "The Future of AI"
        assert json_ld["description"] == sample_episode.description
        assert "uploadDate" in json_ld
        assert "duration" in json_ld
        
        # Check series linking
        assert "partOfSeries" in json_ld
        assert json_ld["partOfSeries"]["@type"] == "TVSeries"
        assert json_ld["partOfSeries"]["name"] == "Tech Talk"
        
        # Check host information
        assert "actor" in json_ld
        assert len(json_ld["actor"]) == 1
        assert json_ld["actor"][0]["name"] == "John Doe"
        
        # Check social links in sameAs
        assert "sameAs" in json_ld
        assert "https://youtube.com/watch?v=abc123" in json_ld["sameAs"]
    
    def test_seo_metadata_creation(self, web_generator, sample_episode):
        """Test SEO metadata creation"""
        canonical_url = "https://example.com/episodes/ep_001"
        seo_metadata = web_generator._create_episode_seo_metadata(sample_episode, canonical_url)
        
        assert isinstance(seo_metadata, SEOMetadata)
        assert "The Future of AI" in seo_metadata.title
        assert "Tech Talk" in seo_metadata.title
        assert len(seo_metadata.description) <= 160
        assert seo_metadata.canonical_url == canonical_url
        assert "artificial intelligence" in seo_metadata.keywords
        assert seo_metadata.author == "John Doe"
    
    def test_open_graph_metadata(self, web_generator, sample_episode):
        """Test Open Graph metadata generation"""
        canonical_url = "https://example.com/episodes/ep_001"
        og_data = web_generator._create_episode_open_graph(sample_episode, canonical_url)
        
        assert og_data["og:type"] == "video.episode"
        assert "The Future of AI" in og_data["og:title"]
        assert og_data["og:url"] == canonical_url
        assert og_data["og:image"] == sample_episode.thumbnail_url
        assert "video:duration" in og_data
        assert og_data["video:series"] == "Tech Talk"
    
    def test_twitter_card_metadata(self, web_generator, sample_episode):
        """Test Twitter Card metadata generation"""
        canonical_url = "https://example.com/episodes/ep_001"
        twitter_data = web_generator._create_episode_twitter_card(sample_episode, canonical_url)
        
        assert twitter_data["twitter:card"] == "player"  # Because content_url is present
        assert "The Future of AI" in twitter_data["twitter:title"]
        assert twitter_data["twitter:url"] == canonical_url
        assert twitter_data["twitter:image"] == sample_episode.thumbnail_url
    
    def test_canonical_url_generation(self, web_generator):
        """Test canonical URL generation"""
        # Test episode URL
        episode_url = web_generator.generate_canonical_url("episode", "ep_001")
        assert episode_url == "https://example.com/episodes/ep_001"
        
        # Test series URL
        series_url = web_generator.generate_canonical_url("series", "series_001", series_slug="tech-talk")
        assert series_url == "https://example.com/series/tech-talk"
        
        # Test host URL
        host_url = web_generator.generate_canonical_url("host", "host_001", host_slug="john-doe")
        assert host_url == "https://example.com/hosts/john-doe"
        
        # Test invalid content type
        with pytest.raises(ValueError):
            web_generator.generate_canonical_url("invalid", "test")
    
    def test_redirect_rules_creation(self, web_generator):
        """Test redirect rules creation"""
        old_urls = [
            "/old/episode/123",
            "/legacy/ep_001.html"
        ]
        new_url = "https://example.com/episodes/ep_001"
        
        redirect_rules = web_generator.create_redirect_rules(old_urls, new_url)
        
        assert len(redirect_rules) == 2
        assert redirect_rules[0]["from"] == "/old/episode/123"
        assert redirect_rules[0]["to"] == new_url
        assert redirect_rules[0]["status"] == "301"
        assert redirect_rules[1]["from"] == "/legacy/ep_001.html"
    
    def test_complete_html_rendering(self, web_generator, sample_episode):
        """Test complete HTML document rendering"""
        page = web_generator.generate_episode_page(sample_episode)
        html = web_generator.render_complete_html(page)
        
        # Check HTML structure
        assert html.startswith("<!DOCTYPE html>")
        assert "<html lang=\"en\">" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html.strip()
        
        # Check metadata is included
        assert f"<title>{page.title}</title>" in html
        assert f'<meta name="description" content="{page.meta_description}">' in html
        assert f'<link rel="canonical" href="{page.canonical_url}">' in html
        
        # Check JSON-LD is embedded
        assert '<script type="application/ld+json">' in html
        assert '"@type": "TVEpisode"' in html
        
        # Check Open Graph tags
        assert 'property="og:type"' in html
        assert 'property="og:title"' in html
        
        # Check content is included
        assert page.content in html


class TestURLPattern:
    """Test URL pattern functionality"""
    
    def test_default_patterns(self):
        """Test default URL patterns"""
        patterns = URLPattern()
        
        assert patterns.base_url == "https://example.com"
        assert patterns.episode_pattern == "/episodes/{episode_id}"
        assert patterns.series_pattern == "/series/{series_slug}"
        assert patterns.host_pattern == "/hosts/{host_slug}"
    
    def test_custom_patterns(self):
        """Test custom URL patterns"""
        patterns = URLPattern(
            base_url="https://custom.com",
            episode_pattern="/shows/{series_slug}/{episode_id}",
            series_pattern="/shows/{series_slug}",
            host_pattern="/people/{host_slug}"
        )
        
        assert patterns.base_url == "https://custom.com"
        assert patterns.episode_pattern == "/shows/{series_slug}/{episode_id}"
    
    def test_url_generation(self, sample_episode, sample_series, sample_host):
        """Test URL generation methods"""
        patterns = URLPattern()
        
        episode_url = patterns.generate_episode_url(sample_episode)
        assert episode_url == "https://example.com/episodes/ep_001"
        
        series_url = patterns.generate_series_url(sample_series)
        assert series_url == "https://example.com/series/tech-talk"
        
        host_url = patterns.generate_host_url(sample_host)
        assert host_url == "https://example.com/hosts/john-doe"


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_web_generator(self):
        """Test web generator factory function"""
        generator = create_web_generator(
            base_url="https://test.com",
            site_name="Test Site",
            site_description="Test description"
        )
        
        assert isinstance(generator, WebGenerator)
        assert generator.site_name == "Test Site"
        assert generator.url_patterns.base_url == "https://test.com"
    
    def test_generate_clean_slug(self):
        """Test slug generation"""
        assert generate_clean_slug("Hello World") == "hello-world"
        assert generate_clean_slug("Tech Talk: AI & ML") == "tech-talk-ai-ml"
        assert generate_clean_slug("  Multiple   Spaces  ") == "multiple-spaces"
        assert generate_clean_slug("Special!@#$%Characters") == "specialcharacters"
        assert generate_clean_slug("---Multiple---Hyphens---") == "multiple-hyphens"
    
    def test_validate_url_patterns(self):
        """Test URL pattern validation"""
        # Valid patterns
        valid_patterns = URLPattern()
        errors = validate_url_patterns(valid_patterns)
        assert len(errors) == 0
        
        # Invalid base URL
        invalid_patterns = URLPattern(base_url="invalid-url")
        errors = validate_url_patterns(invalid_patterns)
        assert len(errors) > 0
        assert "Base URL must start with http://" in errors[0]
        
        # Missing placeholders
        invalid_patterns = URLPattern(episode_pattern="/episodes/")
        errors = validate_url_patterns(invalid_patterns)
        assert any("episode_pattern must contain {episode_id}" in error for error in errors)


class TestSchemaOrgCompliance:
    """Test Schema.org compliance and structured data contract validation"""
    
    def test_tv_episode_schema_required_fields(self, web_generator, sample_episode):
        """Test TVEpisode schema contains all required Schema.org fields"""
        page = web_generator.generate_episode_page(sample_episode, use_tv_episode_schema=True)
        json_ld = page.json_ld
        
        # Required Schema.org TVEpisode fields
        required_fields = [
            "@context", "@type", "@id", "name", "description", 
            "uploadDate", "duration", "partOfSeries", "actor"
        ]
        
        for field in required_fields:
            assert field in json_ld, f"Required field '{field}' missing from TVEpisode schema"
        
        # Validate field types and formats
        assert json_ld["@context"] == "https://schema.org"
        assert json_ld["@type"] == "TVEpisode"
        assert json_ld["@id"].startswith("https://")
        assert isinstance(json_ld["name"], str)
        assert isinstance(json_ld["description"], str)
        assert "T" in json_ld["uploadDate"]  # ISO 8601 format
        assert json_ld["duration"].startswith("PT")  # ISO 8601 duration format
        assert json_ld["partOfSeries"]["@type"] == "TVSeries"
        assert isinstance(json_ld["actor"], list)
    
    def test_video_object_schema_required_fields(self, web_generator, sample_episode):
        """Test VideoObject schema contains all required Schema.org fields"""
        page = web_generator.generate_episode_page(sample_episode, use_tv_episode_schema=False)
        json_ld = page.json_ld
        
        # Required Schema.org VideoObject fields
        required_fields = [
            "@context", "@type", "@id", "name", "description",
            "uploadDate", "duration", "thumbnailUrl", "contentUrl"
        ]
        
        for field in required_fields:
            assert field in json_ld, f"Required field '{field}' missing from VideoObject schema"
        
        # Validate VideoObject specific fields
        assert json_ld["@type"] == "VideoObject"
        assert json_ld["thumbnailUrl"].startswith("https://")
        assert json_ld["contentUrl"].startswith("https://")
    
    def test_structured_data_contract_compliance(self, web_generator, sample_episode):
        """Test compliance with Structured Data Contract requirements"""
        page = web_generator.generate_episode_page(sample_episode)
        json_ld = page.json_ld
        
        # Test required contract fields from requirements
        contract_required_fields = {
            "@context": {"expected_value": "https://schema.org"},
            "@type": {"expected_values": ["TVEpisode", "VideoObject"]},
            "name": {"type": str},
            "description": {"type": str},
            "uploadDate": {"type": str},
            "duration": {"type": str},
            "partOfSeries": {"type": dict},
            "actor": {"type": list},
            "publisher": {"type": dict},
            "thumbnailUrl": {"type": str},
            "contentUrl": {"type": str}
        }
        
        for field, validation in contract_required_fields.items():
            assert field in json_ld, f"Contract field '{field}' missing"
            
            if "expected_value" in validation:
                assert json_ld[field] == validation["expected_value"], f"Field '{field}' has wrong value"
            elif "expected_values" in validation:
                assert json_ld[field] in validation["expected_values"], f"Field '{field}' has invalid value"
            elif "type" in validation:
                assert isinstance(json_ld[field], validation["type"]), f"Field '{field}' has wrong type"
    
    def test_same_as_links_inclusion(self, web_generator, sample_episode):
        """Test sameAs links are properly included from social media URLs"""
        # Ensure episode has social links
        sample_episode.social_links = {
            "youtube": "https://youtube.com/watch?v=abc123",
            "twitter": "https://twitter.com/example/status/123456",
            "instagram": "https://instagram.com/p/abc123"
        }
        
        page = web_generator.generate_episode_page(sample_episode)
        json_ld = page.json_ld
        
        # Check sameAs field exists and contains social URLs
        assert "sameAs" in json_ld, "sameAs field missing from JSON-LD"
        assert isinstance(json_ld["sameAs"], list), "sameAs should be a list"
        
        # Verify all valid social URLs are included
        same_as_urls = json_ld["sameAs"]
        assert "https://youtube.com/watch?v=abc123" in same_as_urls
        assert "https://twitter.com/example/status/123456" in same_as_urls
        assert "https://instagram.com/p/abc123" in same_as_urls
    
    def test_accessibility_features_compliance(self, web_generator, sample_episode):
        """Test accessibility features are properly declared"""
        page = web_generator.generate_episode_page(sample_episode)
        json_ld = page.json_ld
        
        # Check accessibility features
        assert "accessibilityFeature" in json_ld
        assert "audioDescription" in json_ld["accessibilityFeature"]
        
        # If transcript exists, captions should be declared
        if sample_episode.transcript_path:
            assert "captions" in json_ld["accessibilityFeature"]
            assert "transcript" in json_ld
            assert json_ld["transcript"]["@type"] == "MediaObject"
    
    def test_publisher_information_completeness(self, web_generator, sample_episode):
        """Test publisher information meets Schema.org requirements"""
        page = web_generator.generate_episode_page(sample_episode)
        json_ld = page.json_ld
        
        # Validate publisher object
        assert "publisher" in json_ld
        publisher = json_ld["publisher"]
        
        assert publisher["@type"] == "Organization"
        assert "name" in publisher
        assert "url" in publisher
        assert publisher["url"].startswith("https://")


class TestHTMLStructureValidation:
    """Test HTML page structure and content validation"""
    
    def test_episode_page_html_structure(self, web_generator, sample_episode):
        """Test episode page HTML has proper semantic structure"""
        page = web_generator.generate_episode_page(sample_episode)
        html = web_generator.render_complete_html(page)
        
        # Check HTML5 semantic structure
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "<head>" in html and "</head>" in html
        assert "<body>" in html and "</body>" in html
        assert "<main>" in html and "</main>" in html
        assert "<header>" in html and "</header>" in html
        assert "<footer>" in html and "</footer>" in html
        
        # Check article structure for episode content
        assert "<article" in page.content
        assert 'class="episode"' in page.content
        
        # Check required metadata in head
        assert f'<title>{page.title}</title>' in html
        assert f'<link rel="canonical" href="{page.canonical_url}">' in html
        assert 'type="application/ld+json"' in html
    
    def test_series_page_html_structure(self, web_generator, sample_series, sample_episode):
        """Test series page HTML has proper structure"""
        episodes = [sample_episode]
        page = web_generator.generate_series_index(sample_series, episodes)
        
        # Check series-specific structure
        assert 'class="series-page"' in page.content
        assert 'class="series-header"' in page.content
        assert 'class="episodes-list"' in page.content
        
        # Check episode cards are present
        assert 'class="episode-card"' in page.content
        assert sample_episode.title in page.content
    
    def test_host_profile_html_structure(self, web_generator, sample_host, sample_episode):
        """Test host profile page HTML has proper structure"""
        episodes = [sample_episode]
        page = web_generator.generate_host_profile(sample_host, episodes)
        
        # Check host-specific structure
        assert 'class="host-profile"' in page.content
        assert 'class="host-header"' in page.content
        assert 'class="host-info"' in page.content
        
        # Check host information is present
        assert sample_host.name in page.content
        if sample_host.bio:
            assert sample_host.bio in page.content
    
    def test_breadcrumb_navigation_structure(self, web_generator, sample_episode):
        """Test breadcrumb navigation is properly structured"""
        page = web_generator.generate_episode_page(sample_episode)
        
        # Check breadcrumb structure
        assert 'class="breadcrumb"' in page.content
        assert 'aria-label="Breadcrumb"' in page.content
        
        # Check breadcrumb links
        assert '<a href="/">Home</a>' in page.content
        assert sample_episode.series.title in page.content
    
    def test_meta_tags_completeness(self, web_generator, sample_episode):
        """Test all required meta tags are present"""
        page = web_generator.generate_episode_page(sample_episode)
        html = web_generator.render_complete_html(page)
        
        # Required meta tags
        required_meta_tags = [
            'charset="UTF-8"',
            'name="viewport"',
            'name="description"',
            'rel="canonical"',
            'property="og:type"',
            'property="og:title"',
            'property="og:url"',
            'name="twitter:card"'
        ]
        
        for meta_tag in required_meta_tags:
            assert meta_tag in html, f"Required meta tag '{meta_tag}' missing"


class TestSEOOptimization:
    """Test SEO optimization features"""
    
    def test_canonical_url_consistency(self, web_generator, sample_episode):
        """Test canonical URLs are consistent across all metadata"""
        page = web_generator.generate_episode_page(sample_episode)
        html = web_generator.render_complete_html(page)
        
        canonical_url = page.canonical_url
        
        # Check canonical URL appears in all relevant places
        assert f'<link rel="canonical" href="{canonical_url}">' in html
        assert f'"og:url" content="{canonical_url}"' in html
        assert f'"twitter:url" content="{canonical_url}"' in html
        assert f'"@id": "{canonical_url}"' in html  # JSON-LD
    
    def test_meta_description_length_optimization(self, web_generator, sample_episode):
        """Test meta descriptions are optimized for search engines"""
        # Test with long description
        long_description = "A" * 300  # Very long description
        sample_episode.description = long_description
        
        page = web_generator.generate_episode_page(sample_episode)
        
        # Meta description should be truncated to ~160 characters
        assert len(page.meta_description) <= 160
        assert page.meta_description.endswith("...")
    
    def test_title_tag_optimization(self, web_generator, sample_episode):
        """Test title tags include proper hierarchy and branding"""
        page = web_generator.generate_episode_page(sample_episode)
        
        # Title should include episode, series, and site name
        assert sample_episode.title in page.title
        assert sample_episode.series.title in page.title
        assert web_generator.site_name in page.title
        
        # Check title length is reasonable for SEO
        assert len(page.title) <= 70  # Google's recommended limit
    
    def test_open_graph_video_metadata(self, web_generator, sample_episode):
        """Test Open Graph video metadata is complete"""
        page = web_generator.generate_episode_page(sample_episode)
        
        og_data = page.open_graph
        
        # Required Open Graph video fields
        assert og_data["og:type"] == "video.episode"
        assert "og:video" in og_data
        assert "video:duration" in og_data
        assert "video:series" in og_data
        
        # Validate duration format
        duration_seconds = int(sample_episode.duration.total_seconds())
        assert og_data["video:duration"] == str(duration_seconds)
    
    def test_twitter_card_video_player(self, web_generator, sample_episode):
        """Test Twitter Card video player metadata"""
        page = web_generator.generate_episode_page(sample_episode)
        
        twitter_data = page.twitter_card
        
        # Should use player card for video content
        assert twitter_data["twitter:card"] == "player"
        assert "twitter:player" in twitter_data
        assert "twitter:player:width" in twitter_data
        assert "twitter:player:height" in twitter_data


class TestHTMLGeneration:
    """Test HTML content generation"""
    
    def test_html_escaping(self, web_generator):
        """Test HTML escaping functionality"""
        test_text = '<script>alert("xss")</script>'
        escaped = web_generator._escape_html(test_text)
        
        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "&quot;" in escaped  # Quotes should be escaped
        assert "<script>" not in escaped
    
    def test_duration_formatting(self, web_generator):
        """Test duration formatting"""
        # Test hours, minutes, seconds
        duration1 = timedelta(hours=1, minutes=30, seconds=45)
        formatted1 = web_generator._format_duration(duration1)
        assert formatted1 == "1:30:45"
        
        # Test minutes and seconds only
        duration2 = timedelta(minutes=5, seconds=30)
        formatted2 = web_generator._format_duration(duration2)
        assert formatted2 == "5:30"
        
        # Test seconds only
        duration3 = timedelta(seconds=45)
        formatted3 = web_generator._format_duration(duration3)
        assert formatted3 == "0:45"
    
    def test_link_display_names(self, web_generator):
        """Test external link display name generation"""
        assert web_generator._get_link_display_name("https://wikipedia.org/wiki/Test") == "Wikipedia"
        assert web_generator._get_link_display_name("https://wikidata.org/wiki/Q123") == "Wikidata"
        assert web_generator._get_link_display_name("https://twitter.com/user") == "Twitter/X"
        assert web_generator._get_link_display_name("https://example.com/page") == "Example.Com"
    
    def test_breadcrumb_rendering(self, web_generator):
        """Test breadcrumb navigation rendering"""
        breadcrumb = [
            {"text": "Home", "url": "/"},
            {"text": "Series", "url": "/series"},
            {"text": "Current Page", "url": None}
        ]
        
        rendered = web_generator._render_breadcrumb(breadcrumb)
        
        assert '<a href="/">Home</a>' in rendered
        assert '<a href="/series">Series</a>' in rendered
        assert '<span>Current Page</span>' in rendered
        assert ' / ' in rendered
    
    def test_social_links_rendering(self, web_generator, sample_episode):
        """Test social media links are properly rendered"""
        # Add social links to episode
        sample_episode.social_links = {
            "youtube": "https://youtube.com/watch?v=abc123",
            "twitter": "https://twitter.com/example/status/123456"
        }
        
        page = web_generator.generate_episode_page(sample_episode)
        
        # Check social links section is rendered
        assert 'class="social-links"' in page.content
        assert "Watch & Share" in page.content
        assert "youtube.com" in page.content
        assert "twitter.com" in page.content
    
    def test_guest_information_rendering(self, web_generator, sample_episode):
        """Test guest information is properly rendered"""
        page = web_generator.generate_episode_page(sample_episode)
        
        # Check guest section is rendered
        assert 'class="episode-guests"' in page.content
        assert "Featured Guests" in page.content
        assert sample_episode.guests[0].name in page.content


class TestAnalyticsIntegration:
    """Test analytics tracking integration"""
    
    def test_analytics_code_embedding(self, sample_episode):
        """Test analytics tracking code is embedded in pages"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        # Create analytics tracker
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID"
        )
        analytics_tracker = AnalyticsTracker(config)
        
        # Create web generator with analytics
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        # Generate episode page
        page = generator.generate_episode_page(sample_episode)
        
        # Verify analytics code is present
        assert page.analytics_code is not None
        assert "GA_MEASUREMENT_ID" in page.analytics_code
        assert "gtag" in page.analytics_code
        assert "episode" in page.analytics_code  # page type
    
    def test_analytics_custom_data(self, sample_episode):
        """Test custom analytics data is included"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID"
        )
        analytics_tracker = AnalyticsTracker(config)
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify custom data is included
        assert sample_episode.episode_id in page.analytics_code
        assert sample_episode.series.series_id in page.analytics_code
    
    def test_analytics_disabled(self, sample_episode):
        """Test page generation without analytics tracker"""
        generator = WebGenerator()  # No analytics tracker
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify no analytics code is generated
        assert page.analytics_code is None
    
    def test_analytics_privacy_compliance(self, sample_episode):
        """Test privacy-compliant analytics configuration"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID",
            cookie_consent_required=True,
            anonymize_ip=True
        )
        analytics_tracker = AnalyticsTracker(config)
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify privacy features are included
        assert "analytics_consent" in page.analytics_code
        assert "anonymize_ip" in page.analytics_code


if __name__ == "__main__":
    pytest.main([__file__])
cl
ass TestAnalyticsIntegration:
    """Test analytics tracking integration"""
    
    def test_analytics_code_embedding(self, sample_episode):
        """Test analytics tracking code is embedded in pages"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        # Create analytics tracker
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID"
        )
        analytics_tracker = AnalyticsTracker(config)
        
        # Create web generator with analytics
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        # Generate episode page
        page = generator.generate_episode_page(sample_episode)
        
        # Verify analytics code is present
        assert page.analytics_code is not None
        assert "GA_MEASUREMENT_ID" in page.analytics_code
        assert "gtag" in page.analytics_code
        assert "episode" in page.analytics_code  # page type
    
    def test_analytics_custom_data(self, sample_episode):
        """Test custom analytics data is included"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID"
        )
        analytics_tracker = AnalyticsTracker(config)
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify custom data is included
        assert sample_episode.episode_id in page.analytics_code
        assert sample_episode.series.series_id in page.analytics_code
    
    def test_analytics_disabled(self, sample_episode):
        """Test page generation without analytics tracker"""
        generator = WebGenerator()  # No analytics tracker
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify no analytics code is generated
        assert page.analytics_code is None
    
    def test_analytics_privacy_compliance(self, sample_episode):
        """Test privacy-compliant analytics configuration"""
        from src.core.analytics_tracker import AnalyticsTracker, AnalyticsConfig, AnalyticsProvider
        
        config = AnalyticsConfig(
            provider=AnalyticsProvider.GOOGLE_ANALYTICS,
            tracking_id="GA_MEASUREMENT_ID",
            cookie_consent_required=True,
            anonymize_ip=True
        )
        analytics_tracker = AnalyticsTracker(config)
        generator = WebGenerator(analytics_tracker=analytics_tracker)
        
        page = generator.generate_episode_page(sample_episode)
        
        # Verify privacy features are included
        assert "analytics_consent" in page.analytics_code
        assert "anonymize_ip" in page.analytics_code