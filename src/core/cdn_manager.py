"""
CDN Manager for cache configuration and performance optimization.

This module provides comprehensive CDN management capabilities including:
- Cache configuration with TTL management
- Compression and optimization
- Cache invalidation and performance monitoring
"""

import hashlib
import gzip
import json
import mimetypes

try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Cache type classifications for different content types."""
    HTML_PAGE = "html_page"
    STATIC_ASSET = "static_asset"
    TRANSCRIPT = "transcript"
    MEDIA = "media"
    FEED = "feed"
    JSON_DATA = "json_data"


class CompressionType(Enum):
    """Supported compression algorithms."""
    GZIP = "gzip"
    BROTLI = "brotli"
    NONE = "none"


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    ttl_seconds: int
    max_age_seconds: int
    stale_while_revalidate_seconds: int = 0
    stale_if_error_seconds: int = 0
    immutable: bool = False
    must_revalidate: bool = False
    no_cache: bool = False
    no_store: bool = False
    public: bool = True
    
    def to_cache_control_header(self) -> str:
        """Generate Cache-Control header value."""
        directives = []
        
        if self.no_cache:
            directives.append("no-cache")
        if self.no_store:
            directives.append("no-store")
        if self.must_revalidate:
            directives.append("must-revalidate")
        if self.immutable:
            directives.append("immutable")
        
        if self.public:
            directives.append("public")
        else:
            directives.append("private")
            
        directives.append(f"max-age={self.max_age_seconds}")
        
        if self.stale_while_revalidate_seconds > 0:
            directives.append(f"stale-while-revalidate={self.stale_while_revalidate_seconds}")
        if self.stale_if_error_seconds > 0:
            directives.append(f"stale-if-error={self.stale_if_error_seconds}")
            
        return ", ".join(directives)


@dataclass
class CompressionConfig:
    """Configuration for content compression."""
    enabled: bool = True
    gzip_level: int = 6
    brotli_level: int = 6
    min_size_bytes: int = 1024
    mime_types: List[str] = field(default_factory=lambda: [
        'text/html',
        'text/css',
        'text/javascript',
        'application/javascript',
        'application/json',
        'application/xml',
        'text/xml',
        'application/rss+xml',
        'application/atom+xml',
        'text/plain'
    ])


@dataclass
class CacheHeaders:
    """HTTP cache headers for a resource."""
    cache_control: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    expires: Optional[str] = None
    vary: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for HTTP headers."""
        headers = {"Cache-Control": self.cache_control}
        
        if self.etag:
            headers["ETag"] = self.etag
        if self.last_modified:
            headers["Last-Modified"] = self.last_modified
        if self.expires:
            headers["Expires"] = self.expires
        if self.vary:
            headers["Vary"] = self.vary
            
        return headers


@dataclass
class OptimizedAsset:
    """Optimized asset with compression and cache headers."""
    content: bytes
    content_type: str
    encoding: Optional[str]
    headers: CacheHeaders
    original_size: int
    compressed_size: int
    compression_ratio: float


class CacheConfigurationSystem:
    """System for managing cache configurations across different content types."""
    
    def __init__(self):
        self.configs = self._create_default_configs()
        
    def _create_default_configs(self) -> Dict[CacheType, CacheConfig]:
        """Create default cache configurations per content type."""
        return {
            # HTML pages: Short TTL for dynamic content
            CacheType.HTML_PAGE: CacheConfig(
                ttl_seconds=300,  # 5 minutes
                max_age_seconds=300,
                stale_while_revalidate_seconds=600,  # 10 minutes
                stale_if_error_seconds=3600,  # 1 hour
                public=True
            ),
            
            # Static assets: Medium TTL with versioning
            CacheType.STATIC_ASSET: CacheConfig(
                ttl_seconds=86400,  # 1 day
                max_age_seconds=86400,
                stale_while_revalidate_seconds=86400,
                public=True
            ),
            
            # Transcripts: Long TTL, immutable
            CacheType.TRANSCRIPT: CacheConfig(
                ttl_seconds=2592000,  # 30 days minimum as required
                max_age_seconds=2592000,
                immutable=True,
                public=True
            ),
            
            # Media files: Long TTL, immutable
            CacheType.MEDIA: CacheConfig(
                ttl_seconds=2592000,  # 30 days minimum as required
                max_age_seconds=2592000,
                immutable=True,
                public=True
            ),
            
            # Feeds: Short TTL for freshness
            CacheType.FEED: CacheConfig(
                ttl_seconds=900,  # 15 minutes
                max_age_seconds=900,
                stale_while_revalidate_seconds=1800,  # 30 minutes
                public=True
            ),
            
            # JSON data: Medium TTL
            CacheType.JSON_DATA: CacheConfig(
                ttl_seconds=1800,  # 30 minutes
                max_age_seconds=1800,
                stale_while_revalidate_seconds=3600,  # 1 hour
                public=True
            )
        }
    
    def get_config(self, cache_type: CacheType) -> CacheConfig:
        """Get cache configuration for a content type."""
        return self.configs.get(cache_type, self.configs[CacheType.HTML_PAGE])
    
    def set_config(self, cache_type: CacheType, config: CacheConfig) -> None:
        """Set cache configuration for a content type."""
        self.configs[cache_type] = config
    
    def get_cache_type_for_path(self, file_path: str) -> CacheType:
        """Determine cache type based on file path."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        # Check for transcript files
        if suffix in ['.vtt', '.srt'] or 'transcript' in path.name.lower():
            return CacheType.TRANSCRIPT
            
        # Check for media files
        if suffix in ['.mp4', '.webm', '.mp3', '.wav', '.m4a', '.jpg', '.jpeg', '.png', '.webp']:
            return CacheType.MEDIA
            
        # Check for feeds
        if suffix in ['.xml', '.rss'] or 'sitemap' in path.name.lower() or 'feed' in path.name.lower():
            return CacheType.FEED
            
        # Check for JSON data
        if suffix == '.json':
            return CacheType.JSON_DATA
            
        # Check for HTML pages
        if suffix in ['.html', '.htm']:
            return CacheType.HTML_PAGE
            
        # Default to static asset
        return CacheType.STATIC_ASSET


class ETagGenerator:
    """Generator for ETag values based on content."""
    
    @staticmethod
    def generate_etag(content: Union[str, bytes], weak: bool = False) -> str:
        """Generate ETag from content."""
        if isinstance(content, str):
            content = content.encode('utf-8')
            
        # Use SHA-256 hash for strong ETags
        hash_value = hashlib.sha256(content).hexdigest()[:16]
        
        if weak:
            return f'W/"{hash_value}"'
        else:
            return f'"{hash_value}"'
    
    @staticmethod
    def generate_file_etag(file_path: str, include_mtime: bool = True) -> str:
        """Generate ETag from file content and optionally modification time."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Read file content
        content = path.read_bytes()
        
        # Include modification time for stronger validation
        if include_mtime:
            mtime = int(path.stat().st_mtime)
            content += str(mtime).encode('utf-8')
            
        return ETagGenerator.generate_etag(content)


