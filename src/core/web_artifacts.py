"""
Web Artifact Generator for the Video Processing Pipeline

Generates professional HTML pages, JSON metadata, and structured data
for TV/journalistic content presentation with responsive design and
accessibility compliance.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from urllib.parse import quote

from .config import PipelineConfig
from .logging import get_logger
from .exceptions import ProcessingError
from .models import EpisodeObject, EditorialContent, EnrichmentResult, EpisodeMetadata
from .journalistic_formatter import JournalisticFormatter
from ..utils.transcript_cleaner import clean_transcript

logger = get_logger('pipeline.web_artifacts')


@dataclass
class WebArtifactResult:
    """Result of web artifact generation"""
    html_path: str
    json_path: str
    metadata_path: str
    folder_path: str
    assets_created: List[str]
    schema_validation: Dict[str, Any]
    generation_time: float


class WebArtifactGenerator:
    """
    Web artifact generator for professional TV/journalistic presentation
    
    Creates responsive HTML pages with embedded JSON-LD schema markup,
    complete JSON metadata exports, and organized folder structures
    for web publishing workflows.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logger
        
        # Output configuration
        self.output_base = Path(config.get('output', {}).get('web_artifacts', 'output/web'))
        self.template_dir = Path(__file__).parent / 'templates'
        
        # Web configuration
        self.base_url = config.get('web', {}).get('base_url', '')
        self.cdn_url = config.get('web', {}).get('cdn_url', '')
        self.analytics_id = config.get('web', {}).get('analytics_id', '')
        
        # Ensure output directory exists
        self.output_base.mkdir(parents=True, exist_ok=True)
    
    def generate_web_artifacts(self, episode: EpisodeObject) -> WebArtifactResult:
        """
        Generate complete web artifacts for an episode
        
        Args:
            episode: Episode object with all processing data
            
        Returns:
            WebArtifactResult: Generated artifact information
            
        Raises:
            ProcessingError: If artifact generation fails
        """
        start_time = datetime.now()
        
        self.logger.info(
            "Generating web artifacts",
            episode_id=episode.episode_id
        )
        
        try:
            # Create episode folder structure
            episode_folder = self._create_episode_folder(episode)
            
            # Generate HTML page
            html_path = self.generate_episode_html(episode, episode_folder)
            
            # Generate JSON metadata
            json_path = self.create_json_metadata(episode, episode_folder)
            
            # Generate complete metadata export
            metadata_path = self.create_metadata_export(episode, episode_folder)
            
            # Validate generated artifacts
            schema_validation = self._validate_artifacts(html_path, json_path)
            
            # Calculate generation time
            generation_time = (datetime.now() - start_time).total_seconds()
            
            result = WebArtifactResult(
                html_path=str(html_path),
                json_path=str(json_path),
                metadata_path=str(metadata_path),
                folder_path=str(episode_folder),
                assets_created=[
                    str(html_path),
                    str(json_path),
                    str(metadata_path)
                ],
                schema_validation=schema_validation,
                generation_time=generation_time
            )
            
            self.logger.info(
                "Web artifacts generated successfully",
                episode_id=episode.episode_id,
                generation_time=generation_time,
                artifacts_count=len(result.assets_created)
            )
            
            return result
        
        except Exception as e:
            error_msg = f"Failed to generate web artifacts: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="web_artifact_generation")
    
    def generate_episode_html(self, episode: EpisodeObject, 
                            output_folder: Optional[Path] = None) -> Path:
        """
        Generate responsive HTML page with TV/journalistic styling
        
        Args:
            episode: Episode object with all data
            output_folder: Optional output folder (defaults to episode folder)
            
        Returns:
            Path: Path to generated HTML file
        """
        try:
            if output_folder is None:
                output_folder = self._create_episode_folder(episode)
            
            # Generate HTML content
            html_content = self._generate_html_content(episode)
            
            # Write HTML file
            html_path = output_folder / 'index.html'
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.debug(
                "HTML page generated",
                episode_id=episode.episode_id,
                html_path=str(html_path)
            )
            
            return html_path
        
        except Exception as e:
            error_msg = f"Failed to generate HTML page: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="html_generation")
    
    def create_json_metadata(self, episode: EpisodeObject,
                           output_folder: Optional[Path] = None) -> Path:
        """
        Generate complete episode metadata JSON with all enrichment data
        
        Args:
            episode: Episode object with all data
            output_folder: Optional output folder (defaults to episode folder)
            
        Returns:
            Path: Path to generated JSON file
        """
        try:
            if output_folder is None:
                output_folder = self._create_episode_folder(episode)
            
            # Generate complete metadata
            metadata = self._generate_complete_metadata(episode)
            
            # Write JSON file
            json_path = output_folder / 'metadata.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.debug(
                "JSON metadata generated",
                episode_id=episode.episode_id,
                json_path=str(json_path)
            )
            
            return json_path
        
        except Exception as e:
            error_msg = f"Failed to generate JSON metadata: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="json_metadata_generation")
    
    def create_metadata_export(self, episode: EpisodeObject,
                             output_folder: Optional[Path] = None) -> Path:
        """
        Create comprehensive metadata export for web publishing workflows
        
        Args:
            episode: Episode object with all data
            output_folder: Optional output folder (defaults to episode folder)
            
        Returns:
            Path: Path to generated export file
        """
        try:
            if output_folder is None:
                output_folder = self._create_episode_folder(episode)
            
            # Generate export data
            export_data = self._generate_export_data(episode)
            
            # Write export file
            export_path = output_folder / 'export.json'
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.debug(
                "Metadata export generated",
                episode_id=episode.episode_id,
                export_path=str(export_path)
            )
            
            return export_path
        
        except Exception as e:
            error_msg = f"Failed to generate metadata export: {str(e)}"
            self.logger.error(error_msg, episode_id=episode.episode_id, exception=e)
            raise ProcessingError(error_msg, stage="metadata_export_generation")
    
    def generate_json_ld_schema(self, episode: EpisodeObject) -> Dict[str, Any]:
        """
        Generate JSON-LD schema markup optimized for news and media discovery
        
        Args:
            episode: Episode object with all data
            
        Returns:
            Dict[str, Any]: JSON-LD structured data
        """
        try:
            # Base TVEpisode schema
            schema = {
                "@context": "https://schema.org",
                "@type": "TVEpisode",
                "identifier": episode.episode_id,
                "url": self._generate_episode_url(episode),
                "dateCreated": episode.created_at.isoformat() if episode.created_at else None,
                "dateModified": episode.updated_at.isoformat() if episode.updated_at else None
            }
            
            # Add episode metadata
            self._add_episode_metadata_to_schema(schema, episode)
            
            # Add series information
            self._add_series_info_to_schema(schema, episode)
            
            # Add person/guest information
            self._add_person_info_to_schema(schema, episode)
            
            # Add organization information
            self._add_organization_info_to_schema(schema, episode)
            
            # Add content information
            self._add_content_info_to_schema(schema, episode)
            
            # Add media information
            self._add_media_info_to_schema(schema, episode)
            
            return schema
        
        except Exception as e:
            self.logger.warning(
                "Failed to generate JSON-LD schema",
                episode_id=episode.episode_id,
                exception=e
            )
            # Return minimal schema
            return {
                "@context": "https://schema.org",
                "@type": "TVEpisode",
                "identifier": episode.episode_id,
                "name": episode.metadata.title or episode.episode_id
            }
    
    # Private helper methods
    
    def _create_episode_folder(self, episode: EpisodeObject) -> Path:
        """Create organized folder structure for episode"""
        # Create folder path: show/season/episode_id
        folder_parts = [episode.metadata.show_slug]
        
        if episode.metadata.season:
            folder_parts.append(f"season-{episode.metadata.season}")
        
        folder_parts.append(episode.episode_id)
        
        episode_folder = self.output_base / Path(*folder_parts)
        episode_folder.mkdir(parents=True, exist_ok=True)
        
        return episode_folder
    
    def _generate_html_content(self, episode: EpisodeObject) -> str:
        """Generate complete HTML content for episode"""
        # Generate JSON-LD schema
        json_ld = self.generate_json_ld_schema(episode)
        
        # Get episode data
        title = self._get_episode_title(episode)
        description = self._get_episode_description(episode)
        
        # Generate HTML template
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self._escape_html(title)}</title>
    <meta name="description" content="{self._escape_html(description)}">
    
    <!-- SEO Meta Tags -->
    {self._generate_seo_meta_tags(episode)}
    
    <!-- JSON-LD Schema -->
    <script type="application/ld+json">
{json.dumps(json_ld, indent=2)}
    </script>
    
    <!-- Styles -->
    {self._generate_css_styles()}
    
    {self._generate_analytics_code()}
