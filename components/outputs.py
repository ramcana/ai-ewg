"""
Output browser and content management interface components

Provides Streamlit components for viewing episode results, file organization,
content previews, and download links for generated content.
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

from utils.api_client import create_api_client, PipelineApiClient, EpisodeInfo
from utils.file_manager import create_file_manager, FileManager, EpisodeFileStructure

logger = logging.getLogger(__name__)


class OutputBrowserInterface:
    """
    Output browser and content management interface
    
    Handles episode results display, file organization status,
    content previews, and download links for generated content.
    """
    
    def __init__(self):
        """Initialize output browser interface"""
        self.api_client = create_api_client()
        self.file_manager = create_file_manager()
        
        # Initialize session state for outputs
        if 'selected_episode_id' not in st.session_state:
            st.session_state.selected_episode_id = None
        if 'episodes_data' not in st.session_state:
            st.session_state.episodes_data = []
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = None
    
    def load_episodes_data(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Load episodes data from API with caching
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            List: Episodes data with file organization info
        """
        # Check if we need to refresh data
        now = datetime.now()
        last_refresh = st.session_state.last_refresh
        
        if (not force_refresh and 
            last_refresh and 
            (now - last_refresh).seconds < 30 and 
            st.session_state.episodes_data):
            return st.session_state.episodes_data
        
        try:
            # Get episodes from API with progress indicator
            with st.spinner("📡 Loading episodes from API..."):
                response = self.api_client.list_episodes(limit=50, force_refresh=force_refresh)
            
            episodes_data = []
            
            if response.success and response.data:
                # API returns a list directly, not a dict with 'episodes' key
                api_episodes = response.data if isinstance(response.data, list) else response.data.get('episodes', [])
                
                # Show progress for processing episodes data
                if len(api_episodes) > 5:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                for i, episode_data in enumerate(api_episodes):
                    if len(api_episodes) > 5:
                        status_text.text(f"Processing episode {i+1} of {len(api_episodes)}...")
                        progress_bar.progress((i + 1) / len(api_episodes))
                    
                    episode = self.api_client.parse_episode_info(episode_data)
                    
                    # Get file structure for this episode (with caching)
                    file_structure = self.file_manager.get_episode_file_structure(episode.episode_id)
                    
                    # Get episode status for processing metrics (with caching)
                    status_response = self.api_client.get_episode_status(episode.episode_id)
                    processing_time = None
                    if status_response.success and status_response.data:
                        processing_time = status_response.data.get('processing_time_seconds')
                
                # Clear progress indicators
                if len(api_episodes) > 5:
                    progress_bar.empty()
                    status_text.empty()
                    
                    episodes_data.append({
                        'episode_id': episode.episode_id,
                        'title': episode.title or 'Untitled',
                        'show_name': episode.show_name or 'Unknown Show',
                        'status': episode.status or 'unknown',
                        'processing_stage': episode.processing_stage or 'unknown',
                        'clips_count': file_structure.clips_dir.file_count,
                        'social_packages_count': file_structure.social_dir.file_count,
                        'total_files': file_structure.total_files,
                        'total_size_mb': file_structure.total_size_mb,
                        'is_complete': file_structure.is_complete,
                        'missing_components': file_structure.missing_components,
                        'processing_time': processing_time,
                        'source_path': episode.source_path,
                        'duration': episode.duration,
                        'error': episode.error,
                        'file_structure': file_structure
                    })
            
            # Cache the data
            st.session_state.episodes_data = episodes_data
            st.session_state.last_refresh = now
            
            return episodes_data
            
        except Exception as e:
            logger.error(f"Error loading episodes data: {e}")
            st.error(f"Failed to load episodes data: {str(e)}")
            return st.session_state.episodes_data or []
    
    def render_episodes_table(self, episodes_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Render episode status table with filtering and sorting
        
        Args:
            episodes_data: List of episode data dictionaries
            
        Returns:
            str or None: Selected episode ID if any
        """
        if not episodes_data:
            st.info("No episodes found. Process some videos first to see results here.")
            return None
        
        st.subheader("📊 Episode Results")
        
        # Create DataFrame for display
        df_data = []
        for episode in episodes_data:
            df_data.append({
                'Episode ID': episode['episode_id'],
                'Title': episode['title'],
                'Show': episode['show_name'],
                'Status': episode['status'],
                'Stage': episode['processing_stage'],
                'Clips': episode['clips_count'],
                'Social Packages': episode['social_packages_count'],
                'Total Files': episode['total_files'],
                'Size (MB)': f"{episode['total_size_mb']:.1f}",
                'Complete': '✅' if episode['is_complete'] else '⚠️',
                'Processing Time': f"{episode['processing_time']:.1f}s" if episode['processing_time'] else 'N/A'
            })
        
        df = pd.DataFrame(df_data)
        
        # Filtering controls
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status_filter = st.selectbox(
                "Filter by Status:",
                ['All'] + list(df['Status'].unique()),
                key="status_filter"
            )
        
        with col2:
            stage_filter = st.selectbox(
                "Filter by Stage:",
                ['All'] + list(df['Stage'].unique()),
                key="stage_filter"
            )
        
        with col3:
            complete_filter = st.selectbox(
                "Filter by Completion:",
                ['All', 'Complete (✅)', 'Incomplete (⚠️)'],
                key="complete_filter"
            )
        
        with col4:
            sort_by = st.selectbox(
                "Sort by:",
                ['Episode ID', 'Title', 'Status', 'Stage', 'Clips', 'Total Files', 'Size (MB)'],
                key="sort_by"
            )
        
        # Apply filters
        filtered_df = df.copy()
        
        if status_filter != 'All':
            filtered_df = filtered_df[filtered_df['Status'] == status_filter]
        
        if stage_filter != 'All':
            filtered_df = filtered_df[filtered_df['Stage'] == stage_filter]
        
        if complete_filter != 'All':
            if complete_filter == 'Complete (✅)':
                filtered_df = filtered_df[filtered_df['Complete'] == '✅']
            else:
                filtered_df = filtered_df[filtered_df['Complete'] == '⚠️']
        
        # Apply sorting
        if sort_by in ['Clips', 'Total Files']:
            filtered_df = filtered_df.sort_values(sort_by, ascending=False)
        elif sort_by == 'Size (MB)':
            # Convert back to float for sorting
            filtered_df['Size_Float'] = filtered_df['Size (MB)'].str.replace(' MB', '').astype(float)
            filtered_df = filtered_df.sort_values('Size_Float', ascending=False)
            filtered_df = filtered_df.drop('Size_Float', axis=1)
        else:
            filtered_df = filtered_df.sort_values(sort_by)
        
        # Display results count
        st.write(f"**Showing {len(filtered_df)} of {len(df)} episodes**")
        
        # Display table with selection
        if len(filtered_df) > 0:
            # Use st.dataframe with selection
            selected_rows = st.dataframe(
                filtered_df,
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            # Get selected episode ID
            if selected_rows.selection.rows:
                selected_idx = selected_rows.selection.rows[0]
                selected_episode_id = filtered_df.iloc[selected_idx]['Episode ID']
                st.session_state.selected_episode_id = selected_episode_id
                return selected_episode_id
        
        return st.session_state.selected_episode_id
    
    def render_file_organization_status(self) -> None:
        """
        Render file organization status display
        """
        st.subheader("📁 File Organization Status")
        
        try:
            # Get overall organization status
            org_status = self.file_manager.get_file_organization_status()
            
            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Files", org_status['total_files'])
            
            with col2:
                st.metric("Total Size", f"{org_status['total_size_mb']:.1f} MB")
            
            with col3:
                st.metric("Episodes with Clips", org_status['episodes_with_clips'])
            
            with col4:
                st.metric("Episodes with Social", org_status['episodes_with_social'])
            
            # Directory breakdown
            st.write("**Directory Breakdown:**")
            
            directories = org_status.get('directories', {})
            
            dir_data = []
            for dir_name, dir_info in directories.items():
                # Ensure Episodes column has consistent data type (string)
                episodes_count = dir_info.get('episodes', 0)
                episodes_display = str(episodes_count) if episodes_count is not None else "0"
                
                dir_data.append({
                    'Directory': dir_name.title(),
                    'Files': dir_info.get('files', 0),
                    'Size (MB)': f"{dir_info.get('size_mb', 0):.1f}",
                    'Episodes': episodes_display
                })
            
            if dir_data:
                dir_df = pd.DataFrame(dir_data)
                st.dataframe(dir_df, width="stretch", hide_index=True)
            
        except Exception as e:
            st.error(f"Error loading file organization status: {str(e)}")
    
    def render_episode_details(self, episode_id: str, episodes_data: List[Dict[str, Any]]) -> None:
        """
        Render detailed information for selected episode
        
        Args:
            episode_id: Selected episode ID
            episodes_data: List of all episodes data
        """
        # Find episode data
        episode_data = None
        for ep in episodes_data:
            if ep['episode_id'] == episode_id:
                episode_data = ep
                break
        
        if not episode_data:
            st.error(f"Episode {episode_id} not found")
            return
        
        st.subheader(f"📄 Episode Details: {episode_data['title']}")
        
        # Basic information
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Basic Information:**")
            st.write(f"**Episode ID:** {episode_data['episode_id']}")
            st.write(f"**Title:** {episode_data['title']}")
            st.write(f"**Show:** {episode_data['show_name']}")
            st.write(f"**Status:** {episode_data['status']}")
            st.write(f"**Processing Stage:** {episode_data['processing_stage']}")
            
            if episode_data['duration']:
                st.write(f"**Duration:** {episode_data['duration']:.1f} seconds")
            
            if episode_data['processing_time']:
                st.write(f"**Processing Time:** {episode_data['processing_time']:.1f} seconds")
        
        with col2:
            st.write("**File Summary:**")
            st.write(f"**Total Files:** {episode_data['total_files']}")
            st.write(f"**Total Size:** {episode_data['total_size_mb']:.1f} MB")
            st.write(f"**Clips Generated:** {episode_data['clips_count']}")
            st.write(f"**Social Packages:** {episode_data['social_packages_count']}")
            st.write(f"**Complete:** {'✅ Yes' if episode_data['is_complete'] else '⚠️ No'}")
            
            if episode_data['missing_components']:
                st.write(f"**Missing:** {', '.join(episode_data['missing_components'])}")
        
        # Error information if any
        if episode_data['error']:
            st.error(f"**Error:** {episode_data['error']}")
        
        # Episode statistics button
        if st.button(f"📊 View Detailed Statistics", key=f"stats_{episode_id}"):
            preview_interface = ContentPreviewInterface()
            preview_interface.render_episode_statistics(episode_id)
        
        # File structure details
        file_structure = episode_data['file_structure']
        
        st.markdown("---")
        st.write("**Generated Files:**")
        
        # Clips section
        with st.expander(f"🎬 Clips ({file_structure.clips_dir.file_count} files)", expanded=True):
            if file_structure.clips_dir.file_count > 0:
                st.success(f"✅ {file_structure.clips_dir.file_count} clip files ({file_structure.clips_dir.total_size_mb:.1f} MB)")
                
                # Show clip files with download links
                for clip_file in file_structure.clips_dir.files:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"📹 {clip_file.name}")
                    
                    with col2:
                        st.write(f"{clip_file.size_mb:.1f} MB")
                    
                    with col3:
                        if clip_file.exists and clip_file.is_valid:
                            # Create download button
                            try:
                                with open(clip_file.path, 'rb') as f:
                                    st.download_button(
                                        "⬇️ Download",
                                        data=f.read(),
                                        file_name=clip_file.name,
                                        mime="video/mp4",
                                        key=f"download_{clip_file.name}_{episode_id}"
                                    )
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        else:
                            st.error("❌ Invalid")
            else:
                st.info("No clips generated yet")
        
        # Social packages section
        with st.expander(f"📱 Social Media Packages ({file_structure.social_dir.file_count} files)", expanded=False):
            if file_structure.social_dir.file_count > 0:
                st.success(f"✅ {file_structure.social_dir.file_count} social packages")
                
                # Platform configurations for display
                platform_configs = {
                    'twitter': {'name': 'Twitter', 'icon': '🐦', 'color': '#1DA1F2'},
                    'instagram': {'name': 'Instagram', 'icon': '📸', 'color': '#E4405F'},
                    'tiktok': {'name': 'TikTok', 'icon': '🎵', 'color': '#000000'},
                    'facebook': {'name': 'Facebook', 'icon': '👥', 'color': '#1877F2'}
                }
                
                # Load and display social packages
                for platform in ['twitter', 'instagram', 'tiktok', 'facebook']:
                    package = self.file_manager.load_social_package(episode_id, platform)
                    if package:
                        config = platform_configs.get(platform, {})
                        
                        with st.container():
                            # Platform header with styling
                            st.markdown(f"""
                            <div style="background-color: {config.get('color', '#666')}; color: white; 
                                       padding: 8px 12px; border-radius: 5px; margin: 5px 0;">
                                <strong>{config.get('icon', '📱')} {config.get('name', platform.title())}</strong>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                caption = package.get('caption', '')
                                st.text_area(
                                    f"Caption ({len(caption)} chars):",
                                    caption,
                                    height=100,
                                    key=f"caption_{platform}_{episode_id}",
                                    disabled=True
                                )
                                
                                hashtags = package.get('hashtags', [])
                                if hashtags:
                                    # Display hashtags as styled badges
                                    hashtag_html = ""
                                    for hashtag in hashtags:
                                        hashtag_html += f"""
                                        <span style="background-color: {config.get('color', '#666')}; color: white; 
                                                     padding: 2px 6px; border-radius: 10px; margin: 2px; 
                                                     display: inline-block; font-size: 12px;">
                                            {hashtag}
                                        </span>
                                        """
                                    
                                    st.markdown("**Hashtags:**")
                                    st.markdown(hashtag_html, unsafe_allow_html=True)
                                
                                # Show metadata
                                created_at = package.get('created_at')
                                if created_at:
                                    try:
                                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                        st.caption(f"Created: {created_date.strftime('%Y-%m-%d %H:%M')}")
                                    except:
                                        st.caption(f"Created: {created_at}")
                            
                            with col2:
                                # Download social package as JSON
                                st.download_button(
                                    f"⬇️ Download",
                                    data=json.dumps(package, indent=2),
                                    file_name=f"{episode_id}_{platform}.json",
                                    mime="application/json",
                                    key=f"download_social_{platform}_{episode_id}",
                                    width="stretch"
                                )
                                
                                # Preview social package
                                if st.button(f"👁️ Preview", key=f"preview_social_{platform}_{episode_id}", width="stretch"):
                                    preview_interface = ContentPreviewInterface()
                                    preview_interface.render_social_package_preview(episode_id, platform, package)
                                
                                # Validation status with detailed validation
                                from components.social_validator import validate_social_package
                                
                                validation_result = validate_social_package(package, platform)
                                
                                if validation_result.is_valid:
                                    st.success(f"✅ Valid ({validation_result.score:.0f}/100)")
                                else:
                                    st.error(f"❌ Issues ({validation_result.score:.0f}/100)")
                                
                                # Show validation details on click
                                if st.button(f"📋 Details", key=f"validation_{platform}_{episode_id}", width="stretch"):
                                    st.markdown("### Validation Details")
                                    from components.social_validator import SocialPackageValidator
                                    validator = SocialPackageValidator()
                                    validator.render_validation_results(validation_result)
                            
                            st.markdown("---")
                
                # Generate missing packages button
                st.markdown("### Generate Missing Packages")
                
                # Check which platforms are missing
                existing_platforms = []
                for platform in ['twitter', 'instagram', 'tiktok', 'facebook']:
                    if self.file_manager.load_social_package(episode_id, platform):
                        existing_platforms.append(platform)
                
                missing_platforms = [p for p in ['twitter', 'instagram', 'tiktok', 'facebook'] if p not in existing_platforms]
                
                if missing_platforms:
                    st.info(f"Missing packages for: {', '.join(missing_platforms)}")
                    
                    if st.button("🚀 Generate Missing Packages", key=f"generate_missing_{episode_id}"):
                        from components.social_generator import create_social_generator
                        
                        generator = create_social_generator()
                        
                        with st.spinner("Generating missing social packages..."):
                            results = generator.generate_packages_for_episode(episode_id, missing_platforms)
                            
                            success_count = sum(1 for success in results.values() if success)
                            total_count = len(results)
                            
                            if success_count == total_count:
                                st.success(f"✅ Generated {success_count} missing packages!")
                                st.rerun()  # Refresh to show new packages
                            elif success_count > 0:
                                st.warning(f"⚠️ Generated {success_count}/{total_count} packages")
                            else:
                                st.error("❌ Failed to generate packages")
                else:
                    st.success("✅ All platform packages exist")
            else:
                st.info("No social packages created yet")
                
                # Generate all packages button
                if st.button("🚀 Generate Social Packages", key=f"generate_all_{episode_id}"):
                    from components.social_generator import create_social_generator
                    
                    generator = create_social_generator()
                    platforms = ['twitter', 'instagram', 'facebook']  # Default platforms
                    
                    with st.spinner("Generating social media packages..."):
                        results = generator.generate_packages_for_episode(episode_id, platforms)
                        
                        success_count = sum(1 for success in results.values() if success)
                        total_count = len(results)
                        
                        if success_count == total_count:
                            st.success(f"✅ Generated {success_count} social packages!")
                            st.rerun()  # Refresh to show new packages
                        elif success_count > 0:
                            st.warning(f"⚠️ Generated {success_count}/{total_count} packages")
                        else:
                            st.error("❌ Failed to generate packages")
        
        # HTML pages section
        with st.expander("🌐 HTML Pages", expanded=False):
            html_path = self.file_manager.get_html_page_path(episode_id, episode_data.get('show_slug'))
            
            if html_path:
                st.success(f"✅ HTML page available")
                st.write(f"**Path:** {html_path}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"🔗 Open HTML Page", key=f"open_html_{episode_id}"):
                        # Show HTML path for user to open
                        st.info(f"Open this file in your browser: {html_path}")
                
                with col2:
                    # Provide link to view in new tab (if served)
                    st.markdown(f"[🌐 View in Browser](file://{html_path})")
                
                with col3:
                    if st.button(f"👁️ Preview HTML", key=f"preview_html_{episode_id}"):
                        # Show HTML preview inline
                        preview_interface = ContentPreviewInterface()
                        preview_interface.render_html_preview(episode_id, html_path)
            else:
                st.info("No HTML page found")
        
        # Transcripts section
        with st.expander(f"📝 Transcripts ({len(file_structure.transcript_files)} files)", expanded=False):
            if file_structure.transcript_files:
                for transcript in file_structure.transcript_files:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"📄 {transcript.name}")
                    
                    with col2:
                        st.write(f"{transcript.size_mb:.2f} MB")
                    
                    with col3:
                        if transcript.exists and transcript.is_valid:
                            try:
                                with open(transcript.path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                st.download_button(
                                    "⬇️ Download",
                                    data=content,
                                    file_name=transcript.name,
                                    mime="text/plain",
                                    key=f"download_transcript_{transcript.name}_{episode_id}"
                                )
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        else:
                            st.error("❌ Invalid")
            else:
                st.info("No transcript files found")


def render_view_outputs_page():
    """
    Main function to render the view outputs page
    """
    st.header("📁 View Outputs")
    
    st.write("""
    Browse and manage generated content from video processing workflows.
    View episode results, download clips, preview social media packages, and access HTML pages.
    """)
    
    # Initialize output browser interface
    interface = OutputBrowserInterface()
    
    # Refresh controls
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("🔄 Refresh Data", width="stretch"):
            interface.load_episodes_data(force_refresh=True)
            st.success("Data refreshed!")
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False)
    
    with col3:
        if st.session_state.last_refresh:
            st.write(f"Last updated: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    
    # Load episodes data
    episodes_data = interface.load_episodes_data()
    
    # Render file organization status
    interface.render_file_organization_status()
    
    st.markdown("---")
    
    # Render episodes table with selection
    selected_episode_id = interface.render_episodes_table(episodes_data)
    
    # Show episode details if one is selected
    if selected_episode_id:
        st.markdown("---")
        interface.render_episode_details(selected_episode_id, episodes_data)
    
    # Auto-refresh functionality
    if auto_refresh:
        import time
        time.sleep(10)  # Refresh every 10 seconds
        st.rerun()


class ContentPreviewInterface:
    """
    Content preview capabilities interface
    
    Handles HTML page previews, social media package previews,
    and episode statistics display.
    """
    
    def __init__(self):
        """Initialize content preview interface"""
        self.api_client = create_api_client()
        self.file_manager = create_file_manager()
    
    def render_html_preview(self, episode_id: str, html_path: str) -> None:
        """
        Render HTML page preview using iframe integration
        
        Args:
            episode_id: Episode identifier
            html_path: Path to HTML file
        """
        st.subheader("🌐 HTML Page Preview")
        
        try:
            if not Path(html_path).exists():
                st.error(f"HTML file not found: {html_path}")
                return
            
            # Read HTML content
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Display preview options
            col1, col2 = st.columns([3, 1])
            
            with col1:
                preview_mode = st.radio(
                    "Preview Mode:",
                    ["Iframe", "Raw HTML", "Source Code"],
                    horizontal=True,
                    key=f"preview_mode_{episode_id}"
                )
            
            with col2:
                if st.button("🔗 Open in Browser", key=f"open_browser_{episode_id}"):
                    st.info(f"Open this file in your browser: {html_path}")
            
            # Render based on selected mode
            if preview_mode == "Iframe":
                # Use iframe for preview (with height control)
                iframe_height = st.slider(
                    "Preview Height:",
                    min_value=400,
                    max_value=1200,
                    value=600,
                    step=50,
                    key=f"iframe_height_{episode_id}"
                )
                
                # Create iframe with HTML content
                st.components.v1.html(
                    html_content,
                    height=iframe_height,
                    scrolling=True
                )
            
            elif preview_mode == "Raw HTML":
                # Display rendered HTML in a container
                st.markdown("**Rendered HTML:**")
                st.markdown(html_content, unsafe_allow_html=True)
            
            else:  # Source Code
                # Display HTML source code
                st.markdown("**HTML Source Code:**")
                st.code(html_content, language='html')
            
        except Exception as e:
            st.error(f"Error loading HTML preview: {str(e)}")
    
    def render_social_package_preview(self, episode_id: str, platform: str, package_data: Dict[str, Any]) -> None:
        """
        Render social media package preview with caption and hashtag display
        
        Args:
            episode_id: Episode identifier
            platform: Social media platform
            package_data: Package data dictionary
        """
        st.subheader(f"📱 {platform.title()} Package Preview")
        
        try:
            # Platform-specific styling and limits
            platform_config = {
                'twitter': {
                    'color': '#1DA1F2',
                    'char_limit': 280,
                    'icon': '🐦'
                },
                'instagram': {
                    'color': '#E4405F',
                    'char_limit': 2200,
                    'icon': '📸'
                },
                'tiktok': {
                    'color': '#000000',
                    'char_limit': 150,
                    'icon': '🎵'
                },
                'facebook': {
                    'color': '#1877F2',
                    'char_limit': 63206,
                    'icon': '👥'
                }
            }
            
            config = platform_config.get(platform, platform_config['twitter'])
            
            # Display platform header
            st.markdown(f"""
            <div style="background-color: {config['color']}; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <h4>{config['icon']} {platform.title()} Post Preview</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Caption preview
            caption = package_data.get('caption', '')
            char_count = len(caption)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("**Caption:**")
                
                # Show character count with color coding
                if char_count <= config['char_limit']:
                    char_color = "green"
                elif char_count <= config['char_limit'] * 1.1:
                    char_color = "orange"
                else:
                    char_color = "red"
                
                st.markdown(f"<span style='color: {char_color}'>Characters: {char_count}/{config['char_limit']}</span>", unsafe_allow_html=True)
                
                # Display caption in a styled container
                st.markdown(f"""
                <div style="border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #f9f9f9; margin: 10px 0;">
                    {caption.replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # Package metadata
                st.markdown("**Package Info:**")
                st.write(f"**Platform:** {platform.title()}")
                
                created_at = package_data.get('created_at')
                if created_at:
                    try:
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        st.write(f"**Created:** {created_date.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        st.write(f"**Created:** {created_at}")
                
                # Media files info
                media_files = package_data.get('media_files', [])
                st.write(f"**Media Files:** {len(media_files)}")
            
            # Hashtags display
            hashtags = package_data.get('hashtags', [])
            if hashtags:
                st.markdown("**Hashtags:**")
                
                # Display hashtags as badges
                hashtag_html = ""
                for hashtag in hashtags:
                    hashtag_html += f"""
                    <span style="background-color: {config['color']}; color: white; padding: 3px 8px; 
                                 border-radius: 15px; margin: 2px; display: inline-block; font-size: 12px;">
                        {hashtag}
                    </span>
                    """
                
                st.markdown(hashtag_html, unsafe_allow_html=True)
            
            # Platform-specific validation
            st.markdown("---")
            st.markdown("**Platform Validation:**")
            
            validation_results = []
            
            # Character limit check
            if char_count <= config['char_limit']:
                validation_results.append("✅ Caption length OK")
            else:
                validation_results.append(f"❌ Caption too long ({char_count - config['char_limit']} chars over limit)")
            
            # Hashtag count check
            if platform == 'twitter' and len(hashtags) > 2:
                validation_results.append("⚠️ Consider reducing hashtags for Twitter (recommended: 1-2)")
            elif platform == 'instagram' and len(hashtags) > 30:
                validation_results.append("❌ Too many hashtags for Instagram (max: 30)")
            else:
                validation_results.append("✅ Hashtag count OK")
            
            # Display validation results
            for result in validation_results:
                st.write(result)
            
        except Exception as e:
            st.error(f"Error rendering social package preview: {str(e)}")
    
    def render_episode_statistics(self, episode_id: str) -> None:
        """
        Render episode statistics and processing metrics
        
        Args:
            episode_id: Episode identifier
        """
        st.subheader("📊 Episode Statistics")
        
        try:
            # Get episode status from API
            status_response = self.api_client.get_episode_status(episode_id)
            
            if not status_response.success:
                st.error(f"Failed to get episode statistics: {status_response.error}")
                return
            
            status_data = status_response.data or {}
            
            # Get file structure for additional metrics
            file_structure = self.file_manager.get_episode_file_structure(episode_id)
            
            # Processing metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                processing_time = status_data.get('processing_time_seconds')
                if processing_time:
                    st.metric("Processing Time", f"{processing_time:.1f}s")
                else:
                    st.metric("Processing Time", "N/A")
            
            with col2:
                duration = status_data.get('duration')
                if duration:
                    st.metric("Episode Duration", f"{duration:.1f}s")
                else:
                    st.metric("Episode Duration", "N/A")
            
            with col3:
                success_rate = 100.0 if file_structure.is_complete else 0.0
                st.metric("Success Rate", f"{success_rate:.0f}%")
            
            with col4:
                st.metric("Total Files", file_structure.total_files)
            
            # File breakdown
            st.markdown("---")
            st.markdown("**File Breakdown:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # File counts
                st.write("**File Counts:**")
                st.write(f"• Clips: {file_structure.clips_dir.file_count}")
                st.write(f"• Social Packages: {file_structure.social_dir.file_count}")
                st.write(f"• Transcripts: {len(file_structure.transcript_files)}")
                st.write(f"• Metadata: {1 if file_structure.meta_file and file_structure.meta_file.is_valid else 0}")
            
            with col2:
                # File sizes
                st.write("**File Sizes:**")
                st.write(f"• Clips: {file_structure.clips_dir.total_size_mb:.1f} MB")
                st.write(f"• Social: {file_structure.social_dir.total_size_mb:.1f} MB")
                
                transcript_size = sum(f.size_mb for f in file_structure.transcript_files if f.is_valid)
                st.write(f"• Transcripts: {transcript_size:.1f} MB")
                
                meta_size = file_structure.meta_file.size_mb if file_structure.meta_file and file_structure.meta_file.is_valid else 0
                st.write(f"• Metadata: {meta_size:.1f} MB")
            
            # Processing stages timeline
            st.markdown("---")
            st.markdown("**Processing Timeline:**")
            
            # Get processing history if available
            processing_history = status_data.get('processing_history', [])
            
            if processing_history:
                timeline_data = []
                for entry in processing_history:
                    timeline_data.append({
                        'Stage': entry.get('stage', 'Unknown'),
                        'Status': entry.get('status', 'Unknown'),
                        'Timestamp': entry.get('timestamp', 'N/A'),
                        'Duration': f"{entry.get('duration_seconds', 0):.1f}s" if entry.get('duration_seconds') else 'N/A'
                    })
                
                if timeline_data:
                    timeline_df = pd.DataFrame(timeline_data)
                    st.dataframe(timeline_df, width="stretch", hide_index=True)
            else:
                # Show current stage info
                current_stage = status_data.get('stage', 'unknown')
                stage_status = status_data.get('status', 'unknown')
                
                st.info(f"Current Stage: {current_stage} ({stage_status})")
            
            # Error information
            error_info = status_data.get('error')
            if error_info:
                st.markdown("---")
                st.markdown("**Error Information:**")
                st.error(error_info)
            
            # Missing components
            if file_structure.missing_components:
                st.markdown("---")
                st.markdown("**Missing Components:**")
                for component in file_structure.missing_components:
                    st.warning(f"• {component.replace('_', ' ').title()}")
            
        except Exception as e:
            st.error(f"Error loading episode statistics: {str(e)}")


def render_content_preview_page():
    """
    Render content preview page with HTML and social media previews
    """
    st.header("👁️ Content Preview")
    
    st.write("""
    Preview generated content including HTML pages, social media packages, and episode statistics.
    """)
    
    # Initialize preview interface
    preview_interface = ContentPreviewInterface()
    
    # Episode selection
    st.subheader("📋 Select Episode")
    
    # Load episodes for selection
    api_client = create_api_client()
    response = api_client.list_episodes(limit=20)
    
    if response.success and response.data:
        episodes = response.data.get('episodes', [])
        
        if episodes:
            # Create episode selection dropdown
            episode_options = {}
            for ep_data in episodes:
                episode = api_client.parse_episode_info(ep_data)
                display_name = f"{episode.episode_id} - {episode.title or 'Untitled'}"
                episode_options[display_name] = episode.episode_id
            
            selected_display = st.selectbox(
                "Choose an episode:",
                list(episode_options.keys()),
                key="preview_episode_select"
            )
            
            selected_episode_id = episode_options[selected_display]
            
            if selected_episode_id:
                # Content preview tabs
                tab1, tab2, tab3 = st.tabs(["📊 Statistics", "🌐 HTML Preview", "📱 Social Packages"])
                
                with tab1:
                    preview_interface.render_episode_statistics(selected_episode_id)
                
                with tab2:
                    # HTML preview
                    file_manager = create_file_manager()
                    html_path = file_manager.get_html_page_path(selected_episode_id)
                    
                    if html_path:
                        preview_interface.render_html_preview(selected_episode_id, html_path)
                    else:
                        st.info("No HTML page found for this episode")
                
                with tab3:
                    # Social media packages preview
                    file_manager = create_file_manager()
                    
                    platforms = ['twitter', 'instagram', 'tiktok', 'facebook']
                    available_platforms = []
                    
                    for platform in platforms:
                        package = file_manager.load_social_package(selected_episode_id, platform)
                        if package:
                            available_platforms.append(platform)
                    
                    if available_platforms:
                        selected_platform = st.selectbox(
                            "Select platform:",
                            available_platforms,
                            key="preview_platform_select"
                        )
                        
                        package_data = file_manager.load_social_package(selected_episode_id, selected_platform)
                        if package_data:
                            preview_interface.render_social_package_preview(
                                selected_episode_id, 
                                selected_platform, 
                                package_data
                            )
                    else:
                        st.info("No social media packages found for this episode")
        else:
            st.info("No episodes found")
    else:
        st.error("Failed to load episodes for preview")