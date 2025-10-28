"""
Social Media Package Generation Component

Implements platform-specific package creation with caption generation,
hashtag creation, and content formatting for Twitter, Instagram, TikTok, and Facebook.
"""

import streamlit as st
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from utils.api_client import create_api_client, PipelineApiClient, EpisodeInfo
from utils.file_manager import create_file_manager, FileManager

logger = logging.getLogger(__name__)


@dataclass
class SocialPackageData:
    """Social media package data structure"""
    platform: str
    episode_id: str
    caption: str
    hashtags: List[str]
    media_files: List[str]
    created_at: datetime
    metadata: Dict[str, Any]


class SocialMediaPackageGenerator:
    """
    Social media package generator for platform-specific content creation
    
    Generates captions, hashtags, and formatted packages for Twitter, Instagram,
    TikTok, and Facebook based on episode metadata and content.
    """
    
    def __init__(self):
        """Initialize social media package generator"""
        self.api_client = create_api_client()
        self.file_manager = create_file_manager()
        
        # Platform configurations
        self.platform_configs = {
            'twitter': {
                'name': 'Twitter',
                'char_limit': 280,
                'hashtag_limit': 2,
                'color': '#1DA1F2',
                'icon': '🐦'
            },
            'instagram': {
                'name': 'Instagram',
                'char_limit': 2200,
                'hashtag_limit': 30,
                'color': '#E4405F',
                'icon': '📸'
            },
            'tiktok': {
                'name': 'TikTok',
                'char_limit': 150,
                'hashtag_limit': 10,
                'color': '#000000',
                'icon': '🎵'
            },
            'facebook': {
                'name': 'Facebook',
                'char_limit': 63206,
                'hashtag_limit': 10,
                'color': '#1877F2',
                'icon': '👥'
            }
        }
    
    def extract_episode_metadata(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract episode metadata from API and files
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Dict: Episode metadata including title, show, guests, topics
        """
        try:
            # Get episode status from API
            response = self.api_client.get_episode_status(episode_id)
            
            if not response.success:
                logger.error(f"Failed to get episode status: {response.error}")
                return None
            
            episode_data = response.data or {}
            
            # Load enrichment data from meta file
            meta_file_path = Path("data/meta") / f"{episode_id}.json"
            enrichment_data = {}
            
            if meta_file_path.exists():
                try:
                    with open(meta_file_path, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                        enrichment_data = meta_data.get('enrichment_data', {})
                except Exception as e:
                    logger.warning(f"Could not load meta file for {episode_id}: {e}")
            
            # Extract key information
            title = episode_data.get('title', 'Untitled Episode')
            show_name = episode_data.get('show_name', 'Unknown Show')
            
            # Extract guests from enrichment data
            guests = []
            enriched_guests = enrichment_data.get('enriched_guests', [])
            for guest in enriched_guests:
                if isinstance(guest, dict):
                    guests.append({
                        'name': guest.get('name', ''),
                        'title': guest.get('title', ''),
                        'organization': guest.get('organization', ''),
                        'expertise': guest.get('expertise', [])
                    })
            
            # Extract topics and key takeaways
            summary_data = enrichment_data.get('summary', {})
            topics = summary_data.get('tags', [])
            key_takeaway = summary_data.get('key_takeaway', '')
            description = summary_data.get('description', '')
            
            # Extract additional context
            intelligence_data = enrichment_data.get('intelligence_data', {})
            analysis = intelligence_data.get('analysis', {})
            
            return {
                'episode_id': episode_id,
                'title': title,
                'show_name': show_name,
                'guests': guests,
                'topics': topics,
                'key_takeaway': key_takeaway,
                'description': description,
                'analysis': analysis,
                'duration': episode_data.get('duration'),
                'source_path': episode_data.get('source_path')
            }
            
        except Exception as e:
            logger.error(f"Error extracting episode metadata for {episode_id}: {e}")
            return None
    
    def generate_caption(self, episode_metadata: Dict[str, Any], platform: str) -> str:
        """
        Generate platform-specific caption based on episode metadata
        
        Args:
            episode_metadata: Episode metadata dictionary
            platform: Target platform (twitter, instagram, tiktok, facebook)
            
        Returns:
            str: Generated caption text
        """
        title = episode_metadata.get('title', 'Untitled Episode')
        show_name = episode_metadata.get('show_name', 'Unknown Show')
        guests = episode_metadata.get('guests', [])
        key_takeaway = episode_metadata.get('key_takeaway', '')
        description = episode_metadata.get('description', '')
        
        # Platform-specific caption generation
        if platform == 'twitter':
            return self._generate_twitter_caption(title, show_name, guests, key_takeaway)
        elif platform == 'instagram':
            return self._generate_instagram_caption(title, show_name, guests, key_takeaway, description)
        elif platform == 'tiktok':
            return self._generate_tiktok_caption(title, show_name, guests, key_takeaway)
        elif platform == 'facebook':
            return self._generate_facebook_caption(title, show_name, guests, key_takeaway, description)
        else:
            return self._generate_generic_caption(title, show_name, guests, key_takeaway)
    
    def _generate_twitter_caption(self, title: str, show_name: str, guests: List[Dict], key_takeaway: str) -> str:
        """Generate Twitter-optimized caption (280 chars)"""
        caption_parts = []
        
        # Start with key takeaway or title
        if key_takeaway and len(key_takeaway) < 150:
            caption_parts.append(key_takeaway)
        else:
            caption_parts.append(f"New episode: {title}")
        
        # Add guest mention if space allows
        if guests:
            guest_names = [guest.get('name', '') for guest in guests[:2]]  # Max 2 guests
            guest_text = f"with {', '.join(guest_names)}"
            
            # Check if we have space
            current_length = len(' '.join(caption_parts))
            if current_length + len(guest_text) + 20 < 250:  # Leave space for hashtags
                caption_parts.append(guest_text)
        
        # Add show attribution
        if show_name and show_name.lower() not in ' '.join(caption_parts).lower():
            show_text = f"on {show_name}"
            current_length = len(' '.join(caption_parts))
            if current_length + len(show_text) + 20 < 250:
                caption_parts.append(show_text)
        
        return ' '.join(caption_parts)
    
    def _generate_instagram_caption(self, title: str, show_name: str, guests: List[Dict], 
                                  key_takeaway: str, description: str) -> str:
        """Generate Instagram-optimized caption (2200 chars)"""
        caption_parts = []
        
        # Start with engaging hook
        if key_takeaway:
            caption_parts.append(f"🎙️ {key_takeaway}")
        else:
            caption_parts.append(f"🎙️ New episode of {show_name} is live!")
        
        caption_parts.append("")  # Empty line for spacing
        
        # Add episode title
        caption_parts.append(f"📺 {title}")
        
        # Add guest information with more detail
        if guests:
            caption_parts.append("")
            caption_parts.append("🎯 Featured guests:")
            for guest in guests[:3]:  # Max 3 guests for Instagram
                name = guest.get('name', '')
                title = guest.get('title', '')
                org = guest.get('organization', '')
                
                guest_line = f"• {name}"
                if title:
                    guest_line += f", {title}"
                if org:
                    guest_line += f" at {org}"
                
                caption_parts.append(guest_line)
        
        # Add description if available
        if description and len(description) > 50:
            caption_parts.append("")
            caption_parts.append("💡 What you'll learn:")
            # Truncate description to fit within Instagram limits
            desc_text = description[:300] + "..." if len(description) > 300 else description
            caption_parts.append(desc_text)
        
        # Add call to action
        caption_parts.append("")
        caption_parts.append("🎧 Listen now! Link in bio.")
        
        return '\n'.join(caption_parts)
    
    def _generate_tiktok_caption(self, title: str, show_name: str, guests: List[Dict], key_takeaway: str) -> str:
        """Generate TikTok-optimized caption (150 chars)"""
        # TikTok captions should be short and punchy
        if key_takeaway and len(key_takeaway) < 100:
            caption = f"🔥 {key_takeaway}"
        else:
            caption = f"🔥 New {show_name} episode!"
        
        # Add guest mention if space allows
        if guests and len(caption) < 100:
            guest_name = guests[0].get('name', '')
            if guest_name:
                addition = f" with {guest_name}"
                if len(caption + addition) < 120:  # Leave space for hashtags
                    caption += addition
        
        return caption
    
    def _generate_facebook_caption(self, title: str, show_name: str, guests: List[Dict], 
                                 key_takeaway: str, description: str) -> str:
        """Generate Facebook-optimized caption (longer form)"""
        caption_parts = []
        
        # Start with engaging introduction
        if key_takeaway:
            caption_parts.append(f"🎙️ {key_takeaway}")
        else:
            caption_parts.append(f"🎙️ We're excited to share our latest {show_name} episode!")
        
        caption_parts.append("")
        
        # Add episode title
        caption_parts.append(f"📺 Episode: {title}")
        
        # Add detailed guest information
        if guests:
            caption_parts.append("")
            caption_parts.append("🎯 In this episode, we're joined by:")
            
            for guest in guests:
                name = guest.get('name', '')
                title = guest.get('title', '')
                org = guest.get('organization', '')
                expertise = guest.get('expertise', [])
                
                guest_info = f"• {name}"
                if title and org:
                    guest_info += f", {title} at {org}"
                elif title:
                    guest_info += f", {title}"
                elif org:
                    guest_info += f" from {org}"
                
                if expertise:
                    guest_info += f" (Expert in: {', '.join(expertise[:3])})"
                
                caption_parts.append(guest_info)
        
        # Add description/summary
        if description:
            caption_parts.append("")
            caption_parts.append("💡 What we discuss:")
            caption_parts.append(description)
        
        # Add call to action
        caption_parts.append("")
        caption_parts.append("🎧 Listen to the full episode now!")
        caption_parts.append("👆 What did you think of this episode? Let us know in the comments!")
        
        return '\n'.join(caption_parts)
    
    def _generate_generic_caption(self, title: str, show_name: str, guests: List[Dict], key_takeaway: str) -> str:
        """Generate generic caption for unknown platforms"""
        caption_parts = []
        
        if key_takeaway:
            caption_parts.append(key_takeaway)
        else:
            caption_parts.append(f"New episode: {title}")
        
        if guests:
            guest_names = [guest.get('name', '') for guest in guests[:2]]
            caption_parts.append(f"Featuring {', '.join(guest_names)}")
        
        caption_parts.append(f"From {show_name}")
        
        return ' '.join(caption_parts)
    
    def generate_hashtags(self, episode_metadata: Dict[str, Any], platform: str) -> List[str]:
        """
        Generate relevant hashtags based on episode content
        
        Args:
            episode_metadata: Episode metadata dictionary
            platform: Target platform
            
        Returns:
            List[str]: Generated hashtags
        """
        hashtags = []
        
        # Get platform limits
        config = self.platform_configs.get(platform, {})
        max_hashtags = config.get('hashtag_limit', 10)
        
        # Extract topics and create hashtags
        topics = episode_metadata.get('topics', [])
        show_name = episode_metadata.get('show_name', '')
        guests = episode_metadata.get('guests', [])
        
        # Add show-based hashtag
        if show_name:
            show_hashtag = self._create_hashtag(show_name)
            if show_hashtag:
                hashtags.append(show_hashtag)
        
        # Add topic-based hashtags
        for topic in topics[:max_hashtags-2]:  # Reserve space for show and guest hashtags
            topic_hashtag = self._create_hashtag(topic)
            if topic_hashtag and topic_hashtag not in hashtags:
                hashtags.append(topic_hashtag)
        
        # Add guest expertise hashtags
        for guest in guests[:2]:  # Max 2 guests
            expertise = guest.get('expertise', [])
            for skill in expertise[:2]:  # Max 2 skills per guest
                skill_hashtag = self._create_hashtag(skill)
                if skill_hashtag and skill_hashtag not in hashtags and len(hashtags) < max_hashtags:
                    hashtags.append(skill_hashtag)
        
        # Add generic podcast/content hashtags if we have space
        generic_hashtags = ['#podcast', '#interview', '#insights', '#learning']
        for generic in generic_hashtags:
            if len(hashtags) < max_hashtags and generic not in hashtags:
                hashtags.append(generic)
        
        return hashtags[:max_hashtags]
    
    def _create_hashtag(self, text: str) -> Optional[str]:
        """
        Create a valid hashtag from text
        
        Args:
            text: Input text
            
        Returns:
            str or None: Valid hashtag or None if invalid
        """
        if not text:
            return None
        
        # Clean text: remove special characters, spaces, convert to camelCase
        import re
        
        # Remove special characters and split on spaces/punctuation
        words = re.findall(r'\b\w+\b', text.lower())
        
        if not words:
            return None
        
        # Create camelCase hashtag
        if len(words) == 1:
            hashtag = f"#{words[0].capitalize()}"
        else:
            # First word lowercase, rest capitalized
            hashtag = f"#{words[0]}" + "".join(word.capitalize() for word in words[1:])
        
        # Validate hashtag length and content
        if len(hashtag) > 30 or len(hashtag) < 3:
            return None
        
        # Check for AI/tech topics and use appropriate casing
        tech_terms = {
            'ai': 'AI',
            'ml': 'ML',
            'api': 'API',
            'iot': 'IoT',
            'saas': 'SaaS',
            'tech': 'Tech',
            'startup': 'Startup',
            'business': 'Business'
        }
        
        for term, proper_case in tech_terms.items():
            if term in text.lower():
                return f"#{proper_case}"
        
        return hashtag
    
    def create_social_package(self, episode_id: str, platform: str) -> Optional[SocialPackageData]:
        """
        Create complete social media package for episode and platform
        
        Args:
            episode_id: Episode identifier
            platform: Target platform
            
        Returns:
            SocialPackageData or None: Generated package data
        """
        try:
            # Extract episode metadata
            episode_metadata = self.extract_episode_metadata(episode_id)
            
            if not episode_metadata:
                logger.error(f"Could not extract metadata for episode {episode_id}")
                return None
            
            # Generate caption
            caption = self.generate_caption(episode_metadata, platform)
            
            # Generate hashtags
            hashtags = self.generate_hashtags(episode_metadata, platform)
            
            # Find media files (clips)
            media_files = []
            clips_dir = Path("data/clips") / episode_id
            if clips_dir.exists():
                for clip_file in clips_dir.glob("*.mp4"):
                    media_files.append(str(clip_file))
            
            # Create package data
            package_data = SocialPackageData(
                platform=platform,
                episode_id=episode_id,
                caption=caption,
                hashtags=hashtags,
                media_files=media_files,
                created_at=datetime.now(),
                metadata={
                    'title': episode_metadata.get('title'),
                    'show_name': episode_metadata.get('show_name'),
                    'guests': episode_metadata.get('guests', []),
                    'topics': episode_metadata.get('topics', []),
                    'duration': episode_metadata.get('duration'),
                    'platform_config': self.platform_configs.get(platform, {})
                }
            )
            
            return package_data
            
        except Exception as e:
            logger.error(f"Error creating social package for {episode_id}/{platform}: {e}")
            return None
    
    def save_social_package(self, package_data: SocialPackageData) -> bool:
        """
        Save social media package to file system
        
        Args:
            package_data: Package data to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Convert to dictionary for JSON serialization
            package_dict = {
                'platform': package_data.platform,
                'episode_id': package_data.episode_id,
                'caption': package_data.caption,
                'hashtags': package_data.hashtags,
                'media_files': package_data.media_files,
                'created_at': package_data.created_at.isoformat(),
                'metadata': package_data.metadata
            }
            
            # Save using file manager
            return self.file_manager.save_social_package(
                package_data.episode_id,
                package_data.platform,
                package_dict
            )
            
        except Exception as e:
            logger.error(f"Error saving social package: {e}")
            return False
    
    def generate_packages_for_episode(self, episode_id: str, platforms: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Generate social media packages for multiple platforms
        
        Args:
            episode_id: Episode identifier
            platforms: List of platforms (default: all supported platforms)
            
        Returns:
            Dict[str, bool]: Platform -> success status
        """
        if platforms is None:
            platforms = list(self.platform_configs.keys())
        
        results = {}
        
        for platform in platforms:
            try:
                # Create package
                package_data = self.create_social_package(episode_id, platform)
                
                if package_data:
                    # Save package
                    success = self.save_social_package(package_data)
                    results[platform] = success
                    
                    if success:
                        logger.info(f"Generated social package for {episode_id}/{platform}")
                    else:
                        logger.error(f"Failed to save social package for {episode_id}/{platform}")
                else:
                    results[platform] = False
                    logger.error(f"Failed to create social package for {episode_id}/{platform}")
                    
            except Exception as e:
                logger.error(f"Error generating package for {episode_id}/{platform}: {e}")
                results[platform] = False
        
        return results


def render_social_package_generation_interface():
    """
    Render social media package generation interface with job tracking
    """
    st.subheader("📱 Social Media Package Generation")
    
    st.write("""
    Generate platform-specific social media packages with AI-powered captions, hashtags,
    and optimized content formatting. Track generation progress in real-time.
    """)
    
    # Add tabs for generation and monitoring
    tab1, tab2 = st.tabs(["🚀 Generate Packages", "📊 Job Monitor"])
    
    with tab1:
        render_package_generation_tab()
    
    with tab2:
        render_job_monitoring_tab()


def render_package_generation_tab():
    """
    Render the package generation tab
    """
    
    # Initialize components
    generator = SocialMediaPackageGenerator()
    api_client = create_api_client()
    
    # Episode selection
    st.markdown("### 1️⃣ Select Episode")
    
    # Load episodes from API
    response = api_client.list_episodes(limit=50)
    
    if not response.success or not response.data:
        st.error("Failed to load episodes. Please check API connection.")
        return
    
    # API returns a list directly, not a dict with 'episodes' key
    episodes = response.data if isinstance(response.data, list) else response.data.get('episodes', [])
    
    if not episodes:
        st.info("No episodes found. Process some videos first.")
        return
    
    # Create episode selection
    episode_options = {}
    for ep_data in episodes:
        episode = api_client.parse_episode_info(ep_data)
        display_name = f"{episode.episode_id} - {episode.title or 'Untitled'}"
        episode_options[display_name] = episode.episode_id
    
    selected_display = st.selectbox(
        "Choose an episode:",
        list(episode_options.keys()),
        key="social_gen_episode_select"
    )
    
    selected_episode_id = episode_options[selected_display]
    
    # Platform selection with enhanced UI
    st.markdown("### 2️⃣ Select Platforms")
    
    # Map old platform names to new API names
    platform_mapping = {
        'twitter': 'x',
        'instagram': 'instagram',
        'tiktok': 'tiktok',
        'facebook': 'facebook'
    }
    
    # Get platform requirements from API
    import requests
    try:
        platforms_response = requests.get(f"{api_client.base_url}/social/platforms")
        available_platforms = platforms_response.json() if platforms_response.ok else ['youtube', 'instagram', 'x', 'tiktok', 'facebook']
    except:
        available_platforms = ['youtube', 'instagram', 'x', 'tiktok', 'facebook']
    
    platform_configs = generator.platform_configs
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        youtube_enabled = st.checkbox("🎥 YouTube", value=True, help="16:9 landscape videos, up to 10 minutes")
        instagram_enabled = st.checkbox(f"{platform_configs['instagram']['icon']} Instagram", value=True, help="9:16 vertical Reels, up to 90 seconds")
    
    with col2:
        x_enabled = st.checkbox("🐦 X (Twitter)", value=True, help="16:9 landscape, up to 2:20 minutes")
        tiktok_enabled = st.checkbox(f"{platform_configs['tiktok']['icon']} TikTok", value=False, help="9:16 vertical, up to 3 minutes")
    
    with col3:
        facebook_enabled = st.checkbox(f"{platform_configs['facebook']['icon']} Facebook", value=True, help="16:9 landscape, up to 4 minutes")
    
    # Build selected platforms list with API names
    selected_platforms = []
    if youtube_enabled:
        selected_platforms.append('youtube')
    if instagram_enabled:
        selected_platforms.append('instagram')
    if x_enabled:
        selected_platforms.append('x')
    if tiktok_enabled:
        selected_platforms.append('tiktok')
    if facebook_enabled:
        selected_platforms.append('facebook')
    
    if not selected_platforms:
        st.warning("Please select at least one platform.")
        return
    
    # Generation controls with API integration
    st.markdown("### 3️⃣ Generate Packages")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Generate Social Packages", type="primary", use_container_width=True):
            with st.spinner("Submitting package generation job..."):
                try:
                    # Call new API endpoint
                    import requests
                    response = requests.post(
                        f"{api_client.base_url}/social/generate",
                        json={
                            "episode_id": selected_episode_id,
                            "platforms": selected_platforms,
                            "metadata_overrides": None
                        }
                    )
                    
                    if response.ok:
                        result = response.json()
                        job_id = result.get('job_id')
                        
                        st.success(f"✅ Job submitted successfully!")
                        st.info(f"**Job ID:** `{job_id}`")
                        st.info(f"**Platforms:** {', '.join(selected_platforms)}")
                        st.info("Switch to the 'Job Monitor' tab to track progress.")
                        
                        # Store job_id in session state for monitoring
                        if 'social_jobs' not in st.session_state:
                            st.session_state['social_jobs'] = []
                        st.session_state['social_jobs'].append(job_id)
                        
                    else:
                        st.error(f"❌ Failed to submit job: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ Error submitting job: {str(e)}")
    
    with col2:
        if st.button("👁️ Preview Packages", use_container_width=True):
            # Show preview of what would be generated
            st.markdown("### Package Preview")
            
            episode_metadata = generator.extract_episode_metadata(selected_episode_id)
            
            if episode_metadata:
                for platform in selected_platforms:
                    config = platform_configs[platform]
                    
                    with st.expander(f"{config['icon']} {config['name']} Preview"):
                        # Generate preview
                        caption = generator.generate_caption(episode_metadata, platform)
                        hashtags = generator.generate_hashtags(episode_metadata, platform)
                        
                        st.markdown(f"**Caption ({len(caption)}/{config['char_limit']} chars):**")
                        st.text_area(
                            f"{platform}_caption_preview",
                            caption,
                            height=100,
                            disabled=True,
                            label_visibility="collapsed"
                        )
                        
                        st.markdown("**Hashtags:**")
                        hashtag_text = " ".join(hashtags)
                        st.code(hashtag_text)
                        
                        # Comprehensive validation
                        from components.social_validator import validate_social_package
                        
                        # Create temporary package data for validation
                        temp_package = {
                            'caption': caption,
                            'hashtags': hashtags,
                            'media_files': [],
                            'platform': platform
                        }
                        
                        validation_result = validate_social_package(temp_package, platform)
                        
                        if validation_result.is_valid:
                            st.success(f"✅ Package valid for {config['name']} (Score: {validation_result.score:.0f}/100)")
                        else:
                            st.error(f"❌ Package has issues (Score: {validation_result.score:.0f}/100)")
                            
                            # Show key issues
                            if validation_result.errors:
                                for error in validation_result.errors[:2]:  # Show first 2 errors
                                    st.error(f"• {error.message}")
                            
                            if validation_result.warnings:
                                for warning in validation_result.warnings[:2]:  # Show first 2 warnings
                                    st.warning(f"• {warning.message}")
            else:
                st.error("Could not load episode metadata for preview")


def render_job_monitoring_tab():
    """
    Render the job monitoring tab with real-time progress tracking
    """
    st.markdown("### Active Jobs")
    
    api_client = create_api_client()
    
    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Monitor social media package generation jobs in real-time.")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=True)
    
    if auto_refresh:
        st.info("🔄 Auto-refreshing every 3 seconds...")
        import time
        time.sleep(3)
        st.rerun()
    
    # Fetch jobs from API
    try:
        import requests
        response = requests.get(f"{api_client.base_url}/social/jobs?limit=20")
        
        if not response.ok:
            st.error(f"Failed to fetch jobs: {response.text}")
            return
        
        jobs = response.json()
        
        if not jobs:
            st.info("No jobs found. Generate some packages to see them here!")
            return
        
        # Display jobs
        for job in jobs:
            job_id = job['job_id']
            episode_id = job['episode_id']
            platforms = job['platforms']
            status = job['status']
            progress = job['progress']
            created_at = job['created_at']
            
            # Status color coding
            status_colors = {
                'pending': '🟡',
                'processing': '🔵',
                'completed': '🟢',
                'failed': '🔴',
                'cancelled': '⚫'
            }
            status_icon = status_colors.get(status, '⚪')
            
            with st.expander(f"{status_icon} {job_id} - {episode_id} ({status.upper()})", expanded=(status == 'processing')):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Episode:** {episode_id}")
                    st.write(f"**Platforms:** {', '.join(platforms)}")
                    st.write(f"**Status:** {status}")
                
                with col2:
                    st.write(f"**Created:** {created_at}")
                    st.write(f"**Progress:** {progress:.1f}%")
                
                # Progress bar
                if status == 'processing':
                    st.progress(progress / 100.0)
                
                # Show packages generated
                packages_generated = job.get('packages_generated', {})
                if packages_generated:
                    st.markdown("**✅ Packages Generated:**")
                    for platform, path in packages_generated.items():
                        st.write(f"- {platform}: `{path}`")
                
                # Show errors
                errors = job.get('errors', {})
                if errors:
                    st.markdown("**❌ Errors:**")
                    for platform, error in errors.items():
                        st.error(f"{platform}: {error}")
                
                # Show warnings
                warnings = job.get('warnings', [])
                if warnings:
                    st.markdown("**⚠️ Warnings:**")
                    for warning in warnings:
                        st.warning(warning)
        
        # Stats summary
        st.markdown("---")
        st.markdown("### Job Statistics")
        
        stats_response = requests.get(f"{api_client.base_url}/social/stats")
        if stats_response.ok:
            stats = stats_response.json()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Jobs", stats.get('total', 0))
            with col2:
                st.metric("Completed", stats.get('completed', 0))
            with col3:
                st.metric("Processing", stats.get('processing', 0))
            with col4:
                st.metric("Failed", stats.get('failed', 0))
        
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")


# Convenience function for creating generator instance
def create_social_generator() -> SocialMediaPackageGenerator:
    """
    Create and return a configured social media package generator
    
    Returns:
        SocialMediaPackageGenerator: Configured generator instance
    """
    return SocialMediaPackageGenerator()