class LastModifiedGenerator:
    """Generator for Last-Modified header values."""
    
    @staticmethod
    def generate_last_modified(timestamp: Optional[datetime] = None) -> str:
        """Generate Last-Modified header value."""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        # Format according to RFC 7232
        return timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    @staticmethod
    def generate_file_last_modified(file_path: str) -> str:
        """Generate Last-Modified header from file modification time."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        return LastModifiedGenerator.generate_last_modified(mtime)


class CacheHeaderGenerator:
    """Generator for complete cache header sets."""
    
    def __init__(self, cache_config_system: CacheConfigurationSystem):
        self.cache_config_system = cache_config_system
        
    def generate_headers(
        self,
        file_path: str,
        content: Optional[Union[str, bytes]] = None,
        cache_type: Optional[CacheType] = None
    ) -> CacheHeaders:
        """Generate complete cache headers for a file."""
        
        # Determine cache type if not provided
        if cache_type is None:
            cache_type = self.cache_config_system.get_cache_type_for_path(file_path)
            
        # Get cache configuration
        config = self.cache_config_system.get_config(cache_type)
        
        # Generate ETag
        etag = None
        if content is not None:
            etag = ETagGenerator.generate_etag(content)
        elif Path(file_path).exists():
            etag = ETagGenerator.generate_file_etag(file_path)
            
        # Generate Last-Modified
        last_modified = None
        if Path(file_path).exists():
            last_modified = LastModifiedGenerator.generate_file_last_modified(file_path)
        else:
            last_modified = LastModifiedGenerator.generate_last_modified()
            
        # Generate Expires header for immutable content
        expires = None
        if config.immutable:
            expires_time = datetime.utcnow() + timedelta(seconds=config.max_age_seconds)
            expires = expires_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
        return CacheHeaders(
            cache_control=config.to_cache_control_header(),
            etag=etag,
            last_modified=last_modified,
            expires=expires,
            vary="Accept-Encoding"  # Always vary on encoding for compressed content
        )
    
    def generate_headers_for_content(
        self,
        content: Union[str, bytes],
        content_type: str,
        cache_type: CacheType
    ) -> CacheHeaders:
        """Generate cache headers for in-memory content."""
        
        # Get cache configuration
        config = self.cache_config_system.get_config(cache_type)
        
        # Generate ETag from content
        etag = ETagGenerator.generate_etag(content)
        
        # Generate Last-Modified as current time
        last_modified = LastModifiedGenerator.generate_last_modified()
        
        # Generate Expires header for immutable content
        expires = None
        if config.immutable:
            expires_time = datetime.utcnow() + timedelta(seconds=config.max_age_seconds)
            expires = expires_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
        return CacheHeaders(
            cache_control=config.to_cache_control_header(),
            etag=etag,
            last_modified=last_modified,
            expires=expires,
            vary="Accept-Encoding"
        )


def create_cache_configuration_system() -> CacheConfigurationSystem:
    """Factory function to create a cache configuration system."""
    return CacheConfigurationSystem()


def create_cache_header_generator(
    cache_config_system: Optional[CacheConfigurationSystem] = None
) -> CacheHeaderGenerator:
    """Factory function to create a cache header generator."""
    if cache_config_system is None:
        cache_config_system = create_cache_configuration_system()
    return CacheHeaderGenerator(cache_config_system)

class ContentCompressor:
    """Content compression system supporting Gzip and Brotli."""
    
    def __init__(self, config: CompressionConfig):
        self.config = config
        
    def should_compress(self, content: bytes, content_type: str) -> bool:
        """Determine if content should be compressed."""
        if not self.config.enabled:
            return False
            
        # Check minimum size threshold
        if len(content) < self.config.min_size_bytes:
            return False
            
        # Check if content type is compressible
        return any(mime_type in content_type for mime_type in self.config.mime_types)
    
    def compress_gzip(self, content: bytes) -> bytes:
        """Compress content using Gzip."""
        return gzip.compress(content, compresslevel=self.config.gzip_level)
    
    def compress_brotli(self, content: bytes) -> bytes:
        """Compress content using Brotli."""
        if not BROTLI_AVAILABLE:
            raise ImportError("Brotli compression not available. Install brotli package.")
        return brotli.compress(content, quality=self.config.brotli_level)
    
    def compress_content(
        self,
        content: Union[str, bytes],
        content_type: str,
        compression_type: CompressionType = CompressionType.GZIP
    ) -> Tuple[bytes, Optional[str], float]:
        """
        Compress content and return compressed data, encoding, and compression ratio.
        
        Returns:
            Tuple of (compressed_content, encoding_header, compression_ratio)
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
            
        if not self.should_compress(content, content_type):
            return content, None, 1.0
            
        original_size = len(content)
        
        if compression_type == CompressionType.GZIP:
            compressed = self.compress_gzip(content)
            encoding = "gzip"
        elif compression_type == CompressionType.BROTLI:
            compressed = self.compress_brotli(content)
            encoding = "br"
        else:
            return content, None, 1.0
            
        compressed_size = len(compressed)
        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
        
        return compressed, encoding, compression_ratio


