"""
Clip management interface components

Provides Streamlit components for clip parameter configuration,
clip discovery preview, bulk rendering controls, and clip generation monitoring.
"""

import streamlit as st
import pandas as pd
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from utils.api_client import create_api_client, ClipInfo
from utils.helpers import format_duration, format_file_size


def render_clip_management_page():
    """
    Main clip management page with parameter configuration and discovery preview
    """
    st.header("✂️ Clip Management")
    
    # Initialize API client with caching
    api_client = create_api_client(enable_cache=True)
    
    # Check API connectivity with loading indicator
    with st.spinner("🔍 Checking API connectivity..."):
        health_response = api_client.check_health()
    
    if not health_response.success:
        st.error(f"❌ Cannot connect to API: {health_response.error}")
        st.info("Please ensure the AI-EWG pipeline is running at localhost:8000")
        return
    
    st.success("✅ Connected to AI-EWG Pipeline")
    
    # Episode selection with loading indicator
    st.subheader("📺 Select Episode")
    
    with st.spinner("📡 Loading episodes..."):
        episodes_response = api_client.list_episodes(limit=50)
    
    if not episodes_response.success:
        st.error(f"Failed to load episodes: {episodes_response.error}")
        return
    
    # Handle different response formats
    if isinstance(episodes_response.data, dict):
        episodes_data = episodes_response.data.get('episodes', [])
    elif isinstance(episodes_response.data, list):
        episodes_data = episodes_response.data
    else:
        episodes_data = []
    
    if not episodes_data:
        st.warning("No episodes found. Please process some videos first.")
        return
    
    # Create episode selection dropdown with status checking (like process_clips.py)
    episode_options = {}
    rendered_episodes = []
    
    with st.spinner("🔍 Checking episode status for clip readiness..."):
        for episode in episodes_data:
            episode_id = episode.get('episode_id', '')
            title = episode.get('title', 'Unknown Title')
            show_name = episode.get('show_name', 'Unknown Show')
            
            # Check episode status like original process_clips.py
            try:
                status_response = api_client.get_episode_status(episode_id)
                if status_response.success and status_response.data:
                    stage = status_response.data.get('stage', 'unknown')
                    if stage == 'rendered':
                        display_name = f"{show_name} - {title} ({episode_id}) ✅ RENDERED"
                        episode_options[display_name] = episode_id
                        rendered_episodes.append(episode)
                    else:
                        # Show non-rendered episodes but mark them as not ready
                        display_name = f"{show_name} - {title} ({episode_id}) ⏳ {stage.upper()}"
                        episode_options[display_name] = episode_id
                else:
                    # If we can't check status, assume it might be processed
                    display_name = f"{show_name} - {title} ({episode_id}) ❓ STATUS UNKNOWN"
                    episode_options[display_name] = episode_id
            except Exception as e:
                # If status check fails, still show the episode
                display_name = f"{show_name} - {title} ({episode_id}) ❓ STATUS UNKNOWN"
                episode_options[display_name] = episode_id
    
    # Show status summary like original process_clips.py
    if rendered_episodes:
        st.success(f"✅ Found {len(rendered_episodes)} rendered episode(s) ready for clip generation")
    else:
        st.warning("⚠️ No rendered episodes found. Episodes must be fully processed before clip generation.")
        st.info("💡 **Tip**: Process episodes to 'rendered' stage first using the 'Process Videos' page.")
    
    selected_display = st.selectbox(
        "Choose an episode to manage clips:",
        options=list(episode_options.keys()),
        help="Select an episode to configure clip parameters and preview discovered clips"
    )
    
    if not selected_display:
        return
    
    selected_episode_id = episode_options[selected_display]
    
    # Validate episode is ready for clip processing (like process_clips.py)
    episode_ready = False
    try:
        status_response = api_client.get_episode_status(selected_episode_id)
        if status_response.success and status_response.data:
            stage = status_response.data.get('stage', 'unknown')
            if stage == 'rendered':
                episode_ready = True
                st.success(f"✅ Episode is rendered and ready for clip generation")
            else:
                st.warning(f"⚠️ Episode is in '{stage}' stage. Clips can only be generated from rendered episodes.")
                st.info("💡 **Next Steps**: Complete episode processing to 'rendered' stage first.")
        else:
            st.warning("❓ Cannot verify episode status. Proceeding with caution...")
            episode_ready = True  # Allow processing if status check fails
    except Exception as e:
        st.warning(f"❓ Status check failed: {e}. Proceeding with caution...")
        episode_ready = True  # Allow processing if status check fails
    
    if not episode_ready:
        st.info("🚫 Clip management is disabled for non-rendered episodes.")
        return
    
    # Clip parameter configuration
    st.markdown("---")
    render_clip_parameter_controls(selected_episode_id, api_client)
    
    # Clip discovery and preview
    st.markdown("---")
    render_clip_discovery_preview(selected_episode_id, api_client)
    
    # Clip generation monitoring
    st.markdown("---")
    render_clip_generation_monitoring(selected_episode_id, api_client)