</head>
<body>
    <div class="container">
        <!-- Header -->
        {self._generate_header(episode)}
        
        <!-- Episode Info -->
        {self._generate_episode_info(episode)}
        
        <!-- Guest Credentials -->
        {self._generate_guest_credentials(episode)}
        
        <!-- Video Section -->
        {self._generate_video_section(episode)}
        
        <!-- Transcript -->
        {self._generate_transcript_section(episode)}
        
        <!-- Related Content -->
        {self._generate_related_content(episode)}
        
        <!-- Footer -->
        {self._generate_footer(episode)}
    </div>
    
    <!-- Scripts -->
    {self._generate_javascript()}
</body>
</html>"""
        
        return html_template
    
    def _generate_seo_meta_tags(self, episode: EpisodeObject) -> str:
        """Generate SEO meta tags"""
        tags = []
        
        # Basic meta tags
        title = self._get_episode_title(episode)
        description = self._get_episode_description(episode)
        
        # Keywords from topic tags
        keywords = []
        if episode.editorial and episode.editorial.topic_tags:
            keywords.extend(episode.editorial.topic_tags)
        if episode.metadata.show_name:
            keywords.append(episode.metadata.show_name)
        
        if keywords:
            tags.append(f'<meta name="keywords" content="{", ".join(keywords[:10])}">')
        
        # Open Graph tags
        tags.append(f'<meta property="og:title" content="{self._escape_html(title)}">')
        tags.append(f'<meta property="og:description" content="{self._escape_html(description)}">')
        tags.append('<meta property="og:type" content="video.episode">')
        
        episode_url = self._generate_episode_url(episode)
        if episode_url:
            tags.append(f'<meta property="og:url" content="{episode_url}">')
        
        # Twitter Card tags
        tags.append('<meta name="twitter:card" content="summary_large_image">')
        tags.append(f'<meta name="twitter:title" content="{self._escape_html(title)}">')
        tags.append(f'<meta name="twitter:description" content="{self._escape_html(description)}">')
        
        # Canonical URL
        if episode_url:
            tags.append(f'<link rel="canonical" href="{episode_url}">')
        
        return '\n    '.join(tags)
    
    def _generate_css_styles(self) -> str:
        """Generate responsive CSS styles for TV/journalistic presentation with AI enhancements"""
        return """<style>