class AssetOptimizer:
    """Asset optimization system for images and other static content."""
    
    def __init__(self):
        self.supported_image_types = {'.jpg', '.jpeg', '.png', '.webp'}
        
    def should_optimize(self, file_path: str) -> bool:
        """Determine if asset should be optimized."""
        return Path(file_path).suffix.lower() in self.supported_image_types
    
    def optimize_image(self, file_path: str, quality: int = 85) -> Optional[bytes]:
        """
        Optimize image file (placeholder implementation).
        
        In a real implementation, this would use libraries like Pillow or ImageIO
        to resize, compress, and optimize images.
        """
        path = Path(file_path)
        
        if not path.exists() or not self.should_optimize(file_path):
            return None
            
        # Placeholder: In real implementation, would optimize the image
        # For now, just return the original content
        return path.read_bytes()
    
    def generate_responsive_variants(
        self,
        file_path: str,
        sizes: List[Tuple[int, int]] = None
    ) -> Dict[str, bytes]:
        """
        Generate responsive image variants (placeholder implementation).
        
        Returns dictionary mapping size descriptors to optimized image data.
        """
        if sizes is None:
            sizes = [(1920, 1080), (1280, 720), (640, 360)]
            
        variants = {}
        original_content = self.optimize_image(file_path)
        
        if original_content is None:
            return variants
            
        # Placeholder: In real implementation, would generate actual variants
        for width, height in sizes:
            size_key = f"{width}x{height}"
            variants[size_key] = original_content
            
        return variants