def render_clip_parameter_controls(episode_id: str, api_client):
    """
    Render clip parameter configuration controls
    
    Args:
        episode_id: Selected episode ID
        api_client: API client instance
    """
    st.subheader("⚙️ Clip Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Duration Settings**")
        
        # Duration range slider (20s to 2m)
        duration_range = st.slider(
            "Clip Duration Range",
            min_value=20,
            max_value=120,
            value=(20, 120),
            step=5,
            format="%d seconds",
            help="Set minimum and maximum clip duration in seconds (default: 20-120s matches process_clips.py)"
        )
        
        min_duration_ms = duration_range[0] * 1000
        max_duration_ms = duration_range[1] * 1000
        
        # Score threshold
        score_threshold = st.slider(
            "Score Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.05,
            format="%.2f",
            help="Minimum score for clip selection (0.3 = balanced, lower = more clips, higher = fewer but better clips)"
        )
        
        # Maximum clips
        max_clips = st.number_input(
            "Maximum Clips",
            min_value=1,
            max_value=20,
            value=8,
            help="Maximum number of clips to discover (default: 8 matches process_clips.py)"
        )
    
    with col2:
        st.markdown("**Format Settings**")
        
        # Aspect ratio selection
        aspect_ratio_options = {
            "9:16 (Vertical/TikTok)": "9x16",
            "16:9 (Horizontal/YouTube)": "16x9", 
            "1:1 (Square/Instagram)": "1x1"
        }
        
        selected_ratios = st.multiselect(
            "Aspect Ratios",
            options=list(aspect_ratio_options.keys()),
            default=["9:16 (Vertical/TikTok)", "16:9 (Horizontal/YouTube)"],
            help="Select aspect ratios for clip generation"
        )
        
        aspect_ratios = [aspect_ratio_options[ratio] for ratio in selected_ratios]
        
        # Variant selection
        variant_options = {
            "Clean (No Subtitles)": "clean",
            "Subtitled": "subtitled"
        }
        
        selected_variants = st.multiselect(
            "Clip Variants",
            options=list(variant_options.keys()),
            default=["Clean (No Subtitles)", "Subtitled"],
            help="Select clip variants to generate"
        )
        
        variants = [variant_options[variant] for variant in selected_variants]
    
    # Store parameters in session state
    clip_params = {
        "min_duration_ms": min_duration_ms,
        "max_duration_ms": max_duration_ms,
        "score_threshold": score_threshold,
        "max_clips": max_clips,
        "aspect_ratios": aspect_ratios,
        "variants": variants
    }
    
    st.session_state[f'clip_params_{episode_id}'] = clip_params
    
    # Parameter summary
    st.markdown("**Current Settings:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Duration", f"{duration_range[0]}-{duration_range[1]}s")
    with col2:
        st.metric("Score Threshold", f"{score_threshold:.2f}")
    with col3:
        st.metric("Max Clips", str(max_clips))
    
    st.write(f"**Aspect Ratios:** {', '.join(aspect_ratios)}")
    st.write(f"**Variants:** {', '.join(variants)}")


