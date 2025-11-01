"""
JSON-LD Generator for SEO and Structured Data

Generates Schema.org structured data for episodes, clips, and social media content.
Enables Google Key Moments, rich snippets, and enhanced search visibility.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class JSONLDGenerator:
    """
    Generator for Schema.org JSON-LD structured data
    
    Creates structured data for:
    - VideoObject (full episodes)
    - Clip (short-form content with partOf relationship)
    - Person (guests and hosts)
    - Organization (show/channel)
    """
    
    def __init__(self, base_url: str = "https://example.com"):
        """
        Initialize JSON-LD generator
        
        Args:
            base_url: Base URL for canonical links
        """
        self.base_url = base_url.rstrip('/')
        self.context = "https://schema.org"
    
    def generate_episode_jsonld(self, episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate JSON-LD for a full episode
        
        Args:
            episode_data: Episode metadata dictionary
        
        Returns:
            JSON-LD dictionary
        """
        episode_id = episode_data.get('episode_id', '')
        title = episode_data.get('title', 'Untitled Episode')
        show_name = episode_data.get('show_name', 'Unknown Show')
        description = episode_data.get('description', '')
        duration = episode_data.get('duration', 0)
        
        # Extract enrichment data
        enrichment = episode_data.get('enrichment', {})
        guests = enrichment.get('enriched_guests', [])
        topics = enrichment.get('topics', [])
        
        # Build JSON-LD
        jsonld = {
            "@context": self.context,
            "@type": "VideoObject",
            "@id": f"{self.base_url}/episodes/{episode_id}",
            "name": title,
            "description": description,
            "uploadDate": episode_data.get('created_at', datetime.now().isoformat()),
            "duration": self._format_duration(duration),
            "thumbnailUrl": f"{self.base_url}/thumbnails/{episode_id}.jpg",
            "contentUrl": f"{self.base_url}/videos/{episode_id}.mp4",
            "embedUrl": f"{self.base_url}/embed/{episode_id}",
            "interactionStatistic": {
                "@type": "InteractionCounter",
                "interactionType": "https://schema.org/WatchAction",
                "userInteractionCount": 0
            }
        }
        
        # Add show/series information
        if show_name:
            jsonld["partOfSeries"] = {
                "@type": "CreativeWorkSeries",
                "name": show_name,
                "url": f"{self.base_url}/shows/{self._slugify(show_name)}"
            }
        
        # Add guests as actors/contributors
        if guests:
            jsonld["actor"] = [
                self._generate_person_jsonld(guest)
                for guest in guests
            ]
        
        # Add topics as keywords
        if topics:
            jsonld["keywords"] = ", ".join(topics)
        
        # Add publisher information
        jsonld["publisher"] = {
            "@type": "Organization",
            "name": show_name,
            "url": self.base_url
        }
        
        return jsonld
    
    def generate_clip_jsonld(self, clip_data: Dict[str, Any], 
                            episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate JSON-LD for a clip with partOf relationship
        
        Args:
            clip_data: Clip metadata dictionary
            episode_data: Parent episode metadata
        
        Returns:
            JSON-LD dictionary with Clip type
        """
        clip_id = clip_data.get('clip_id', '')
        episode_id = episode_data.get('episode_id', '')
        title = clip_data.get('title', 'Untitled Clip')
        description = clip_data.get('description', '')
        start_time = clip_data.get('start_time', 0)
        end_time = clip_data.get('end_time', 0)
        duration = end_time - start_time
        
        # Build JSON-LD for clip
        jsonld = {
            "@context": self.context,
            "@type": "Clip",
            "@id": f"{self.base_url}/clips/{clip_id}",
            "name": title,
            "description": description,
            "uploadDate": clip_data.get('created_at', datetime.now().isoformat()),
            "duration": self._format_duration(duration),
            "thumbnailUrl": f"{self.base_url}/thumbnails/clips/{clip_id}.jpg",
            "contentUrl": f"{self.base_url}/videos/clips/{clip_id}.mp4",
            "embedUrl": f"{self.base_url}/embed/clips/{clip_id}",
            
            # Link to parent episode
            "partOf": {
                "@type": "VideoObject",
                "@id": f"{self.base_url}/episodes/{episode_id}",
                "name": episode_data.get('title', ''),
                "url": f"{self.base_url}/episodes/{episode_id}"
            },
            
            # Timestamps for seeking
            "startOffset": start_time,
            "endOffset": end_time,
            
            # Enable SeekToAction for Google Key Moments
            "potentialAction": {
                "@type": "SeekToAction",
                "target": f"{self.base_url}/episodes/{episode_id}?t={start_time}",
                "startOffset-input": "required name=seek_to_second_number"
            }
        }
        
        # Add topics/keywords if available
        topics = clip_data.get('topics', [])
        if topics:
            jsonld["keywords"] = ", ".join(topics)
        
        # Add publisher
        jsonld["publisher"] = {
            "@type": "Organization",
            "name": episode_data.get('show_name', 'Unknown Show'),
            "url": self.base_url
        }
        
        return jsonld
    
    def generate_social_package_jsonld(self, package_data: Dict[str, Any],
                                      episode_data: Dict[str, Any],
                                      platform: str) -> Dict[str, Any]:
        """
        Generate JSON-LD for social media package
        
        Args:
            package_data: Package metadata
            episode_data: Episode metadata
            platform: Target platform
        
        Returns:
            JSON-LD dictionary
        """
        package_id = f"{episode_data.get('episode_id', '')}_{platform}"
        
        jsonld = {
            "@context": self.context,
            "@type": "VideoObject",
            "@id": f"{self.base_url}/social/{package_id}",
            "name": package_data.get('title', ''),
            "description": package_data.get('caption', ''),
            "uploadDate": datetime.now().isoformat(),
            "thumbnailUrl": package_data.get('thumbnail_path', ''),
            "contentUrl": package_data.get('video_path', ''),
            
            # Platform-specific distribution
            "distribution": {
                "@type": "BroadcastEvent",
                "isLiveBroadcast": False,
                "videoFormat": self._get_platform_format(platform)
            },
            
            # Link to original episode
            "isBasedOn": {
                "@type": "VideoObject",
                "@id": f"{self.base_url}/episodes/{episode_data.get('episode_id', '')}",
                "name": episode_data.get('title', '')
            }
        }
        
        # Add hashtags as keywords
        hashtags = package_data.get('hashtags', [])
        if hashtags:
            jsonld["keywords"] = ", ".join(h.strip('#') for h in hashtags)
        
        return jsonld
    
    def generate_episode_with_clips_jsonld(self, episode_data: Dict[str, Any],
                                          clips_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate comprehensive JSON-LD with episode and all clips
        
        Args:
            episode_data: Episode metadata
            clips_data: List of clip metadata
        
        Returns:
            JSON-LD with hasPart relationships
        """
        # Generate base episode JSON-LD
        jsonld = self.generate_episode_jsonld(episode_data)
        
        # Add clips as parts
        if clips_data:
            jsonld["hasPart"] = [
                {
                    "@type": "Clip",
                    "@id": f"{self.base_url}/clips/{clip.get('clip_id', '')}",
                    "name": clip.get('title', ''),
                    "startOffset": clip.get('start_time', 0),
                    "endOffset": clip.get('end_time', 0),
                    "url": f"{self.base_url}/clips/{clip.get('clip_id', '')}"
                }
                for clip in clips_data
            ]
        
        return jsonld
    
    def _generate_person_jsonld(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate JSON-LD for a person (guest/host)
        
        Args:
            person_data: Person metadata
        
        Returns:
            Person JSON-LD
        """
        name = person_data.get('name', '')
        
        person = {
            "@type": "Person",
            "name": name
        }
        
        # Add job title if available
        title = person_data.get('title', '')
        if title:
            person["jobTitle"] = title
        
        # Add organization if available
        org = person_data.get('organization', '')
        if org:
            person["worksFor"] = {
                "@type": "Organization",
                "name": org
            }
        
        # Add expertise as knowsAbout
        expertise = person_data.get('expertise', [])
        if expertise:
            person["knowsAbout"] = expertise
        
        return person
    
    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in ISO 8601 format (PT#H#M#S)
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            ISO 8601 duration string
        """
        if not seconds:
            return "PT0S"
        
        td = timedelta(seconds=int(seconds))
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        secs = td.seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}H")
        if minutes > 0:
            parts.append(f"{minutes}M")
        if secs > 0 or not parts:
            parts.append(f"{secs}S")
        
        return "PT" + "".join(parts)
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-safe slug
        
        Args:
            text: Input text
        
        Returns:
            URL-safe slug
        """
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')
    
    def _get_platform_format(self, platform: str) -> str:
        """
        Get video format description for platform
        
        Args:
            platform: Platform name
        
        Returns:
            Format description
        """
        formats = {
            'youtube': 'YouTube Video',
            'instagram': 'Instagram Reel',
            'x': 'Twitter Video',
            'tiktok': 'TikTok Video',
            'facebook': 'Facebook Video'
        }
        return formats.get(platform, 'Video')
    
    def save_jsonld(self, jsonld: Dict[str, Any], output_path: Path) -> bool:
        """
        Save JSON-LD to file
        
        Args:
            jsonld: JSON-LD dictionary
            output_path: Output file path
        
        Returns:
            True if saved successfully
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(jsonld, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved JSON-LD to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save JSON-LD: {e}")
            return False
    
    def generate_html_script_tag(self, jsonld: Dict[str, Any]) -> str:
        """
        Generate HTML script tag for embedding JSON-LD
        
        Args:
            jsonld: JSON-LD dictionary
        
        Returns:
            HTML script tag string
        """
        json_str = json.dumps(jsonld, ensure_ascii=False)
        return f'<script type="application/ld+json">\n{json_str}\n</script>'


# Convenience function
def create_jsonld_generator(base_url: str = "https://example.com") -> JSONLDGenerator:
    """
    Create and return a configured JSON-LD generator
    
    Args:
        base_url: Base URL for canonical links
    
    Returns:
        JSONLDGenerator: Configured generator instance
    """
    return JSONLDGenerator(base_url)