class AssetBundler:
    """Asset bundling and minification system."""
    
    def __init__(self):
        self.css_extensions = {'.css'}
        self.js_extensions = {'.js'}
        
    def should_minify(self, file_path: str) -> bool:
        """Determine if file should be minified."""
        suffix = Path(file_path).suffix.lower()
        return suffix in self.css_extensions or suffix in self.js_extensions
    
    def minify_css(self, content: str) -> str:
        """
        Minify CSS content (basic implementation).
        
        In production, would use a proper CSS minifier.
        """
        # Basic minification: remove comments and extra whitespace
        import re
        
        # Remove CSS comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r';\s*}', '}', content)
        content = re.sub(r'{\s*', '{', content)
        content = re.sub(r'}\s*', '}', content)
        content = re.sub(r':\s*', ':', content)
        content = re.sub(r';\s*', ';', content)
        
        return content.strip()
    
    def minify_js(self, content: str) -> str:
        """
        Minify JavaScript content (basic implementation).
        
        In production, would use a proper JS minifier like UglifyJS or Terser.
        """
        # Basic minification: remove comments and extra whitespace
        import re
        
        # Remove single-line comments (but preserve URLs)
        content = re.sub(r'(?<!:)//.*$', '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
    
    def minify_content(self, content: str, file_path: str) -> str:
        """Minify content based on file type."""
        if not self.should_minify(file_path):
            return content
            
        suffix = Path(file_path).suffix.lower()
        
        if suffix in self.css_extensions:
            return self.minify_css(content)
        elif suffix in self.js_extensions:
            return self.minify_js(content)
        else:
            return content
    
    def bundle_assets(
        self,
        asset_paths: List[str],
        bundle_type: str = 'css'
    ) -> str:
        """Bundle multiple assets into a single file."""
        bundled_content = []
        
        for asset_path in asset_paths:
            path = Path(asset_path)
            if path.exists():
                content = path.read_text(encoding='utf-8')
                minified = self.minify_content(content, asset_path)
                bundled_content.append(minified)
                
        return '\n'.join(bundled_content)


def create_compression_config(
    gzip_level: int = 6,
    brotli_level: int = 6,
    min_size_bytes: int = 1024
) -> CompressionConfig:
    """Factory function to create compression configuration."""
    return CompressionConfig(
        enabled=True,
        gzip_level=gzip_level,
        brotli_level=brotli_level,
        min_size_bytes=min_size_bytes
    )


def create_content_compressor(config: Optional[CompressionConfig] = None) -> ContentCompressor:
    """Factory function to create content compressor."""
    if config is None:
        config = create_compression_config()
    return ContentCompressor(config)


def create_asset_optimizer() -> AssetOptimizer:
    """Factory function to create asset optimizer."""
    return AssetOptimizer()


def create_asset_bundler() -> AssetBundler:
    """Factory function to create asset bundler."""
    return AssetBundler()
class CDNManager:
    """
    Main CDN Manager class integrating cache configuration, compression, and optimization.
    
    This class provides the primary interface for CDN management operations including:
    - Cache header generation with TTL management
    - Content compression (Gzip and Brotli)
    - Asset optimization and bundling
    - Performance monitoring
    """
    
    def __init__(
        self,
        cache_config_system: Optional[CacheConfigurationSystem] = None,
        compression_config: Optional[CompressionConfig] = None
    ):
        self.cache_config_system = cache_config_system or create_cache_configuration_system()
        self.cache_header_generator = CacheHeaderGenerator(self.cache_config_system)
        self.content_compressor = ContentCompressor(compression_config or create_compression_config())
        self.asset_optimizer = AssetOptimizer()
        self.asset_bundler = AssetBundler()
        
    def optimize_asset(
        self,
        file_path: str,
        content: Optional[Union[str, bytes]] = None,
        enable_compression: bool = True,
        compression_type: CompressionType = CompressionType.GZIP
    ) -> OptimizedAsset:
        """
        Optimize an asset with compression and cache headers.
        
        Args:
            file_path: Path to the asset file
            content: Optional content (if not provided, reads from file)
            enable_compression: Whether to apply compression
            compression_type: Type of compression to use
            
        Returns:
            OptimizedAsset with compressed content and cache headers
        """
        path = Path(file_path)
        
        # Get content
        if content is None:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            content = path.read_bytes()
        elif isinstance(content, str):
            content = content.encode('utf-8')
            
        original_size = len(content)
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'
            
        # Apply asset-specific optimizations
        if self.asset_optimizer.should_optimize(file_path):
            optimized_content = self.asset_optimizer.optimize_image(file_path)
            if optimized_content is not None:
                content = optimized_content
                
        # Apply minification for CSS/JS
        if self.asset_bundler.should_minify(file_path):
            content_str = content.decode('utf-8')
            minified = self.asset_bundler.minify_content(content_str, file_path)
            content = minified.encode('utf-8')
            
        # Apply compression
        encoding = None
        compression_ratio = 1.0
        
        if enable_compression:
            compressed_content, encoding, compression_ratio = self.content_compressor.compress_content(
                content, content_type, compression_type
            )
            content = compressed_content
            
        # Generate cache headers
        cache_type = self.cache_config_system.get_cache_type_for_path(file_path)
        headers = self.cache_header_generator.generate_headers_for_content(
            content, content_type, cache_type
        )
        
        # Add encoding header if compressed
        if encoding:
            headers_dict = headers.to_dict()
            headers_dict['Content-Encoding'] = encoding
            headers = CacheHeaders(
                cache_control=headers.cache_control,
                etag=headers.etag,
                last_modified=headers.last_modified,
                expires=headers.expires,
                vary=headers.vary
            )
            
        return OptimizedAsset(
            content=content,
            content_type=content_type,
            encoding=encoding,
            headers=headers,
            original_size=original_size,
            compressed_size=len(content),
            compression_ratio=compression_ratio
        )
    
    def optimize_html_page(
        self,
        html_content: str,
        page_path: str = "index.html",
        enable_compression: bool = True
    ) -> OptimizedAsset:
        """Optimize HTML page with compression and cache headers."""
        return self.optimize_asset(
            page_path,
            content=html_content,
            enable_compression=enable_compression,
            compression_type=CompressionType.GZIP
        )
    
    def optimize_json_data(
        self,
        json_data: Union[str, Dict, List],
        file_path: str = "data.json",
        enable_compression: bool = True
    ) -> OptimizedAsset:
        """Optimize JSON data with compression and cache headers."""
        if isinstance(json_data, (dict, list)):
            json_content = json.dumps(json_data, separators=(',', ':'))
        else:
            json_content = json_data
            
        return self.optimize_asset(
            file_path,
            content=json_content,
            enable_compression=enable_compression,
            compression_type=CompressionType.GZIP
        )
    
    def optimize_feed(
        self,
        feed_content: str,
        feed_path: str = "feed.xml",
        enable_compression: bool = True
    ) -> OptimizedAsset:
        """Optimize RSS/XML feed with compression and cache headers."""
        return self.optimize_asset(
            feed_path,
            content=feed_content,
            enable_compression=enable_compression,
            compression_type=CompressionType.GZIP
        )
    
    def bundle_and_optimize_assets(
        self,
        asset_paths: List[str],
        bundle_name: str,
        bundle_type: str = 'css'
    ) -> OptimizedAsset:
        """Bundle multiple assets and optimize the result."""
        bundled_content = self.asset_bundler.bundle_assets(asset_paths, bundle_type)
        bundle_path = f"{bundle_name}.{bundle_type}"
        
        return self.optimize_asset(
            bundle_path,
            content=bundled_content,
            enable_compression=True
        )
    
    def get_cache_headers_for_file(self, file_path: str) -> CacheHeaders:
        """Get cache headers for a file without optimization."""
        return self.cache_header_generator.generate_headers(file_path)
    
    def configure_cache_type(self, cache_type: CacheType, config: CacheConfig) -> None:
        """Configure cache settings for a specific content type."""
        self.cache_config_system.set_config(cache_type, config)
    
    def get_compression_stats(self, assets: List[OptimizedAsset]) -> Dict[str, Any]:
        """Get compression statistics for a list of optimized assets."""
        total_original = sum(asset.original_size for asset in assets)
        total_compressed = sum(asset.compressed_size for asset in assets)
        
        return {
            'total_assets': len(assets),
            'total_original_size': total_original,
            'total_compressed_size': total_compressed,
            'total_savings_bytes': total_original - total_compressed,
            'total_savings_percent': ((total_original - total_compressed) / total_original * 100) if total_original > 0 else 0,
            'average_compression_ratio': sum(asset.compression_ratio for asset in assets) / len(assets) if assets else 1.0,
            'compressed_assets': sum(1 for asset in assets if asset.encoding is not None)
        }


def create_cdn_manager(
    cache_config_system: Optional[CacheConfigurationSystem] = None,
    compression_config: Optional[CompressionConfig] = None
) -> CDNManager:
    """Factory function to create CDN Manager."""
    return CDNManager(cache_config_system, compression_config)

class InvalidationType(Enum):
    """Types of cache invalidation operations."""
    SELECTIVE = "selective"
    WILDCARD = "wildcard"
    FULL_PURGE = "full_purge"
    TAG_BASED = "tag_based"


@dataclass
class InvalidationRequest:
    """Request for cache invalidation."""
    paths: List[str]
    invalidation_type: InvalidationType
    tags: Optional[List[str]] = None
    reason: Optional[str] = None
    priority: int = 0  # Higher numbers = higher priority
    
    
@dataclass
class InvalidationResult:
    """Result of cache invalidation operation."""
    request_id: str
    status: str  # pending, completed, failed
    invalidated_paths: List[str]
    failed_paths: List[str]
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class CacheWarmingRequest:
    """Request for cache warming."""
    urls: List[str]
    priority: int = 0
    user_agents: List[str] = field(default_factory=lambda: ['CDN-Warmer/1.0'])
    
    
@dataclass
class CacheWarmingResult:
    """Result of cache warming operation."""
    request_id: str
    warmed_urls: List[str]
    failed_urls: List[str]
    total_time_seconds: float
    average_response_time_ms: float


class CDNProviderInterface:
    """Interface for CDN provider integrations."""
    
    def purge_paths(self, paths: List[str]) -> InvalidationResult:
        """Purge specific paths from CDN cache."""
        raise NotImplementedError
    
    def purge_tags(self, tags: List[str]) -> InvalidationResult:
        """Purge cache entries by tags."""
        raise NotImplementedError
    
    def purge_all(self) -> InvalidationResult:
        """Purge entire CDN cache."""
        raise NotImplementedError
    
    def warm_cache(self, urls: List[str]) -> CacheWarmingResult:
        """Warm CDN cache by requesting URLs."""
        raise NotImplementedError


class CloudflareCDNProvider(CDNProviderInterface):
    """Cloudflare CDN provider implementation."""
    
    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        
    def purge_paths(self, paths: List[str]) -> InvalidationResult:
        """Purge specific paths from Cloudflare cache."""
        import uuid
        import requests
        
        request_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json'
            }
            
            # Cloudflare expects full URLs, not just paths
            # In real implementation, would construct full URLs
            data = {
                'files': paths[:30]  # Cloudflare limit is 30 URLs per request
            }
            
            url = f"{self.base_url}/zones/{self.zone_id}/purge_cache"
            
            # Placeholder for actual API call
            # response = requests.post(url, json=data, headers=headers)
            
            # Simulate successful response
            return InvalidationResult(
                request_id=request_id,
                status="completed",
                invalidated_paths=paths,
                failed_paths=[],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            return InvalidationResult(
                request_id=request_id,
                status="failed",
                invalidated_paths=[],
                failed_paths=paths,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    def purge_tags(self, tags: List[str]) -> InvalidationResult:
        """Purge cache entries by tags."""
        import uuid
        
        request_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        try:
            # Placeholder implementation
            return InvalidationResult(
                request_id=request_id,
                status="completed",
                invalidated_paths=[],  # Tag-based purging doesn't return specific paths
                failed_paths=[],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            return InvalidationResult(
                request_id=request_id,
                status="failed",
                invalidated_paths=[],
                failed_paths=[],
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    def purge_all(self) -> InvalidationResult:
        """Purge entire Cloudflare cache."""
        import uuid
        
        request_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        try:
            # Placeholder implementation
            return InvalidationResult(
                request_id=request_id,
                status="completed",
                invalidated_paths=["*"],
                failed_paths=[],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            return InvalidationResult(
                request_id=request_id,
                status="failed",
                invalidated_paths=[],
                failed_paths=["*"],
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    def warm_cache(self, urls: List[str]) -> CacheWarmingResult:
        """Warm cache by making HTTP requests."""
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        warmed_urls = []
        failed_urls = []
        response_times = []
        
        for url in urls:
            try:
                # Placeholder for actual HTTP request
                # In real implementation, would make actual requests
                request_start = time.time()
                
                # Simulate request
                time.sleep(0.01)  # Simulate network delay
                
                request_time = (time.time() - request_start) * 1000  # Convert to ms
                response_times.append(request_time)
                warmed_urls.append(url)
                
            except Exception:
                failed_urls.append(url)
        
        total_time = time.time() - start_time
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return CacheWarmingResult(
            request_id=request_id,
            warmed_urls=warmed_urls,
            failed_urls=failed_urls,
            total_time_seconds=total_time,
            average_response_time_ms=avg_response_time
        )


class CacheInvalidationSystem:
    """System for managing cache invalidation and warming operations."""
    
    def __init__(self, cdn_provider: CDNProviderInterface):
        self.cdn_provider = cdn_provider
        self.invalidation_history: List[InvalidationResult] = []
        self.warming_history: List[CacheWarmingResult] = []
        
    def invalidate_paths(
        self,
        paths: List[str],
        reason: Optional[str] = None,
        priority: int = 0
    ) -> InvalidationResult:
        """Invalidate specific paths."""
        request = InvalidationRequest(
            paths=paths,
            invalidation_type=InvalidationType.SELECTIVE,
            reason=reason,
            priority=priority
        )
        
        result = self.cdn_provider.purge_paths(paths)
        self.invalidation_history.append(result)
        
        logger.info(f"Cache invalidation completed: {result.request_id}, "
                   f"invalidated {len(result.invalidated_paths)} paths")
        
        return result
    
    def invalidate_by_tags(
        self,
        tags: List[str],
        reason: Optional[str] = None
    ) -> InvalidationResult:
        """Invalidate cache entries by tags."""
        request = InvalidationRequest(
            paths=[],
            invalidation_type=InvalidationType.TAG_BASED,
            tags=tags,
            reason=reason
        )
        
        result = self.cdn_provider.purge_tags(tags)
        self.invalidation_history.append(result)
        
        logger.info(f"Tag-based cache invalidation completed: {result.request_id}")
        
        return result
    
    def invalidate_content_update(
        self,
        episode_id: str,
        updated_content_types: List[str]
    ) -> List[InvalidationResult]:
        """Invalidate cache for content updates."""
        results = []
        
        # Build paths to invalidate based on content types
        paths_to_invalidate = []
        
        if 'episode' in updated_content_types:
            paths_to_invalidate.extend([
                f"/episodes/{episode_id}.html",
                f"/episodes/{episode_id}/",
                f"/api/episodes/{episode_id}.json"
            ])
        
        if 'transcript' in updated_content_types:
            paths_to_invalidate.extend([
                f"/transcripts/{episode_id}.vtt",
                f"/transcripts/{episode_id}.txt"
            ])
        
        if 'feeds' in updated_content_types:
            paths_to_invalidate.extend([
                "/feed.xml",
                "/sitemap.xml",
                "/sitemap-videos.xml"
            ])
        
        if paths_to_invalidate:
            result = self.invalidate_paths(
                paths_to_invalidate,
                reason=f"Content update for episode {episode_id}"
            )
            results.append(result)
        
        return results
    
    def invalidate_series_update(self, series_id: str) -> List[InvalidationResult]:
        """Invalidate cache for series updates."""
        paths_to_invalidate = [
            f"/series/{series_id}.html",
            f"/series/{series_id}/",
            f"/api/series/{series_id}.json",
            f"/feeds/{series_id}.xml",
            "/",  # Home page may show series info
            "/series/",  # Series index page
        ]
        
        result = self.invalidate_paths(
            paths_to_invalidate,
            reason=f"Series update for {series_id}"
        )
        
        return [result]
    
    def warm_critical_paths(self, base_url: str) -> CacheWarmingResult:
        """Warm cache for critical content paths."""
        critical_urls = [
            f"{base_url}/",
            f"{base_url}/episodes/",
            f"{base_url}/series/",
            f"{base_url}/feed.xml",
            f"{base_url}/sitemap.xml"
        ]
        
        result = self.cdn_provider.warm_cache(critical_urls)
        self.warming_history.append(result)
        
        logger.info(f"Cache warming completed: {result.request_id}, "
                   f"warmed {len(result.warmed_urls)} URLs")
        
        return result
    
    def warm_episode_content(self, base_url: str, episode_ids: List[str]) -> CacheWarmingResult:
        """Warm cache for specific episodes."""
        episode_urls = []
        
        for episode_id in episode_ids:
            episode_urls.extend([
                f"{base_url}/episodes/{episode_id}.html",
                f"{base_url}/api/episodes/{episode_id}.json"
            ])
        
        result = self.cdn_provider.warm_cache(episode_urls)
        self.warming_history.append(result)
        
        return result
    
    def get_invalidation_stats(self) -> Dict[str, Any]:
        """Get statistics about cache invalidation operations."""
        if not self.invalidation_history:
            return {
                'total_invalidations': 0,
                'successful_invalidations': 0,
                'failed_invalidations': 0,
                'success_rate': 0.0
            }
        
        successful = sum(1 for result in self.invalidation_history if result.status == 'completed')
        failed = sum(1 for result in self.invalidation_history if result.status == 'failed')
        
        return {
            'total_invalidations': len(self.invalidation_history),
            'successful_invalidations': successful,
            'failed_invalidations': failed,
            'success_rate': (successful / len(self.invalidation_history)) * 100,
            'total_paths_invalidated': sum(len(result.invalidated_paths) for result in self.invalidation_history)
        }


def create_cloudflare_cdn_provider(api_token: str, zone_id: str) -> CloudflareCDNProvider:
    """Factory function to create Cloudflare CDN provider."""
    return CloudflareCDNProvider(api_token, zone_id)


def create_cache_invalidation_system(cdn_provider: CDNProviderInterface) -> CacheInvalidationSystem:
    """Factory function to create cache invalidation system."""
    return CacheInvalidationSystem(cdn_provider)
@dataclass

class PerformanceMetrics:
    """Performance metrics for CDN operations."""
    cache_hit_rate: float
    average_response_time_ms: float
    bandwidth_saved_bytes: int
    compression_ratio: float
    total_requests: int
    cached_requests: int
    
    
class PerformanceMonitor:
    """Monitor CDN performance metrics."""
    
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.request_log: List[Dict[str, Any]] = []
        
    def record_request(
        self,
        path: str,
        cache_hit: bool,
        response_time_ms: float,
        bytes_served: int,
        compression_ratio: float = 1.0
    ) -> None:
        """Record a request for performance tracking."""
        self.request_log.append({
            'timestamp': datetime.utcnow(),
            'path': path,
            'cache_hit': cache_hit,
            'response_time_ms': response_time_ms,
            'bytes_served': bytes_served,
            'compression_ratio': compression_ratio
        })
        
        # Keep only recent requests (last 10000)
        if len(self.request_log) > 10000:
            self.request_log = self.request_log[-10000:]
    
    def calculate_current_metrics(self) -> PerformanceMetrics:
        """Calculate current performance metrics."""
        if not self.request_log:
            return PerformanceMetrics(
                cache_hit_rate=0.0,
                average_response_time_ms=0.0,
                bandwidth_saved_bytes=0,
                compression_ratio=1.0,
                total_requests=0,
                cached_requests=0
            )
        
        total_requests = len(self.request_log)
        cached_requests = sum(1 for req in self.request_log if req['cache_hit'])
        cache_hit_rate = (cached_requests / total_requests) * 100
        
        avg_response_time = sum(req['response_time_ms'] for req in self.request_log) / total_requests
        
        total_bytes = sum(req['bytes_served'] for req in self.request_log)
        total_compressed_bytes = sum(
            req['bytes_served'] * req['compression_ratio'] for req in self.request_log
        )
        bandwidth_saved = total_bytes - total_compressed_bytes
        
        avg_compression_ratio = sum(req['compression_ratio'] for req in self.request_log) / total_requests
        
        return PerformanceMetrics(
            cache_hit_rate=cache_hit_rate,
            average_response_time_ms=avg_response_time,
            bandwidth_saved_bytes=int(bandwidth_saved),
            compression_ratio=avg_compression_ratio,
            total_requests=total_requests,
            cached_requests=cached_requests
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        metrics = self.calculate_current_metrics()
        
        # Calculate trends if we have historical data
        trend_data = {}
        if len(self.metrics_history) >= 2:
            previous_metrics = self.metrics_history[-2]
            current_metrics = self.metrics_history[-1]
            
            trend_data = {
                'cache_hit_rate_trend': current_metrics.cache_hit_rate - previous_metrics.cache_hit_rate,
                'response_time_trend': current_metrics.average_response_time_ms - previous_metrics.average_response_time_ms,
                'bandwidth_savings_trend': current_metrics.bandwidth_saved_bytes - previous_metrics.bandwidth_saved_bytes
            }
        
        return {
            'current_metrics': {
                'cache_hit_rate_percent': metrics.cache_hit_rate,
                'average_response_time_ms': metrics.average_response_time_ms,
                'bandwidth_saved_mb': metrics.bandwidth_saved_bytes / (1024 * 1024),
                'compression_ratio': metrics.compression_ratio,
                'total_requests': metrics.total_requests,
                'cached_requests': metrics.cached_requests
            },
            'trends': trend_data,
            'recommendations': self._generate_recommendations(metrics)
        }
    
    def _generate_recommendations(self, metrics: PerformanceMetrics) -> List[str]:
        """Generate performance recommendations based on metrics."""
        recommendations = []
        
        if metrics.cache_hit_rate < 80:
            recommendations.append("Cache hit rate is below 80%. Consider increasing cache TTL for static assets.")
        
        if metrics.average_response_time_ms > 500:
            recommendations.append("Average response time is high. Consider enabling more aggressive compression.")
        
        if metrics.compression_ratio > 0.8:
            recommendations.append("Compression ratio could be improved. Enable Brotli compression for better results.")
        
        if metrics.total_requests > 0 and metrics.bandwidth_saved_bytes / metrics.total_requests < 1024:
            recommendations.append("Low bandwidth savings per request. Review compression settings.")
        
        return recommendations


# Enhanced CDN Manager with invalidation and monitoring
class EnhancedCDNManager(CDNManager):
    """
    Enhanced CDN Manager with cache invalidation and performance monitoring.
    
    Extends the base CDN Manager with:
    - Cache invalidation system
    - Performance monitoring
    - Advanced cache management
    """
    
    def __init__(
        self,
        cache_config_system: Optional[CacheConfigurationSystem] = None,
        compression_config: Optional[CompressionConfig] = None,
        cdn_provider: Optional[CDNProviderInterface] = None
    ):
        super().__init__(cache_config_system, compression_config)
        
        self.invalidation_system = None
        if cdn_provider:
            self.invalidation_system = CacheInvalidationSystem(cdn_provider)
            
        self.performance_monitor = PerformanceMonitor()
        
    def set_cdn_provider(self, cdn_provider: CDNProviderInterface) -> None:
        """Set CDN provider for invalidation operations."""
        self.invalidation_system = CacheInvalidationSystem(cdn_provider)
    
    def invalidate_content_cache(
        self,
        content_type: str,
        content_id: str,
        updated_assets: List[str] = None
    ) -> List[InvalidationResult]:
        """Invalidate cache for updated content."""
        if not self.invalidation_system:
            logger.warning("No CDN provider configured for cache invalidation")
            return []
        
        if content_type == 'episode':
            return self.invalidation_system.invalidate_content_update(content_id, updated_assets or ['episode'])
        elif content_type == 'series':
            return self.invalidation_system.invalidate_series_update(content_id)
        else:
            # Generic path invalidation
            paths = [f"/{content_type}/{content_id}.html", f"/api/{content_type}/{content_id}.json"]
            return [self.invalidation_system.invalidate_paths(paths, f"{content_type} update")]
    
    def warm_content_cache(self, base_url: str, content_ids: List[str] = None) -> CacheWarmingResult:
        """Warm cache for content."""
        if not self.invalidation_system:
            logger.warning("No CDN provider configured for cache warming")
            return CacheWarmingResult("", [], [], 0.0, 0.0)
        
        if content_ids:
            return self.invalidation_system.warm_episode_content(base_url, content_ids)
        else:
            return self.invalidation_system.warm_critical_paths(base_url)
    
    def record_request_metrics(
        self,
        path: str,
        cache_hit: bool,
        response_time_ms: float,
        bytes_served: int,
        compression_ratio: float = 1.0
    ) -> None:
        """Record request metrics for performance monitoring."""
        self.performance_monitor.record_request(
            path, cache_hit, response_time_ms, bytes_served, compression_ratio
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        report = self.performance_monitor.get_performance_report()
        
        # Add invalidation statistics if available
        if self.invalidation_system:
            report['invalidation_stats'] = self.invalidation_system.get_invalidation_stats()
        
        return report
    
    def optimize_and_deploy_content(
        self,
        content_bundle: Dict[str, Union[str, bytes]],
        base_url: str,
        invalidate_existing: bool = True
    ) -> Dict[str, OptimizedAsset]:
        """Optimize content bundle and optionally invalidate existing cache."""
        optimized_assets = {}
        paths_to_invalidate = []
        
        # Optimize each asset in the bundle
        for file_path, content in content_bundle.items():
            optimized_asset = self.optimize_asset(file_path, content)
            optimized_assets[file_path] = optimized_asset
            
            # Track paths for invalidation
            if invalidate_existing:
                paths_to_invalidate.append(f"/{file_path}")
        
        # Invalidate existing cache
        if invalidate_existing and self.invalidation_system and paths_to_invalidate:
            self.invalidation_system.invalidate_paths(
                paths_to_invalidate,
                reason="Content deployment"
            )
        
        # Warm cache for new content
        if self.invalidation_system:
            urls_to_warm = [f"{base_url}/{path}" for path in content_bundle.keys()]
            self.invalidation_system.cdn_provider.warm_cache(urls_to_warm)
        
        return optimized_assets


def create_enhanced_cdn_manager(
    cache_config_system: Optional[CacheConfigurationSystem] = None,
    compression_config: Optional[CompressionConfig] = None,
    cdn_provider: Optional[CDNProviderInterface] = None
) -> EnhancedCDNManager:
    """Factory function to create enhanced CDN Manager."""
    return EnhancedCDNManager(cache_config_system, compression_config, cdn_provider)