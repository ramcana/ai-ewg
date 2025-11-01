"""
Video processing workflow interface components

Provides Streamlit components for video processing workflow including
folder input controls, processing options, progress tracking, and
unified workflow automation with comprehensive error handling.
"""

import streamlit as st
import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import time
from datetime import datetime
import logging

from utils.api_client import create_api_client, PipelineApiClient, EpisodeInfo, ProcessingProgress
from utils.file_manager import create_file_manager, FileManager
from utils.error_handler import (
    ErrorHandler, RetryHandler, ProgressTracker, handle_api_operation,
    show_connection_error, show_processing_error, show_success_notification
)

logger = logging.getLogger(__name__)


class VideoProcessingInterface:
    """
    Video processing workflow interface
    
    Handles folder input, processing options, progress tracking,
    and unified workflow automation for video processing.
    """
    
    def __init__(self):
        """Initialize processing interface"""
        self.api_client = create_api_client()
        self.file_manager = create_file_manager()
        
        # Initialize session state for processing
        if 'processing_active' not in st.session_state:
            st.session_state.processing_active = False
        if 'processing_episodes' not in st.session_state:
            st.session_state.processing_episodes = []
        if 'processing_progress' not in st.session_state:
            st.session_state.processing_progress = {}
        if 'processing_results' not in st.session_state:
            st.session_state.processing_results = {}
    
    def clear_all_caches(self, episode_id: Optional[str] = None):
        """
        Clear all caches to prevent stale data issues when reprocessing
        
        Args:
            episode_id: If provided, clear only caches for this episode. Otherwise clear all.
        """
        try:
            logger.info(f"Clearing caches for episode: {episode_id if episode_id else 'ALL'}")
            
            if episode_id:
                # Clear episode-specific caches
                cache_keys_to_remove = []
                
                # Find all cache keys related to this episode
                for key in st.session_state.keys():
                    if episode_id in str(key):
                        cache_keys_to_remove.append(key)
                
                # Remove episode-specific cache keys
                for key in cache_keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                        logger.debug(f"Cleared cache key: {key}")
                
                # Clear file manager cache for this episode
                if hasattr(self.file_manager, 'enable_cache') and self.file_manager.enable_cache:
                    if 'file_cache' in st.session_state:
                        file_cache = st.session_state['file_cache']
                        file_timestamps = st.session_state.get('file_cache_timestamps', {})
                        
                        keys_to_remove = []
                        for cache_key in file_cache.keys():
                            if episode_id in cache_key:
                                keys_to_remove.append(cache_key)
                        
                        for cache_key in keys_to_remove:
                            if cache_key in file_cache:
                                del file_cache[cache_key]
                            if cache_key in file_timestamps:
                                del file_timestamps[cache_key]
                            logger.debug(f"Cleared file cache key: {cache_key}")
                
                # Clear API client cache for this episode
                if hasattr(self.api_client, 'clear_episode_cache'):
                    self.api_client.clear_episode_cache(episode_id)
                
            else:
                # Clear all caches
                cache_keys_to_clear = [
                    'episodes_data', 'last_refresh', 'processing_progress', 'processing_results',
                    'file_cache', 'file_cache_timestamps', 'api_cache', 'cache_timestamps',
                    'dashboard_notifications', 'copied_files_for_cleanup'
                ]
                
                # Clear specific cache keys
                for key in cache_keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                        logger.debug(f"Cleared global cache key: {key}")
                
                # Clear all episode-specific caches
                keys_to_remove = []
                for key in st.session_state.keys():
                    if any(pattern in key for pattern in ['clip_metadata_', 'discovered_clips_', 'episode_', 'social_']):
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                        logger.debug(f"Cleared episode cache key: {key}")
                
                # Reinitialize file manager and API client to clear their internal caches
                self.file_manager = create_file_manager()
                self.api_client = create_api_client()
            
            logger.info(f"Successfully cleared caches for: {episode_id if episode_id else 'ALL'}")
            
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
            st.warning(f"Warning: Failed to clear some caches: {str(e)}")
    
    def clear_failed_episode_cache(self, episode_id: str):
        """
        Clear cache specifically for a failed episode to ensure clean retry
        
        Args:
            episode_id: Episode ID to clear cache for
        """
        try:
            logger.info(f"Clearing failed episode cache for: {episode_id}")
            
            # Clear all caches for this episode
            self.clear_all_caches(episode_id)
            
            # Reset processing progress for this episode
            if episode_id in st.session_state.processing_progress:
                del st.session_state.processing_progress[episode_id]
            
            # Clear any error states
            error_keys = [f'error_{episode_id}', f'retry_count_{episode_id}', f'last_error_{episode_id}']
            for key in error_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            logger.info(f"Successfully cleared failed episode cache for: {episode_id}")
            
        except Exception as e:
            logger.error(f"Error clearing failed episode cache: {e}")
            st.error(f"Failed to clear cache for episode {episode_id}: {str(e)}")
    
    def cleanup_failed_episode_files(self, episode_id: str):
        """
        Clean up temporary and partial files for a failed episode
        
        Args:
            episode_id: Episode ID to clean up files for
        """
        try:
            logger.info(f"Cleaning up failed episode files for: {episode_id}")
            
            # Clean up temporary files in various directories
            cleanup_paths = [
                Path("data/temp"),
                Path("data/processing"),
                Path("data/outputs") / episode_id,
                Path("input_videos/_uncategorized")  # Temporary copied files
            ]
            
            files_cleaned = 0
            for cleanup_path in cleanup_paths:
                if cleanup_path.exists():
                    # Look for files related to this episode
                    for file_path in cleanup_path.rglob('*'):
                        if file_path.is_file() and episode_id in str(file_path):
                            try:
                                file_path.unlink()
                                files_cleaned += 1
                                logger.debug(f"Cleaned up file: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to clean up file {file_path}: {e}")
            
            # Clean up any temporary copied files from session state
            if 'copied_files_for_cleanup' in st.session_state:
                copied_files = st.session_state['copied_files_for_cleanup']
                remaining_files = []
                
                for copied_file in copied_files:
                    if episode_id in copied_file:
                        try:
                            Path(copied_file).unlink()
                            files_cleaned += 1
                            logger.debug(f"Cleaned up copied file: {copied_file}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up copied file {copied_file}: {e}")
                            remaining_files.append(copied_file)
                    else:
                        remaining_files.append(copied_file)
                
                st.session_state['copied_files_for_cleanup'] = remaining_files
            
            if files_cleaned > 0:
                logger.info(f"Successfully cleaned up {files_cleaned} files for episode: {episode_id}")
            else:
                logger.info(f"No files to clean up for episode: {episode_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up failed episode files for {episode_id}: {e}")
            # Don't raise the exception as this is cleanup - log and continue
    
    def validate_folder_path(self, folder_path: str) -> Tuple[bool, str, List[str]]:
        """
        Validate folder path and discover video files
        
        Args:
            folder_path: Path to folder to validate
            
        Returns:
            Tuple: (is_valid, message, video_files)
        """
        if not folder_path:
            return False, "Please enter a folder path", []
        
        path = Path(folder_path)
        
        if not path.exists():
            return False, f"Folder does not exist: {folder_path}", []
        
        if not path.is_dir():
            return False, f"Path is not a directory: {folder_path}", []
        
        # Look for video files
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        video_files = []
        
        try:
            for file_path in path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    video_files.append(str(file_path))
        except Exception as e:
            return False, f"Error scanning folder: {str(e)}", []
        
        if not video_files:
            return False, f"No video files found in: {folder_path}", []
        
        return True, f"Found {len(video_files)} video file(s)", video_files
    
    def render_folder_input_section(self) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Render folder input controls with validation and browse functionality
        
        Returns:
            Tuple: (selected_folder_path, processing_options)
        """
        st.subheader("📁 Video Folder Selection")
        
        # Show uploaded files that are already in temp folder
        temp_upload_dir = Path("data/temp/uploaded")
        if temp_upload_dir.exists():
            uploaded_files = list(temp_upload_dir.glob("*.mp4")) + list(temp_upload_dir.glob("*.avi")) + \
                           list(temp_upload_dir.glob("*.mov")) + list(temp_upload_dir.glob("*.mkv"))
            
            if uploaded_files:
                with st.expander(f"📤 Previously Uploaded Files ({len(uploaded_files)})", expanded=True):
                    st.write("**Files ready to process:**")
                    
                    for i, file in enumerate(uploaded_files):
                        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                        
                        with col1:
                            st.write(f"📹 **{file.name}**")
                        
                        with col2:
                            file_size_mb = file.stat().st_size / (1024 * 1024)
                            st.write(f"{file_size_mb:.1f} MB")
                        
                        with col3:
                            if st.button("✅ Use", key=f"use_upload_{i}", width='stretch'):
                                st.session_state['selected_upload_path'] = str(temp_upload_dir)
                                st.success(f"Selected: {file.name}")
                                st.rerun()
                        
                        with col4:
                            if st.button("🗑️", key=f"delete_upload_{i}", width='stretch'):
                                try:
                                    file.unlink()
                                    st.success(f"Deleted {file.name}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    
                    st.markdown("---")
                    col_use_all, col_clear_all = st.columns(2)
                    
                    with col_use_all:
                        if st.button("✅ Process All Uploaded Files", key="use_all_uploads", type="primary", width='stretch'):
                            st.session_state['selected_upload_path'] = str(temp_upload_dir)
                            st.success(f"Ready to process {len(uploaded_files)} files")
                            st.rerun()
                    
                    with col_clear_all:
                        if st.button("🗑️ Clear All Uploads", key="clear_all_uploads", width='stretch'):
                            if st.session_state.get('confirm_clear_uploads'):
                                for file in uploaded_files:
                                    try:
                                        file.unlink()
                                    except:
                                        pass
                                st.success("All uploads cleared")
                                st.session_state['confirm_clear_uploads'] = False
                                st.rerun()
                            else:
                                st.session_state['confirm_clear_uploads'] = True
                                st.warning("⚠️ Click again to confirm deletion")
        
        # Check if reprocessing a selected episode
        reprocess_path = st.session_state.get('reprocess_source_path')
        reprocess_id = st.session_state.get('reprocess_episode_id')
        
        if reprocess_path and reprocess_id:
            st.info(f"🔄 **Reprocessing Episode:** {reprocess_id}")
            st.write(f"**Source:** `{reprocess_path}`")
            
            if st.button("❌ Clear Reprocess Selection", key="clear_reprocess"):
                del st.session_state['reprocess_source_path']
                del st.session_state['reprocess_episode_id']
                st.rerun()
        
        # Add loading indicator for folder validation
        if 'folder_validation_loading' not in st.session_state:
            st.session_state.folder_validation_loading = False
        
        # Folder path input methods
        input_method = st.radio(
            "Select input method:",
            ["Text Input", "Browse Folders"],
            horizontal=True
        )
        
        folder_path = None
        
        # Priority: 1) Uploaded files, 2) Reprocess path, 3) Manual input
        selected_upload_path = st.session_state.get('selected_upload_path')
        
        if selected_upload_path:
            folder_path = selected_upload_path
            st.success(f"✅ Using uploaded files from: `{folder_path}`")
            
            if st.button("❌ Clear Upload Selection", key="clear_upload_selection"):
                del st.session_state['selected_upload_path']
                st.rerun()
        elif reprocess_path:
            folder_path = str(Path(reprocess_path).parent)
            st.success(f"✅ Using source folder from selected episode: `{folder_path}`")
        elif input_method == "Text Input":
            # Text input with validation
            folder_path = st.text_input(
                "Folder Path:",
                placeholder="Enter path to folder containing videos (e.g., C:\\Videos\\Episodes)",
                help="Enter the full path to the folder containing video files to process"
            )
            
            # Add some common folder suggestions
            st.write("**Common locations:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📁 input_videos/_uncategorized", width="stretch"):
                    folder_path = "input_videos/_uncategorized"
            
            with col2:
                if st.button("📁 input_videos/TheNewsForum", width="stretch"):
                    folder_path = "input_videos/TheNewsForum"
            
            with col3:
                if st.button("📁 Browse Current Dir", width="stretch"):
                    folder_path = "."
        
        else:
            # File uploader for folder browsing (Streamlit limitation workaround)
            st.info("💡 **Tip**: Use the text input method above for better folder selection, or drag & drop files here")
            st.info("📁 **File Size Limit**: Up to 4GB per file supported")
            
            uploaded_files = st.file_uploader(
                "Upload video files:",
                type=['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'],
                accept_multiple_files=True,
                help="Upload video files directly (alternative to folder selection). Max file size: 4GB per file"
            )
            
            if uploaded_files:
                # Save uploaded files to temp directory with progress indication
                temp_dir = Path("data/temp/uploaded")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                # Show upload progress for multiple files
                if len(uploaded_files) > 1:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                total_size = 0
                for i, uploaded_file in enumerate(uploaded_files):
                    if len(uploaded_files) > 1:
                        status_text.text(f"Saving file {i+1} of {len(uploaded_files)}: {uploaded_file.name}")
                        progress_bar.progress((i + 1) / len(uploaded_files))
                    
                    file_path = temp_dir / uploaded_file.name
                    file_size = uploaded_file.size if hasattr(uploaded_file, 'size') else len(uploaded_file.getbuffer())
                    total_size += file_size
                    
                    # Show warning for very large files
                    if file_size > 2 * 1024 * 1024 * 1024:  # 2GB
                        st.warning(f"Large file detected: {uploaded_file.name} ({file_size / (1024*1024*1024):.1f} GB)")
                    
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                # Clear progress indicators
                if len(uploaded_files) > 1:
                    progress_bar.empty()
                    status_text.empty()
                
                folder_path = str(temp_dir)
                total_size_gb = total_size / (1024 * 1024 * 1024)
                st.success(f"✅ Uploaded {len(uploaded_files)} file(s) to {folder_path}")
                st.info(f"📊 Total upload size: {total_size_gb:.2f} GB")
        
        # Validate folder path if provided with loading indicator
        video_files = []
        if folder_path:
            with st.spinner("🔍 Validating folder and discovering video files..."):
                is_valid, message, video_files = self.validate_folder_path(folder_path)
            
            if is_valid:
                st.success(f"✅ {message}")
                
                # Show discovered video files with selection
                with st.expander(f"📹 Select Video Files to Process ({len(video_files)} found)", expanded=True):
                    st.write("**Select which files to process:**")
                    
                    # Add select all / deselect all buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Select All", key="select_all_files"):
                            st.session_state['selected_files'] = video_files.copy()
                            st.rerun()
                    with col2:
                        if st.button("❌ Deselect All", key="deselect_all_files"):
                            st.session_state['selected_files'] = []
                            st.rerun()
                    
                    # Initialize selected files in session state
                    if 'selected_files' not in st.session_state:
                        st.session_state['selected_files'] = []
                    
                    # Show checkboxes for each file
                    for i, video_file in enumerate(video_files):
                        file_path = Path(video_file)
                        file_size = file_path.stat().st_size / (1024*1024) if file_path.exists() else 0
                        
                        # Check if file is in selected list
                        is_selected = video_file in st.session_state['selected_files']
                        
                        # Create checkbox
                        selected = st.checkbox(
                            f"{file_path.name} ({file_size:.1f} MB)",
                            value=is_selected,
                            key=f"file_checkbox_{i}_{file_path.name}"
                        )
                        
                        # Update selection state
                        if selected and video_file not in st.session_state['selected_files']:
                            st.session_state['selected_files'].append(video_file)
                        elif not selected and video_file in st.session_state['selected_files']:
                            st.session_state['selected_files'].remove(video_file)
                    
                    # Show selection summary
                    selected_count = len(st.session_state['selected_files'])
                    if selected_count > 0:
                        st.success(f"✅ {selected_count} file(s) selected for processing")
                    else:
                        st.warning("⚠️ No files selected. Please select at least one file to process.")
                    
                    # Update video_files to only include selected files
                    video_files = st.session_state['selected_files'].copy()
            else:
                st.error(f"❌ {message}")
                folder_path = None
        
        # Processing options
        st.markdown("---")
        st.subheader("⚙️ Processing Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Auto-enable force_reprocess if user selected an episode to reprocess
            default_force_reprocess = bool(st.session_state.get('reprocess_episode_id'))
            
            force_reprocess = st.checkbox(
                "Force Reprocess",
                value=default_force_reprocess,
                help="Force reprocessing even if episodes are already processed (clears cache and forces fresh processing). Auto-enabled when reprocessing a selected episode."
            )
            
            if default_force_reprocess and force_reprocess:
                st.info("✅ Force reprocess enabled - will regenerate all files")
            
            clear_cache_on_start = st.checkbox(
                "Clear Cache on Start",
                value=True,
                help="Clear all caches before starting processing to prevent stale data issues"
            )
            
            target_stage = st.selectbox(
                "Target Stage:",
                ["rendered", "editorial", "enriched", "transcribed"],
                index=0,
                help="Processing stage to complete (rendered = full processing)"
            )
        
        with col2:
            auto_clips = st.checkbox(
                "Auto-generate Clips",
                value=False,
                help="Automatically generate clips after episode processing"
            )
            
            auto_social = st.checkbox(
                "Auto-create Social Packages",
                value=True,
                help="Automatically create social media packages"
            )
        
        # Debug information
        if st.checkbox("🐛 Show Debug Info", value=False, help="Show debugging information for troubleshooting"):
            st.write("**Debug Information:**")
            st.write(f"- Folder path: {folder_path}")
            st.write(f"- Video files found: {len(video_files)}")
            if video_files:
                st.write("- Video files:")
                for i, vf in enumerate(video_files[:5]):  # Show first 5
                    st.write(f"  {i+1}. {vf}")
                if len(video_files) > 5:
                    st.write(f"  ... and {len(video_files) - 5} more")
        
        processing_options = {
            "force_reprocess": force_reprocess,
            "clear_cache_on_start": clear_cache_on_start,
            "target_stage": target_stage,
            "auto_clips": auto_clips,
            "auto_social": auto_social,
            "video_files": video_files
        }
        
        return folder_path, processing_options
    
    def detect_stuck_processes(self) -> List[str]:
        """
        Detect episodes that may be stuck in processing
        
        Returns:
            List[str]: Episode IDs that appear to be stuck
        """
        stuck_episodes = []
        current_time = datetime.now()
        
        if not st.session_state.processing_active:
            return stuck_episodes
        
        progress_data = st.session_state.processing_progress
        
        for episode_id, progress_info in progress_data.items():
            # Skip completed or failed episodes
            if progress_info.get('completed') or progress_info.get('error'):
                continue
            
            # Check if episode has been in the same stage for too long
            last_update = progress_info.get('last_update')
            if last_update:
                if isinstance(last_update, str):
                    try:
                        last_update = datetime.fromisoformat(last_update)
                    except:
                        continue
                
                time_since_update = (current_time - last_update).total_seconds()
                
                # Consider stuck if no progress for more than 10 minutes
                if time_since_update > 600:  # 10 minutes
                    current_stage = progress_info.get('current_stage', 'unknown')
                    progress_percentage = progress_info.get('progress_percentage', 0)
                    
                    # Additional checks for different stages
                    stage_timeouts = {
                        'processing': 1800,  # 30 minutes for main processing
                        'clips': 900,       # 15 minutes for clip generation
                        'social': 300,      # 5 minutes for social packages
                        'transcribed': 1200, # 20 minutes for transcription
                        'enriched': 600,    # 10 minutes for enrichment
                        'editorial': 300    # 5 minutes for editorial
                    }
                    
                    timeout_threshold = stage_timeouts.get(current_stage, 600)  # Default 10 minutes
                    
                    if time_since_update > timeout_threshold:
                        stuck_episodes.append(episode_id)
        
        return stuck_episodes

    def render_stuck_process_recovery(self, stuck_episodes: List[str]) -> None:
        """
        Render recovery options for stuck processes
        
        Args:
            stuck_episodes: List of episode IDs that appear stuck
        """
        if not stuck_episodes:
            return
        
        st.warning(f"⚠️ Detected {len(stuck_episodes)} potentially stuck episode(s)")
        
        with st.expander("🔧 Stuck Process Recovery Options", expanded=True):
            st.write("**Stuck Episodes:**")
            
            progress_data = st.session_state.processing_progress
            
            for episode_id in stuck_episodes:
                progress_info = progress_data.get(episode_id, {})
                current_stage = progress_info.get('current_stage', 'unknown')
                last_update = progress_info.get('last_update', 'unknown')
                
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**{episode_id}**")
                    st.write(f"Stage: {current_stage}, Last update: {last_update}")
                
                with col2:
                    if st.button(f"🔄 Retry", key=f"retry_stuck_{episode_id}", width="stretch"):
                        # Reset the stuck episode and retry
                        self.retry_stuck_episode(episode_id)
                        st.rerun()
                
                with col3:
                    if st.button(f"⏹️ Skip", key=f"skip_stuck_{episode_id}", width="stretch"):
                        # Mark as failed and skip
                        self.skip_stuck_episode(episode_id)
                        st.rerun()
            
            # Bulk actions
            st.markdown("**Bulk Actions:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Retry All Stuck", width="stretch"):
                    for episode_id in stuck_episodes:
                        self.retry_stuck_episode(episode_id)
                    st.success(f"✅ Retrying {len(stuck_episodes)} stuck episodes")
                    st.rerun()
            
            with col2:
                if st.button("⏹️ Skip All Stuck", width="stretch"):
                    for episode_id in stuck_episodes:
                        self.skip_stuck_episode(episode_id)
                    st.success(f"✅ Skipped {len(stuck_episodes)} stuck episodes")
                    st.rerun()
            
            with col3:
                if st.button("🧹 Deep Clean & Retry", width="stretch"):
                    # Perform deep cleanup and retry
                    self.clear_all_caches_and_state(stuck_episodes)
                    for episode_id in stuck_episodes:
                        self.retry_stuck_episode(episode_id)
                    st.success(f"✅ Deep cleaned and retrying {len(stuck_episodes)} episodes")
                    st.rerun()

    def retry_stuck_episode(self, episode_id: str) -> None:
        """
        Retry a stuck episode with cleanup
        
        Args:
            episode_id: Episode ID to retry
        """
        try:
            # Clear cache for this episode
            self.clear_all_caches_and_state([episode_id])
            
            # Reset progress state
            if episode_id in st.session_state.processing_progress:
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'discovered',
                    'progress_percentage': 10,
                    'message': 'Retrying after being stuck',
                    'error': None,
                    'completed': False,
                    'last_update': datetime.now().isoformat()
                })
            
            logger.info(f"Retrying stuck episode: {episode_id}")
            
        except Exception as e:
            logger.error(f"Error retrying stuck episode {episode_id}: {e}")

    def skip_stuck_episode(self, episode_id: str) -> None:
        """
        Skip a stuck episode by marking it as failed
        
        Args:
            episode_id: Episode ID to skip
        """
        try:
            # Mark as failed
            if episode_id in st.session_state.processing_progress:
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'failed',
                    'progress_percentage': 0,
                    'message': 'Skipped due to being stuck',
                    'error': 'Process was stuck and skipped by user',
                    'completed': False,
                    'last_update': datetime.now().isoformat()
                })
            
            logger.info(f"Skipped stuck episode: {episode_id}")
            
        except Exception as e:
            logger.error(f"Error skipping stuck episode {episode_id}: {e}")
    
    def delete_failed_episode(self, episode_id: str) -> bool:
        """
        Delete a failed episode from the database and clean up all associated files
        
        Args:
            episode_id: Episode ID to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            logger.info(f"Deleting failed episode: {episode_id}")
            
            # Step 1: Clean up all files
            self.cleanup_failed_episode_files(episode_id)
            
            # Step 2: Delete from API/database
            delete_response = self.api_client.delete_episode(episode_id)
            
            if not delete_response.success:
                logger.warning(f"API deletion failed for {episode_id}: {delete_response.error}")
                # Continue with local cleanup even if API delete fails
            
            # Step 3: Remove from session state
            if episode_id in st.session_state.processing_progress:
                del st.session_state.processing_progress[episode_id]
            
            if episode_id in st.session_state.processing_results:
                del st.session_state.processing_results[episode_id]
            
            # Remove from processing episodes list
            if 'processing_episodes' in st.session_state:
                st.session_state.processing_episodes = [
                    ep for ep in st.session_state.processing_episodes 
                    if ep.episode_id != episode_id
                ]
            
            # Step 4: Clear all caches
            self.clear_failed_episode_cache(episode_id)
            
            logger.info(f"Successfully deleted failed episode: {episode_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting failed episode {episode_id}: {e}")
            st.error(f"Failed to delete episode {episode_id}: {str(e)}")
            return False

    def render_progress_tracking(self) -> None:
        """
        Render real-time progress tracking display with stuck process detection
        """
        if not st.session_state.processing_active:
            return
        
        st.markdown("---")
        st.subheader("📊 Processing Progress")
        
        episodes = st.session_state.processing_episodes
        progress_data = st.session_state.processing_progress
        
        if not episodes:
            st.info("No episodes currently being processed")
            return
        
        # Detect stuck processes
        stuck_episodes = self.detect_stuck_processes()
        
        # Show stuck process recovery if needed
        if stuck_episodes:
            self.render_stuck_process_recovery(stuck_episodes)
        
        # Overall progress
        total_episodes = len(episodes)
        completed_episodes = sum(1 for ep in episodes if progress_data.get(ep.episode_id, {}).get('completed', False))
        overall_progress = completed_episodes / total_episodes if total_episodes > 0 else 0
        
        st.progress(overall_progress, text=f"Overall Progress: {completed_episodes}/{total_episodes} episodes completed")
        
        # Individual episode progress
        for i, episode in enumerate(episodes):
            episode_id = episode.episode_id
            progress_info = progress_data.get(episode_id, {})
            
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**Episode {i+1}**: {episode.title or episode_id}")
                
                with col2:
                    current_stage = progress_info.get('current_stage', 'queued')
                    st.write(f"Stage: {current_stage}")
                
                with col3:
                    if progress_info.get('completed', False):
                        st.success("✅ Done")
                    elif progress_info.get('error'):
                        st.error("❌ Error")
                    else:
                        st.info("⏳ Processing")
                
                # Progress bar for individual episode
                episode_progress = progress_info.get('progress_percentage', 0) / 100
                progress_text = progress_info.get('message', 'Queued for processing')
                
                st.progress(episode_progress, text=progress_text)
                
                # Show error if any
                if progress_info.get('error'):
                    st.error(f"Error: {progress_info['error']}")
        
        # Auto-refresh progress every 3 seconds when processing is active
        if st.session_state.processing_active:
            # Use a placeholder for auto-refresh
            placeholder = st.empty()
            with placeholder.container():
                st.info("🔄 Processing active - page will refresh automatically...")
            
            # Auto-refresh after a delay
            time.sleep(3)
            st.rerun()
    
    def create_episodes_from_video_files(self, video_files: List[str], folder_path: str) -> List[EpisodeInfo]:
        """
        Create episode objects directly from video files for direct processing
        
        Args:
            video_files: List of video file paths
            folder_path: Base folder path
            
        Returns:
            List[EpisodeInfo]: Created episode objects
        """
        episodes = []
        
        try:
            for video_file in video_files:
                file_path = Path(video_file)
                
                # Skip if file doesn't exist or isn't accessible
                if not file_path.exists() or not file_path.is_file():
                    logger.warning(f"Skipping inaccessible file: {video_file}")
                    continue
                
                # Generate episode ID from filename
                episode_id = self.generate_episode_id_from_filename(file_path.name)
                
                # Create episode info object
                episode = EpisodeInfo(
                    episode_id=episode_id,
                    title=file_path.stem,  # Filename without extension
                    show_name="Direct Upload",  # Default show name
                    status="discovered",
                    processing_stage="raw",
                    source_path=str(file_path.absolute()),
                    duration=None,  # Will be determined during processing
                    error=None
                )
                
                episodes.append(episode)
                logger.info(f"Created episode for direct processing: {episode_id} from {video_file}")
            
            return episodes
            
        except Exception as e:
            logger.error(f"Error creating episodes from video files: {e}")
            return []
    
    def attempt_direct_folder_registration(self, folder_path: str, video_files: List[str]) -> List[EpisodeInfo]:
        """
        Attempt to register a folder with the API for episode discovery
        
        This method tries several approaches to get the API to recognize
        video files from arbitrary folders.
        
        Args:
            folder_path: Path to the folder containing videos
            video_files: List of video file paths
            
        Returns:
            List[EpisodeInfo]: Successfully registered episodes
        """
        episodes = []
        
        try:
            # Approach 1: Copy files to a monitored directory temporarily
            st.info("📁 Attempting to register files with API...")
            
            # Use the uncategorized directory (MUST match config/pipeline.yaml)
            # Using relative path to match config: "input_videos/_uncategorized"
            monitored_dir = Path("input_videos/_uncategorized")
            monitored_dir.mkdir(parents=True, exist_ok=True)
            
            copied_files = []
            
            with st.spinner("Copying files to monitored directory..."):
                for video_file in video_files:
                    source_path = Path(video_file)
                    if not source_path.exists():
                        continue
                    
                    # Create unique filename to avoid conflicts
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    target_filename = f"{timestamp}_{source_path.name}"
                    target_path = monitored_dir / target_filename
                    
                    try:
                        # Copy file to monitored directory
                        import shutil
                        shutil.copy2(source_path, target_path)
                        copied_files.append(str(target_path))
                        logger.info(f"Copied {source_path} to {target_path}")
                        
                    except Exception as e:
                        logger.error(f"Failed to copy {source_path}: {e}")
                        continue
            
            if not copied_files:
                st.error("Failed to copy any files to monitored directory")
                return []
            
            st.success(f"✅ Copied {len(copied_files)} files to monitored directory")
            
            # Approach 2: Wait a moment for file system to settle
            time.sleep(2)
            
            # Approach 3: Trigger API discovery again
            with st.spinner("Re-discovering episodes..."):
                discover_response = self.api_client.discover_episodes()
                
                if discover_response.success and discover_response.data:
                    # Parse discovered episodes
                    if isinstance(discover_response.data, dict):
                        episodes_data = discover_response.data.get('episodes', [])
                    elif isinstance(discover_response.data, list):
                        episodes_data = discover_response.data
                    else:
                        episodes_data = []
                    
                    # Look for episodes that match our copied files
                    for episode_data in episodes_data:
                        episode = self.api_client.parse_episode_info(episode_data)
                        
                        # Check if this episode corresponds to one of our copied files
                        if episode.source_path:
                            episode_path = Path(episode.source_path)
                            if any(copied_file in str(episode_path) for copied_file in copied_files):
                                episodes.append(episode)
                                logger.info(f"Found registered episode: {episode.episode_id}")
            
            if episodes:
                st.success(f"🎉 Successfully registered {len(episodes)} episodes with API!")
                
                # Store the copied files for cleanup later
                if 'copied_files_for_cleanup' not in st.session_state:
                    st.session_state.copied_files_for_cleanup = []
                st.session_state.copied_files_for_cleanup.extend(copied_files)
                
            else:
                st.warning("⚠️ Files copied but no episodes discovered by API")
                
                # Clean up copied files if discovery failed
                for copied_file in copied_files:
                    try:
                        Path(copied_file).unlink()
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {copied_file}: {e}")
            
            return episodes
            
        except Exception as e:
            logger.error(f"Error in direct folder registration: {e}")
            st.error(f"Registration failed: {str(e)}")
            return []

    def generate_episode_id_from_filename(self, filename: str) -> str:
        """
        Generate a consistent episode ID from filename
        
        Args:
            filename: Video filename
            
        Returns:
            str: Generated episode ID
        """
        # Remove extension and clean filename
        base_name = Path(filename).stem
        
        # Replace spaces and special characters with underscores
        clean_name = "".join(c if c.isalnum() else "_" for c in base_name.lower())
        
        # Remove multiple consecutive underscores
        while "__" in clean_name:
            clean_name = clean_name.replace("__", "_")
        
        # Remove leading/trailing underscores
        clean_name = clean_name.strip("_")
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return f"direct_{clean_name}_{timestamp}"

    def cleanup_temporary_files(self) -> None:
        """
        Clean up temporary files that were copied for API registration
        """
        if 'copied_files_for_cleanup' not in st.session_state:
            return
        
        copied_files = st.session_state.copied_files_for_cleanup
        if not copied_files:
            return
        
        try:
            cleaned_count = 0
            for copied_file in copied_files:
                try:
                    file_path = Path(copied_file)
                    if file_path.exists():
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"Cleaned up temporary file: {copied_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {copied_file}: {e}")
            
            if cleaned_count > 0:
                st.info(f"🧹 Cleaned up {cleaned_count} temporary files")
            
            # Clear the cleanup list
            st.session_state.copied_files_for_cleanup = []
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def create_social_media_package(self, episode: EpisodeInfo) -> Dict[str, bool]:
        """
        Create social media packages for an episode using the advanced generator
        
        Args:
            episode: Episode information
            
        Returns:
            Dict: Platform -> success status
        """
        try:
            # Import the advanced social media generator
            from components.social_generator import create_social_generator
            
            # Create generator instance
            generator = create_social_generator()
            
            # Generate packages for default platforms
            platforms = ['twitter', 'instagram', 'facebook']  # Skip TikTok by default
            
            # Generate packages
            results = generator.generate_packages_for_episode(episode.episode_id, platforms)
            
            return results
            
        except Exception as e:
            logger.error(f"Error creating social media packages: {e}")
            return {platform: False for platform in ['twitter', 'instagram', 'facebook']}
    
    def process_episode_workflow(self, episode: EpisodeInfo, options: Dict[str, Any]) -> bool:
        """
        Process a single episode through the complete workflow with comprehensive error handling
        
        Args:
            episode: Episode to process
            options: Processing options
            
        Returns:
            bool: True if processing succeeded
        """
        episode_id = episode.episode_id
        
        try:
            # Update progress: Starting processing
            st.session_state.processing_progress[episode_id].update({
                'current_stage': 'processing',
                'progress_percentage': 20,
                'message': 'Starting episode processing...',
                'last_update': datetime.now().isoformat()
            })
            
            # Step 1: Clear any previous errors for this episode
            try:
                from utils.error_reporter import clear_processing_errors
                clear_processing_errors(episode_id)
            except ImportError:
                pass  # Error reporter may not be available
            
            # Step 2: Process episode through API with retry logic
            logger.info(f"Processing episode {episode_id} to stage {options['target_stage']}")
            
            def process_operation():
                return self.api_client.process_episode(
                    episode_id=episode_id,
                    target_stage=options['target_stage'],
                    force_reprocess=options['force_reprocess'],
                    clear_cache=options.get('clear_cache_on_start', False)
                )
            
            try:
                process_response = RetryHandler.with_retry(
                    process_operation,
                    max_attempts=2,  # Reduced attempts for episode processing
                    delay_seconds=5.0,
                    operation_name=f"Episode {episode_id} Processing",
                    show_progress=False  # Don't show progress in background thread
                )
                
                if not process_response.success:
                    raise Exception(f"Episode processing failed: {process_response.error}")
                
                # Validate HTML output like original process_episode.py
                self.validate_episode_outputs(episode_id, process_response.data)
                
            except Exception as e:
                # Log the error and update progress
                error_msg = f"Episode processing failed after retries: {str(e)}"
                logger.error(error_msg)
                
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'failed',
                    'progress_percentage': 0,
                    'message': error_msg,
                    'error': str(e),
                    'completed': False
                })
                
                return False
            
            # Update progress: Episode processed
            st.session_state.processing_progress[episode_id].update({
                'current_stage': options['target_stage'],
                'progress_percentage': 60,
                'message': f'Episode processed to {options["target_stage"]} stage',
                'last_update': datetime.now().isoformat()
            })
            
            # Step 2: Generate clips if requested (with error handling)
            if options.get('auto_clips', False):
                logger.info(f"Generating clips for episode {episode_id}")
                
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'clips',
                    'progress_percentage': 70,
                    'message': 'Generating clips...',
                    'last_update': datetime.now().isoformat()
                })
                
                try:
                    # Discover clips first
                    discover_response = self.api_client.discover_clips(
                        episode_id=episode_id,
                        max_clips=3,
                        min_duration_ms=20000,
                        max_duration_ms=120000,
                        aspect_ratios=["9x16", "16x9"],
                        score_threshold=0.3
                    )
                    
                    if discover_response.success:
                        # Render clips in bulk
                        render_response = self.api_client.render_clips_bulk(
                            episode_id=episode_id,
                            variants=["clean", "subtitled"],
                            aspect_ratios=["9x16", "16x9"]
                        )
                        
                        if not render_response.success:
                            logger.warning(f"Clip rendering failed for {episode_id}: {render_response.error}")
                            # Don't fail the entire episode for clip issues
                            st.session_state.processing_progress[episode_id].update({
                                'message': f'Episode processed, but clip rendering failed: {render_response.error}'
                            })
                    else:
                        logger.warning(f"Clip discovery failed for {episode_id}: {discover_response.error}")
                        st.session_state.processing_progress[episode_id].update({
                            'message': f'Episode processed, but clip discovery failed: {discover_response.error}'
                        })
                        
                except Exception as e:
                    logger.warning(f"Clip generation error for {episode_id}: {e}")
                    # Don't fail the entire episode for clip issues
                    st.session_state.processing_progress[episode_id].update({
                        'message': f'Episode processed, but clip generation failed: {str(e)}'
                    })
            
            # Step 3: Create social media packages if requested (with error handling)
            if options.get('auto_social', False):
                logger.info(f"Creating social media packages for episode {episode_id}")
                
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'social',
                    'progress_percentage': 85,
                    'message': 'Creating social media packages...'
                })
                
                try:
                    # Create social packages using advanced generator
                    social_results = self.create_social_media_package(episode)
                    
                    # Log results
                    success_count = sum(1 for success in social_results.values() if success)
                    total_count = len(social_results)
                    
                    if success_count == total_count:
                        logger.info(f"Successfully created {success_count} social packages for {episode_id}")
                    elif success_count > 0:
                        logger.warning(f"Created {success_count}/{total_count} social packages for {episode_id}")
                        st.session_state.processing_progress[episode_id].update({
                            'message': f'Episode processed, partial social packages created ({success_count}/{total_count})'
                        })
                    else:
                        logger.error(f"Failed to create any social packages for {episode_id}")
                        st.session_state.processing_progress[episode_id].update({
                            'message': 'Episode processed, but social package creation failed'
                        })
                        
                except Exception as e:
                    logger.warning(f"Social package creation error for {episode_id}: {e}")
                    # Don't fail the entire episode for social package issues
                    st.session_state.processing_progress[episode_id].update({
                        'message': f'Episode processed, but social package creation failed: {str(e)}'
                    })
            
            # Step 4: Ensure file organization (with error handling)
            try:
                self.file_manager.create_episode_directories(episode_id)
            except Exception as e:
                logger.warning(f"File organization error for {episode_id}: {e}")
                # Don't fail the episode for file organization issues
            
            # Mark as completed
            st.session_state.processing_progress[episode_id].update({
                'current_stage': 'completed',
                'progress_percentage': 100,
                'message': 'Episode processing completed successfully',
                'completed': True
            })
            
            logger.info(f"Successfully completed processing for episode {episode_id}")
            return True
            
        except Exception as e:
            logger.error(f"Critical error processing episode {episode_id}: {e}")
            
            # Clean up failed episode files
            try:
                self.cleanup_failed_episode_files(episode_id)
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'failed',
                    'progress_percentage': 0,
                    'message': f'Processing failed: {str(e)} (files cleaned up)',
                    'error': str(e),
                    'completed': False
                })
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup for failed episode {episode_id}: {cleanup_error}")
                st.session_state.processing_progress[episode_id].update({
                    'current_stage': 'failed',
                    'progress_percentage': 0,
                    'message': f'Processing failed: {str(e)} (cleanup also failed)',
                    'error': str(e),
                    'completed': False
                })
            
            return False
    
    def validate_episode_outputs(self, episode_id: str, response_data: Dict[str, Any]) -> None:
        """
        Validate episode outputs like the original process_episode.py
        
        Args:
            episode_id: Episode identifier
            response_data: API response data
        """
        try:
            if not response_data:
                logger.warning(f"No response data for episode {episode_id}")
                return
            
            # Check if processing was successful
            if not response_data.get('success'):
                logger.error(f"Episode processing failed: {response_data.get('error')}")
                return
            
            # Check for HTML output (like original script)
            outputs = response_data.get('outputs', {})
            if outputs.get('rendered_html'):
                html_path = outputs.get('html_path', 'unknown')
                logger.info(f"HTML generated for {episode_id}: {html_path}")
                
                # Check for Phase 2 features in HTML (like original script)
                html_content = outputs['rendered_html']
                has_guests = 'Featured Guests' in html_content
                has_badges = 'credibility-badge' in html_content
                has_verified = 'Verified Expert' in html_content or 'Identified Contributor' in html_content
                
                logger.info(f"Phase 2 Integration Check for {episode_id}:")
                logger.info(f"  Guest Section: {'YES' if has_guests else 'NO'}")
                logger.info(f"  Credibility Badges: {'YES' if has_badges else 'NO'}")
                logger.info(f"  Verified Experts: {'YES' if has_verified else 'NO'}")
                
                # Update progress with HTML validation results
                st.session_state.processing_progress[episode_id].update({
                    'html_generated': True,
                    'html_path': html_path,
                    'phase2_features': {
                        'guests': has_guests,
                        'badges': has_badges,
                        'verified': has_verified
                    }
                })
            else:
                logger.warning(f"No HTML output found for episode {episode_id}")
                st.session_state.processing_progress[episode_id].update({
                    'html_generated': False
                })
            
            # Check metadata (like original script)
            metadata = response_data.get('metadata', {})
            if metadata:
                logger.info(f"Metadata for {episode_id}:")
                logger.info(f"  Show: {metadata.get('show_name', 'Unknown')}")
                logger.info(f"  Title: {metadata.get('title', 'Unknown')}")
                logger.info(f"  Host: {metadata.get('host', 'Unknown')}")
                guests = metadata.get('guests', [])
                if guests is not None:
                    logger.info(f"  Guests: {len(guests)}")
                else:
                    logger.info(f"  Guests: 0")
                
                # Store metadata in progress for display
                st.session_state.processing_progress[episode_id].update({
                    'metadata': metadata
                })
            
        except Exception as e:
            logger.error(f"Error validating outputs for episode {episode_id}: {e}")

    def clear_all_caches_and_state(self, episode_ids: List[str] = None) -> None:
        """
        Clear all cached data and state for episodes to ensure clean reprocessing
        
        Args:
            episode_ids: List of episode IDs to clear cache for. If None, clears all.
        """
        try:
            # Clear Streamlit session state caches
            cache_keys_to_clear = []
            
            if episode_ids:
                # Clear specific episode caches
                for episode_id in episode_ids:
                    cache_keys_to_clear.extend([
                        f'clip_metadata_{episode_id}',
                        f'discovered_clips_{episode_id}',
                        f'episode_status_{episode_id}',
                        f'episode_outputs_{episode_id}',
                        f'social_packages_{episode_id}'
                    ])
            else:
                # Clear all episode-related caches
                keys_to_check = list(st.session_state.keys())
                for key in keys_to_check:
                    if any(pattern in key for pattern in [
                        'clip_metadata_', 'discovered_clips_', 'episode_status_',
                        'episode_outputs_', 'social_packages_', 'processing_progress'
                    ]):
                        cache_keys_to_clear.append(key)
            
            # Remove cache keys from session state
            cleared_count = 0
            for key in cache_keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
                    cleared_count += 1
            
            # Clear file manager caches
            if hasattr(self.file_manager, 'enable_cache') and self.file_manager.enable_cache:
                if 'file_cache' in st.session_state:
                    if episode_ids:
                        # Clear specific episode file caches
                        file_cache = st.session_state['file_cache']
                        file_timestamps = st.session_state.get('file_cache_timestamps', {})
                        
                        keys_to_remove = []
                        for cache_key in file_cache.keys():
                            if any(episode_id in cache_key for episode_id in episode_ids):
                                keys_to_remove.append(cache_key)
                        
                        for key in keys_to_remove:
                            if key in file_cache:
                                del file_cache[key]
                                cleared_count += 1
                            if key in file_timestamps:
                                del file_timestamps[key]
                    else:
                        # Clear all file caches
                        cleared_count += len(st.session_state.get('file_cache', {}))
                        st.session_state['file_cache'] = {}
                        st.session_state['file_cache_timestamps'] = {}
            
            # Clear API client caches
            if 'api_cache' in st.session_state:
                if episode_ids:
                    # Clear specific episode API caches
                    api_cache = st.session_state['api_cache']
                    cache_timestamps = st.session_state.get('cache_timestamps', {})
                    
                    keys_to_remove = []
                    for cache_key in api_cache.keys():
                        if any(episode_id in cache_key for episode_id in episode_ids):
                            keys_to_remove.append(cache_key)
                    
                    for key in keys_to_remove:
                        if key in api_cache:
                            del api_cache[key]
                            cleared_count += 1
                        if key in cache_timestamps:
                            del cache_timestamps[key]
                else:
                    # Clear all API caches
                    cleared_count += len(st.session_state.get('api_cache', {}))
                    st.session_state['api_cache'] = {}
                    st.session_state['cache_timestamps'] = {}
            
            # Clear error states
            try:
                from utils.error_reporter import clear_processing_errors
                if episode_ids:
                    for episode_id in episode_ids:
                        clear_processing_errors(episode_id)
                else:
                    clear_processing_errors()  # Clear all errors
            except ImportError:
                pass  # Error reporter may not be available
            
            logger.info(f"Cleared {cleared_count} cache entries for episodes: {episode_ids or 'all'}")
            
        except Exception as e:
            logger.error(f"Error during cache and state cleanup: {e}")

    def cleanup_episode_files_on_failure(self, episode_ids: List[str], keep_transcripts: bool = True) -> None:
        """
        Clean up episode files when processing fails to prevent stale data issues
        
        Args:
            episode_ids: List of episode IDs to clean up
            keep_transcripts: Whether to keep transcript files
        """
        try:
            for episode_id in episode_ids:
                try:
                    # Use file manager to clean up episode files
                    cleanup_success = self.file_manager.cleanup_episode_files(
                        episode_id, 
                        keep_transcripts=keep_transcripts
                    )
                    if cleanup_success:
                        logger.info(f"Cleaned up file system artifacts for failed episode: {episode_id}")
                    else:
                        logger.warning(f"Failed to clean up file system artifacts for episode: {episode_id}")
                except Exception as e:
                    logger.warning(f"Error cleaning up file system for episode {episode_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during file cleanup for failed episodes: {e}")

    def start_processing_workflow(self, folder_path: str, options: Dict[str, Any]) -> None:
        """
        Start the unified processing workflow with comprehensive error handling
        
        Args:
            folder_path: Path to folder containing videos
            options: Processing options dictionary
        """
        try:
            # Check if we're retrying with a different folder path
            if 'retry_folder_path' in st.session_state:
                folder_path = st.session_state['retry_folder_path']
                del st.session_state['retry_folder_path']
                st.info(f"🔄 Retrying discovery with folder: {folder_path}")
            
            # Clear caches if requested (default behavior to prevent stale data)
            if options.get('clear_cache_on_start', True) or options.get('force_reprocess', False):
                if options.get('force_reprocess', False):
                    st.info("🧹 Force reprocess enabled - performing deep cleanup...")
                else:
                    st.info("🧹 Clearing caches to prevent stale data issues...")
                self.clear_all_caches_and_state()
                st.success("✅ Caches and state cleared")
            
            st.session_state.processing_active = True
            st.session_state.processing_episodes = []
            st.session_state.processing_progress = {}
            st.session_state.processing_results = {}
            
            # Step 1: Test API connectivity first
            with st.spinner("🔍 Checking API connectivity..."):
                health_response = self.api_client.check_health()
                
                if not health_response.success:
                    error_info = ErrorHandler.get_api_error_info(
                        health_response.error or "API health check failed"
                    )
                    ErrorHandler.display_error(error_info)
                    
                    if error_info.retry_possible:
                        if st.button("🔄 Retry Connection"):
                            st.rerun()
                    
                    st.session_state.processing_active = False
                    return
            
            # Step 2: Check if user has selected specific files
            selected_video_files = options.get('video_files', [])
            episodes = []
            discover_response = None  # Initialize to avoid UnboundLocalError
            
            # Normalize selected file paths for comparison (define early for all code paths)
            selected_paths = {str(Path(f).resolve()) for f in selected_video_files} if selected_video_files else set()
            
            if selected_video_files:
                st.info(f"🔍 Loading {len(selected_video_files)} selected file(s) from database...")
                
                list_response = self.api_client.list_episodes(limit=1000)
                
                if list_response.success and list_response.data:
                    all_episodes_data = list_response.data.get('episodes', []) if isinstance(list_response.data, dict) else list_response.data
                    
                    # Find matching episodes
                    for episode_data in all_episodes_data:
                        episode = self.api_client.parse_episode_info(episode_data)
                        episode_path = str(Path(episode.source_path).resolve())
                        
                        if episode_path in selected_paths:
                            episodes.append(episode)
                            logger.info(f"Found existing episode: {episode.episode_id} at {episode.source_path}")
                    
                    st.success(f"✅ Found {len(episodes)} existing episode(s) in database")
                    
                    # If some files don't have episodes yet, run discovery for those only
                    if len(episodes) < len(selected_video_files):
                        missing_count = len(selected_video_files) - len(episodes)
                        st.info(f"🔍 {missing_count} file(s) not in database, running discovery...")
                        
                        discover_response = self.api_client.discover_episodes()
                        
                        if discover_response.success and discover_response.data:
                            # Parse newly discovered episodes
                            new_episodes_data = discover_response.data.get('episodes', []) if isinstance(discover_response.data, dict) else discover_response.data
                            
                            # Add only the missing episodes
                            for episode_data in new_episodes_data:
                                episode = self.api_client.parse_episode_info(episode_data)
                                episode_path = str(Path(episode.source_path).resolve())
                                
                                # Only add if it's one of the selected files and not already in our list
                                if episode_path in selected_paths and not any(ep.episode_id == episode.episode_id for ep in episodes):
                                    episodes.append(episode)
                                    logger.info(f"Discovered new episode: {episode.episode_id} at {episode.source_path}")
                            
                            st.success(f"✅ Added {len(episodes) - (len(selected_video_files) - missing_count)} newly discovered episode(s)")
                
                # Show what we found
                if episodes:
                    show_success_notification(
                        f"Ready to process {len(episodes)} episode(s)",
                        f"Loaded from database without full discovery"
                    )
                    
                    # Show selected episodes
                    with st.expander("📹 Selected Episodes", expanded=True):
                        for episode in episodes:
                            st.write(f"- **{episode.title or episode.episode_id}** ({episode.source_path})")
                else:
                    st.warning("⚠️ No matching episodes found in database")
                    st.info("💡 Files may need to be discovered first. Running full discovery...")
                    
                    # Fall back to full discovery
                    discover_response = self.api_client.discover_episodes()
                    
                    if discover_response.success and discover_response.data:
                        episodes_data = discover_response.data.get('episodes', []) if isinstance(discover_response.data, dict) else discover_response.data
                        
                        # Filter to selected files
                        for episode_data in episodes_data:
                            episode = self.api_client.parse_episode_info(episode_data)
                            episode_path = str(Path(episode.source_path).resolve())
                            
                            if episode_path in selected_paths:
                                episodes.append(episode)
                        
                        if episodes:
                            st.success(f"✅ Discovered {len(episodes)} episode(s)")
            else:
                # No files selected - run full discovery (old behavior)
                st.info("🔍 No files selected, running full discovery...")
                discover_response = self.api_client.discover_episodes()
                
                if discover_response.success and discover_response.data:
                    episodes_data = discover_response.data.get('episodes', []) if isinstance(discover_response.data, dict) else discover_response.data
                    
                    for episode_data in episodes_data:
                        episode = self.api_client.parse_episode_info(episode_data)
                        episodes.append(episode)
                    
                    if episodes:
                        show_success_notification(
                            f"Discovered {len(episodes)} episode(s) from API",
                            f"Found episodes in: {folder_path}" if folder_path else None
                        )
                        
                        with st.expander("📹 Discovered Episodes", expanded=True):
                            for episode in episodes:
                                st.write(f"- **{episode.title or episode.episode_id}** ({episode.source_path})")
                    else:
                        st.info("🔍 No episodes found via API discovery, trying local file discovery...")
            
            # Fallback: Handle direct folder processing when API discovery finds nothing
            if not episodes and options.get('video_files'):
                st.warning("⚠️ No episodes found via API discovery")
                st.info("🔄 Attempting direct folder processing...")
                
                video_files = options.get('video_files', [])
                st.info(f"🔍 Found {len(video_files)} video files")
                
                # Try to register the folder with the API and re-discover
                episodes = self.attempt_direct_folder_registration(folder_path, video_files)
                
                if episodes:
                    st.success(f"✅ Successfully registered {len(episodes)} episode(s) for processing")
                    
                    # Show the files that will be processed
                    with st.expander("📹 Episodes Ready for Processing", expanded=False):
                        for episode in episodes:
                            st.write(f"- **{episode.title or episode.episode_id}** ({episode.source_path})")
                else:
                    # Final fallback - show manual options
                    st.error("❌ Unable to register episodes with API")
                    
                    st.write("**Video Files Found:**")
                    for video_file in video_files:
                        file_path = Path(video_file)
                        file_size = file_path.stat().st_size / (1024*1024) if file_path.exists() else 0
                        st.write(f"- {file_path.name} ({file_size:.1f} MB)")
                    
                    st.info("💡 **Manual Processing Options:**")
                    st.write("1. **Restart API Server**: Stop and restart the API server to pick up configuration changes")
                    st.write("2. **Copy Files**: Copy files to a monitored directory (e.g., input_videos/_uncategorized)")
                    st.write("3. **Wait and Retry**: The API may need time to detect new files")
                    
                    # Provide copy command for Windows
                    if video_files and len(video_files) == 1:
                        source_file = Path(video_files[0])
                        target_dir = "input_videos\\_uncategorized"
                        copy_command = f'copy "{source_file}" "{target_dir}"'
                        st.code(f"Windows Command: {copy_command}")
                    
                    # Add retry button
                    if st.button("🔄 Retry Discovery"):
                        st.rerun()
                        st.rerun()
            
            # Handle API discovery failure
            elif discover_response and not discover_response.success:
                error_info = ErrorHandler.get_api_error_info(
                    discover_response.error or "Episode discovery failed"
                )
                ErrorHandler.display_error(error_info)
                
                # Cannot proceed without API discovery
                st.error("❌ Cannot proceed without successful API discovery")
                st.info("💡 **To resolve this:**")
                st.write("- Ensure the AI-EWG pipeline API is running")
                st.write("- Check API connectivity")
                st.write("- Try refreshing the page and retrying")
            
            if not episodes:
                st.error("❌ No episodes found to process")
                st.write("**Troubleshooting:**")
                st.write("1. Check if video files exist in the specified folder")
                st.write("2. Ensure the API server is running and accessible")
                st.write("3. Verify folder permissions and file formats")
                
                st.session_state.processing_active = False
                return
            
            st.session_state.processing_episodes = episodes
            
            # Initialize progress tracking
            for episode in episodes:
                st.session_state.processing_progress[episode.episode_id] = {
                    'current_stage': 'discovered',
                    'progress_percentage': 10,
                    'message': 'Episode discovered, queued for processing',
                    'completed': False,
                    'error': None,
                    'last_update': datetime.now().isoformat()
                }
            
            # Start batch processing with enhanced error handling
            self.start_batch_processing_with_error_handling(episodes, options)
            
        except Exception as e:
            logger.error(f"Error starting processing workflow: {e}")
            
            error_info = ErrorHandler.get_api_error_info(str(e))
            ErrorHandler.display_error(error_info)
            
            st.session_state.processing_active = False
            
            # Offer retry option
            if st.button("🔄 Retry Workflow"):
                st.rerun()
    
    def start_batch_processing_with_error_handling(self, episodes: List[EpisodeInfo], options: Dict[str, Any]) -> None:
        """
        Start batch processing of episodes with comprehensive error handling
        
        Args:
            episodes: List of episodes to process
            options: Processing options
        """
        # Process episodes synchronously to avoid session state threading issues
        successful_episodes = 0
        failed_episodes = 0
        
        try:
            # Show processing status
            st.info(f"🚀 Starting batch processing of {len(episodes)} episodes...")
            
            # Create a progress container
            progress_container = st.container()
            
            with progress_container:
                overall_progress = st.progress(0)
                status_text = st.empty()
                
                for i, episode in enumerate(episodes):
                    # Update overall progress
                    progress = (i + 1) / len(episodes)
                    overall_progress.progress(progress)
                    status_text.text(f"Processing episode {i+1}/{len(episodes)}: {episode.episode_id}")
                    
                    logger.info(f"Processing episode {i+1}/{len(episodes)}: {episode.episode_id}")
                    
                    try:
                        success = self.process_episode_workflow(episode, options)
                        
                        if success:
                            successful_episodes += 1
                        else:
                            failed_episodes += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing episode {episode.episode_id}: {e}")
                        failed_episodes += 1
                        
                        # Update progress with error
                        if episode.episode_id in st.session_state.processing_progress:
                            st.session_state.processing_progress[episode.episode_id].update({
                                'current_stage': 'failed',
                                'progress_percentage': 0,
                                'message': f'Processing failed: {str(e)}',
                                'error': str(e),
                                'completed': False
                            })
                
                # Complete processing
                overall_progress.progress(1.0)
                status_text.text("Processing completed!")
                
                # Mark overall processing as complete
                st.session_state.processing_active = False
                
                # Log final results
                total_episodes = len(episodes)
                logger.info(f"Batch processing completed: {successful_episodes} successful, {failed_episodes} failed out of {total_episodes}")
                
                # Store final results for display
                st.session_state.processing_results = {
                    'total': total_episodes,
                    'successful': successful_episodes,
                    'failed': failed_episodes,
                    'completed_at': datetime.now().isoformat()
                }
                
                # Show completion message
                if failed_episodes == 0:
                    st.success(f"✅ All {total_episodes} episodes processed successfully!")
                else:
                    st.warning(f"⚠️ Processing completed: {successful_episodes} successful, {failed_episodes} failed")
                    
                    # Clean up failed episodes to prevent stale data issues
                    failed_episode_ids = []
                    for episode in episodes:
                        progress_info = st.session_state.processing_progress.get(episode.episode_id, {})
                        if progress_info.get('error') or progress_info.get('current_stage') == 'failed':
                            failed_episode_ids.append(episode.episode_id)
                    
                    if failed_episode_ids:
                        st.info(f"🧹 Cleaning up {len(failed_episode_ids)} failed episodes to prevent stale data...")
                        self.cleanup_episode_files_on_failure(failed_episode_ids, keep_transcripts=True)
                        self.clear_all_caches_and_state(failed_episode_ids)
                        st.success("✅ Failed episode cleanup completed")
                
                # Clean up temporary copied files
                self.cleanup_temporary_files()
                    
        except Exception as e:
            logger.error(f"Critical batch processing error: {e}")
            st.session_state.processing_active = False
            
            # Store error in session state for display
            st.session_state.processing_results = {
                'total': len(episodes),
                'successful': successful_episodes,
                'failed': failed_episodes + 1,
                'critical_error': str(e),
                'completed_at': datetime.now().isoformat()
            }
            
            st.error(f"Critical processing error: {str(e)}")
        
        show_success_notification(
            f"Started batch processing of {len(episodes)} episodes",
            "Processing will continue in the background. Monitor progress below."
        )
    
    def render_processing_controls(self, folder_path: Optional[str], options: Dict[str, Any]) -> None:
        """
        Render processing control buttons and status
        
        Args:
            folder_path: Selected folder path
            options: Processing options
        """
        st.markdown("---")
        st.subheader("🚀 Processing Controls")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Start processing button
            can_start = (folder_path is not None and 
                        len(options.get('video_files', [])) > 0 and 
                        not st.session_state.processing_active)
            
            if st.button(
                "🎬 Start Processing",
                disabled=not can_start,
                width="stretch",
                type="primary"
            ):
                self.start_processing_workflow(folder_path, options)
        
        with col2:
            # Stop processing button
            if st.button(
                "⏹️ Stop Processing",
                disabled=not st.session_state.processing_active,
                width="stretch"
            ):
                st.session_state.processing_active = False
                st.success("Processing stopped")
                st.rerun()
        
        with col3:
            # Clear results button
            if st.button(
                "🗑️ Clear Results",
                disabled=st.session_state.processing_active,
                width="stretch"
            ):
                st.session_state.processing_episodes = []
                st.session_state.processing_progress = {}
                st.session_state.processing_results = {}
                st.success("Results cleared")
                st.rerun()
        
        with col4:
            # Deep cleanup button
            if st.button(
                "🧹 Deep Clean",
                disabled=st.session_state.processing_active,
                width="stretch",
                help="Clear all caches, state, and temporary files"
            ):
                with st.spinner("Performing deep cleanup..."):
                    # Perform comprehensive cleanup
                    self.clear_all_caches_and_state()
                    
                    # Clear all processing state
                    st.session_state.processing_episodes = []
                    st.session_state.processing_progress = {}
                    st.session_state.processing_results = {}
                    
                    # Clear temporary files
                    self.cleanup_temporary_files()
                    
                    # Also clear any failed episode files if we have episode data
                    if st.session_state.get('processing_episodes'):
                        failed_episode_ids = []
                        for episode in st.session_state.processing_episodes:
                            progress_info = st.session_state.processing_progress.get(episode.episode_id, {})
                            if progress_info.get('error'):
                                failed_episode_ids.append(episode.episode_id)
                        
                        if failed_episode_ids:
                            self.cleanup_episode_files_on_failure(failed_episode_ids)
                
                st.success("🧹 Deep cleanup completed - all caches and temporary files cleared")
                st.rerun()
        
        # Additional cache management controls
        if not st.session_state.processing_active:
            st.markdown("---")
            st.subheader("🧹 Cache Management")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🗑️ Clear All Caches", width="stretch", help="Clear all caches to prevent stale data issues"):
                    self.clear_all_caches()
                    st.success("✅ All caches cleared")
                    st.rerun()
            
            with col2:
                if st.button("🧹 Deep Cleanup", width="stretch", help="Clear caches and clean up temporary files"):
                    # Clear all caches
                    self.clear_all_caches()
                    
                    # Clean up temporary files for all episodes
                    if st.session_state.processing_episodes:
                        for episode in st.session_state.processing_episodes:
                            progress_info = st.session_state.processing_progress.get(episode.episode_id, {})
                            if progress_info.get('error'):
                                self.cleanup_failed_episode_files(episode.episode_id)
                    
                    st.success("🧹 Deep cleanup completed - all caches and temporary files cleared")
                    st.rerun()
            
            with col3:
                # Show cache statistics
                cache_stats = {
                    'session_keys': len([k for k in st.session_state.keys() if 'cache' in k.lower() or 'episode' in k.lower()]),
                    'file_cache': len(st.session_state.get('file_cache', {})),
                    'api_cache': len(st.session_state.get('api_cache', {}))
                }
                
                total_cache_items = sum(cache_stats.values())
                if st.button(f"📊 Cache Stats ({total_cache_items})", width="stretch", help="Show cache statistics"):
                    st.write("**Cache Statistics:**")
                    st.write(f"- Session cache keys: {cache_stats['session_keys']}")
                    st.write(f"- File cache items: {cache_stats['file_cache']}")
                    st.write(f"- API cache items: {cache_stats['api_cache']}")
                    st.write(f"- Total cached items: {total_cache_items}")
        
        # Processing status with health monitoring
        if st.session_state.processing_active:
            # Show active processing status with health indicators
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info("🔄 Processing is active")
            
            with col2:
                # Show processing health
                stuck_episodes = self.detect_stuck_processes()
                if stuck_episodes:
                    st.warning(f"⚠️ {len(stuck_episodes)} stuck")
                else:
                    st.success("✅ All healthy")
            
            with col3:
                # Show system resource status (simplified)
                try:
                    import psutil
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory_percent = psutil.virtual_memory().percent
                    
                    if cpu_percent > 90 or memory_percent > 90:
                        st.error(f"🔴 Resources: {cpu_percent:.0f}% CPU, {memory_percent:.0f}% RAM")
                    elif cpu_percent > 70 or memory_percent > 70:
                        st.warning(f"🟡 Resources: {cpu_percent:.0f}% CPU, {memory_percent:.0f}% RAM")
                    else:
                        st.success(f"🟢 Resources: {cpu_percent:.0f}% CPU, {memory_percent:.0f}% RAM")
                except ImportError:
                    st.info("📊 Resource monitoring unavailable")
                except Exception:
                    st.info("📊 Resource data unavailable")
            
            st.info("Use the progress section below to monitor detailed status and handle any stuck processes.")
            
        elif st.session_state.processing_episodes:
            st.success("✅ Processing completed. Check results below.")
        else:
            st.info("💡 Select a folder with video files and click 'Start Processing' to begin.")
    
    def render_processing_results(self) -> None:
        """
        Render processing results summary with enhanced error handling and retry options
        """
        episodes = st.session_state.processing_episodes
        progress_data = st.session_state.processing_progress
        final_results = st.session_state.processing_results
        
        if not episodes:
            return
        
        st.markdown("---")
        st.subheader("📋 Processing Results")
        
        # Show final results summary if available
        if final_results and not st.session_state.processing_active:
            if final_results.get('critical_error'):
                st.error(f"🚨 Critical Error: {final_results['critical_error']}")
                
                if st.button("🔄 Retry All Failed Episodes"):
                    # Reset failed episodes and restart processing
                    failed_episodes = [ep for ep in episodes if progress_data.get(ep.episode_id, {}).get('error')]
                    if failed_episodes:
                        # Reset their progress
                        for episode in failed_episodes:
                            st.session_state.processing_progress[episode.episode_id] = {
                                'current_stage': 'discovered',
                                'progress_percentage': 10,
                                'message': 'Queued for retry',
                                'completed': False,
                                'error': None
                            }
                        st.rerun()
            else:
                # Show completion notification
                total = final_results.get('total', 0)
                successful = final_results.get('successful', 0)
                failed = final_results.get('failed', 0)
                
                if failed == 0:
                    show_success_notification(
                        f"All {total} episodes processed successfully! 🎉",
                        f"Completed at: {final_results.get('completed_at', 'Unknown')}"
                    )
                else:
                    st.warning(f"⚠️ Processing completed with {failed} failures out of {total} episodes")
        
        # Results summary
        total_episodes = len(episodes)
        completed_episodes = sum(1 for ep in episodes if progress_data.get(ep.episode_id, {}).get('completed', False))
        failed_episodes = sum(1 for ep in episodes if progress_data.get(ep.episode_id, {}).get('error'))
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Episodes", total_episodes)
        
        with col2:
            st.metric("Completed", completed_episodes, delta=f"{completed_episodes}/{total_episodes}")
        
        with col3:
            st.metric("Failed", failed_episodes, delta=f"{failed_episodes}/{total_episodes}")
        
        with col4:
            success_rate = ((completed_episodes / total_episodes) * 100) if total_episodes > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        # Detailed results table with enhanced error information
        if episodes:
            st.write("**Episode Details:**")
            
            results_data = []
            for episode in episodes:
                progress_info = progress_data.get(episode.episode_id, {})
                
                # Format status with emoji
                status = progress_info.get('current_stage', 'unknown')
                if status == 'completed':
                    status_display = "✅ Completed"
                elif status == 'failed':
                    status_display = "❌ Failed"
                elif progress_info.get('error'):
                    status_display = f"⚠️ {status} (Error)"
                else:
                    status_display = f"🔄 {status}"
                
                # Add HTML generation status like original process_episode.py
                html_status = "❌ No HTML"
                if progress_info.get('html_generated'):
                    html_status = "✅ HTML Generated"
                elif progress_info.get('current_stage') == 'completed':
                    html_status = "⚠️ Completed but no HTML"
                
                results_data.append({
                    "Episode ID": episode.episode_id,
                    "Title": episode.title or "Unknown",
                    "Status": status_display,
                    "Progress": f"{progress_info.get('progress_percentage', 0):.0f}%",
                    "HTML": html_status,
                    "Message": progress_info.get('message', 'No status'),
                    "Error": progress_info.get('error', '') or 'None'
                })
            
            st.dataframe(results_data, width="stretch")
            
            # Show retry/delete options for failed episodes
            failed_episode_list = [ep for ep in episodes if progress_data.get(ep.episode_id, {}).get('error')]
            
            if failed_episode_list and not st.session_state.processing_active:
                st.subheader("🔄 Manage Failed Episodes")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔄 Retry All Failed", width="stretch", type="primary"):
                        # Clear caches for all failed episodes first
                        st.info("🧹 Clearing caches for failed episodes...")
                        for episode in failed_episode_list:
                            self.clear_failed_episode_cache(episode.episode_id)
                        
                        # Reset failed episodes and restart processing
                        for episode in failed_episode_list:
                            st.session_state.processing_progress[episode.episode_id] = {
                                'current_stage': 'discovered',
                                'progress_percentage': 10,
                                'message': 'Cache cleared and queued for retry',
                                'completed': False,
                                'error': None
                            }
                        
                        # Get current processing options (simplified)
                        retry_options = {
                            'force_reprocess': True,
                            'clear_cache_on_start': True,
                            'target_stage': 'rendered',
                            'auto_clips': True,
                            'auto_social': True,
                            'video_files': []
                        }
                        
                        st.success(f"✅ Cleared caches for {len(failed_episode_list)} failed episodes")
                        self.start_batch_processing_with_error_handling(failed_episode_list, retry_options)
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete All Failed", width="stretch", type="secondary"):
                        # Confirm deletion
                        if 'confirm_delete_all' not in st.session_state:
                            st.session_state['confirm_delete_all'] = True
                            st.warning(f"⚠️ Are you sure you want to delete {len(failed_episode_list)} failed episode(s)? Click again to confirm.")
                            st.rerun()
                        else:
                            # Perform deletion
                            deleted_count = 0
                            for episode in failed_episode_list:
                                if self.delete_failed_episode(episode.episode_id):
                                    deleted_count += 1
                            
                            st.success(f"✅ Deleted {deleted_count} failed episode(s)")
                            del st.session_state['confirm_delete_all']
                            st.rerun()
                
                with col3:
                    if st.button("📋 Show Error Details", width="stretch"):
                        # Show detailed error information
                        for episode in failed_episode_list:
                            progress_info = progress_data.get(episode.episode_id, {})
                            error = progress_info.get('error', 'Unknown error')
                            
                            with st.expander(f"❌ Error for {episode.title or episode.episode_id}"):
                                st.error(f"**Error:** {error}")
                                st.write(f"**Stage:** {progress_info.get('current_stage', 'unknown')}")
                                st.write(f"**Message:** {progress_info.get('message', 'No message')}")
                                
                                # Individual episode actions
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    if st.button(f"🔄 Retry", key=f"retry_{episode.episode_id}", width="stretch"):
                                        self.clear_failed_episode_cache(episode.episode_id)
                                        st.session_state.processing_progress[episode.episode_id] = {
                                            'current_stage': 'discovered',
                                            'progress_percentage': 10,
                                            'message': 'Queued for retry',
                                            'completed': False,
                                            'error': None
                                        }
                                        st.rerun()
                                
                                with col_b:
                                    if st.button(f"🗑️ Delete", key=f"delete_{episode.episode_id}", width="stretch"):
                                        if self.delete_failed_episode(episode.episode_id):
                                            st.success(f"✅ Deleted {episode.episode_id}")
                                            st.rerun()
                                
                                # Provide specific remediation based on error type
                                if "Connection" in error or "timeout" in error.lower():
                                    st.info("💡 **Suggestion:** Check API server connectivity and try again")
                                elif "FileNotFound" in error or "No such file" in error:
                                    st.info("💡 **Suggestion:** Verify source video files exist and are accessible")
                                elif "Permission" in error:
                                    st.info("💡 **Suggestion:** Check file permissions and disk space")
                                else:
                                    st.info("💡 **Suggestion:** Check server logs for more details")
            
            # Show file organization results for completed episodes
            completed_episode_list = [ep for ep in episodes if progress_data.get(ep.episode_id, {}).get('completed', False)]
            
            if completed_episode_list:
                st.write("**Generated Files:**")
                
                for episode in completed_episode_list:
                    with st.expander(f"📁 Files for {episode.title or episode.episode_id}", expanded=False):
                        try:
                            # Get file structure for this episode
                            file_structure = self.file_manager.get_episode_file_structure(episode.episode_id)
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Clips:**")
                                if file_structure.clips_dir.file_count > 0:
                                    st.success(f"✅ {file_structure.clips_dir.file_count} clip files ({file_structure.clips_dir.total_size_mb:.1f} MB)")
                                    for clip_file in file_structure.clips_dir.files[:5]:  # Show first 5
                                        st.write(f"- {clip_file.name} ({clip_file.size_mb:.1f} MB)")
                                else:
                                    st.info("No clips generated")
                                
                                st.write("**Transcripts:**")
                                if file_structure.transcript_files:
                                    for transcript in file_structure.transcript_files:
                                        st.write(f"- {transcript.name} ({transcript.size_mb:.1f} MB)")
                                else:
                                    st.info("No transcripts found")
                            
                            with col2:
                                st.write("**Social Packages:**")
                                if file_structure.social_dir.file_count > 0:
                                    st.success(f"✅ {file_structure.social_dir.file_count} social packages")
                                    
                                    # Load and display social package previews
                                    for platform in ['twitter', 'instagram', 'tiktok', 'facebook']:
                                        package = self.file_manager.load_social_package(episode.episode_id, platform)
                                        if package:
                                            caption = package.get('caption', '')
                                            hashtags = package.get('hashtags', [])
                                            
                                            st.write(f"**{platform.title()}:**")
                                            st.write(f"Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
                                            if hashtags:
                                                st.write(f"Hashtags: {' '.join(hashtags[:5])}")  # Show first 5 hashtags
                                else:
                                    st.info("No social packages created")
                            
                            st.write("**HTML Pages:**")
                            html_path = self.file_manager.get_html_page_path(episode.episode_id)
                            if html_path:
                                st.success(f"✅ HTML page available")
                                if st.button(f"🔗 View HTML", key=f"html_{episode.episode_id}"):
                                    st.write(f"HTML page: {html_path}")
                            else:
                                st.info("No HTML page found")
                            
                            # Show HTML output validation like original process_episode.py
                            progress_info = progress_data.get(episode.episode_id, {})
                            if progress_info.get('html_generated'):
                                st.write("**HTML Output:**")
                                html_path = progress_info.get('html_path', 'Unknown')
                                st.success(f"✅ HTML generated: {html_path}")
                                
                                # Show Phase 2 features like original script
                                phase2_features = progress_info.get('phase2_features', {})
                                if phase2_features:
                                    st.write("**Phase 2 Integration Check:**")
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        guest_status = "✅ YES" if phase2_features.get('guests') else "❌ NO"
                                        st.write(f"Guest Section: {guest_status}")
                                    
                                    with col2:
                                        badge_status = "✅ YES" if phase2_features.get('badges') else "❌ NO"
                                        st.write(f"Credibility Badges: {badge_status}")
                                    
                                    with col3:
                                        verified_status = "✅ YES" if phase2_features.get('verified') else "❌ NO"
                                        st.write(f"Verified Experts: {verified_status}")
                                
                                # Show metadata like original script
                                metadata = progress_info.get('metadata', {})
                                if metadata:
                                    st.write("**Metadata:**")
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        st.write(f"Show: {metadata.get('show_name', 'Unknown')}")
                                        st.write(f"Title: {metadata.get('title', 'Unknown')}")
                                    
                                    with col2:
                                        st.write(f"Host: {metadata.get('host', 'Unknown')}")
                                        guests = metadata.get('guests', [])
                                        guest_count = len(guests) if guests else 0
                                        st.write(f"Guests: {guest_count}")
                            else:
                                st.warning("⚠️ No HTML output generated")
                        
                        except Exception as e:
                            st.error(f"Error loading file structure for {episode.episode_id}: {str(e)}")


def render_video_processing_page():
    """
    Main function to render the video processing page
    """
    st.header("🎬 Video Processing Workflow")
    
    st.write("""
    Process video folders through the complete AI-EWG pipeline. This unified workflow handles
    video transcription, enrichment, HTML generation, clip creation, and social media package generation.
    """)
    
    # Initialize processing interface
    interface = VideoProcessingInterface()
    
    # Show previously processed videos at the top
    with st.expander("📚 Previously Processed Videos", expanded=False):
        try:
            from utils.api_client import create_api_client
            api_client = create_api_client()
            
            # Get list of episodes
            response = api_client.list_episodes(limit=100, force_refresh=True)
            
            if response.success and response.data:
                episodes = response.data
                
                if episodes:
                    st.write(f"**Total Episodes:** {len(episodes)}")
                    
                    # Episode selection dropdown
                    st.markdown("### 🎯 Select Episode to Reprocess")
                    episode_options = {}
                    for ep in episodes:
                        episode_id = ep.get('episode_id', 'N/A')
                        title = ep.get('title', 'Unknown')[:40]
                        show = ep.get('show_name', 'Unknown')
                        stage = ep.get('stage', 'N/A')
                        status_icon = '✅' if stage == 'rendered' else '⚠️' if stage == 'failed' else '🔄'
                        display_name = f"{status_icon} {show} - {title} ({stage})"
                        episode_options[display_name] = episode_id
                    
                    selected_display = st.selectbox(
                        "Choose an episode to reprocess or view details:",
                        options=list(episode_options.keys()),
                        key="reprocess_episode_select"
                    )
                    
                    selected_episode_id = episode_options.get(selected_display)
                    
                    if selected_episode_id:
                        # Show selected episode details
                        selected_ep = next((ep for ep in episodes if ep.get('episode_id') == selected_episode_id), None)
                        
                        if selected_ep:
                            col_info1, col_info2, col_info3 = st.columns(3)
                            with col_info1:
                                st.metric("Current Stage", selected_ep.get('stage', 'Unknown'))
                            with col_info2:
                                st.metric("Show", selected_ep.get('show_name', 'Unknown'))
                            with col_info3:
                                source_path = selected_ep.get('source_path', 'N/A')
                                st.metric("Source", source_path.split('\\')[-1] if source_path != 'N/A' else 'N/A')
                            
                            # Reprocess button
                            st.markdown("---")
                            col_reprocess, col_view = st.columns(2)
                            
                            with col_reprocess:
                                if st.button("🔄 Reprocess This Episode", key="reprocess_selected", type="primary", width='stretch'):
                                    # Set the source path in session state for the processing interface
                                    if selected_ep.get('source_path'):
                                        st.session_state['reprocess_episode_id'] = selected_episode_id
                                        st.session_state['reprocess_source_path'] = selected_ep.get('source_path')
                                        st.success(f"✅ Ready to reprocess: {selected_episode_id}")
                                        st.info("👇 Configure processing options below and click 'Start Processing'")
                                    else:
                                        st.error("❌ Source path not found for this episode")
                            
                            with col_view:
                                if st.button("📁 View Episode Details", key="view_selected", width='stretch'):
                                    st.session_state['current_page'] = 'View Outputs'
                                    st.session_state['selected_episode_id'] = selected_episode_id
                                    st.rerun()
                    
                    # Show all episodes table
                    st.markdown("---")
                    st.markdown("### 📋 All Episodes")
                    
                    # Create a simple table
                    import pandas as pd
                    
                    table_data = []
                    for ep in episodes:
                        table_data.append({
                            'Episode ID': ep.get('episode_id', 'N/A')[:30],
                            'Title': ep.get('title', 'N/A')[:40],
                            'Show': ep.get('show_name', 'Unknown'),
                            'Stage': ep.get('stage', 'N/A'),
                            'Status': '✅' if ep.get('stage') == 'rendered' else '⚠️'
                        })
                    
                    df = pd.DataFrame(table_data)
                    
                    # Display table
                    st.dataframe(df, width='stretch', hide_index=True)
                    
                    # Quick actions
                    st.markdown("---")
                    st.write("**Quick Actions:**")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🔄 Refresh List", key="refresh_processed_list", width='stretch'):
                            st.rerun()
                    
                    with col2:
                        if st.button("📁 View All Outputs", key="goto_outputs", width='stretch'):
                            st.session_state['current_page'] = 'View Outputs'
                            st.rerun()
                    
                    with col3:
                        # Delete failed episodes button
                        failed_count = sum(1 for ep in episodes if ep.get('stage') == 'failed')
                        if failed_count > 0:
                            if st.button(f"🗑️ Clean Failed ({failed_count})", key="clean_failed", type="secondary", width='stretch'):
                                st.session_state['show_bulk_delete'] = True
                    
                    # Bulk delete confirmation
                    if st.session_state.get('show_bulk_delete', False):
                        st.warning(f"⚠️ Delete all {failed_count} failed episodes?")
                        col_yes, col_no = st.columns(2)
                        
                        with col_yes:
                            if st.button("✅ Yes, Delete All Failed", key="confirm_bulk_delete", type="primary", width='stretch'):
                                with st.spinner("Deleting failed episodes..."):
                                    deleted_count = 0
                                    for ep in episodes:
                                        if ep.get('stage') == 'failed':
                                            try:
                                                response = api_client.delete_episode(ep['episode_id'], delete_files=True)
                                                if response.success:
                                                    deleted_count += 1
                                            except Exception as e:
                                                st.error(f"Failed to delete {ep['episode_id']}: {e}")
                                    
                                    st.success(f"✅ Deleted {deleted_count} failed episodes!")
                                    st.session_state['show_bulk_delete'] = False
                                    st.rerun()
                        
                        with col_no:
                            if st.button("❌ Cancel", key="cancel_bulk_delete", width='stretch'):
                                st.session_state['show_bulk_delete'] = False
                                st.rerun()
                else:
                    st.info("No processed videos found yet.")
            else:
                st.warning("Unable to load processed videos list.")
        except Exception as e:
            st.error(f"Error loading processed videos: {str(e)}")
    
    st.markdown("---")
    
    # Render folder input section
    folder_path, processing_options = interface.render_folder_input_section()
    
    # Render processing controls
    interface.render_processing_controls(folder_path, processing_options)
    
    # Render progress tracking
    interface.render_progress_tracking()
    
    # Render results
    interface.render_processing_results()