def render_clip_discovery_preview(episode_id: str, api_client):
    """
    Render clip discovery preview with timing and score information
    
    Args:
        episode_id: Selected episode ID
        api_client: API client instance
    """
    st.subheader("🔍 Clip Discovery Preview")
    
    # Get clip parameters from session state
    clip_params = st.session_state.get(f'clip_params_{episode_id}', {})
    
    if not clip_params:
        st.warning("Please configure clip parameters above first.")
        return
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        # Discover clips button
        if st.button("🔍 Discover Clips", type="primary", width="stretch"):
            with st.spinner("Discovering clips..."):
                discovery_response = api_client.discover_clips(
                    episode_id=episode_id,
                    max_clips=clip_params.get("max_clips", 3),
                    min_duration_ms=clip_params.get("min_duration_ms", 20000),
                    max_duration_ms=clip_params.get("max_duration_ms", 120000),
                    aspect_ratios=clip_params.get("aspect_ratios", ["9x16", "16x9"]),
                    score_threshold=clip_params.get("score_threshold", 0.3)
                )
                
                if discovery_response.success:
                    st.session_state[f'discovered_clips_{episode_id}'] = discovery_response.data
                    st.success(f"✅ Discovered {len(discovery_response.data.get('clips', []))} clips")
                else:
                    st.error(f"❌ Discovery failed: {discovery_response.error}")
    
    with col1:
        st.write("Click 'Discover Clips' to find potential clips based on your parameters.")
    
    # Display discovered clips
    discovered_data = st.session_state.get(f'discovered_clips_{episode_id}')
    
    if discovered_data and 'clips' in discovered_data:
        clips = discovered_data['clips']
        
        if clips:
            st.markdown("**Discovered Clips:**")
            
            # Create clips dataframe for display
            clips_df_data = []
            for i, clip in enumerate(clips):
                start_time = format_duration(clip.get('start_ms', 0))
                end_time = format_duration(clip.get('end_ms', 0))
                duration = format_duration(clip.get('duration_ms', 0))
                score = clip.get('score', 0.0)
                title = clip.get('title', f'Clip {i+1}')
                
                clips_df_data.append({
                    'Clip': title,
                    'Start': start_time,
                    'End': end_time,
                    'Duration': duration,
                    'Score': f"{score:.3f}",
                    'Quality': get_score_quality(score)
                })
            
            clips_df = pd.DataFrame(clips_df_data)
            
            # Display clips table
            st.dataframe(
                clips_df,
                width="stretch",
                hide_index=True
            )
            
            # Bulk rendering controls
            render_bulk_rendering_controls(episode_id, clips, clip_params, api_client)
        else:
            st.info("No clips found with current parameters. Try adjusting the score threshold or duration range.")