/* Reset and Base Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Georgia', 'Times New Roman', serif;
    line-height: 1.6;
    color: #333;
    background-color: #fff;
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1rem;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}

/* AI Enhanced Badge */
.ai-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: bold;
    display: inline-block;
    margin-bottom: 1.5rem;
}

/* AI Content Boxes */
.key-takeaway {
    background: #f0f8ff;
    border-left: 4px solid #0066cc;
    padding: 1rem;
    margin: 1.5rem 0;
}

.takeaways-list {
    background: #f0fff0;
    border-left: 4px solid #28a745;
    padding: 1rem;
    margin: 1.5rem 0;
}

.takeaways-list ul {
    margin-left: 1.5rem;
    margin-top: 0.5rem;
}

.takeaways-list li {
    margin-bottom: 0.5rem;
}

.analysis-box {
    background: #fff9e6;
    border-left: 4px solid #ffa500;
    padding: 1rem;
    margin: 1.5rem 0;
}

.topics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1rem 0;
}

.topic-tag {
    background: #e9ecef;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.875rem;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Arial', 'Helvetica', sans-serif;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #1a1a1a;
}

h1 {
    font-size: 2.5rem;
    line-height: 1.2;
}

h2 {
    font-size: 2rem;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
}

h3 {
    font-size: 1.5rem;
    color: #34495e;
}

p {
    margin-bottom: 1rem;
    font-size: 1.1rem;
}

/* Header */
.header {
    background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
    color: white;
    padding: 2rem 0;
    margin-bottom: 2rem;
}

.show-title {
    font-size: 1.2rem;
    opacity: 0.9;
    margin-bottom: 0.5rem;
}

.episode-title {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 1rem;
}

.host-info {
    font-size: 1.1rem;
    color: #3498db;
    font-weight: 500;
    margin-bottom: 0.5rem;
}

.episode-meta {
    font-size: 1rem;
    opacity: 0.8;
}

/* Episode Info */
.episode-info {
    background: #f8f9fa;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    border-left: 4px solid #3498db;
}

.key-takeaway {
    font-size: 1.3rem;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 1rem;
    font-style: italic;
}

.episode-summary {
    font-size: 1.1rem;
    line-height: 1.7;
    margin-bottom: 1.5rem;
}

.topic-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.tag {
    background: #3498db;
    color: white;
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 500;
}

/* Guest Credentials */
.guests-section {
    margin-bottom: 2rem;
}

.guest-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-top: 1rem;
}

.guest-card {
    background: white;
    border: 1px solid #e1e8ed;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: box-shadow 0.3s ease;
}

.guest-card:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.guest-name {
    font-size: 1.3rem;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 0.5rem;
}

.guest-title {
    font-size: 1rem;
    color: #7f8c8d;
    margin-bottom: 0.5rem;
}

.guest-affiliation {
    font-size: 0.9rem;
    color: #95a5a6;
    margin-bottom: 1rem;
}

.credibility-badge {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 15px;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
}

.badge-verified {
    background: #27ae60;
    color: white;
}

.badge-identified {
    background: #f39c12;
    color: white;
}

.badge-guest {
    background: #95a5a6;
    color: white;
}

/* Video Section */
.video-section {
    background: #2c3e50;
    color: white;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    text-align: center;
}

.video-placeholder {
    background: #34495e;
    border: 2px dashed #7f8c8d;
    border-radius: 8px;
    padding: 3rem 2rem;
    margin: 1rem 0;
}

.video-info {
    font-size: 1.1rem;
    margin-bottom: 1rem;
}

.download-links {
    display: flex;
    justify-content: center;
    gap: 1rem;
    flex-wrap: wrap;
}

.download-btn {
    background: #3498db;
    color: white;
    padding: 0.8rem 1.5rem;
    text-decoration: none;
    border-radius: 5px;
    font-weight: 600;
    transition: background 0.3s ease;
}

.download-btn:hover {
    background: #2980b9;
}

/* Transcript */
.transcript-section {
    margin-bottom: 2rem;
}

.transcript-content {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 2rem;
    max-height: 600px;
    overflow-y: auto;
}

.transcript-segment {
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e9ecef;
}

.transcript-segment:last-child {
    border-bottom: none;
    margin-bottom: 0;
}

.speaker-label {
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 0.5rem;
    font-size: 1rem;
}

.speaker-text {
    font-size: 1rem;
    line-height: 1.6;
    color: #495057;
}

.timestamp {
    font-size: 0.8rem;
    color: #6c757d;
    font-family: monospace;
}

/* Related Content */
.related-section {
    background: #f8f9fa;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.related-list {
    list-style: none;
}

.related-item {
    padding: 1rem;
    border-bottom: 1px solid #e9ecef;
    transition: background 0.3s ease;
}

.related-item:hover {
    background: #e9ecef;
}

.related-item:last-child {
    border-bottom: none;
}

.related-link {
    color: #3498db;
    text-decoration: none;
    font-weight: 600;
}

.related-link:hover {
    text-decoration: underline;
}

/* Footer */
.footer {
    background: #2c3e50;
    color: white;
    padding: 2rem 0;
    text-align: center;
    margin-top: 3rem;
}

.footer-content {
    font-size: 0.9rem;
    opacity: 0.8;
}

/* Responsive Design */
@media (max-width: 768px) {
    .container {
        padding: 0 15px;
    }
    
    .episode-title {
        font-size: 2rem;
    }
    
    h1 {
        font-size: 2rem;
    }
    
    h2 {
        font-size: 1.5rem;
    }
    
    .guest-grid {
        grid-template-columns: 1fr;
    }
    
    .download-links {
        flex-direction: column;
        align-items: center;
    }
    
    .episode-info,
    .video-section,
    .transcript-content,
    .related-section {
        padding: 1.5rem;
    }
}

