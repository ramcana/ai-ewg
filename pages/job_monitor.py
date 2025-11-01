"""
Job Monitor Page - Monitor async processing jobs and review outputs
"""

import streamlit as st
import requests
import time
from datetime import datetime
from pathlib import Path
import json

# Page config
st.set_page_config(
    page_title="Job Monitor",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Job Monitor & Output Review")
st.markdown("Monitor async processing jobs and review generated content")

# API client
BASE_URL = "http://localhost:8000"

# Show summary metrics at the top
try:
    episodes_response = requests.get(f"{BASE_URL}/episodes?limit=100", timeout=5)
    if episodes_response.status_code == 200:
        all_episodes = episodes_response.json()
        
        # Count by stage
        stage_counts = {}
        for ep in all_episodes:
            stage = ep.get('stage', 'unknown')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        # Display metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("📚 Total Episodes", len(all_episodes))
        col2.metric("🔍 Discovered", stage_counts.get('discovered', 0))
        col3.metric("📝 Transcribed", stage_counts.get('transcribed', 0))
        col4.metric("🤖 Enriched", stage_counts.get('enriched', 0))
        col5.metric("✅ Rendered", stage_counts.get('rendered', 0))
        
        st.divider()
except:
    pass

# Tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(["🔄 Active Jobs", "✅ Completed Jobs", "📹 Episodes", "🎬 Clips"])

# Tab 1: Active Jobs
with tab1:
    st.header("Active Processing Jobs")
    
    if st.button("🔄 Refresh Jobs", key="refresh_active"):
        st.rerun()
    
    try:
        # Get running jobs
        response = requests.get(f"{BASE_URL}/async/jobs?status=running&limit=20", timeout=5)
        
        if response.status_code == 200:
            jobs = response.json()
            
            if jobs:
                for job in jobs:
                    with st.expander(f"🔄 {job['job_type']} - {job['job_id'][:8]}...", expanded=True):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.metric("Progress", f"{job['progress']:.1f}%")
                            st.progress(job['progress'] / 100.0)
                            st.caption(f"**Stage:** {job['current_stage']}")
                            st.caption(f"**Message:** {job['message']}")
                        
                        with col2:
                            eta = job.get('eta_seconds')
                            if eta:
                                mins = int(eta // 60)
                                secs = int(eta % 60)
                                st.metric("ETA", f"{mins}m {secs}s")
                            else:
                                st.metric("ETA", "Calculating...")
                            
                            started = job.get('started_at')
                            if started:
                                st.caption(f"Started: {started[11:19]}")
                        
                        with col3:
                            st.metric("Status", job['status'].upper())
                            
                            # Episode ID from parameters
                            params = job.get('parameters', {})
                            if 'episode_id' in params:
                                episode_id = params['episode_id']
                                st.caption(f"Episode: {episode_id[:20]}...")
            else:
                st.info("No active jobs")
        else:
            st.error(f"Failed to fetch jobs: {response.status_code}")
    
    except Exception as e:
        st.error(f"Error: {e}")
    
    # Queue stats
    st.divider()
    st.subheader("Queue Statistics")
    
    try:
        stats = requests.get(f"{BASE_URL}/async/stats", timeout=5).json()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Queued", stats.get('queued', 0))
        col2.metric("Running", stats.get('running', 0))
        col3.metric("Completed", stats.get('completed', 0))
        col4.metric("Failed", stats.get('failed', 0))
    
    except Exception as e:
        st.error(f"Error fetching stats: {e}")

# Tab 2: Completed Jobs
with tab2:
    st.header("Completed Jobs")
    
    if st.button("🔄 Refresh", key="refresh_completed"):
        st.rerun()
    
    try:
        response = requests.get(f"{BASE_URL}/async/jobs?status=completed&limit=20", timeout=5)
        
        if response.status_code == 200:
            jobs = response.json()
            
            if jobs:
                for job in jobs:
                    # Get episode details if available
                    params = job.get('parameters', {})
                    episode_id = params.get('episode_id', 'Unknown')
                    
                    # Try to fetch episode data
                    episode_data = None
                    show_name = "Unknown"
                    episode_title = "Unknown"
                    
                    try:
                        if episode_id != 'Unknown':
                            ep_response = requests.get(f"{BASE_URL}/episodes/{episode_id}", timeout=3)
                            if ep_response.status_code == 200:
                                episode_data = ep_response.json()
                                show_name = episode_data.get('show', 'Unknown')
                                episode_title = episode_data.get('title', episode_id)
                    except:
                        pass
                    
                    # Display with show and episode name
                    with st.expander(f"✅ {show_name} - {episode_title}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.caption(f"**Job Type:** {job['job_type']}")
                            st.caption(f"**Episode ID:** {episode_id}")
                            st.caption(f"**Job ID:** {job['job_id'][:16]}...")
                            
                            # Show result summary
                            result = job.get('result', {})
                            if result:
                                duration = result.get('duration', 0)
                                if duration:
                                    st.caption(f"**Processing Time:** {duration:.1f}s ({duration/60:.1f} min)")
                        
                        with col2:
                            completed = job.get('completed_at')
                            if completed:
                                st.caption(f"**Completed:**")
                                st.caption(f"{completed[11:19]}")
                            
                            started = job.get('started_at')
                            if started:
                                st.caption(f"**Started:**")
                                st.caption(f"{started[11:19]}")
                        
                        with col3:
                            # View episode button
                            if episode_data:
                                stage = episode_data.get('stage', 'unknown')
                                st.metric("Stage", stage.upper())
                                
                                if stage == 'rendered':
                                    output_path = Path(f"data/outputs/{show_name}/{episode_id}/index.html")
                                    if output_path.exists():
                                        if st.button("📄 Open HTML", key=f"html_{job['job_id']}"):
                                            import webbrowser
                                            webbrowser.open(f"file:///{output_path.absolute()}")
                        
                        # Expandable details
                        with st.expander("📊 Full Result Data"):
                            if result:
                                st.json(result)
                            else:
                                st.caption("No result data")
            else:
                st.info("📝 No completed jobs in queue")
                st.caption("💡 **Tip:** Job history is cleared when the API server restarts. Check the **Episodes** tab to see all processed videos.")
    
    except Exception as e:
        st.error(f"Error: {e}")

# Tab 3: Episodes
with tab3:
    st.header("Processed Episodes")
    
    if st.button("🔄 Refresh Episodes", key="refresh_episodes"):
        st.rerun()
    
    try:
        response = requests.get(f"{BASE_URL}/episodes?limit=50", timeout=5)
        
        if response.status_code == 200:
            episodes = response.json()
            
            if episodes:
                # Group by show
                shows = {}
                for episode in episodes:
                    show = episode.get('show', 'Unknown')
                    if show not in shows:
                        shows[show] = []
                    shows[show].append(episode)
                
                # Display by show
                for show_name, show_episodes in shows.items():
                    st.subheader(f"📺 {show_name} ({len(show_episodes)} episodes)")
                    
                    for episode in show_episodes:
                        episode_id = episode.get('episode_id')
                        title = episode.get('title', episode_id)
                        stage = episode.get('stage', 'unknown')
                        duration = episode.get('duration', 0)
                        
                        # Status emoji
                        status_emoji = {
                            'discovered': '🔍',
                            'prepared': '⚙️',
                            'transcribed': '📝',
                            'enriched': '🤖',
                            'rendered': '✅'
                        }.get(stage, '❓')
                        
                        with st.expander(f"{status_emoji} {title} - {stage.upper()}", expanded=False):
                            col1, col2, col3 = st.columns([2, 1, 1])
                            
                            with col1:
                                st.caption(f"**Episode ID:** {episode_id}")
                                st.caption(f"**Duration:** {duration:.1f}s ({duration/60:.1f} min)")
                                
                                # Show enrichment data if available
                                enrichment = episode.get('enrichment')
                                if enrichment:
                                    summary = enrichment.get('summary', '')
                                    if summary:
                                        st.caption(f"**Summary:** {summary[:200]}...")
                            
                            with col2:
                                st.metric("Processing Stage", stage.upper())
                                
                                # Show metadata
                                metadata = episode.get('metadata', {})
                                if metadata:
                                    file_size = metadata.get('file_size', 0)
                                    if file_size:
                                        size_mb = file_size / (1024 * 1024)
                                        st.caption(f"**Size:** {size_mb:.1f} MB")
                            
                            with col3:
                                # Action buttons
                                if stage == 'rendered':
                                    output_path = Path(f"data/outputs/{show_name}/{episode_id}/index.html")
                                    if output_path.exists():
                                        if st.button("📄 Open HTML", key=f"html_ep_{episode_id}"):
                                            import webbrowser
                                            webbrowser.open(f"file:///{output_path.absolute()}")
                                
                                # View transcript
                                if stage in ['transcribed', 'enriched', 'rendered']:
                                    transcript_path = Path(f"data/transcripts/{episode_id}.txt")
                                    if transcript_path.exists():
                                        if st.button("📝 Transcript", key=f"trans_{episode_id}"):
                                            with open(transcript_path, 'r', encoding='utf-8') as f:
                                                with st.expander("📄 Full Transcript", expanded=True):
                                                    st.text_area("", f.read(), height=400, key=f"text_{episode_id}")
            else:
                st.info("No episodes found. Run discovery first.")
    
    except Exception as e:
        st.error(f"Error: {e}")

# Tab 4: Clips
with tab4:
    st.header("Generated Clips")
    
    # Episode selector
    try:
        episodes_response = requests.get(f"{BASE_URL}/episodes?limit=50", timeout=5)
        
        if episodes_response.status_code == 200:
            episodes = episodes_response.json()
            episode_options = {ep.get('title', ep.get('episode_id')): ep.get('episode_id') for ep in episodes}
            
            selected_title = st.selectbox("Select Episode", list(episode_options.keys()))
            selected_episode_id = episode_options.get(selected_title)
            
            if selected_episode_id:
                # Get clips for episode
                clips_response = requests.get(
                    f"{BASE_URL}/episodes/{selected_episode_id}/clips",
                    timeout=5
                )
                
                if clips_response.status_code == 200:
                    clips_data = clips_response.json()
                    clips = clips_data.get('clips', [])
                    
                    if clips:
                        st.success(f"Found {len(clips)} clip(s)")
                        
                        for i, clip in enumerate(clips):
                            with st.expander(f"🎬 Clip {i+1}: {clip.get('title', 'Untitled')}", expanded=i==0):
                                col1, col2 = st.columns([2, 1])
                                
                                with col1:
                                    st.caption(f"**ID:** {clip.get('id')}")
                                    st.caption(f"**Duration:** {clip.get('duration_ms', 0) / 1000:.1f}s")
                                    st.caption(f"**Score:** {clip.get('score', 0):.2f}")
                                    
                                    caption = clip.get('caption')
                                    if caption:
                                        st.markdown(f"**Caption:** {caption}")
                                    
                                    hashtags = clip.get('hashtags', [])
                                    if hashtags:
                                        st.markdown(f"**Hashtags:** {' '.join(hashtags)}")
                                
                                with col2:
                                    status = clip.get('status', 'unknown')
                                    st.metric("Status", status.upper())
                                    
                                    # Check for rendered files
                                    clip_dir = Path(f"data/clips/{selected_episode_id}")
                                    if clip_dir.exists():
                                        clip_files = list(clip_dir.glob(f"{clip.get('id')}*"))
                                        if clip_files:
                                            st.caption(f"**Files:** {len(clip_files)}")
                                            for file in clip_files[:4]:
                                                st.caption(f"- {file.name}")
                    else:
                        st.info("No clips found for this episode")
                        
                        # Offer to discover clips
                        if st.button("🔍 Discover Clips", key=f"discover_{selected_episode_id}"):
                            with st.spinner("Discovering clips..."):
                                discover_response = requests.post(
                                    f"{BASE_URL}/episodes/{selected_episode_id}/discover_clips",
                                    json={
                                        "max_clips": 5,
                                        "min_duration_ms": 20000,
                                        "max_duration_ms": 120000
                                    },
                                    timeout=30
                                )
                                
                                if discover_response.status_code == 200:
                                    st.success("Clips discovered! Refresh to view.")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to discover clips: {discover_response.status_code}")
                else:
                    st.error(f"Failed to fetch clips: {clips_response.status_code}")
    
    except Exception as e:
        st.error(f"Error: {e}")

# Auto-refresh option
st.sidebar.header("Settings")
auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)

if auto_refresh:
    time.sleep(30)
    st.rerun()
