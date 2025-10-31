"""
Tests for CDN Manager and performance optimization components.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from src.core.cdn_manager import (
    CDNManager,
    EnhancedCDNManager,
    CacheConfigurationSystem,
    CacheHeaderGenerator,
    ContentCompressor,
    AssetOptimizer,
    AssetBundler,
    CacheInvalidationSystem,
    PerformanceMonitor,
    CloudflareCDNProvider,
    CacheType,
    CacheConfig,
    CompressionType,
    CompressionConfig,
    create_cdn_manager,
    create_enhanced_cdn_manager,
    create_cache_configuration_system,
    create_compression_config
)


class TestCacheConfigurationSystem:
    """Test cache configuration system."""
    
    def test_default_configs_created(self):
        """Test that default cache configurations are created."""
        cache_system = create_cache_configuration_system()
        
        # Check that all cache types have configurations
        for cache_type in CacheType:
            config = cache_system.get_config(cache_type)
            assert isinstance(config, CacheConfig)
            assert config.ttl_seconds > 0
            assert config.max_age_seconds > 0
    
    def test_transcript_immutable_cache(self):
        """Test that transcripts have immutable cache configuration."""
        cache_system = create_cache_configuration_system()
        config = cache_system.get_config(CacheType.TRANSCRIPT)
        
        assert config.immutable is True
        assert config.max_age_seconds >= 2592000  # 30 days minimum
    
    def test_media_immutable_cache(self):
        """Test that media files have immutable cache configuration."""
        cache_system = create_cache_configuration_system()
        config = cache_system.get_config(CacheType.MEDIA)
        
        assert config.immutable is True
        assert config.max_age_seconds >= 2592000  # 30 days minimum
    
    def test_cache_type_detection(self):
        """Test cache type detection from file paths."""
        cache_system = create_cache_configuration_system()
        
        # Test transcript files
        assert cache_system.get_cache_type_for_path("episode1.vtt") == CacheType.TRANSCRIPT
        assert cache_system.get_cache_type_for_path("transcript.srt") == CacheType.TRANSCRIPT
        
        # Test media files
        assert cache_system.get_cache_type_for_path("video.mp4") == CacheType.MEDIA
        assert cache_system.get_cache_type_for_path("audio.mp3") == CacheType.MEDIA
        assert cache_system.get_cache_type_for_path("image.jpg") == CacheType.MEDIA
        
        # Test feeds
        assert cache_system.get_cache_type_for_path("feed.xml") == CacheType.FEED
        assert cache_system.get_cache_type_for_path("sitemap.xml") == CacheType.FEED
        
        # Test HTML pages
        assert cache_system.get_cache_type_for_path("index.html") == CacheType.HTML_PAGE
        
        # Test JSON data
        assert cache_system.get_cache_type_for_path("data.json") == CacheType.JSON_DATA
    
    def test_cache_control_header_generation(self):
        """Test Cache-Control header generation."""
        config = CacheConfig(
            ttl_seconds=3600,
            max_age_seconds=3600,
            stale_while_revalidate_seconds=1800,
            immutable=True,
            public=True
        )
        
        header = config.to_cache_control_header()
        
        assert "max-age=3600" in header
        assert "stale-while-revalidate=1800" in header
        assert "immutable" in header
        assert "public" in header


class TestContentCompressor:
    """Test content compression functionality."""
    
    def test_compression_config_creation(self):
        """Test compression configuration creation."""
        config = create_compression_config()
        
        assert config.enabled is True
        assert config.gzip_level == 6
        assert config.brotli_level == 6
        assert config.min_size_bytes == 1024
        assert 'text/html' in config.mime_types
    
    def test_should_compress_logic(self):
        """Test compression decision logic."""
        config = create_compression_config(min_size_bytes=100)
        compressor = ContentCompressor(config)
        
        # Small content should not be compressed
        small_content = b"small"
        assert not compressor.should_compress(small_content, "text/html")
        
        # Large compressible content should be compressed
        large_content = b"x" * 200
        assert compressor.should_compress(large_content, "text/html")
        
        # Non-compressible content type should not be compressed
        assert not compressor.should_compress(large_content, "image/jpeg")
    
    def test_gzip_compression(self):
        """Test Gzip compression."""
        config = create_compression_config(min_size_bytes=10)
        compressor = ContentCompressor(config)
        
        content = "This is test content that should be compressed" * 10
        compressed, encoding, ratio = compressor.compress_content(
            content, "text/html", CompressionType.GZIP
        )
        
        assert encoding == "gzip"
        assert ratio < 1.0  # Should be compressed
        assert len(compressed) < len(content.encode('utf-8'))
    
    def test_brotli_compression(self):
        """Test Brotli compression."""
        config = create_compression_config(min_size_bytes=10)
        compressor = ContentCompressor(config)
        
        content = "This is test content that should be compressed" * 10
        compressed, encoding, ratio = compressor.compress_content(
            content, "text/html", CompressionType.BROTLI
        )
        
        assert encoding == "br"
        assert ratio < 1.0  # Should be compressed
        assert len(compressed) < len(content.encode('utf-8'))


class TestCDNManager:
    """Test CDN Manager functionality."""
    
    def test_cdn_manager_creation(self):
        """Test CDN Manager creation."""
        cdn_manager = create_cdn_manager()
        
        assert isinstance(cdn_manager, CDNManager)
        assert cdn_manager.cache_config_system is not None
        assert cdn_manager.content_compressor is not None
        assert cdn_manager.asset_optimizer is not None
        assert cdn_manager.asset_bundler is not None
    
    def test_html_page_optimization(self):
        """Test HTML page optimization."""
        cdn_manager = create_cdn_manager()
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body><h1>Hello World</h1></body>
        </html>
        """
        
        optimized = cdn_manager.optimize_html_page(html_content)
        
        assert optimized.content_type == "text/html"
        assert optimized.headers.cache_control is not None
        assert optimized.headers.etag is not None
        assert optimized.compression_ratio <= 1.0
    
    def test_json_data_optimization(self):
        """Test JSON data optimization."""
        cdn_manager = create_cdn_manager()
        
        json_data = {
            "episodes": [
                {"id": "ep1", "title": "Episode 1"},
                {"id": "ep2", "title": "Episode 2"}
            ]
        }
        
        optimized = cdn_manager.optimize_json_data(json_data)
        
        assert optimized.content_type == "application/json"
        assert optimized.headers.cache_control is not None
        assert optimized.compression_ratio <= 1.0
    
    def test_feed_optimization(self):
        """Test RSS/XML feed optimization."""
        cdn_manager = create_cdn_manager()
        
        feed_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
        <title>Test Feed</title>
        <description>Test RSS Feed</description>
        </channel>
        </rss>"""
        
        optimized = cdn_manager.optimize_feed(feed_content)
        
        assert optimized.content_type in ["application/rss+xml", "text/xml"]
        assert optimized.headers.cache_control is not None
        assert optimized.compression_ratio <= 1.0
    
    def test_compression_stats(self):
        """Test compression statistics calculation."""
        cdn_manager = create_cdn_manager()
        
        # Create some optimized assets
        assets = [
            cdn_manager.optimize_html_page("<html><body>Test 1</body></html>"),
            cdn_manager.optimize_json_data({"test": "data"}),
            cdn_manager.optimize_feed("<?xml version='1.0'?><rss></rss>")
        ]
        
        stats = cdn_manager.get_compression_stats(assets)
        
        assert stats['total_assets'] == 3
        assert stats['total_original_size'] > 0
        assert stats['total_compressed_size'] > 0
        assert 'total_savings_percent' in stats
        assert 'average_compression_ratio' in stats


class TestAssetBundler:
    """Test asset bundling functionality."""
    
    def test_css_minification(self):
        """Test CSS minification."""
        bundler = AssetBundler()
        
        css_content = """
        /* This is a comment */
        body {
            margin: 0;
            padding: 10px;
        }
        
        .header {
            background-color: blue;
        }
        """
        
        minified = bundler.minify_css(css_content)
        
        # Should remove comments and extra whitespace
        assert "/* This is a comment */" not in minified
        assert len(minified) < len(css_content)
        assert "margin:0" in minified or "margin: 0" in minified
    
    def test_js_minification(self):
        """Test JavaScript minification."""
        bundler = AssetBundler()
        
        js_content = """
        // This is a comment
        function test() {
            var x = 1;
            return x + 1;
        }
        
        /* Multi-line
           comment */
        var result = test();
        """
        
        minified = bundler.minify_js(js_content)
        
        # Should remove comments and extra whitespace
        assert "// This is a comment" not in minified
        assert "/* Multi-line" not in minified
        assert len(minified) < len(js_content)


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    def test_request_recording(self):
        """Test request metrics recording."""
        monitor = PerformanceMonitor()
        
        # Record some requests
        monitor.record_request("/page1.html", True, 150.0, 1024, 0.7)
        monitor.record_request("/page2.html", False, 300.0, 2048, 0.8)
        monitor.record_request("/api/data.json", True, 100.0, 512, 0.6)
        
        assert len(monitor.request_log) == 3
    
    def test_metrics_calculation(self):
        """Test performance metrics calculation."""
        monitor = PerformanceMonitor()
        
        # Record requests with known values
        monitor.record_request("/page1.html", True, 100.0, 1000, 0.7)
        monitor.record_request("/page2.html", True, 200.0, 2000, 0.8)
        monitor.record_request("/page3.html", False, 300.0, 1500, 0.9)
        
        metrics = monitor.calculate_current_metrics()
        
        assert metrics.total_requests == 3
        assert metrics.cached_requests == 2
        assert metrics.cache_hit_rate == (2/3) * 100  # 66.67%
        assert metrics.average_response_time_ms == 200.0  # (100+200+300)/3
    
    def test_performance_report(self):
        """Test performance report generation."""
        monitor = PerformanceMonitor()
        
        # Record some requests
        monitor.record_request("/page1.html", True, 150.0, 1024, 0.7)
        monitor.record_request("/page2.html", False, 300.0, 2048, 0.8)
        
        report = monitor.get_performance_report()
        
        assert 'current_metrics' in report
        assert 'recommendations' in report
        assert report['current_metrics']['total_requests'] == 2


class TestEnhancedCDNManager:
    """Test Enhanced CDN Manager with invalidation and monitoring."""
    
    def test_enhanced_cdn_manager_creation(self):
        """Test Enhanced CDN Manager creation."""
        cdn_manager = create_enhanced_cdn_manager()
        
        assert isinstance(cdn_manager, EnhancedCDNManager)
        assert cdn_manager.performance_monitor is not None
        # invalidation_system should be None without CDN provider
        assert cdn_manager.invalidation_system is None
    
    def test_performance_metrics_recording(self):
        """Test performance metrics recording."""
        cdn_manager = create_enhanced_cdn_manager()
        
        # Record some metrics
        cdn_manager.record_request_metrics("/page1.html", True, 150.0, 1024, 0.7)
        cdn_manager.record_request_metrics("/page2.html", False, 300.0, 2048, 0.8)
        
        report = cdn_manager.get_performance_report()
        
        assert report['current_metrics']['total_requests'] == 2
        assert report['current_metrics']['cache_hit_rate_percent'] == 50.0
    
    def test_content_optimization_and_deployment(self):
        """Test content optimization and deployment."""
        cdn_manager = create_enhanced_cdn_manager()
        
        content_bundle = {
            "index.html": "<html><body>Home Page</body></html>",
            "data.json": '{"episodes": []}',
            "feed.xml": "<?xml version='1.0'?><rss></rss>"
        }
        
        optimized_assets = cdn_manager.optimize_and_deploy_content(
            content_bundle,
            "https://example.com",
            invalidate_existing=False  # Skip invalidation since no CDN provider
        )
        
        assert len(optimized_assets) == 3
        assert "index.html" in optimized_assets
        assert "data.json" in optimized_assets
        assert "feed.xml" in optimized_assets
        
        # Check that all assets are optimized
        for asset in optimized_assets.values():
            assert asset.headers.cache_control is not None
            assert asset.headers.etag is not None


if __name__ == "__main__":
    pytest.main([__file__])