@media (max-width: 480px) {
    .episode-title {
        font-size: 1.5rem;
    }
    
    .episode-info,
    .video-section,
    .transcript-content,
    .related-section {
        padding: 1rem;
    }
}

/* Accessibility */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* Print Styles */
@media print {
    .video-section,
    .download-links,
    .footer {
        display: none;
    }
    
    body {
        font-size: 12pt;
        line-height: 1.4;
    }
    
    .transcript-content {
        max-height: none;
        overflow: visible;
    }
}
</style>"""
    
    def _generate_analytics_code(self) -> str:
        """Generate analytics tracking code if configured"""
        if not self.analytics_id:
            return ""
        
        return f"""
    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={self.analytics_id}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', '{self.analytics_id}');
    </script>"""
    
    def _generate_header(self, episode: EpisodeObject) -> str:
        """Generate header section with show name, episode info, and host"""
        # Get show name (prefer AI-extracted, fallback to metadata)
        enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
        show_name = enrichment.get('show_name_extracted') or episode.metadata.show_name or "Episode"
        
        # Get host name from AI extraction
        host_name = enrichment.get('host_name_extracted', '')
        ai_analysis = enrichment.get('ai_analysis', {})
        if not host_name:
            host_name = ai_analysis.get('host_name', '')
        
        title = self._get_episode_title(episode)
        
        # Generate episode metadata string
        meta_parts = []
        
        # Episode number/season
        if episode.metadata.season and episode.metadata.episode:
            meta_parts.append(f"S{episode.metadata.season}E{episode.metadata.episode}")
        elif episode.metadata.episode:
            meta_parts.append(f"Episode {episode.metadata.episode}")
        
        # Date
        if episode.metadata.date:
            meta_parts.append(episode.metadata.date)
        
        # Duration
        if episode.media.duration_seconds:
            duration_min = int(episode.media.duration_seconds // 60)
            meta_parts.append(f"{duration_min} min")
        
        meta_string = " • ".join(meta_parts)
        
        # Build header HTML
        header_html = f"""<header class="header">
            <div class="container">
                <div class="show-title">{self._escape_html(show_name)}</div>
                <h1 class="episode-title">{self._escape_html(title)}</h1>"""
        
        # Add host name if available
        if host_name:
            header_html += f"""
                <div class="host-info">Hosted by {self._escape_html(host_name)}</div>"""
        
        # Add episode metadata
        if meta_string:
            header_html += f"""
                <div class="episode-meta">{self._escape_html(meta_string)}</div>"""
        
        header_html += """
            </div>
        </header>"""
        
        return header_html
    
    def _generate_episode_info(self, episode: EpisodeObject) -> str:
        """Generate episode information section with AI enhancements"""
        sections = []
        
        # Check for AI-enhanced enrichment data
        ai_analysis = None
        if episode.enrichment:
            # Try to get AI analysis from enrichment
            enrichment_data = episode.enrichment
            if hasattr(enrichment_data, 'get'):
                ai_analysis = enrichment_data.get('ai_analysis', {})
            elif hasattr(enrichment_data, 'ai_analysis'):
                ai_analysis = enrichment_data.ai_analysis
        
        # AI Enhanced Badge
        if ai_analysis and (ai_analysis.get('executive_summary') or ai_analysis.get('key_takeaways')):
            sections.append('<div class="ai-badge">AI ENHANCED</div>')
        
        # Executive Summary (AI-generated)
        if ai_analysis and ai_analysis.get('executive_summary'):
            summary_text = ai_analysis['executive_summary']
            sections.append(f'''<div class="key-takeaway">
                <h2 style="margin-top:0;">Executive Summary</h2>
                <p>{self._escape_html(summary_text)}</p>
            </div>''')
        
        # Key Takeaways (AI-generated)
        if ai_analysis and ai_analysis.get('key_takeaways'):
            takeaways = ai_analysis['key_takeaways']
            if takeaways:
                takeaway_items = ''.join([f'<li>{self._escape_html(t)}</li>' for t in takeaways])
                sections.append(f'''<div class="takeaways-list">
                    <h2 style="margin-top:0;">Key Takeaways</h2>
                    <ul>{takeaway_items}</ul>
                </div>''')
        
        # Topics Covered (AI-generated)
        if ai_analysis and ai_analysis.get('topics'):
            topics = ai_analysis['topics']
            if topics:
                topic_tags = ''.join([f'<span class="topic-tag">{self._escape_html(t)}</span>' for t in topics])
                sections.append(f'''<h2>Topics Covered</h2>
                <div class="topics">{topic_tags}</div>''')
        
        # Deep Analysis (AI-generated)
        if ai_analysis and ai_analysis.get('deep_analysis'):
            analysis_text = ai_analysis['deep_analysis']
            sections.append(f'''<div class="analysis-box">
                <h2 style="margin-top:0;">Deep Analysis</h2>
                <p>{self._escape_html(analysis_text)}</p>
            </div>''')
        
        # Fallback to editorial content if no AI analysis
        if not sections and episode.editorial:
            editorial = episode.editorial
            
            # Key takeaway
            if editorial.key_takeaway:
                sections.append(f'<div class="key-takeaway">{self._escape_html(editorial.key_takeaway)}</div>')
            
            # Summary
            if editorial.summary:
                sections.append(f'<div class="episode-summary">{self._escape_html(editorial.summary)}</div>')
            
            # Topic tags
            if editorial.topic_tags:
                tags = [f'<span class="tag">{self._escape_html(tag)}</span>' for tag in editorial.topic_tags]
                sections.append(f'<div class="topic-tags">{"".join(tags)}</div>')
        
        if not sections:
            return ""
        
        return f'''<section class="episode-info">
            {"".join(sections)}
        </section>'''
    
    def _generate_guest_credentials(self, episode: EpisodeObject) -> str:
        """Generate guest credentials section with verification badges"""
        # Handle enrichment as dict
        enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
        if not enrichment:
            return ""
        
        scores_data = enrichment.get('proficiency_scores', {})
        if not scores_data or 'scored_people' not in scores_data:
            return ""
        
        guests = scores_data['scored_people']
        if not guests:
            return ""
        
        guest_cards = []
        for guest in guests:
            name = guest.get('name', '')
            if not name:
                continue
            
            title = guest.get('job_title', '')
            affiliation = guest.get('affiliation', '')
            badge = guest.get('credibilityBadge', 'Guest')
            score = guest.get('proficiencyScore', 0)
            reasoning = guest.get('reasoning', '')
            
            # Determine badge class
            badge_class = 'badge-guest'
            if badge == 'Verified Expert':
                badge_class = 'badge-verified'
            elif badge == 'Identified Contributor':
                badge_class = 'badge-identified'
            
            # Build guest card
            card_html = f"""<div class="guest-card">
                <div class="guest-name">{self._escape_html(name)}</div>"""
            
            if title:
                card_html += f'<div class="guest-title">{self._escape_html(title)}</div>'
            
            if affiliation:
                card_html += f'<div class="guest-affiliation">{self._escape_html(affiliation)}</div>'
            
            card_html += f'<div class="credibility-badge {badge_class}">{self._escape_html(badge)}</div>'
            
            if reasoning and len(reasoning) < 200:
                card_html += f'<div class="guest-reasoning" style="margin-top: 1rem; font-size: 0.9rem; color: #6c757d;">{self._escape_html(reasoning)}</div>'
            
            card_html += '</div>'
            guest_cards.append(card_html)
        
        if not guest_cards:
            return ""
        
        return f"""<section class="guests-section">
            <h2>Featured Guests</h2>
            <div class="guest-grid">
                {"".join(guest_cards)}
            </div>
        </section>"""
    
    def _generate_video_section(self, episode: EpisodeObject) -> str:
        """Generate video embed placeholder and download links"""
        # Video info
        info_parts = []
        if episode.media.duration_seconds:
            duration_min = int(episode.media.duration_seconds // 60)
            duration_sec = int(episode.media.duration_seconds % 60)
            info_parts.append(f"Duration: {duration_min}:{duration_sec:02d}")
        
        if episode.media.resolution:
            info_parts.append(f"Resolution: {episode.media.resolution}")
        
        video_info = " • ".join(info_parts) if info_parts else ""
        
        # Download links
        download_links = []
        
        # Original video file
        if episode.source.path:
            filename = Path(episode.source.path).name
            download_links.append(f'<a href="#" class="download-btn" onclick="alert(\'Video download: {filename}\')">Download Video</a>')
        
        # Transcript files
        download_links.append('<a href="transcript.txt" class="download-btn">Download Transcript</a>')
        download_links.append('<a href="captions.vtt" class="download-btn">Download Captions</a>')
        
        return f"""<section class="video-section">
            <h2>Video Content</h2>
            <div class="video-placeholder">
                <p>Video Player Placeholder</p>
                <p style="font-size: 0.9rem; opacity: 0.7;">Video embed integration point</p>
            </div>
            {f'<div class="video-info">{self._escape_html(video_info)}</div>' if video_info else ''}
            <div class="download-links">
                {"".join(download_links)}
            </div>
        </section>"""
    
    def _generate_transcript_section(self, episode: EpisodeObject) -> str:
        """Generate speaker-labeled transcript presentation"""
        if not episode.transcription or not episode.transcription.text:
            return ""
        
        transcript_html = ""
        
        # Check if we have diarization data for speaker labels
        enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
        diarization = enrichment.get('diarization', {})
        if diarization and 'segments' in diarization:
            
            # Use diarized segments
            segments = diarization['segments']
            for segment in segments:
                speaker = segment.get('speaker', 'Speaker')
                text = segment.get('text', '').strip()
                start_time = segment.get('start', 0)
                
                if text:
                    # Format timestamp
                    minutes = int(start_time // 60)
                    seconds = int(start_time % 60)
                    timestamp = f"{minutes}:{seconds:02d}"
                    
                    transcript_html += f"""<div class="transcript-segment">
                        <div class="speaker-label">{self._escape_html(speaker)} <span class="timestamp">[{timestamp}]</span></div>
                        <div class="speaker-text">{self._escape_html(text)}</div>
                    </div>"""
        else:
            # Use plain transcript with paragraph breaks
            text = episode.transcription.text
            paragraphs = text.split('\n\n')
            
            for i, paragraph in enumerate(paragraphs):
                paragraph = paragraph.strip()
                if paragraph:
                    transcript_html += f"""<div class="transcript-segment">
                        <div class="speaker-label">Transcript</div>
                        <div class="speaker-text">{self._escape_html(paragraph)}</div>
                    </div>"""
        
        if not transcript_html:
            return ""
        
        return f"""<section class="transcript-section">
            <h2>Transcript</h2>
            <div class="transcript-content">
                {transcript_html}
            </div>
        </section>"""
    
    def _generate_related_content(self, episode: EpisodeObject) -> str:
        """Generate related content section"""
        if not episode.editorial or not episode.editorial.related_episodes:
            return ""
        
        related_items = []
        for related_id in episode.editorial.related_episodes:
            # For now, just show the episode ID as a placeholder
            # In a full implementation, this would fetch episode metadata
            related_items.append(f"""<li class="related-item">
                <a href="../{related_id}/" class="related-link">{related_id}</a>
            </li>""")
        
        if not related_items:
            return ""
        
        return f"""<section class="related-section">
            <h2>Related Episodes</h2>
            <ul class="related-list">
                {"".join(related_items)}
            </ul>
        </section>"""
    
    def _generate_footer(self, episode: EpisodeObject) -> str:
        """Generate footer section"""
        return f"""<footer class="footer">
            <div class="container">
                <div class="footer-content">
                    <p>Generated by Video Processing Pipeline • Episode ID: {episode.episode_id}</p>
                    <p>Last updated: {episode.updated_at.strftime('%B %d, %Y') if episode.updated_at else 'Unknown'}</p>
                </div>
            </div>
        </footer>"""
    
    def _generate_javascript(self) -> str:
        """Generate JavaScript for interactive features"""
        return """<script>