def render_bulk_rendering_controls(episode_id: str, clips: List[Dict], clip_params: Dict, api_client):
    """
    Render bulk rendering controls for discovered clips
    
    Args:
        episode_id: Episode ID
        clips: List of discovered clips
        clip_params: Clip parameters
        api_client: API client instance
    """
    st.markdown("---")
    st.subheader("🎬 Bulk Rendering")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Clip selection
        clip_selection = st.selectbox(
            "Clips to Render",
            options=["All Clips", "Top Scoring Only", "Custom Selection"],
            help="Choose which clips to render"
        )
    
    with col2:
        # Force re-render option
        force_rerender = st.checkbox(
            "Force Re-render",
            value=False,
            help="Re-render clips even if they already exist"
        )
    
    with col3:
        # Render button
        render_button = st.button(
            "🎬 Render Clips",
            type="primary",
            width="stretch",
            help="Start bulk clip rendering"
        )
    
    # Handle clip selection
    selected_clips = clips
    if clip_selection == "Top Scoring Only":
        # Select top 50% by score
        sorted_clips = sorted(clips, key=lambda x: x.get('score', 0), reverse=True)
        selected_clips = sorted_clips[:max(1, len(sorted_clips) // 2)]
    elif clip_selection == "Custom Selection":
        # Allow individual clip selection
        st.markdown("**Select Individual Clips:**")
        selected_indices = []
        
        for i, clip in enumerate(clips):
            title = clip.get('title', f'Clip {i+1}')
            score = clip.get('score', 0.0)
            duration = format_duration(clip.get('duration_ms', 0))
            
            if st.checkbox(f"{title} (Score: {score:.3f}, Duration: {duration})", key=f"clip_select_{i}"):
                selected_indices.append(i)
        
        selected_clips = [clips[i] for i in selected_indices]
    
    # Display selection summary
    if selected_clips:
        st.info(f"📊 Selected {len(selected_clips)} clips for rendering")
        
        # Show rendering parameters
        variants = clip_params.get("variants", ["clean", "subtitled"])
        aspect_ratios = clip_params.get("aspect_ratios", ["9x16", "16x9"])
        
        total_renders = len(selected_clips) * len(variants) * len(aspect_ratios)
        st.write(f"**Total renders:** {total_renders} files ({len(selected_clips)} clips × {len(variants)} variants × {len(aspect_ratios)} ratios)")
    
    # Handle render button click
    if render_button and selected_clips:
        clip_ids = [clip.get('id') for clip in selected_clips if clip.get('id')]
        
        if not clip_ids:
            st.error("No valid clip IDs found for rendering")
            return
        
        with st.spinner(f"Starting bulk render of {len(clip_ids)} clips..."):
            render_response = api_client.render_clips_bulk(
                episode_id=episode_id,
                clip_ids=clip_ids,
                variants=clip_params.get("variants", ["clean", "subtitled"]),
                aspect_ratios=clip_params.get("aspect_ratios", ["9x16", "16x9"]),
                force_rerender=force_rerender
            )
            
            if render_response.success:
                st.success("✅ Bulk rendering started successfully!")
                
                # Show render job details
                render_data = render_response.data
                if render_data and 'jobs' in render_data:
                    st.write(f"**Render Jobs Created:** {len(render_data['jobs'])}")
                    
                    # Store render job info for monitoring
                    st.session_state[f'render_jobs_{episode_id}'] = render_data
                elif render_data:
                    # Handle different response formats
                    clips_successful = render_data.get('clips_successful', 0)
                    clips_failed = render_data.get('clips_failed', 0)
                    st.write(f"**Clips Rendered:** {clips_successful} successful, {clips_failed} failed")
                
                # Clear discovered clips and metadata cache to force refresh
                if f'discovered_clips_{episode_id}' in st.session_state:
                    del st.session_state[f'discovered_clips_{episode_id}']
                if f'clip_metadata_{episode_id}' in st.session_state:
                    del st.session_state[f'clip_metadata_{episode_id}']
                
                # Auto-refresh to show new clips
                st.rerun()
                
            else:
                st.error(f"❌ Bulk rendering failed: {render_response.error}")


def check_clip_files_on_disk(episode_id: str) -> Dict[str, Any]:
    """
    Check what clip files exist on disk (like process_clips.py check_clip_files)
    
    Args:
        episode_id: Episode ID to check
        
    Returns:
        Dict with file statistics and details
    """
    clips_dir = Path(f"data/clips/{episode_id}")
    
    if not clips_dir.exists():
        return {
            'clips_dir_exists': False,
            'total_folders': 0,
            'total_files': 0,
            'total_size_mb': 0,
            'clip_folders': []
        }
    
    clip_folders = [d for d in clips_dir.iterdir() if d.is_dir()]
    total_files = 0
    total_size_mb = 0
    folder_details = []
    
    for clip_folder in sorted(clip_folders):
        files = list(clip_folder.glob("*"))
        folder_files = [f for f in files if f.is_file()]
        
        folder_size_mb = 0
        file_details = []
        
        for file in sorted(folder_files):
            try:
                size_mb = file.stat().st_size / (1024 * 1024)
                folder_size_mb += size_mb
                total_size_mb += size_mb
                total_files += 1
                
                file_details.append({
                    'name': file.name,
                    'size_mb': size_mb,
                    'path': str(file)
                })
            except Exception as e:
                file_details.append({
                    'name': file.name,
                    'size_mb': 0,
                    'path': str(file),
                    'error': str(e)
                })
        
        folder_details.append({
            'name': clip_folder.name,
            'file_count': len(folder_files),
            'size_mb': folder_size_mb,
            'files': file_details
        })
    
    return {
        'clips_dir_exists': True,
        'total_folders': len(clip_folders),
        'total_files': total_files,
        'total_size_mb': total_size_mb,
        'clip_folders': folder_details
    }


def render_clip_generation_monitoring(episode_id: str, api_client):
    """
    Render clip generation monitoring interface with metadata display and retry functionality
    
    Args:
        episode_id: Selected episode ID
        api_client: API client instance
    """
    st.subheader("📊 Generated Clips")
    
    # Add file checking button like process_clips.py
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("📁 Check Files", width="stretch", help="Check what clip files exist on disk"):
            file_stats = check_clip_files_on_disk(episode_id)
            
            if file_stats['clips_dir_exists']:
                st.success(f"📊 Found {file_stats['total_folders']} clip folders, {file_stats['total_files']} files, {file_stats['total_size_mb']:.1f}MB total")
                
                # Show detailed file breakdown like process_clips.py
                with st.expander("📁 Detailed File Breakdown", expanded=False):
                    for folder in file_stats['clip_folders']:
                        st.write(f"**📂 {folder['name']}/** ({folder['file_count']} files, {folder['size_mb']:.1f}MB)")
                        for file in folder['files']:
                            if 'error' in file:
                                st.write(f"  ❌ {file['name']} - Error: {file['error']}")
                            else:
                                st.write(f"  📄 {file['name']} ({file['size_mb']:.1f}MB)")
            else:
                st.warning("📁 No clips directory found")
    
    with col3:
        # Refresh button
        if st.button("🔄 Refresh", width="stretch"):
            # Clear cached data to force refresh
            if f'clip_metadata_{episode_id}' in st.session_state:
                del st.session_state[f'clip_metadata_{episode_id}']
            st.rerun()
    
    # Check for existing clips
    clips_dir = Path(f"data/clips/{episode_id}")
    
    with col1:
        if clips_dir.exists():
            st.info(f"📁 Clips directory: {clips_dir}")
        else:
            st.warning("📁 No clips directory found. Generate clips first.")
    
    # Load and display clip metadata
    clip_metadata = load_clip_metadata(episode_id, clips_dir)
    
    if not clip_metadata:
        st.info("No generated clips found. Use the discovery and rendering controls above to create clips.")
        return
    
    # Display clip metadata table with file verification (like process_clips.py)
    st.markdown("**Generated Clip Files:**")
    
    # File verification statistics
    total_files = 0
    existing_files = 0
    total_size_mb = 0
    
    # Create metadata dataframe with file verification
    metadata_rows = []
    for clip_data in clip_metadata:
        for file_info in clip_data.get('files', []):
            total_files += 1
            
            # Verify file exists like process_clips.py check_clip_files
            file_path = Path(file_info['file_path'])
            file_exists = file_path.exists()
            if file_exists:
                existing_files += 1
                try:
                    actual_size_mb = file_path.stat().st_size / (1024 * 1024)
                    total_size_mb += actual_size_mb
                    file_status = "✅ File exists"
                    file_size_display = f"{actual_size_mb:.1f}MB"
                except Exception:
                    file_status = "⚠️ File exists but unreadable"
                    file_size_display = file_info['file_size']
            else:
                file_status = "❌ File missing"
                file_size_display = file_info['file_size']
            
            metadata_rows.append({
                'Clip ID': clip_data['clip_id'],
                'Variant': file_info['variant'],
                'Aspect Ratio': file_info['aspect_ratio'],
                'Duration': file_info['duration'],
                'File Size': file_size_display,
                'File Status': file_status,
                'Status': file_info['status'],
                'File Path': file_info['file_path']
            })
    
    # Show file verification summary like process_clips.py
    if total_files > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", total_files)
        with col2:
            st.metric("Files Found", existing_files, delta=f"{existing_files}/{total_files}")
        with col3:
            st.metric("Total Size", f"{total_size_mb:.1f} MB")
        
        if existing_files < total_files:
            missing_count = total_files - existing_files
            st.warning(f"⚠️ {missing_count} file(s) are missing from disk")
    
    if metadata_rows:
        metadata_df = pd.DataFrame(metadata_rows)
        
        # Display with styling
        st.dataframe(
            metadata_df,
            width="stretch",
            hide_index=True,
            column_config={
                "File Path": st.column_config.TextColumn(
                    "File Path",
                    width="medium",
                    help="Full path to the generated clip file"
                ),
                "Status": st.column_config.TextColumn(
                    "Status",
                    width="small"
                )
            }
        )
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        total_files = len(metadata_rows)
        successful_files = len([r for r in metadata_rows if r['Status'] == '✅ Ready'])
        failed_files = len([r for r in metadata_rows if r['Status'] == '❌ Missing'])
        
        # Parse file sizes safely
        total_size_mb = 0
        for r in metadata_rows:
            try:
                # Handle both "29.8 MB" and "29.8MB" formats
                size_str = r['File Size'].replace(' MB', '').replace('MB', '')
                total_size_mb += float(size_str)
            except (ValueError, AttributeError):
                pass  # Skip invalid entries
        
        with col1:
            st.metric("Total Files", total_files)
        with col2:
            st.metric("Successful", successful_files)
        with col3:
            st.metric("Failed/Missing", failed_files)
        with col4:
            st.metric("Total Size", f"{total_size_mb:.1f} MB")
        
        # Retry functionality for failed clips
        if failed_files > 0:
            render_retry_controls(episode_id, clip_metadata, api_client)
    
    # Individual clip actions
    render_individual_clip_actions(episode_id, clip_metadata, api_client)


def load_clip_metadata(episode_id: str, clips_dir: Path) -> List[Dict]:
    """
    Load clip metadata from file system
    
    Args:
        episode_id: Episode ID
        clips_dir: Path to clips directory
        
    Returns:
        List[Dict]: Clip metadata information
    """
    # Check session state cache first
    cache_key = f'clip_metadata_{episode_id}'
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    if not clips_dir.exists():
        return []
    
    clip_metadata = []
    
    # Scan for clip directories
    for clip_folder in clips_dir.iterdir():
        if not clip_folder.is_dir():
            continue
        
        clip_id = clip_folder.name
        clip_files = []
        
        # Scan for video files in clip folder
        for file_path in clip_folder.glob("*.mp4"):
            file_info = analyze_clip_file(file_path)
            if file_info:
                clip_files.append(file_info)
        
        if clip_files:
            clip_metadata.append({
                'clip_id': clip_id,
                'folder_path': str(clip_folder),
                'files': clip_files
            })
    
    # Cache the results
    st.session_state[cache_key] = clip_metadata
    
    return clip_metadata


def analyze_clip_file(file_path: Path) -> Optional[Dict]:
    """
    Analyze a clip file and extract metadata
    
    Args:
        file_path: Path to clip file
        
    Returns:
        Optional[Dict]: File metadata or None if analysis fails
    """
    try:
        # Extract variant and aspect ratio from filename
        filename = file_path.stem
        parts = filename.split('_')
        
        variant = "unknown"
        aspect_ratio = "unknown"
        
        # Parse filename pattern: clip_1_9x16_subtitled.mp4
        for part in parts:
            if 'x' in part and part.replace('x', '').replace(':', '').isdigit():
                aspect_ratio = part
            elif part in ['clean', 'subtitled']:
                variant = part
        
        # Get file stats
        file_stats = file_path.stat()
        file_size_mb = file_stats.st_size / (1024 * 1024)
        
        # Determine status
        status = "✅ Ready" if file_stats.st_size > 0 else "❌ Empty"
        
        # Estimate duration (rough approximation based on file size)
        # This is a rough estimate - actual duration would require video analysis
        estimated_duration_s = max(20, min(120, file_size_mb * 2))  # Very rough estimate
        
        return {
            'file_path': str(file_path),
            'filename': file_path.name,
            'variant': variant,
            'aspect_ratio': aspect_ratio,
            'file_size': f"{file_size_mb:.1f} MB",
            'duration': f"{estimated_duration_s:.0f}s",
            'status': status,
            'size_bytes': file_stats.st_size
        }
        
    except Exception as e:
        return {
            'file_path': str(file_path),
            'filename': file_path.name,
            'variant': "unknown",
            'aspect_ratio': "unknown",
            'file_size': "Unknown",
            'duration': "Unknown",
            'status': f"❌ Error: {str(e)}",
            'size_bytes': 0
        }


def render_retry_controls(episode_id: str, clip_metadata: List[Dict], api_client):
    """
    Render retry controls for failed clip generation
    
    Args:
        episode_id: Episode ID
        clip_metadata: Clip metadata list
        api_client: API client instance
    """
    st.markdown("---")
    st.subheader("🔄 Retry Failed Clips")
    
    # Find failed clips
    failed_clips = []
    for clip_data in clip_metadata:
        clip_id = clip_data['clip_id']
        failed_files = [f for f in clip_data['files'] if '❌' in f['status']]
        if failed_files:
            failed_clips.append({
                'clip_id': clip_id,
                'failed_files': failed_files
            })
    
    if not failed_clips:
        st.success("✅ All clips generated successfully!")
        return
    
    st.warning(f"⚠️ Found {len(failed_clips)} clips with issues")
    
    # Display failed clips
    for failed_clip in failed_clips:
        clip_id = failed_clip['clip_id']
        failed_files = failed_clip['failed_files']
        
        with st.expander(f"❌ {clip_id} ({len(failed_files)} failed files)"):
            for file_info in failed_files:
                st.write(f"• {file_info['variant']} {file_info['aspect_ratio']}: {file_info['status']}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Retry single clip
                if st.button(f"🔄 Retry {clip_id}", key=f"retry_{clip_id}"):
                    retry_single_clip(episode_id, clip_id, api_client)
            
            with col2:
                # Delete and regenerate
                if st.button(f"🗑️ Delete & Regenerate {clip_id}", key=f"regen_{clip_id}"):
                    regenerate_single_clip(episode_id, clip_id, api_client)
    
    # Bulk retry controls
    st.markdown("**Bulk Actions:**")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Retry All Failed", type="primary"):
            retry_all_failed_clips(episode_id, failed_clips, api_client)
    
    with col2:
        if st.button("🗑️ Delete All & Regenerate"):
            regenerate_all_failed_clips(episode_id, failed_clips, api_client)


def render_individual_clip_actions(episode_id: str, clip_metadata: List[Dict], api_client):
    """
    Render individual clip action controls
    
    Args:
        episode_id: Episode ID
        clip_metadata: Clip metadata list
        api_client: API client instance
    """
    if not clip_metadata:
        return
    
    st.markdown("---")
    st.subheader("🎬 Individual Clip Actions")
    
    # Clip selection for individual actions
    clip_options = {}
    for clip_data in clip_metadata:
        clip_id = clip_data['clip_id']
        file_count = len(clip_data['files'])
        successful_count = len([f for f in clip_data['files'] if '✅' in f['status']])
        clip_options[f"{clip_id} ({successful_count}/{file_count} files)"] = clip_id
    
    selected_clip_display = st.selectbox(
        "Select clip for individual actions:",
        options=list(clip_options.keys()),
        help="Choose a specific clip to perform actions on"
    )
    
    if selected_clip_display:
        selected_clip_id = clip_options[selected_clip_display]
        
        # Find clip data
        selected_clip_data = next(
            (c for c in clip_metadata if c['clip_id'] == selected_clip_id), 
            None
        )
        
        if selected_clip_data:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Re-render Clip", width="stretch"):
                    retry_single_clip(episode_id, selected_clip_id, api_client)
            
            with col2:
                if st.button("📁 Open Folder", width="stretch"):
                    folder_path = selected_clip_data['folder_path']
                    st.info(f"📁 Clip folder: {folder_path}")
                    st.code(f"explorer {folder_path}", language="bash")
            
            with col3:
                if st.button("🗑️ Delete Clip", width="stretch"):
                    delete_clip_files(selected_clip_id, selected_clip_data)


def retry_single_clip(episode_id: str, clip_id: str, api_client):
    """
    Retry generation for a single clip
    
    Args:
        episode_id: Episode ID
        clip_id: Clip ID to retry
        api_client: API client instance
    """
    with st.spinner(f"Retrying clip generation for {clip_id}..."):
        # Use the single clip render endpoint
        response = api_client.render_clip(
            clip_id=clip_id,
            variants=["clean", "subtitled"],
            aspect_ratios=["9x16", "16x9"],
            force_rerender=True
        )
        
        if response.success:
            st.success(f"✅ Successfully retried clip {clip_id}")
            
            # Clear metadata cache to force refresh
            cache_key = f'clip_metadata_{episode_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            st.rerun()
        else:
            st.error(f"❌ Failed to retry clip {clip_id}: {response.error}")


def regenerate_single_clip(episode_id: str, clip_id: str, api_client):
    """
    Delete and regenerate a single clip
    
    Args:
        episode_id: Episode ID
        clip_id: Clip ID to regenerate
        api_client: API client instance
    """
    # First delete existing files
    clips_dir = Path(f"data/clips/{episode_id}/{clip_id}")
    if clips_dir.exists():
        try:
            import shutil
            shutil.rmtree(clips_dir)
            st.info(f"🗑️ Deleted existing files for {clip_id}")
        except Exception as e:
            st.error(f"❌ Failed to delete files: {str(e)}")
            return
    
    # Then retry generation
    retry_single_clip(episode_id, clip_id, api_client)


def retry_all_failed_clips(episode_id: str, failed_clips: List[Dict], api_client):
    """
    Retry all failed clips
    
    Args:
        episode_id: Episode ID
        failed_clips: List of failed clip information
        api_client: API client instance
    """
    clip_ids = [clip['clip_id'] for clip in failed_clips]
    
    with st.spinner(f"Retrying {len(clip_ids)} failed clips..."):
        # Use bulk render endpoint
        response = api_client.render_clips_bulk(
            episode_id=episode_id,
            clip_ids=clip_ids,
            variants=["clean", "subtitled"],
            aspect_ratios=["9x16", "16x9"],
            force_rerender=True
        )
        
        if response.success:
            st.success(f"✅ Successfully retried {len(clip_ids)} clips")
            
            # Clear metadata cache
            cache_key = f'clip_metadata_{episode_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            st.rerun()
        else:
            st.error(f"❌ Failed to retry clips: {response.error}")


def regenerate_all_failed_clips(episode_id: str, failed_clips: List[Dict], api_client):
    """
    Delete and regenerate all failed clips
    
    Args:
        episode_id: Episode ID
        failed_clips: List of failed clip information
        api_client: API client instance
    """
    # Delete existing files for failed clips
    clips_dir = Path(f"data/clips/{episode_id}")
    deleted_count = 0
    
    for failed_clip in failed_clips:
        clip_id = failed_clip['clip_id']
        clip_folder = clips_dir / clip_id
        
        if clip_folder.exists():
            try:
                import shutil
                shutil.rmtree(clip_folder)
                deleted_count += 1
            except Exception as e:
                st.error(f"❌ Failed to delete {clip_id}: {str(e)}")
    
    if deleted_count > 0:
        st.info(f"🗑️ Deleted files for {deleted_count} clips")
    
    # Retry all failed clips
    retry_all_failed_clips(episode_id, failed_clips, api_client)


def delete_clip_files(clip_id: str, clip_data: Dict):
    """
    Delete files for a specific clip
    
    Args:
        clip_id: Clip ID
        clip_data: Clip metadata
    """
    folder_path = Path(clip_data['folder_path'])
    
    if folder_path.exists():
        try:
            import shutil
            shutil.rmtree(folder_path)
            st.success(f"✅ Deleted all files for clip {clip_id}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to delete clip files: {str(e)}")
    else:
        st.warning(f"⚠️ Clip folder not found: {folder_path}")


def get_score_quality(score: float) -> str:
    """
    Convert numeric score to quality description
    
    Args:
        score: Numeric score (0.0 to 1.0)
        
    Returns:
        str: Quality description
    """
    if score >= 0.8:
        return "🟢 Excellent"
    elif score >= 0.6:
        return "🟡 Good"
    elif score >= 0.4:
        return "🟠 Fair"
    else:
        return "🔴 Poor"