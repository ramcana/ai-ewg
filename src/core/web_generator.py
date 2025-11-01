"""
Web Generator for Content Publishing Platform

Implements HTML page generation with JSON-LD structured data embedding,
SEO metadata, and canonical URL generation for episodes, series, and hosts.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib.parse import quote, urljoin
from dataclasses import dataclass, field

from .publishing_models import Episode, Series, Host, Person
from .structured_data_contract import StructuredDataContract, SchemaType

# Optional import to avoid circular dependency
try:
    from .analytics_tracker import AnalyticsTracker
except ImportError:
    AnalyticsTracker = None


@dataclass
class HTMLPage:
    """Represents a generated HTML page"""
    title: str
    content: str
    canonical_url: str
    meta_description: str
    json_ld: Optional[Dict[str, Any]] = None
    open_graph: Dict[str, str] = field(default_factory=dict)
    twitter_card: Dict[str, str] = field(default_factory=dict)
    additional_meta: Dict[str, str] = field(default_factory=dict)
    css_files: List[str] = field(default_factory=list)
    js_files: List[str] = field(default_factory=list)
    analytics_code: Optional[str] = None


@dataclass
class SEOMetadata:
    """SEO metadata for pages"""
    title: str
    description: str
    canonical_url: str
    keywords: List[str] = field(default_factory=list)
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None


@dataclass
class URLPattern:
    """URL pattern configuration"""
    base_url: str = "https://example.com"
    episode_pattern: str = "/episodes/{episode_id}"
    series_pattern: str = "/series/{series_slug}"
    host_pattern: str = "/hosts/{host_slug}"
    series_index_pattern: str = "/series"
    hosts_index_pattern: str = "/hosts"
    
    def generate_episode_url(self, episode: Episode) -> str:
        """Generate canonical URL for episode"""
        return urljoin(self.base_url, self.episode_pattern.format(
            episode_id=episode.episode_id,
            series_slug=episode.series.slug
        ))
    
    def generate_series_url(self, series: Series) -> str:
        """Generate canonical URL for series"""
        return urljoin(self.base_url, self.series_pattern.format(
            series_slug=series.slug
        ))
    
    def generate_host_url(self, host: Host) -> str:
        """Generate canonical URL for host"""
        return urljoin(self.base_url, self.host_pattern.format(
            host_slug=host.slug
        ))
    
    def generate_series_index_url(self) -> str:
        """Generate URL for series index page"""
        return urljoin(self.base_url, self.series_index_pattern)
    
    def generate_hosts_index_url(self) -> str:
        """Generate URL for hosts index page"""
        return urljoin(self.base_url, self.hosts_index_pattern)


class WebGenerator:
    """
    Web Generator for creating HTML pages with embedded structured data
    
    Generates episode pages, series indexes, and host profiles with proper
    SEO metadata, JSON-LD structured data, and canonical URLs.
    """
    
    def __init__(self, 
                 url_patterns: Optional[URLPattern] = None,
                 site_name: str = "Content Publishing Platform",
                 site_description: str = "Educational content archive and publishing platform",
                 analytics_tracker: Optional[Any] = None):
        """
        Initialize Web Generator
        
        Args:
            url_patterns: URL pattern configuration
            site_name: Site name for metadata
            site_description: Site description for metadata
            analytics_tracker: Optional analytics tracker for embedding tracking codes
        """
        self.url_patterns = url_patterns or URLPattern()
        self.site_name = site_name
        self.site_description = site_description
        self.analytics_tracker = analytics_tracker
        
        # Initialize structured data contracts
        self.video_contract = StructuredDataContract(SchemaType.VIDEO_OBJECT)
        self.tv_episode_contract = StructuredDataContract(SchemaType.TV_EPISODE)
        
        # Template cache
        self._template_cache: Dict[str, str] = {}
    
    def generate_episode_page(self, episode: Episode, use_tv_episode_schema: bool = True) -> HTMLPage:
        """
        Generate HTML page for an episode
        
        Args:
            episode: Episode object to generate page for
            use_tv_episode_schema: Whether to use TVEpisode schema (vs VideoObject)
            
        Returns:
            HTMLPage object with complete page content
        """
        # Generate canonical URL
        canonical_url = self.url_patterns.generate_episode_url(episode)
        
        # Create SEO metadata
        seo_metadata = self._create_episode_seo_metadata(episode, canonical_url)
        
        # Generate JSON-LD structured data
        schema_contract = self.tv_episode_contract if use_tv_episode_schema else self.video_contract
        json_ld = self._generate_episode_jsonld(episode, schema_contract, canonical_url)
        
        # Generate HTML content
        html_content = self._render_episode_template(episode, seo_metadata)
        
        # Create Open Graph metadata
        open_graph = self._create_episode_open_graph(episode, canonical_url)
        
        # Create Twitter Card metadata
        twitter_card = self._create_episode_twitter_card(episode, canonical_url)
        
        # Generate analytics tracking code
        analytics_code = None
        if self.analytics_tracker:
            custom_data = {
                "episode_id": episode.episode_id,
                "series_id": episode.series.series_id if episode.series else None,
                "duration": str(episode.duration) if episode.duration else None
            }
            analytics_code = self.analytics_tracker.generate_tracking_code("episode", custom_data)
        
        return HTMLPage(
            title=seo_metadata.title,
            content=html_content,
            canonical_url=canonical_url,
            meta_description=seo_metadata.description,
            json_ld=json_ld,
            open_graph=open_graph,
            twitter_card=twitter_card,
            css_files=["/assets/css/main.css", "/assets/css/episode.css"],
            js_files=["/assets/js/main.js", "/assets/js/episode.js"],
            analytics_code=analytics_code
        )
    
    def generate_series_index(self, series: Series, episodes: List[Episode]) -> HTMLPage:
        """
        Generate HTML page for a series index
        
        Args:
            series: Series object
            episodes: List of episodes in the series
            
        Returns:
            HTMLPage object with series index content
        """
        # Generate canonical URL
        canonical_url = self.url_patterns.generate_series_url(series)
        
        # Create SEO metadata
        seo_metadata = self._create_series_seo_metadata(series, episodes, canonical_url)
        
        # Generate JSON-LD structured data for series
        json_ld = self._generate_series_jsonld(series, episodes, canonical_url)
        
        # Generate HTML content
        html_content = self._render_series_template(series, episodes, seo_metadata)
        
        # Create Open Graph metadata
        open_graph = self._create_series_open_graph(series, canonical_url)
        
        # Create Twitter Card metadata
        twitter_card = self._create_series_twitter_card(series, canonical_url)
        
        # Generate analytics tracking code
        analytics_code = None
        if self.analytics_tracker:
            custom_data = {
                "series_id": series.series_id,
                "episode_count": len(episodes)
            }
            analytics_code = self.analytics_tracker.generate_tracking_code("series", custom_data)
        
        return HTMLPage(
            title=seo_metadata.title,
            content=html_content,
            canonical_url=canonical_url,
            meta_description=seo_metadata.description,
            json_ld=json_ld,
            open_graph=open_graph,
            twitter_card=twitter_card,
            css_files=["/assets/css/main.css", "/assets/css/series.css"],
            js_files=["/assets/js/main.js"],
            analytics_code=analytics_code
        )
    
    def generate_host_profile(self, host: Host, episodes: List[Episode]) -> HTMLPage:
        """
        Generate HTML page for a host profile
        
        Args:
            host: Host object
            episodes: List of episodes featuring this host
            
        Returns:
            HTMLPage object with host profile content
        """
        # Generate canonical URL
        canonical_url = self.url_patterns.generate_host_url(host)
        
        # Create SEO metadata
        seo_metadata = self._create_host_seo_metadata(host, episodes, canonical_url)
        
        # Generate JSON-LD structured data for person
        json_ld = self._generate_host_jsonld(host, episodes, canonical_url)
        
        # Generate HTML content
        html_content = self._render_host_template(host, episodes, seo_metadata)
        
        # Create Open Graph metadata
        open_graph = self._create_host_open_graph(host, canonical_url)
        
        # Create Twitter Card metadata
        twitter_card = self._create_host_twitter_card(host, canonical_url)
        
        # Generate analytics tracking code
        analytics_code = None
        if self.analytics_tracker:
            custom_data = {
                "host_id": host.person_id,
                "episode_count": len(episodes)
            }
            analytics_code = self.analytics_tracker.generate_tracking_code("host", custom_data)
        
        return HTMLPage(
            title=seo_metadata.title,
            content=html_content,
            canonical_url=canonical_url,
            meta_description=seo_metadata.description,
            json_ld=json_ld,
            open_graph=open_graph,
            twitter_card=twitter_card,
            css_files=["/assets/css/main.css", "/assets/css/host.css"],
            js_files=["/assets/js/main.js"],
            analytics_code=analytics_code
        )
    
    def _create_episode_seo_metadata(self, episode: Episode, canonical_url: str) -> SEOMetadata:
        """Create SEO metadata for episode page"""
        # Create title with series context
        title = f"{episode.title} - {episode.series.title} - {self.site_name}"
        
        # Truncate description for meta description
        description = episode.description
        if len(description) > 160:
            description = description[:157] + "..."
        
        # Extract keywords from tags and series topics
        keywords = episode.tags.copy()
        keywords.extend(episode.series.topics)
        keywords = list(set(keywords))  # Remove duplicates
        
        # Get primary host as author
        author = episode.hosts[0].name if episode.hosts else None
        
        return SEOMetadata(
            title=title,
            description=description,
            canonical_url=canonical_url,
            keywords=keywords,
            author=author,
            published_date=episode.upload_date,
            modified_date=datetime.now(),
            image_url=episode.thumbnail_url,
            video_url=episode.content_url,
            duration_seconds=int(episode.duration.total_seconds()) if episode.duration else None
        )
    
    def _create_series_seo_metadata(self, series: Series, episodes: List[Episode], canonical_url: str) -> SEOMetadata:
        """Create SEO metadata for series page"""
        title = f"{series.title} - {self.site_name}"
        
        # Create description with episode count
        episode_count = len(episodes)
        description = f"{series.description} Browse {episode_count} episodes."
        if len(description) > 160:
            description = description[:157] + "..."
        
        return SEOMetadata(
            title=title,
            description=description,
            canonical_url=canonical_url,
            keywords=series.topics,
            author=series.primary_host.name,
            image_url=series.artwork_url
        )
    
    def _create_host_seo_metadata(self, host: Host, episodes: List[Episode], canonical_url: str) -> SEOMetadata:
        """Create SEO metadata for host profile page"""
        title = f"{host.name} - Host Profile - {self.site_name}"
        
        # Create description from bio and episode count
        episode_count = len(episodes)
        description = host.bio or f"Host profile for {host.name}"
        if episode_count > 0:
            description += f" Featured in {episode_count} episodes."
        
        if len(description) > 160:
            description = description[:157] + "..."
        
        return SEOMetadata(
            title=title,
            description=description,
            canonical_url=canonical_url,
            author=host.name,
            image_url=host.headshot_url
        ) 
   
    def _render_episode_template(self, episode: Episode, seo_metadata: SEOMetadata) -> str:
        """Render episode HTML template"""
        # Format duration for display
        duration_str = self._format_duration(episode.duration) if episode.duration else None
        
        # Format date for display
        date_str = episode.upload_date.strftime('%B %d, %Y')
        
        # Create breadcrumb navigation
        breadcrumb = [
            {"text": "Home", "url": "/"},
            {"text": episode.series.title, "url": self.url_patterns.generate_series_url(episode.series)},
            {"text": episode.title, "url": None}
        ]
        
        # Generate host links
        host_links = []
        for host in episode.hosts:
            host_links.append({
                "name": host.name,
                "url": self.url_patterns.generate_host_url(host),
                "bio": host.bio,
                "headshot_url": host.headshot_url
            })
        
        # Generate guest information
        guest_info = []
        for guest in episode.guests:
            guest_info.append({
                "name": guest.name,
                "bio": guest.bio,
                "same_as_links": guest.same_as_links
            })
        
        # Create social media links
        social_links = []
        for platform, url in episode.social_links.items():
            social_links.append({
                "platform": platform.title(),
                "url": url,
                "icon_class": f"icon-{platform.lower()}"
            })
        
        template = f"""
        <article class="episode">
            <div class="container">
                <header class="episode-header">
                    <nav class="breadcrumb" aria-label="Breadcrumb">
                        {self._render_breadcrumb(breadcrumb)}
                    </nav>
                    
                    <h1>{self._escape_html(episode.title)}</h1>
                    
                    <div class="episode-meta">
                        <time datetime="{episode.upload_date.isoformat()}">{date_str}</time>
                        {f'<span class="duration">{duration_str}</span>' if duration_str else ''}
                        {f'<span class="episode-number">Episode {episode.episode_number}</span>' if episode.episode_number else ''}
                    </div>
                </header>
                
                {f'<div class="episode-thumbnail"><img src="{episode.thumbnail_url}" alt="{self._escape_html(episode.title)}" loading="lazy"></div>' if episode.thumbnail_url else ''}
                
                <div class="episode-content">
                    <section class="episode-description">
                        <h2>About This Episode</h2>
                        <p>{self._escape_html(episode.description)}</p>
                    </section>
                    
                    {self._render_hosts_section(host_links) if host_links else ''}
                    
                    {self._render_guests_section(guest_info) if guest_info else ''}
                    
                    {self._render_topics_section(episode.tags) if episode.tags else ''}
                    
                    {self._render_social_links_section(social_links) if social_links else ''}
                    
                    {f'<section class="episode-transcript"><h2>Transcript</h2><p><a href="{episode.transcript_path}">View Full Transcript</a></p></section>' if episode.transcript_path else ''}
                </div>
            </div>
        </article>
        """
        
        return template.strip()
    
    def _render_series_template(self, series: Series, episodes: List[Episode], seo_metadata: SEOMetadata) -> str:
        """Render series index HTML template"""
        # Sort episodes by upload date (newest first)
        sorted_episodes = sorted(episodes, key=lambda ep: ep.upload_date, reverse=True)
        
        # Create breadcrumb navigation
        breadcrumb = [
            {"text": "Home", "url": "/"},
            {"text": "Series", "url": self.url_patterns.generate_series_index_url()},
            {"text": series.title, "url": None}
        ]
        
        # Generate episode list
        episode_list_html = ""
        for episode in sorted_episodes:
            episode_url = self.url_patterns.generate_episode_url(episode)
            duration_str = self._format_duration(episode.duration) if episode.duration else ""
            date_str = episode.upload_date.strftime('%B %d, %Y')
            
            episode_list_html += f"""
            <article class="episode-card">
                {f'<img src="{episode.thumbnail_url}" alt="{self._escape_html(episode.title)}" class="episode-thumbnail" loading="lazy">' if episode.thumbnail_url else ''}
                <div class="episode-info">
                    <h3><a href="{episode_url}">{self._escape_html(episode.title)}</a></h3>
                    <p class="episode-description">{self._escape_html(episode.description[:200])}{'...' if len(episode.description) > 200 else ''}</p>
                    <div class="episode-meta">
                        <time datetime="{episode.upload_date.isoformat()}">{date_str}</time>
                        {f'<span class="duration">{duration_str}</span>' if duration_str else ''}
                    </div>
                </div>
            </article>
            """
        
        template = f"""
        <div class="series-page">
            <div class="container">
                <header class="series-header">
                    <nav class="breadcrumb" aria-label="Breadcrumb">
                        {self._render_breadcrumb(breadcrumb)}
                    </nav>
                    
                    <div class="series-info">
                        {f'<img src="{series.artwork_url}" alt="{self._escape_html(series.title)}" class="series-artwork">' if series.artwork_url else ''}
                        <div class="series-details">
                            <h1>{self._escape_html(series.title)}</h1>
                            <p class="series-description">{self._escape_html(series.description)}</p>
                            <div class="series-meta">
                                <span class="host">Hosted by <a href="{self.url_patterns.generate_host_url(series.primary_host)}">{self._escape_html(series.primary_host.name)}</a></span>
                                <span class="episode-count">{len(episodes)} episodes</span>
                            </div>
                            {self._render_topics_section(series.topics, "Series Topics") if series.topics else ''}
                        </div>
                    </div>
                </header>
                
                <section class="episodes-list">
                    <h2>Episodes</h2>
                    <div class="episodes-grid">
                        {episode_list_html}
                    </div>
                </section>
            </div>
        </div>
        """
        
        return template.strip()
    
    def _render_host_template(self, host: Host, episodes: List[Episode], seo_metadata: SEOMetadata) -> str:
        """Render host profile HTML template"""
        # Sort episodes by upload date (newest first)
        sorted_episodes = sorted(episodes, key=lambda ep: ep.upload_date, reverse=True)
        
        # Create breadcrumb navigation
        breadcrumb = [
            {"text": "Home", "url": "/"},
            {"text": "Hosts", "url": self.url_patterns.generate_hosts_index_url()},
            {"text": host.name, "url": None}
        ]
        
        # Generate series list for this host
        host_series_dict = {}
        for episode in episodes:
            series_id = episode.series.series_id
            if series_id not in host_series_dict:
                host_series_dict[series_id] = episode.series
        
        host_series = list(host_series_dict.values())
        
        series_list_html = ""
        for series in host_series:
            series_url = self.url_patterns.generate_series_url(series)
            series_episodes = [ep for ep in episodes if ep.series.series_id == series.series_id]
            
            series_list_html += f"""
            <div class="series-card">
                {f'<img src="{series.artwork_url}" alt="{self._escape_html(series.title)}" class="series-artwork">' if series.artwork_url else ''}
                <div class="series-info">
                    <h3><a href="{series_url}">{self._escape_html(series.title)}</a></h3>
                    <p>{self._escape_html(series.description[:150])}{'...' if len(series.description) > 150 else ''}</p>
                    <span class="episode-count">{len(series_episodes)} episodes</span>
                </div>
            </div>
            """
        
        # Generate recent episodes list
        recent_episodes_html = ""
        for episode in sorted_episodes[:10]:  # Show last 10 episodes
            episode_url = self.url_patterns.generate_episode_url(episode)
            date_str = episode.upload_date.strftime('%B %d, %Y')
            
            recent_episodes_html += f"""
            <li class="episode-item">
                <a href="{episode_url}">{self._escape_html(episode.title)}</a>
                <span class="episode-series">{self._escape_html(episode.series.title)}</span>
                <time datetime="{episode.upload_date.isoformat()}">{date_str}</time>
            </li>
            """
        
        # Generate external links
        external_links_html = ""
        for link in host.same_as_links:
            link_text = self._get_link_display_name(link)
            external_links_html += f'<li><a href="{link}" target="_blank" rel="noopener">{link_text} ↗</a></li>'
        
        template = f"""
        <div class="host-profile">
            <div class="container">
                <header class="host-header">
                    <nav class="breadcrumb" aria-label="Breadcrumb">
                        {self._render_breadcrumb(breadcrumb)}
                    </nav>
                    
                    <div class="host-info">
                        {f'<img src="{host.headshot_url}" alt="{self._escape_html(host.name)}" class="host-photo">' if host.headshot_url else ''}
                        <div class="host-details">
                            <h1>{self._escape_html(host.name)}</h1>
                            {f'<p class="host-affiliation">{self._escape_html(host.affiliation)}</p>' if host.affiliation else ''}
                            {f'<p class="host-bio">{self._escape_html(host.bio)}</p>' if host.bio else ''}
                            
                            {f'<ul class="external-links">{external_links_html}</ul>' if external_links_html else ''}
                            
                            <div class="host-stats">
                                <span class="episode-count">{len(episodes)} episodes</span>
                                <span class="series-count">{len(host_series)} series</span>
                            </div>
                        </div>
                    </div>
                </header>
                
                {f'<section class="host-series"><h2>Series</h2><div class="series-grid">{series_list_html}</div></section>' if series_list_html else ''}
                
                {f'<section class="recent-episodes"><h2>Recent Episodes</h2><ul class="episodes-list">{recent_episodes_html}</ul></section>' if recent_episodes_html else ''}
            </div>
        </div>
        """
        
        return template.strip()
    
    def _render_breadcrumb(self, breadcrumb: List[Dict[str, str]]) -> str:
        """Render breadcrumb navigation"""
        items = []
        for item in breadcrumb:
            if item["url"]:
                items.append(f'<a href="{item["url"]}">{self._escape_html(item["text"])}</a>')
            else:
                items.append(f'<span>{self._escape_html(item["text"])}</span>')
        
        return ' / '.join(items)
    
    def _render_hosts_section(self, host_links: List[Dict[str, str]]) -> str:
        """Render hosts section for episode page"""
        hosts_html = ""
        for host in host_links:
            hosts_html += f"""
            <div class="host-card">
                {f'<img src="{host["headshot_url"]}" alt="{self._escape_html(host["name"])}" class="host-photo">' if host.get("headshot_url") else ''}
                <div class="host-info">
                    <h3><a href="{host["url"]}">{self._escape_html(host["name"])}</a></h3>
                    {f'<p class="host-bio">{self._escape_html(host["bio"][:150])}{"..." if len(host.get("bio", "")) > 150 else ""}</p>' if host.get("bio") else ''}
                </div>
            </div>
            """
        
        return f"""
        <section class="episode-hosts">
            <h2>Hosts</h2>
            <div class="hosts-grid">
                {hosts_html}
            </div>
        </section>
        """
    
    def _render_guests_section(self, guest_info: List[Dict[str, Any]]) -> str:
        """Render guests section for episode page"""
        guests_html = ""
        for guest in guest_info:
            external_links = ""
            for link in guest.get("same_as_links", []):
                link_text = self._get_link_display_name(link)
                external_links += f'<a href="{link}" target="_blank" rel="noopener">{link_text} ↗</a> '
            
            guests_html += f"""
            <div class="guest-card">
                <h3>{self._escape_html(guest["name"])}</h3>
                {f'<p class="guest-bio">{self._escape_html(guest["bio"])}</p>' if guest.get("bio") else ''}
                {f'<div class="external-links">{external_links}</div>' if external_links else ''}
            </div>
            """
        
        return f"""
        <section class="episode-guests">
            <h2>Featured Guests</h2>
            <div class="guests-grid">
                {guests_html}
            </div>
        </section>
        """
    
    def _render_topics_section(self, topics: List[str], title: str = "Topics Discussed") -> str:
        """Render topics/tags section"""
        topics_html = ""
        for topic in topics:
            # Create search URL for topic
            search_url = f"/search?q={quote(topic)}"
            topics_html += f'<li><a href="{search_url}" class="topic-tag">{self._escape_html(topic)}</a></li>'
        
        return f"""
        <section class="episode-topics">
            <h2>{title}</h2>
            <ul class="topic-tags">
                {topics_html}
            </ul>
        </section>
        """
    
    def _render_social_links_section(self, social_links: List[Dict[str, str]]) -> str:
        """Render social media links section"""
        links_html = ""
        for link in social_links:
            links_html += f"""
            <li>
                <a href="{link["url"]}" target="_blank" rel="noopener" class="social-link {link["icon_class"]}">
                    {link["platform"]} ↗
                </a>
            </li>
            """
        
        return f"""
        <section class="social-links">
            <h2>Watch & Share</h2>
            <ul class="social-platforms">
                {links_html}
            </ul>
        </section>
        """
    
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
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not text:
            return ""
        
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))
    
    def _get_link_display_name(self, url: str) -> str:
        """Get display name for external link"""
        if "wikipedia.org" in url:
            return "Wikipedia"
        elif "wikidata.org" in url:
            return "Wikidata"
        elif "twitter.com" in url or "x.com" in url:
            return "Twitter/X"
        elif "linkedin.com" in url:
            return "LinkedIn"
        elif "youtube.com" in url:
            return "YouTube"
        elif "instagram.com" in url:
            return "Instagram"
        else:
            # Extract domain name
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.replace("www.", "").title()  
  
    def _generate_episode_jsonld(self, episode: Episode, schema_contract: StructuredDataContract, canonical_url: str) -> Dict[str, Any]:
        """Generate JSON-LD structured data for episode following Structured Data Contract"""
        # Start with base schema from contract
        json_ld = schema_contract.generate_schema_from_episode(episode)
        
        # Override @id with canonical URL
        json_ld["@id"] = canonical_url
        
        # Add canonical URL
        json_ld["url"] = canonical_url
        
        # Enhanced series information with proper linking
        json_ld["partOfSeries"] = {
            "@type": "TVSeries",
            "@id": self.url_patterns.generate_series_url(episode.series),
            "name": episode.series.title,
            "description": episode.series.description,
            "url": self.url_patterns.generate_series_url(episode.series)
        }
        
        # Add series artwork if available
        if episode.series.artwork_url:
            json_ld["partOfSeries"]["image"] = episode.series.artwork_url
        
        # Enhanced host/actor information with proper linking
        if episode.hosts:
            json_ld["actor"] = []
            for host in episode.hosts:
                host_data = {
                    "@type": "Person",
                    "@id": self.url_patterns.generate_host_url(host),
                    "name": host.name,
                    "url": self.url_patterns.generate_host_url(host)
                }
                
                if host.bio:
                    host_data["description"] = host.bio
                
                if host.headshot_url:
                    host_data["image"] = host.headshot_url
                
                if host.affiliation:
                    host_data["affiliation"] = {
                        "@type": "Organization",
                        "name": host.affiliation
                    }
                
                # Add sameAs links for external references
                if host.same_as_links:
                    host_data["sameAs"] = host.same_as_links
                
                json_ld["actor"].append(host_data)
        
        # Add guest information
        if episode.guests:
            if "mentions" not in json_ld:
                json_ld["mentions"] = []
            
            for guest in episode.guests:
                guest_data = {
                    "@type": "Person",
                    "name": guest.name
                }
                
                if guest.bio:
                    guest_data["description"] = guest.bio
                
                if guest.same_as_links:
                    guest_data["sameAs"] = guest.same_as_links
                
                json_ld["mentions"].append(guest_data)
        
        # Enhanced publisher information
        json_ld["publisher"] = {
            "@type": "Organization",
            "name": self.site_name,
            "url": self.url_patterns.base_url,
            "description": self.site_description
        }
        
        # Add social media sameAs links from episode social links
        if episode.social_links:
            # Filter valid URLs for sameAs field
            same_as_urls = []
            for platform, url in episode.social_links.items():
                if self._is_valid_same_as_url(url):
                    same_as_urls.append(url)
            
            if same_as_urls:
                json_ld["sameAs"] = same_as_urls
        
        # Add transcript information if available
        if episode.transcript_path:
            json_ld["transcript"] = {
                "@type": "MediaObject",
                "contentUrl": episode.transcript_path,
                "encodingFormat": "text/vtt"
            }
        
        # Add accessibility features
        json_ld["accessibilityFeature"] = ["audioDescription"]
        if episode.transcript_path:
            json_ld["accessibilityFeature"].append("captions")
        
        # Add content rating and family-friendly status
        json_ld["isFamilyFriendly"] = True
        json_ld["isAccessibleForFree"] = True
        
        # Add episode-specific fields for TV episodes
        if schema_contract.schema_type == SchemaType.TV_EPISODE:
            if episode.episode_number:
                json_ld["episodeNumber"] = episode.episode_number
            
            if episode.season_number:
                json_ld["seasonNumber"] = episode.season_number
        
        # Add rights information if available
        if episode.rights:
            if episode.rights.copyright_holder:
                json_ld["copyrightHolder"] = {
                    "@type": "Organization",
                    "name": episode.rights.copyright_holder
                }
            
            if episode.rights.license_url:
                json_ld["license"] = episode.rights.license_url
        
        return json_ld
    
    def _generate_series_jsonld(self, series: Series, episodes: List[Episode], canonical_url: str) -> Dict[str, Any]:
        """Generate JSON-LD structured data for series"""
        json_ld = {
            "@context": "https://schema.org",
            "@type": "TVSeries",
            "@id": canonical_url,
            "name": series.title,
            "description": series.description,
            "url": canonical_url,
            "numberOfEpisodes": len(episodes)
        }
        
        # Add series artwork
        if series.artwork_url:
            json_ld["image"] = series.artwork_url
        
        # Add primary host information
        json_ld["actor"] = [{
            "@type": "Person",
            "@id": self.url_patterns.generate_host_url(series.primary_host),
            "name": series.primary_host.name,
            "url": self.url_patterns.generate_host_url(series.primary_host)
        }]
        
        if series.primary_host.bio:
            json_ld["actor"][0]["description"] = series.primary_host.bio
        
        # Add publisher information
        json_ld["publisher"] = {
            "@type": "Organization",
            "name": self.site_name,
            "url": self.url_patterns.base_url
        }
        
        # Add genre/topics as keywords
        if series.topics:
            json_ld["genre"] = series.topics
            json_ld["keywords"] = series.topics
        
        # Add episode list with proper linking
        if episodes:
            json_ld["episode"] = []
            for episode in episodes:
                episode_data = {
                    "@type": "TVEpisode",
                    "@id": self.url_patterns.generate_episode_url(episode),
                    "name": episode.title,
                    "url": self.url_patterns.generate_episode_url(episode),
                    "datePublished": episode.upload_date.isoformat()
                }
                
                if episode.episode_number:
                    episode_data["episodeNumber"] = episode.episode_number
                
                if episode.thumbnail_url:
                    episode_data["thumbnailUrl"] = episode.thumbnail_url
                
                json_ld["episode"].append(episode_data)
        
        # Add content ratings
        json_ld["isFamilyFriendly"] = True
        json_ld["isAccessibleForFree"] = True
        
        return json_ld
    
    def _generate_host_jsonld(self, host: Host, episodes: List[Episode], canonical_url: str) -> Dict[str, Any]:
        """Generate JSON-LD structured data for host profile"""
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Person",
            "@id": canonical_url,
            "name": host.name,
            "url": canonical_url
        }
        
        # Add bio as description
        if host.bio:
            json_ld["description"] = host.bio
        
        # Add headshot image
        if host.headshot_url:
            json_ld["image"] = host.headshot_url
        
        # Add affiliation
        if host.affiliation:
            json_ld["affiliation"] = {
                "@type": "Organization",
                "name": host.affiliation
            }
        
        # Add external links as sameAs
        if host.same_as_links:
            json_ld["sameAs"] = host.same_as_links
        
        # Add work examples (episodes)
        if episodes:
            json_ld["workExample"] = []
            for episode in episodes[:10]:  # Limit to recent 10 episodes
                episode_data = {
                    "@type": "TVEpisode",
                    "@id": self.url_patterns.generate_episode_url(episode),
                    "name": episode.title,
                    "url": self.url_patterns.generate_episode_url(episode),
                    "datePublished": episode.upload_date.isoformat()
                }
                json_ld["workExample"].append(episode_data)
        
        # Add job title/role
        json_ld["jobTitle"] = "Host"
        
        return json_ld
    
    def _is_valid_same_as_url(self, url: str) -> bool:
        """Check if URL is suitable for sameAs field in JSON-LD"""
        if not url or not isinstance(url, str):
            return False
        
        # Must be a valid HTTP/HTTPS URL
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Exclude localhost and development URLs
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
   
    def _create_episode_open_graph(self, episode: Episode, canonical_url: str) -> Dict[str, str]:
        """Create Open Graph metadata for episode"""
        og_data = {
            "og:type": "video.episode",
            "og:title": f"{episode.title} - {episode.series.title}",
            "og:description": episode.description[:300] + ("..." if len(episode.description) > 300 else ""),
            "og:url": canonical_url,
            "og:site_name": self.site_name
        }
        
        # Add image
        if episode.thumbnail_url:
            og_data["og:image"] = episode.thumbnail_url
            og_data["og:image:alt"] = f"Thumbnail for {episode.title}"
        
        # Add video-specific metadata
        if episode.content_url:
            og_data["og:video"] = episode.content_url
            og_data["og:video:type"] = "video/mp4"  # Default assumption
        
        if episode.duration:
            og_data["video:duration"] = str(int(episode.duration.total_seconds()))
        
        # Add series information
        og_data["video:series"] = episode.series.title
        
        # Add episode number if available
        if episode.episode_number:
            og_data["video:episode"] = str(episode.episode_number)
        
        # Add tags
        if episode.tags:
            og_data["og:video:tag"] = episode.tags[:5]  # Limit to 5 tags
        
        return og_data
    
    def _create_series_open_graph(self, series: Series, canonical_url: str) -> Dict[str, str]:
        """Create Open Graph metadata for series"""
        og_data = {
            "og:type": "website",
            "og:title": f"{series.title} - {self.site_name}",
            "og:description": series.description[:300] + ("..." if len(series.description) > 300 else ""),
            "og:url": canonical_url,
            "og:site_name": self.site_name
        }
        
        # Add series artwork
        if series.artwork_url:
            og_data["og:image"] = series.artwork_url
            og_data["og:image:alt"] = f"Artwork for {series.title}"
        
        return og_data
    
    def _create_host_open_graph(self, host: Host, canonical_url: str) -> Dict[str, str]:
        """Create Open Graph metadata for host profile"""
        description = host.bio or f"Host profile for {host.name}"
        
        og_data = {
            "og:type": "profile",
            "og:title": f"{host.name} - Host Profile - {self.site_name}",
            "og:description": description[:300] + ("..." if len(description) > 300 else ""),
            "og:url": canonical_url,
            "og:site_name": self.site_name
        }
        
        # Add profile image
        if host.headshot_url:
            og_data["og:image"] = host.headshot_url
            og_data["og:image:alt"] = f"Photo of {host.name}"
        
        # Add profile-specific metadata
        og_data["profile:first_name"] = host.name.split()[0] if host.name else ""
        if len(host.name.split()) > 1:
            og_data["profile:last_name"] = " ".join(host.name.split()[1:])
        
        return og_data
    
    def _create_episode_twitter_card(self, episode: Episode, canonical_url: str) -> Dict[str, str]:
        """Create Twitter Card metadata for episode"""
        twitter_data = {
            "twitter:card": "summary_large_image",
            "twitter:title": f"{episode.title} - {episode.series.title}",
            "twitter:description": episode.description[:200] + ("..." if len(episode.description) > 200 else ""),
            "twitter:url": canonical_url
        }
        
        # Add image
        if episode.thumbnail_url:
            twitter_data["twitter:image"] = episode.thumbnail_url
            twitter_data["twitter:image:alt"] = f"Thumbnail for {episode.title}"
        
        # Add video player card if content URL available
        if episode.content_url:
            twitter_data["twitter:card"] = "player"
            twitter_data["twitter:player"] = episode.content_url
            twitter_data["twitter:player:width"] = "1280"
            twitter_data["twitter:player:height"] = "720"
        
        return twitter_data
    
    def _create_series_twitter_card(self, series: Series, canonical_url: str) -> Dict[str, str]:
        """Create Twitter Card metadata for series"""
        twitter_data = {
            "twitter:card": "summary_large_image",
            "twitter:title": f"{series.title} - {self.site_name}",
            "twitter:description": series.description[:200] + ("..." if len(series.description) > 200 else ""),
            "twitter:url": canonical_url
        }
        
        # Add series artwork
        if series.artwork_url:
            twitter_data["twitter:image"] = series.artwork_url
            twitter_data["twitter:image:alt"] = f"Artwork for {series.title}"
        
        return twitter_data
    
    def _create_host_twitter_card(self, host: Host, canonical_url: str) -> Dict[str, str]:
        """Create Twitter Card metadata for host profile"""
        description = host.bio or f"Host profile for {host.name}"
        
        twitter_data = {
            "twitter:card": "summary",
            "twitter:title": f"{host.name} - Host Profile",
            "twitter:description": description[:200] + ("..." if len(description) > 200 else ""),
            "twitter:url": canonical_url
        }
        
        # Add profile image
        if host.headshot_url:
            twitter_data["twitter:image"] = host.headshot_url
            twitter_data["twitter:image:alt"] = f"Photo of {host.name}"
        
        return twitter_data
    
    def embed_json_ld(self, page: HTMLPage, structured_data: Dict[str, Any]) -> HTMLPage:
        """
        Embed JSON-LD structured data into HTML page
        
        Args:
            page: HTMLPage object to modify
            structured_data: JSON-LD data to embed
            
        Returns:
            Modified HTMLPage with embedded JSON-LD
        """
        # Create JSON-LD script tag
        json_ld_script = f'''
        <script type="application/ld+json">
        {json.dumps(structured_data, indent=2, ensure_ascii=False)}
        </script>'''
        
        # Update page with JSON-LD
        page.json_ld = structured_data
        
        return page
    
    def apply_seo_metadata(self, page: HTMLPage, metadata: SEOMetadata) -> HTMLPage:
        """
        Apply SEO metadata to HTML page
        
        Args:
            page: HTMLPage object to modify
            metadata: SEO metadata to apply
            
        Returns:
            Modified HTMLPage with SEO metadata
        """
        # Update basic metadata
        page.title = metadata.title
        page.meta_description = metadata.description
        page.canonical_url = metadata.canonical_url
        
        # Add additional meta tags
        additional_meta = {}
        
        # Add keywords
        if metadata.keywords:
            additional_meta["keywords"] = ", ".join(metadata.keywords)
        
        # Add author
        if metadata.author:
            additional_meta["author"] = metadata.author
        
        # Add publication dates
        if metadata.published_date:
            additional_meta["article:published_time"] = metadata.published_date.isoformat()
        
        if metadata.modified_date:
            additional_meta["article:modified_time"] = metadata.modified_date.isoformat()
        
        # Add robots meta
        additional_meta["robots"] = "index, follow"
        
        # Add viewport
        additional_meta["viewport"] = "width=device-width, initial-scale=1.0"
        
        page.additional_meta.update(additional_meta)
        
        return page
    
    def generate_canonical_url(self, content_type: str, content_id: str, **kwargs) -> str:
        """
        Generate canonical URL for content
        
        Args:
            content_type: Type of content (episode, series, host)
            content_id: Content identifier
            **kwargs: Additional parameters for URL generation
            
        Returns:
            Canonical URL string
        """
        if content_type == "episode":
            # For episodes, we need the episode object or at least episode_id
            episode_id = content_id
            return urljoin(self.url_patterns.base_url, 
                          self.url_patterns.episode_pattern.format(episode_id=episode_id))
        
        elif content_type == "series":
            series_slug = kwargs.get("series_slug", content_id)
            return urljoin(self.url_patterns.base_url,
                          self.url_patterns.series_pattern.format(series_slug=series_slug))
        
        elif content_type == "host":
            host_slug = kwargs.get("host_slug", content_id)
            return urljoin(self.url_patterns.base_url,
                          self.url_patterns.host_pattern.format(host_slug=host_slug))
        
        else:
            raise ValueError(f"Unknown content type: {content_type}")
    
    def create_redirect_rules(self, old_urls: List[str], new_url: str) -> List[Dict[str, str]]:
        """
        Create 301 redirect rules for legacy URLs
        
        Args:
            old_urls: List of old URLs to redirect from
            new_url: New canonical URL to redirect to
            
        Returns:
            List of redirect rule dictionaries
        """
        redirect_rules = []
        
        for old_url in old_urls:
            redirect_rules.append({
                "from": old_url,
                "to": new_url,
                "status": "301",
                "type": "permanent"
            })
        
        return redirect_rules
    
    def render_complete_html(self, page: HTMLPage) -> str:
        """
        Render complete HTML document with all metadata
        
        Args:
            page: HTMLPage object with all content and metadata
            
        Returns:
            Complete HTML document string
        """
        # Build meta tags
        meta_tags = []
        
        # Basic meta tags
        meta_tags.append(f'<meta charset="UTF-8">')
        meta_tags.append(f'<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        meta_tags.append(f'<title>{self._escape_html(page.title)}</title>')
        meta_tags.append(f'<meta name="description" content="{self._escape_html(page.meta_description)}">')
        meta_tags.append(f'<link rel="canonical" href="{page.canonical_url}">')
        
        # Additional meta tags
        for name, content in page.additional_meta.items():
            meta_tags.append(f'<meta name="{name}" content="{self._escape_html(content)}">')
        
        # Open Graph tags
        for property_name, content in page.open_graph.items():
            if isinstance(content, list):
                for item in content:
                    meta_tags.append(f'<meta property="{property_name}" content="{self._escape_html(item)}">')
            else:
                meta_tags.append(f'<meta property="{property_name}" content="{self._escape_html(content)}">')
        
        # Twitter Card tags
        for name, content in page.twitter_card.items():
            meta_tags.append(f'<meta name="{name}" content="{self._escape_html(content)}">')
        
        # CSS files
        css_links = []
        for css_file in page.css_files:
            css_links.append(f'<link rel="stylesheet" href="{css_file}">')
        
        # JavaScript files
        js_scripts = []
        for js_file in page.js_files:
            js_scripts.append(f'<script src="{js_file}"></script>')
        
        # JSON-LD structured data
        json_ld_script = ""
        if page.json_ld:
            json_ld_script = f'''
        <script type="application/ld+json">
        {json.dumps(page.json_ld, indent=2, ensure_ascii=False)}
        </script>'''
        
        # Combine everything into complete HTML document
        html_document = f'''<!DOCTYPE html>
<html lang="en">
<head>
    {chr(10).join(meta_tags)}
    {chr(10).join(css_links)}
    {json_ld_script}
</head>
<body>
    <header>
        <nav>
            <div class="container">
                <a href="/" class="logo">{self.site_name}</a>
                <ul class="nav-menu">
                    <li><a href="/series">Series</a></li>
                    <li><a href="/hosts">Hosts</a></li>
                    <li><a href="/search">Search</a></li>
                </ul>
            </div>
        </nav>
    </header>
    
    <main>
        {page.content}
    </main>
    
    <footer>
        <div class="container">
            <p>&copy; {datetime.now().year} {self.site_name}. Educational content archive.</p>
            <ul class="footer-links">
                <li><a href="/sitemap.xml">Sitemap</a></li>
                <li><a href="/feeds/rss.xml">RSS Feed</a></li>
            </ul>
        </div>
    </footer>
    
    {chr(10).join(js_scripts)}
</body>
</html>'''
        
        return html_document


# Utility functions for working with WebGenerator

def create_web_generator(base_url: str = "https://example.com", 
                        site_name: str = "Content Publishing Platform",
                        site_description: str = "Educational content archive") -> WebGenerator:
    """
    Create a WebGenerator instance with specified configuration
    
    Args:
        base_url: Base URL for the site
        site_name: Site name for metadata
        site_description: Site description for metadata
        
    Returns:
        Configured WebGenerator instance
    """
    url_patterns = URLPattern(base_url=base_url)
    return WebGenerator(url_patterns, site_name, site_description)


def generate_clean_slug(text: str) -> str:
    """
    Generate clean URL slug from text
    
    Args:
        text: Text to convert to slug
        
    Returns:
        Clean URL slug
    """
    import re
    
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().replace(" ", "-")
    
    # Remove special characters except hyphens and alphanumeric
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug


def validate_url_patterns(url_patterns: URLPattern) -> List[str]:
    """
    Validate URL patterns for common issues
    
    Args:
        url_patterns: URLPattern object to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Check base URL format
    if not url_patterns.base_url.startswith(('http://', 'https://')):
        errors.append("Base URL must start with http:// or https://")
    
    # Check pattern placeholders
    required_placeholders = {
        'episode_pattern': ['{episode_id}'],
        'series_pattern': ['{series_slug}'],
        'host_pattern': ['{host_slug}']
    }
    
    for pattern_name, placeholders in required_placeholders.items():
        pattern_value = getattr(url_patterns, pattern_name)
        for placeholder in placeholders:
            if placeholder not in pattern_value:
                errors.append(f"{pattern_name} must contain {placeholder} placeholder")
    
    return errors