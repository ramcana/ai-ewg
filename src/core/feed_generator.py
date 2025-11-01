"""
Feed Generator for Content Publishing Platform

Implements RSS feed and XML sitemap generation for episodes, series, and hosts.
Provides site-wide feeds, per-series feeds, standard sitemaps, video sitemaps,
and news sitemaps with proper validation and caching mechanisms.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from urllib.parse import urljoin, quote
from dataclasses import dataclass, field
import hashlib

from .publishing_models import (
    Episode, Series, Host, ValidationResult, ValidationError, 
    ValidationWarning, ErrorType, Severity
)
from .content_registry import ContentRegistry


@dataclass
class RSSFeed:
    """RSS feed data structure"""
    title: str
    description: str
    link: str
    language: str = "en-US"
    copyright: Optional[str] = None
    managing_editor: Optional[str] = None
    webmaster: Optional[str] = None
    pub_date: Optional[datetime] = None
    last_build_date: Optional[datetime] = None
    generator: str = "Content Publishing Platform Feed Generator"
    items: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_xml(self) -> str:
        """Convert RSS feed to XML string"""
        # Create RSS root element
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:media", "http://search.yahoo.com/mrss/")
        
        # Create channel element
        channel = ET.SubElement(rss, "channel")
        
        # Add channel metadata
        ET.SubElement(channel, "title").text = self.title
        ET.SubElement(channel, "description").text = self.description
        ET.SubElement(channel, "link").text = self.link
        ET.SubElement(channel, "language").text = self.language
        ET.SubElement(channel, "generator").text = self.generator
        
        if self.copyright:
            ET.SubElement(channel, "copyright").text = self.copyright
        
        if self.managing_editor:
            ET.SubElement(channel, "managingEditor").text = self.managing_editor
        
        if self.webmaster:
            ET.SubElement(channel, "webMaster").text = self.webmaster
        
        if self.pub_date:
            ET.SubElement(channel, "pubDate").text = self._format_rfc822_date(self.pub_date)
        
        if self.last_build_date:
            ET.SubElement(channel, "lastBuildDate").text = self._format_rfc822_date(self.last_build_date)
        
        # Add items
        for item_data in self.items:
            item = ET.SubElement(channel, "item")
            
            # Required fields
            ET.SubElement(item, "title").text = item_data["title"]
            ET.SubElement(item, "description").text = item_data["description"]
            ET.SubElement(item, "link").text = item_data["link"]
            ET.SubElement(item, "guid").text = item_data["guid"]
            
            # Optional fields
            if "pub_date" in item_data:
                ET.SubElement(item, "pubDate").text = self._format_rfc822_date(item_data["pub_date"])
            
            if "author" in item_data:
                ET.SubElement(item, "author").text = item_data["author"]
            
            if "category" in item_data:
                for category in item_data["category"]:
                    ET.SubElement(item, "category").text = category
            
            # Media enclosure for video/audio content
            if "enclosure" in item_data:
                enclosure = ET.SubElement(item, "enclosure")
                enclosure.set("url", item_data["enclosure"]["url"])
                enclosure.set("type", item_data["enclosure"]["type"])
                if "length" in item_data["enclosure"]:
                    enclosure.set("length", str(item_data["enclosure"]["length"]))
            
            # Media namespace elements for rich media
            if "media_content" in item_data:
                media_content = ET.SubElement(item, "media:content")
                media_content.set("url", item_data["media_content"]["url"])
                media_content.set("type", item_data["media_content"]["type"])
                if "duration" in item_data["media_content"]:
                    media_content.set("duration", str(item_data["media_content"]["duration"]))
            
            if "media_thumbnail" in item_data:
                media_thumb = ET.SubElement(item, "media:thumbnail")
                media_thumb.set("url", item_data["media_thumbnail"])
        
        # Convert to string with proper formatting
        ET.indent(rss, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode")
    
    def _format_rfc822_date(self, dt: datetime) -> str:
        """Format datetime as RFC 822 date string for RSS"""
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z") or dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


@dataclass
class XMLSitemap:
    """XML sitemap data structure"""
    urls: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_url(self, loc: str, lastmod: Optional[datetime] = None, 
                changefreq: Optional[str] = None, priority: Optional[float] = None,
                **kwargs) -> None:
        """Add URL to sitemap"""
        url_data = {"loc": loc}
        
        if lastmod:
            url_data["lastmod"] = lastmod.strftime("%Y-%m-%d")
        
        if changefreq:
            url_data["changefreq"] = changefreq
        
        if priority is not None:
            url_data["priority"] = str(priority)
        
        # Add any additional attributes (for video sitemaps, etc.)
        url_data.update(kwargs)
        
        self.urls.append(url_data)
    
    def to_xml(self) -> str:
        """Convert sitemap to XML string"""
        # Create urlset root element
        urlset = ET.Element("urlset")
        urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
        urlset.set("xmlns:video", "http://www.google.com/schemas/sitemap-video/1.1")
        urlset.set("xmlns:news", "http://www.google.com/schemas/sitemap-news/0.9")
        
        # Add URLs
        for url_data in self.urls:
            url_elem = ET.SubElement(urlset, "url")
            
            # Basic URL elements
            ET.SubElement(url_elem, "loc").text = url_data["loc"]
            
            if "lastmod" in url_data:
                ET.SubElement(url_elem, "lastmod").text = url_data["lastmod"]
            
            if "changefreq" in url_data:
                ET.SubElement(url_elem, "changefreq").text = url_data["changefreq"]
            
            if "priority" in url_data:
                ET.SubElement(url_elem, "priority").text = url_data["priority"]
            
            # Video sitemap elements
            if "video" in url_data:
                video_elem = ET.SubElement(url_elem, "video:video")
                video_data = url_data["video"]
                
                ET.SubElement(video_elem, "video:thumbnail_loc").text = video_data["thumbnail_loc"]
                ET.SubElement(video_elem, "video:title").text = video_data["title"]
                ET.SubElement(video_elem, "video:description").text = video_data["description"]
                
                if "content_loc" in video_data:
                    ET.SubElement(video_elem, "video:content_loc").text = video_data["content_loc"]
                
                if "duration" in video_data:
                    ET.SubElement(video_elem, "video:duration").text = str(video_data["duration"])
                
                if "publication_date" in video_data:
                    ET.SubElement(video_elem, "video:publication_date").text = video_data["publication_date"]
                
                if "tags" in video_data:
                    for tag in video_data["tags"]:
                        ET.SubElement(video_elem, "video:tag").text = tag
            
            # News sitemap elements
            if "news" in url_data:
                news_elem = ET.SubElement(url_elem, "news:news")
                news_data = url_data["news"]
                
                publication_elem = ET.SubElement(news_elem, "news:publication")
                ET.SubElement(publication_elem, "news:name").text = news_data["publication_name"]
                ET.SubElement(publication_elem, "news:language").text = news_data["language"]
                
                ET.SubElement(news_elem, "news:publication_date").text = news_data["publication_date"]
                ET.SubElement(news_elem, "news:title").text = news_data["title"]
        
        # Convert to string with proper formatting
        ET.indent(urlset, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(urlset, encoding="unicode")


@dataclass
class FeedCache:
    """Feed caching mechanism"""
    cache_dir: Path
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    
    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_key(self, feed_type: str, identifier: str = "") -> str:
        """Generate cache key for feed"""
        key_string = f"{feed_type}_{identifier}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def is_cached(self, cache_key: str) -> bool:
        """Check if feed is cached and still valid"""
        cache_file = self.cache_dir / f"{cache_key}.xml"
        
        if not cache_file.exists():
            return False
        
        # Check if cache is still valid
        cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - cache_time < self.cache_ttl
    
    def get_cached_feed(self, cache_key: str) -> Optional[str]:
        """Get cached feed content"""
        if not self.is_cached(cache_key):
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.xml"
        return cache_file.read_text(encoding='utf-8')
    
    def cache_feed(self, cache_key: str, content: str) -> None:
        """Cache feed content"""
        cache_file = self.cache_dir / f"{cache_key}.xml"
        cache_file.write_text(content, encoding='utf-8')
    
    def invalidate_cache(self, cache_key: Optional[str] = None) -> None:
        """Invalidate cache (specific key or all)"""
        if cache_key:
            cache_file = self.cache_dir / f"{cache_key}.xml"
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.xml"):
                cache_file.unlink()


class FeedGenerator:
    """
    Feed Generator for RSS feeds and XML sitemaps
    
    Generates site-wide and per-series RSS feeds, standard XML sitemaps,
    video sitemaps with Schema.org metadata, and news sitemaps for recent content.
    """
    
    def __init__(self, 
                 content_registry: ContentRegistry,
                 base_url: str = "https://example.com",
                 site_name: str = "Content Publishing Platform",
                 site_description: str = "Educational content archive and publishing platform",
                 cache_dir: Optional[str] = None):
        """
        Initialize Feed Generator
        
        Args:
            content_registry: ContentRegistry instance for content access
            base_url: Base URL for the site
            site_name: Site name for feed metadata
            site_description: Site description for feed metadata
            cache_dir: Directory for feed caching (defaults to 'data/cache/feeds')
        """
        self.content_registry = content_registry
        self.base_url = base_url.rstrip('/')
        self.site_name = site_name
        self.site_description = site_description
        
        # Initialize caching
        cache_path = Path(cache_dir or "data/cache/feeds")
        self.cache = FeedCache(cache_path)
        
        # Feed configuration
        self.rss_item_limit = 50  # Maximum items per RSS feed
        self.news_sitemap_hours = 48  # Hours for news sitemap inclusion
    
    def generate_site_rss(self, episodes: Optional[List[Episode]] = None) -> RSSFeed:
        """
        Generate site-wide RSS feed with proper episode metadata
        
        Args:
            episodes: Optional list of episodes (fetches all if not provided)
            
        Returns:
            RSSFeed object with site-wide content
        """
        # Check cache first
        cache_key = self.cache.get_cache_key("site_rss")
        cached_content = self.cache.get_cached_feed(cache_key)
        if cached_content:
            # Parse cached content back to RSSFeed object
            return self._parse_rss_from_xml(cached_content)
        
        # Get episodes if not provided
        if episodes is None:
            episodes = self.content_registry.get_episodes()
        
        # Sort episodes by upload date (newest first)
        sorted_episodes = sorted(episodes, key=lambda ep: ep.upload_date, reverse=True)
        
        # Limit to recent episodes
        recent_episodes = sorted_episodes[:self.rss_item_limit]
        
        # Create RSS feed
        rss_feed = RSSFeed(
            title=self.site_name,
            description=self.site_description,
            link=self.base_url,
            copyright=f"© {datetime.now().year} {self.site_name}",
            pub_date=recent_episodes[0].upload_date if recent_episodes else datetime.now(),
            last_build_date=datetime.now()
        )
        
        # Add episodes as RSS items
        for episode in recent_episodes:
            item_data = self._create_rss_item_from_episode(episode)
            rss_feed.items.append(item_data)
        
        # Cache the feed
        xml_content = rss_feed.to_xml()
        self.cache.cache_feed(cache_key, xml_content)
        
        return rss_feed
    
    def generate_series_rss(self, series: Series, episodes: Optional[List[Episode]] = None) -> RSSFeed:
        """
        Generate per-series RSS feed for targeted subscriptions
        
        Args:
            series: Series object to generate feed for
            episodes: Optional list of episodes in series (fetches if not provided)
            
        Returns:
            RSSFeed object with series-specific content
        """
        # Check cache first
        cache_key = self.cache.get_cache_key("series_rss", series.series_id)
        cached_content = self.cache.get_cached_feed(cache_key)
        if cached_content:
            return self._parse_rss_from_xml(cached_content)
        
        # Get series episodes if not provided
        if episodes is None:
            from .content_registry import ContentFilter
            filter_criteria = ContentFilter(series_ids=[series.series_id])
            episodes = self.content_registry.get_episodes(filter_criteria)
        
        # Sort episodes by upload date (newest first)
        sorted_episodes = sorted(episodes, key=lambda ep: ep.upload_date, reverse=True)
        
        # Limit to recent episodes
        recent_episodes = sorted_episodes[:self.rss_item_limit]
        
        # Create series-specific RSS feed
        series_url = urljoin(self.base_url, f"/series/{series.slug}")
        feed_description = f"{series.description} - Episodes from {series.title}"
        
        rss_feed = RSSFeed(
            title=f"{series.title} - {self.site_name}",
            description=feed_description,
            link=series_url,
            copyright=f"© {datetime.now().year} {self.site_name}",
            managing_editor=f"{series.primary_host.name} ({series.primary_host.name}@{self.base_url.split('//')[1]})" if series.primary_host else None,
            pub_date=recent_episodes[0].upload_date if recent_episodes else datetime.now(),
            last_build_date=datetime.now()
        )
        
        # Add episodes as RSS items
        for episode in recent_episodes:
            item_data = self._create_rss_item_from_episode(episode)
            rss_feed.items.append(item_data)
        
        # Cache the feed
        xml_content = rss_feed.to_xml()
        self.cache.cache_feed(cache_key, xml_content)
        
        return rss_feed
    
    def _create_rss_item_from_episode(self, episode: Episode) -> Dict[str, Any]:
        """Create RSS item data from episode"""
        episode_url = urljoin(self.base_url, f"/episodes/{episode.episode_id}")
        
        # Create item description with HTML content
        description = f"<p>{episode.description}</p>"
        
        # Add host information
        if episode.hosts:
            hosts_text = ", ".join([host.name for host in episode.hosts])
            description += f"<p><strong>Hosted by:</strong> {hosts_text}</p>"
        
        # Add guest information
        if episode.guests:
            guests_text = ", ".join([guest.name for guest in episode.guests])
            description += f"<p><strong>Featuring:</strong> {guests_text}</p>"
        
        # Add duration if available
        if episode.duration:
            duration_str = self._format_duration(episode.duration)
            description += f"<p><strong>Duration:</strong> {duration_str}</p>"
        
        # Create RSS item
        item_data = {
            "title": episode.title,
            "description": description,
            "link": episode_url,
            "guid": episode_url,  # Use episode URL as GUID
            "pub_date": episode.upload_date,
            "category": episode.tags + episode.series.topics  # Combine episode tags and series topics
        }
        
        # Add author information
        if episode.hosts:
            primary_host = episode.hosts[0]
            item_data["author"] = f"{primary_host.name}@{self.base_url.split('//')[1]} ({primary_host.name})"
        
        # Add media enclosure if content URL available
        if episode.content_url:
            item_data["enclosure"] = {
                "url": episode.content_url,
                "type": "video/mp4"  # Default assumption
            }
            
            # Add media namespace content
            item_data["media_content"] = {
                "url": episode.content_url,
                "type": "video/mp4"
            }
            
            if episode.duration:
                item_data["media_content"]["duration"] = int(episode.duration.total_seconds())
        
        # Add thumbnail
        if episode.thumbnail_url:
            item_data["media_thumbnail"] = episode.thumbnail_url
        
        return item_data
    
    def _format_duration(self, duration) -> str:
        """Format timedelta as human-readable duration"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def _parse_rss_from_xml(self, xml_content: str) -> RSSFeed:
        """Parse RSS feed from XML content (for cache retrieval)"""
        # This is a simplified parser for cached content
        # In a full implementation, you'd parse the XML back to RSSFeed object
        # For now, return a basic feed structure
        return RSSFeed(
            title="Cached Feed",
            description="Cached RSS feed content",
            link=self.base_url
        )
    
    def validate_rss_feed(self, rss_feed: RSSFeed) -> ValidationResult:
        """
        Validate RSS feed against RSS specification
        
        Args:
            rss_feed: RSSFeed object to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        
        # Required RSS channel elements
        if not rss_feed.title:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS feed title is required",
                location="channel.title",
                severity=Severity.ERROR
            ))
        
        if not rss_feed.description:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS feed description is required",
                location="channel.description",
                severity=Severity.ERROR
            ))
        
        if not rss_feed.link:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS feed link is required",
                location="channel.link",
                severity=Severity.ERROR
            ))
        
        # Validate RSS items
        for i, item in enumerate(rss_feed.items):
            # Required item elements
            if not item.get("title"):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"RSS item {i} missing required title",
                    location=f"item[{i}].title",
                    severity=Severity.ERROR
                ))
            
            if not item.get("description"):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"RSS item {i} missing required description",
                    location=f"item[{i}].description",
                    severity=Severity.ERROR
                ))
            
            # Either link or guid is required
            if not item.get("link") and not item.get("guid"):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"RSS item {i} must have either link or guid",
                    location=f"item[{i}]",
                    severity=Severity.ERROR
                ))
            
            # Validate enclosure if present
            if "enclosure" in item:
                enclosure = item["enclosure"]
                if not enclosure.get("url"):
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"RSS item {i} enclosure missing URL",
                        location=f"item[{i}].enclosure.url",
                        severity=Severity.ERROR
                    ))
                
                if not enclosure.get("type"):
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"RSS item {i} enclosure missing type",
                        location=f"item[{i}].enclosure.type",
                        severity=Severity.ERROR
                    ))
        
        # Check for reasonable item count
        if len(rss_feed.items) > 100:
            warnings.append(ValidationWarning(
                message=f"RSS feed has {len(rss_feed.items)} items, consider limiting to improve performance",
                location="channel.items"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_items": len(rss_feed.items),
                "validation_timestamp": datetime.now().isoformat()
            }
        )
    
    def generate_sitemap(self, urls: Optional[List[str]] = None) -> XMLSitemap:
        """
        Generate standard XML sitemap with all published content URLs
        
        Args:
            urls: Optional list of URLs (generates from content if not provided)
            
        Returns:
            XMLSitemap object with all content URLs
        """
        # Check cache first
        cache_key = self.cache.get_cache_key("sitemap")
        cached_content = self.cache.get_cached_feed(cache_key)
        if cached_content:
            return self._parse_sitemap_from_xml(cached_content)
        
        sitemap = XMLSitemap()
        
        # Add homepage
        sitemap.add_url(
            loc=self.base_url,
            lastmod=datetime.now(),
            changefreq="daily",
            priority=1.0
        )
        
        # Add series index
        sitemap.add_url(
            loc=urljoin(self.base_url, "/series"),
            lastmod=datetime.now(),
            changefreq="weekly",
            priority=0.8
        )
        
        # Add hosts index
        sitemap.add_url(
            loc=urljoin(self.base_url, "/hosts"),
            lastmod=datetime.now(),
            changefreq="weekly",
            priority=0.8
        )
        
        # Add all episodes
        episodes = self.content_registry.get_episodes()
        for episode in episodes:
            episode_url = urljoin(self.base_url, f"/episodes/{episode.episode_id}")
            sitemap.add_url(
                loc=episode_url,
                lastmod=episode.upload_date,
                changefreq="monthly",
                priority=0.9
            )
        
        # Add all series pages
        series_list = self.content_registry.get_all_series()
        for series in series_list:
            series_url = urljoin(self.base_url, f"/series/{series.slug}")
            sitemap.add_url(
                loc=series_url,
                lastmod=datetime.now(),
                changefreq="weekly",
                priority=0.7
            )
        
        # Add all host profiles
        hosts = self.content_registry.get_all_hosts()
        for host in hosts:
            host_url = urljoin(self.base_url, f"/hosts/{host.slug}")
            sitemap.add_url(
                loc=host_url,
                lastmod=datetime.now(),
                changefreq="monthly",
                priority=0.6
            )
        
        # Cache the sitemap
        xml_content = sitemap.to_xml()
        self.cache.cache_feed(cache_key, xml_content)
        
        return sitemap
    
    def generate_video_sitemap(self, episodes: Optional[List[Episode]] = None) -> XMLSitemap:
        """
        Generate video sitemap with Schema.org video metadata blocks
        
        Args:
            episodes: Optional list of episodes (fetches all if not provided)
            
        Returns:
            XMLSitemap object with video metadata
        """
        # Check cache first
        cache_key = self.cache.get_cache_key("video_sitemap")
        cached_content = self.cache.get_cached_feed(cache_key)
        if cached_content:
            return self._parse_sitemap_from_xml(cached_content)
        
        # Get episodes if not provided
        if episodes is None:
            episodes = self.content_registry.get_episodes()
        
        sitemap = XMLSitemap()
        
        # Add episodes with video metadata
        for episode in episodes:
            if not episode.content_url or not episode.thumbnail_url:
                continue  # Skip episodes without video content
            
            episode_url = urljoin(self.base_url, f"/episodes/{episode.episode_id}")
            
            # Create video metadata
            video_data = {
                "thumbnail_loc": episode.thumbnail_url,
                "title": episode.title,
                "description": episode.description[:2048],  # Google limit
                "content_loc": episode.content_url,
                "publication_date": episode.upload_date.isoformat()
            }
            
            # Add duration if available
            if episode.duration:
                video_data["duration"] = int(episode.duration.total_seconds())
            
            # Add tags (limit to 32 as per Google guidelines)
            if episode.tags:
                video_data["tags"] = episode.tags[:32]
            
            sitemap.add_url(
                loc=episode_url,
                lastmod=episode.upload_date,
                changefreq="monthly",
                priority=0.9,
                video=video_data
            )
        
        # Cache the sitemap
        xml_content = sitemap.to_xml()
        self.cache.cache_feed(cache_key, xml_content)
        
        return sitemap
    
    def generate_news_sitemap(self, recent_episodes: Optional[List[Episode]] = None) -> XMLSitemap:
        """
        Generate news sitemap for episodes within 48-hour window
        
        Args:
            recent_episodes: Optional list of recent episodes (filters by date if not provided)
            
        Returns:
            XMLSitemap object with news metadata for recent episodes
        """
        # Check cache first (shorter TTL for news sitemap)
        cache_key = self.cache.get_cache_key("news_sitemap")
        # Use shorter cache TTL for news content
        if hasattr(self.cache, 'cache_ttl'):
            original_ttl = self.cache.cache_ttl
            self.cache.cache_ttl = timedelta(minutes=30)  # 30 minute cache for news
        
        cached_content = self.cache.get_cached_feed(cache_key)
        if cached_content:
            return self._parse_sitemap_from_xml(cached_content)
        
        # Get recent episodes if not provided
        if recent_episodes is None:
            cutoff_time = datetime.now() - timedelta(hours=self.news_sitemap_hours)
            from .content_registry import ContentFilter
            filter_criteria = ContentFilter(date_from=cutoff_time)
            recent_episodes = self.content_registry.get_episodes(filter_criteria)
        else:
            # Filter provided episodes by time window
            cutoff_time = datetime.now() - timedelta(hours=self.news_sitemap_hours)
            recent_episodes = [ep for ep in recent_episodes if ep.upload_date >= cutoff_time]
        
        sitemap = XMLSitemap()
        
        # Add recent episodes as news items
        for episode in recent_episodes:
            episode_url = urljoin(self.base_url, f"/episodes/{episode.episode_id}")
            
            # Create news metadata
            news_data = {
                "publication_name": self.site_name,
                "language": "en",
                "publication_date": episode.upload_date.isoformat(),
                "title": episode.title
            }
            
            sitemap.add_url(
                loc=episode_url,
                lastmod=episode.upload_date,
                news=news_data
            )
        
        # Cache the sitemap
        xml_content = sitemap.to_xml()
        self.cache.cache_feed(cache_key, xml_content)
        
        # Restore original cache TTL
        if hasattr(self.cache, 'cache_ttl') and 'original_ttl' in locals():
            self.cache.cache_ttl = original_ttl
        
        return sitemap
    
    def _parse_sitemap_from_xml(self, xml_content: str) -> XMLSitemap:
        """Parse XML sitemap from cached content"""
        # Simplified parser for cached content
        # In a full implementation, you'd parse the XML back to XMLSitemap object
        return XMLSitemap()
    
    def validate_xml_sitemap(self, sitemap: XMLSitemap) -> ValidationResult:
        """
        Validate XML sitemap against sitemap specification
        
        Args:
            sitemap: XMLSitemap object to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        
        # Check URL count limits
        if len(sitemap.urls) > 50000:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Sitemap has {len(sitemap.urls)} URLs, exceeds limit of 50,000",
                location="urlset",
                severity=Severity.ERROR
            ))
        
        # Validate individual URLs
        for i, url_data in enumerate(sitemap.urls):
            # Required loc element
            if not url_data.get("loc"):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"URL {i} missing required loc element",
                    location=f"url[{i}].loc",
                    severity=Severity.ERROR
                ))
            
            # Validate changefreq values
            if "changefreq" in url_data:
                valid_changefreq = ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"]
                if url_data["changefreq"] not in valid_changefreq:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"URL {i} has invalid changefreq value: {url_data['changefreq']}",
                        location=f"url[{i}].changefreq",
                        severity=Severity.ERROR
                    ))
            
            # Validate priority values
            if "priority" in url_data:
                try:
                    priority = float(url_data["priority"])
                    if not 0.0 <= priority <= 1.0:
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message=f"URL {i} priority must be between 0.0 and 1.0",
                            location=f"url[{i}].priority",
                            severity=Severity.ERROR
                        ))
                except ValueError:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"URL {i} priority must be a valid number",
                        location=f"url[{i}].priority",
                        severity=Severity.ERROR
                    ))
            
            # Validate video sitemap elements
            if "video" in url_data:
                video_data = url_data["video"]
                
                # Required video elements
                required_video_fields = ["thumbnail_loc", "title", "description"]
                for field in required_video_fields:
                    if not video_data.get(field):
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message=f"URL {i} video missing required field: {field}",
                            location=f"url[{i}].video.{field}",
                            severity=Severity.ERROR
                        ))
                
                # Validate video description length
                if video_data.get("description") and len(video_data["description"]) > 2048:
                    warnings.append(ValidationWarning(
                        message=f"URL {i} video description exceeds recommended 2048 characters",
                        location=f"url[{i}].video.description"
                    ))
                
                # Validate duration
                if "duration" in video_data:
                    try:
                        duration = int(video_data["duration"])
                        if duration <= 0:
                            errors.append(ValidationError(
                                error_type=ErrorType.SCHEMA_VALIDATION,
                                message=f"URL {i} video duration must be positive",
                                location=f"url[{i}].video.duration",
                                severity=Severity.ERROR
                            ))
                    except ValueError:
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message=f"URL {i} video duration must be a valid integer",
                            location=f"url[{i}].video.duration",
                            severity=Severity.ERROR
                        ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_urls": len(sitemap.urls),
                "video_urls": len([url for url in sitemap.urls if "video" in url]),
                "news_urls": len([url for url in sitemap.urls if "news" in url]),
                "validation_timestamp": datetime.now().isoformat()
            }
        )
    
    def update_feeds_on_content_change(self, changed_content_ids: List[str]) -> None:
        """
        Update feeds when content changes (automatic feed updates)
        
        Args:
            changed_content_ids: List of content IDs that have changed
        """
        # Invalidate relevant caches
        self.cache.invalidate_cache("site_rss")
        self.cache.invalidate_cache("sitemap")
        self.cache.invalidate_cache("video_sitemap")
        self.cache.invalidate_cache("news_sitemap")
        
        # Invalidate series-specific feeds for affected series
        episodes = self.content_registry.get_episodes()
        affected_series = set()
        
        for episode in episodes:
            if episode.episode_id in changed_content_ids:
                affected_series.add(episode.series.series_id)
        
        for series_id in affected_series:
            series_cache_key = self.cache.get_cache_key("series_rss", series_id)
            self.cache.invalidate_cache(series_cache_key)
    
    def get_feed_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about generated feeds
        
        Returns:
            Dictionary with feed statistics
        """
        episodes = self.content_registry.get_episodes()
        series_list = self.content_registry.get_all_series()
        
        # Calculate recent content for news sitemap
        cutoff_time = datetime.now() - timedelta(hours=self.news_sitemap_hours)
        recent_episodes = [ep for ep in episodes if ep.upload_date >= cutoff_time]
        
        # Count episodes with video content
        video_episodes = [ep for ep in episodes if ep.content_url and ep.thumbnail_url]
        
        return {
            "total_episodes": len(episodes),
            "total_series": len(series_list),
            "video_episodes": len(video_episodes),
            "recent_episodes_48h": len(recent_episodes),
            "rss_item_limit": self.rss_item_limit,
            "news_sitemap_hours": self.news_sitemap_hours,
            "cache_directory": str(self.cache.cache_dir),
            "cache_ttl_hours": self.cache.cache_ttl.total_seconds() / 3600,
            "feeds_available": {
                "site_rss": f"{self.base_url}/feeds/rss.xml",
                "sitemap": f"{self.base_url}/sitemap.xml",
                "video_sitemap": f"{self.base_url}/video-sitemap.xml",
                "news_sitemap": f"{self.base_url}/news-sitemap.xml"
            }
        }


# Utility functions for working with FeedGenerator

def create_feed_generator(content_registry: ContentRegistry,
                         base_url: str = "https://example.com",
                         site_name: str = "Content Publishing Platform") -> FeedGenerator:
    """
    Create a FeedGenerator instance with specified configuration
    
    Args:
        content_registry: ContentRegistry instance
        base_url: Base URL for the site
        site_name: Site name for feed metadata
        
    Returns:
        Configured FeedGenerator instance
    """
    return FeedGenerator(content_registry, base_url, site_name)


def validate_feed_xml(xml_content: str, feed_type: str = "rss") -> ValidationResult:
    """
    Validate XML feed content against specifications
    
    Args:
        xml_content: XML content to validate
        feed_type: Type of feed (rss, sitemap, video_sitemap, news_sitemap)
        
    Returns:
        ValidationResult with validation status
    """
    errors = []
    warnings = []
    
    try:
        # Parse XML to check for well-formedness
        root = ET.fromstring(xml_content)
        
        # Basic validation based on feed type
        if feed_type == "rss":
            if root.tag != "rss":
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="RSS feed must have 'rss' root element",
                    location="root",
                    severity=Severity.ERROR
                ))
            
            # Check for required channel element
            channel = root.find("channel")
            if channel is None:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="RSS feed must have 'channel' element",
                    location="rss.channel",
                    severity=Severity.ERROR
                ))
        
        elif feed_type in ["sitemap", "video_sitemap", "news_sitemap"]:
            if not root.tag.endswith("urlset"):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="Sitemap must have 'urlset' root element",
                    location="root",
                    severity=Severity.ERROR
                ))
    
    except ET.ParseError as e:
        errors.append(ValidationError(
            error_type=ErrorType.SCHEMA_VALIDATION,
            message=f"XML parsing error: {str(e)}",
            location="xml",
            severity=Severity.ERROR
        ))
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        metadata={
            "feed_type": feed_type,
            "validation_timestamp": datetime.now().isoformat()
        }
    )