// Transcript search functionality
document.addEventListener('DOMContentLoaded', function() {
    // Add search functionality if needed
    console.log('Episode page loaded');
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});
</script>"""
    
    def _generate_complete_metadata(self, episode: EpisodeObject) -> Dict[str, Any]:
        """Generate complete metadata JSON"""
        metadata = {
            "episode": {
                "id": episode.episode_id,
                "content_hash": episode.content_hash,
                "processing_stage": episode.processing_stage.value,
                "created_at": episode.created_at.isoformat() if episode.created_at else None,
                "updated_at": episode.updated_at.isoformat() if episode.updated_at else None
            },
            "source": episode.source.to_dict(),
            "media": episode.media.to_dict(),
            "metadata": episode.metadata.to_dict()
        }
        
        # Add transcription data
        if episode.transcription:
            metadata["transcription"] = episode.transcription.to_dict()
        
        # Add enrichment data
        if episode.enrichment:
            # Handle enrichment as dict or object
            if isinstance(episode.enrichment, dict):
                metadata["enrichment"] = episode.enrichment
            else:
                metadata["enrichment"] = episode.enrichment.to_dict()
        
        # Add editorial data
        if episode.editorial:
            metadata["editorial"] = episode.editorial.to_dict()
        
        # Add JSON-LD schema
        metadata["schema"] = self.generate_json_ld_schema(episode)
        
        # Add web metadata
        metadata["web"] = {
            "title": self._get_episode_title(episode),
            "description": self._get_episode_description(episode),
            "url": self._generate_episode_url(episode),
            "generated_at": datetime.now().isoformat()
        }
        
        return metadata
    
    def _generate_export_data(self, episode: EpisodeObject) -> Dict[str, Any]:
        """Generate export data for web publishing workflows"""
        export_data = {
            "episode_id": episode.episode_id,
            "export_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "web_ready": True
        }
        
        # Episode metadata
        export_data["episode"] = {
            "title": self._get_episode_title(episode),
            "description": self._get_episode_description(episode),
            "show_name": episode.metadata.show_name,
            "show_slug": episode.metadata.show_slug,
            "season": episode.metadata.season,
            "episode_number": episode.metadata.episode,
            "date": episode.metadata.date,
            "topic": episode.metadata.topic,
            "duration_seconds": episode.media.duration_seconds
        }
        
        # Guest profiles with proficiency scores
        enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
        scores_data = enrichment.get('proficiency_scores', {})
        if scores_data and 'scored_people' in scores_data:
            export_data["guests"] = []
            for person in scores_data['scored_people']:
                guest_profile = {
                    "name": person.get('name', ''),
                    "title": person.get('job_title', ''),
                    "affiliation": person.get('affiliation', ''),
                    "credibility_badge": person.get('credibilityBadge', 'Guest'),
                    "proficiency_score": person.get('proficiencyScore', 0),
                    "reasoning": person.get('reasoning', ''),
                    "confidence": person.get('confidence', 0)
                }
                export_data["guests"].append(guest_profile)
        
        # Diarized transcript with speaker attribution
        diarization_data = enrichment.get('diarization', {})
        if diarization_data and 'segments' in diarization_data:
            export_data["diarized_transcript"] = {
                "segments": diarization_data['segments'],
                "speaker_count": len(set(seg.get('speaker', '') for seg in diarization_data['segments'])),
                "total_duration": episode.media.duration_seconds
            }
        
        # Editorial content
        if episode.editorial:
            export_data["editorial"] = {
                "key_takeaway": episode.editorial.key_takeaway,
                "summary": episode.editorial.summary,
                "topic_tags": episode.editorial.topic_tags,
                "related_episodes": episode.editorial.related_episodes,
                "quality_score": episode.editorial.quality_score,
                "seo_score": episode.editorial.seo_score
            }
        
        # File references
        export_data["files"] = {
            "html": "index.html",
            "metadata": "metadata.json",
            "transcript_txt": "transcript.txt",
            "transcript_vtt": "captions.vtt",
            "original_video": Path(episode.source.path).name if episode.source.path else None
        }
        
        # SEO data
        export_data["seo"] = {
            "title": self._get_episode_title(episode),
            "description": self._get_episode_description(episode),
            "keywords": episode.editorial.topic_tags if episode.editorial else [],
            "canonical_url": self._generate_episode_url(episode),
            "schema_type": "TVEpisode"
        }
        
        return export_data
    
    def _add_episode_metadata_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add episode metadata to JSON-LD schema"""
        metadata = episode.metadata
        
        # Basic episode info
        if metadata.title:
            schema["name"] = metadata.title
        elif episode.editorial and episode.editorial.key_takeaway:
            schema["name"] = episode.editorial.key_takeaway
        else:
            schema["name"] = episode.episode_id
        
        if episode.editorial and episode.editorial.summary:
            schema["description"] = episode.editorial.summary
        
        # Episode numbers
        if metadata.season:
            schema["seasonNumber"] = metadata.season
        if metadata.episode:
            schema["episodeNumber"] = metadata.episode
        
        # Publication date
        if metadata.date:
            schema["datePublished"] = metadata.date
        
        # Keywords from topic tags
        if episode.editorial and episode.editorial.topic_tags:
            schema["keywords"] = episode.editorial.topic_tags
    
    def _add_series_info_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add TV series information to schema"""
        if episode.metadata.show_name:
            schema["partOfSeries"] = {
                "@type": "TVSeries",
                "name": episode.metadata.show_name,
                "identifier": episode.metadata.show_slug
            }
    
    def _add_person_info_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add person/guest information to schema"""
        # Handle enrichment as dict
        enrichment = episode.enrichment if isinstance(episode.enrichment, dict) else {}
        if not enrichment:
            return
        
        scores_data = enrichment.get('proficiency_scores', {})
        if not scores_data or 'scored_people' not in scores_data:
            return
        
        actors = []
        for person in scores_data['scored_people']:
            name = person.get('name', '')
            if not name:
                continue
            
            actor = {
                "@type": "Person",
                "name": name
            }
            
            if person.get('job_title'):
                actor["jobTitle"] = person.get('job_title')
            
            if person.get('affiliation'):
                actor["worksFor"] = {
                    "@type": "Organization",
                    "name": person.get('affiliation')
                }
            
            # Add same-as links if available
            if person.get('same_as'):
                actor["sameAs"] = person.get('same_as')
            
            actors.append(actor)
        
        if actors:
            schema["actor"] = actors
    
    def _add_organization_info_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add organization information to schema"""
        # This could be expanded to include production companies, networks, etc.
        if episode.metadata.show_name:
            schema["productionCompany"] = {
                "@type": "Organization",
                "name": episode.metadata.show_name
            }
    
    def _add_content_info_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add content information to schema"""
        # Content rating, genre, etc.
        schema["genre"] = "Talk Show"  # Default genre
        
        # Add transcript as text content
        if episode.transcription and episode.transcription.text:
            # Truncate transcript for schema (keep it reasonable)
            transcript_preview = episode.transcription.text[:500]
            if len(episode.transcription.text) > 500:
                transcript_preview += "..."
            schema["transcript"] = transcript_preview
    
    def _add_media_info_to_schema(self, schema: Dict[str, Any], episode: EpisodeObject) -> None:
        """Add media information to schema"""
        media = episode.media
        
        # Duration
        if media.duration_seconds:
            # Convert to ISO 8601 duration format
            hours = int(media.duration_seconds // 3600)
            minutes = int((media.duration_seconds % 3600) // 60)
            seconds = int(media.duration_seconds % 60)
            
            duration_str = "PT"
            if hours > 0:
                duration_str += f"{hours}H"
            if minutes > 0:
                duration_str += f"{minutes}M"
            if seconds > 0:
                duration_str += f"{seconds}S"
            
            schema["duration"] = duration_str
        
        # Video quality
        if media.resolution:
            schema["videoQuality"] = media.resolution
        
        # Encoding format
        if media.video_codec:
            schema["encodingFormat"] = media.video_codec
    
    def _get_episode_title(self, episode: EpisodeObject) -> str:
        """Get the best available title for the episode"""
        if episode.metadata.title:
            return episode.metadata.title
        elif episode.editorial and episode.editorial.key_takeaway:
            return episode.editorial.key_takeaway
        elif episode.metadata.topic:
            return f"{episode.metadata.show_name or 'Episode'}: {episode.metadata.topic}"
        else:
            return episode.episode_id
    
    def _get_episode_description(self, episode: EpisodeObject) -> str:
        """Get the best available description for the episode"""
        if episode.editorial and episode.editorial.summary:
            return episode.editorial.summary
        elif episode.metadata.description:
            return episode.metadata.description
        elif episode.metadata.topic:
            return f"Discussion about {episode.metadata.topic}"
        else:
            return f"Episode {episode.episode_id}"
    
    def _generate_episode_url(self, episode: EpisodeObject) -> str:
        """Generate episode URL"""
        if not self.base_url:
            return ""
        
        # Build URL path
        path_parts = [episode.metadata.show_slug]
        if episode.metadata.season:
            path_parts.append(f"season-{episode.metadata.season}")
        path_parts.append(episode.episode_id)
        
        url_path = "/".join(path_parts)
        return f"{self.base_url.rstrip('/')}/{url_path}/"
    
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
    
    def _validate_artifacts(self, html_path: Path, json_path: Path) -> Dict[str, Any]:
        """Validate generated artifacts"""
        validation_result = {
            "html_valid": False,
            "json_valid": False,
            "schema_valid": False,
            "issues": []
        }
        
        try:
            # Validate HTML file exists and has content
            if html_path.exists():
                html_content = html_path.read_text(encoding='utf-8')
                if len(html_content) > 1000:  # Reasonable minimum size
                    validation_result["html_valid"] = True
                else:
                    validation_result["issues"].append("HTML file too small")
            else:
                validation_result["issues"].append("HTML file not found")
            
            # Validate JSON file
            if json_path.exists():
                try:
                    json_content = json.loads(json_path.read_text(encoding='utf-8'))
                    validation_result["json_valid"] = True
                    
                    # Check for required schema fields
                    if "schema" in json_content:
                        schema = json_content["schema"]
                        if schema.get("@context") == "https://schema.org" and schema.get("@type") == "TVEpisode":
                            validation_result["schema_valid"] = True
                        else:
                            validation_result["issues"].append("Invalid JSON-LD schema structure")
                    else:
                        validation_result["issues"].append("Missing JSON-LD schema in metadata")
                
                except json.JSONDecodeError as e:
                    validation_result["issues"].append(f"Invalid JSON format: {str(e)}")
            else:
                validation_result["issues"].append("JSON metadata file not found")
        
        except Exception as e:
            validation_result["issues"].append(f"Validation error: {str(e)}")
        
        return validation_result


class JSONLDSchemaValidator:
    """Validator for JSON-LD schema markup compliance"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.schema_validator')
    
    def validate_tv_episode_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate TVEpisode schema compliance
        
        Args:
            schema: JSON-LD schema to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        try:
            # Check required fields
            required_fields = ["@context", "@type", "name"]
            for field in required_fields:
                if field not in schema:
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Missing required field: {field}")
            
            # Check @context
            if schema.get("@context") != "https://schema.org":
                validation_result["valid"] = False
                validation_result["errors"].append("Invalid @context, must be 'https://schema.org'")
            
            # Check @type
            if schema.get("@type") != "TVEpisode":
                validation_result["valid"] = False
                validation_result["errors"].append("Invalid @type, must be 'TVEpisode'")
            
            # Check recommended fields
            recommended_fields = ["description", "partOfSeries", "datePublished"]
            for field in recommended_fields:
                if field not in schema:
                    validation_result["warnings"].append(f"Missing recommended field: {field}")
            
            # Validate partOfSeries structure
            if "partOfSeries" in schema:
                series = schema["partOfSeries"]
                if not isinstance(series, dict) or series.get("@type") != "TVSeries":
                    validation_result["warnings"].append("partOfSeries should be a TVSeries object")
            
            # Validate actor structure
            if "actor" in schema:
                actors = schema["actor"]
                if isinstance(actors, list):
                    for i, actor in enumerate(actors):
                        if not isinstance(actor, dict) or actor.get("@type") != "Person":
                            validation_result["warnings"].append(f"Actor {i} should be a Person object")
                        if "name" not in actor:
                            validation_result["warnings"].append(f"Actor {i} missing name field")
            
            # Check duration format
            if "duration" in schema:
                duration = schema["duration"]
                if not isinstance(duration, str) or not duration.startswith("PT"):
                    validation_result["warnings"].append("Duration should be in ISO 8601 format (PT...)")
            
            # Generate recommendations
            if "keywords" not in schema:
                validation_result["recommendations"].append("Add keywords for better SEO")
            
            if "genre" not in schema:
                validation_result["recommendations"].append("Add genre classification")
            
            if "transcript" not in schema:
                validation_result["recommendations"].append("Consider adding transcript excerpt")
        
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Schema validation error: {str(e)}")
        
        return validation_result
    
    def validate_person_schema(self, person_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Person schema within TVEpisode"""
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check required fields for Person
        if person_schema.get("@type") != "Person":
            validation_result["valid"] = False
            validation_result["errors"].append("Person @type must be 'Person'")
        
        if "name" not in person_schema:
            validation_result["valid"] = False
            validation_result["errors"].append("Person must have name field")
        
        # Check recommended fields
        if "jobTitle" not in person_schema:
            validation_result["warnings"].append("Person missing jobTitle")
        
        if "worksFor" not in person_schema:
            validation_result["warnings"].append("Person missing worksFor organization")
        
        # Validate worksFor structure
        if "worksFor" in person_schema:
            org = person_schema["worksFor"]
            if not isinstance(org, dict) or org.get("@type") != "Organization":
                validation_result["warnings"].append("worksFor should be an Organization object")
        
        return validation_result


class WebArtifactOptimizer:
    """Optimizer for web artifacts performance and SEO"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger('pipeline.web_optimizer')
    
    def optimize_html_performance(self, html_content: str) -> str:
        """Optimize HTML for performance"""
        # Minify HTML (basic implementation)
        optimized = re.sub(r'\s+', ' ', html_content)
        optimized = re.sub(r'>\s+<', '><', optimized)
        
        return optimized.strip()
    
    def optimize_images_for_web(self, episode_folder: Path) -> List[str]:
        """Optimize images for web delivery (placeholder)"""
        # This would implement image optimization
        # For now, just return empty list
        return []
    
    def generate_sitemap_entry(self, episode: EpisodeObject) -> Dict[str, Any]:
        """Generate sitemap entry for episode"""
        return {
            "loc": self._generate_episode_url(episode),
            "lastmod": episode.updated_at.isoformat() if episode.updated_at else None,
            "changefreq": "monthly",
            "priority": 0.8
        }
    
    def _generate_episode_url(self, episode: EpisodeObject) -> str:
        """Generate episode URL for sitemap"""
        base_url = self.config.get('web', {}).get('base_url', '')
        if not base_url:
            return ""
        
        path_parts = [episode.metadata.show_slug]
        if episode.metadata.season:
            path_parts.append(f"season-{episode.metadata.season}")
        path_parts.append(episode.episode_id)
        
        url_path = "/".join(path_parts)
        return f"{base_url.rstrip('/')}/{url_path}/"