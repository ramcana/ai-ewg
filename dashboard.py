"""
GUI Control Panel - Streamlit Dashboard
Main entry point for the video processing workflow dashboard
"""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Import processing components
from components.processing import render_video_processing_page
from components.outputs import render_view_outputs_page
from components.clips import render_clip_management_page
from components.social_generator import render_social_package_generation_interface
from components.corrections import render_correction_management_page

# Page configuration
st.set_page_config(
    page_title="AI-EWG Control Panel",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_config() -> Dict[str, Any]:
    """Load authentication configuration from config/users.yaml"""
    config_path = Path("config/users.yaml")
    
    if not config_path.exists():
        # Create default config if it doesn't exist
        create_default_config(config_path)
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    return config

def add_dashboard_notification(message: str, type: str = "info"):
    """Add notification to dashboard notification system"""
    if 'dashboard_notifications' not in st.session_state:
        st.session_state['dashboard_notifications'] = []
    
    notification = {
        'message': message,
        'type': type,
        'timestamp': datetime.now(),
        'id': len(st.session_state['dashboard_notifications'])
    }
    
    st.session_state['dashboard_notifications'].append(notification)
    
    # Keep only last 10 notifications
    if len(st.session_state['dashboard_notifications']) > 10:
        st.session_state['dashboard_notifications'] = st.session_state['dashboard_notifications'][-10:]

def render_sidebar_system_status():
    """Render compact system status in sidebar"""
    from utils.api_client import create_api_client
    
    api_client = create_api_client()
    health_response = api_client.check_health()
    
    if health_response.success:
        st.markdown("""
        <div style="background-color: #e8f5e8; padding: 0.5rem; border-radius: 0.5rem; text-align: center;">
            <small><strong>🟢 API Connected</strong></small>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #fde8e8; padding: 0.5rem; border-radius: 0.5rem; text-align: center;">
            <small><strong>🔴 API Offline</strong></small>
        </div>
        """, unsafe_allow_html=True)

def render_dashboard_notifications():
    """Render dashboard notifications at the top of main content"""
    notifications = st.session_state.get('dashboard_notifications', [])
    
    if not notifications:
        return
    
    # Show only recent notifications (last 3)
    recent_notifications = notifications[-3:]
    
    for notification in recent_notifications:
        # Check if notification is recent (last 30 seconds)
        time_diff = (datetime.now() - notification['timestamp']).total_seconds()
        if time_diff > 30:
            continue
        
        if notification['type'] == 'success':
            st.success(notification['message'])
        elif notification['type'] == 'error':
            st.error(notification['message'])
        elif notification['type'] == 'warning':
            st.warning(notification['message'])
        else:
            st.info(notification['message'])

def set_selected_episode(episode_id: str, episode_data: Dict[str, Any] = None):
    """Set selected episode for cross-page state management"""
    st.session_state['selected_episode_id'] = episode_id
    st.session_state['selected_episode_data'] = episode_data or {}
    add_dashboard_notification(f"Selected episode: {episode_id}", "info")

def get_selected_episode() -> Tuple[Optional[str], Dict[str, Any]]:
    """Get currently selected episode"""
    episode_id = st.session_state.get('selected_episode_id')
    episode_data = st.session_state.get('selected_episode_data', {})
    return episode_id, episode_data

def clear_all_caches():
    """Clear all cached data for performance optimization"""
    cache_keys = ['api_cache', 'cache_timestamps', 'file_cache', 'file_cache_timestamps']
    
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    add_dashboard_notification("All caches cleared", "info")

def deep_cleanup_all_state():
    """Perform comprehensive cleanup of all processing state and caches"""
    try:
        # Clear all standard caches
        cache_keys_to_clear = [
            'processing_active', 'processing_episodes', 'processing_progress', 'processing_results',
            'episodes_data', 'last_refresh', 'file_cache', 'file_cache_timestamps',
            'api_cache', 'cache_timestamps', 'copied_files_for_cleanup', 'dashboard_notifications'
        ]
        
        for key in cache_keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # Clear episode-specific caches (clips, metadata, etc.)
        keys_to_remove = []
        for key in st.session_state.keys():
            if any(pattern in key for pattern in ['clip_metadata_', 'discovered_clips_', 'episode_']):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
        
        add_dashboard_notification("Deep cleanup completed - all state and caches cleared", "success")
        
    except Exception as e:
        add_dashboard_notification(f"Error during deep cleanup: {str(e)}", "error")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for performance monitoring"""
    stats = {
        'api_cache_size': len(st.session_state.get('api_cache', {})),
        'file_cache_size': len(st.session_state.get('file_cache', {})),
        'total_cached_items': 0,
        'cache_hit_ratio': 0.0
    }
    
    stats['total_cached_items'] = stats['api_cache_size'] + stats['file_cache_size']
    
    return stats

def create_default_config(config_path: Path):
    """Create default users.yaml configuration file"""
    config_path.parent.mkdir(exist_ok=True)
    
    # Generate hashed passwords for default users
    passwords = ['admin123', 'editor123']
    hashed_passwords = stauth.Hasher(passwords).generate()
    
    default_config = {
        'credentials': {
            'usernames': {
                'admin': {
                    'email': 'admin@example.com',
                    'name': 'Administrator',
                    'password': hashed_passwords[0]
                },
                'editor': {
                    'email': 'editor@example.com', 
                    'name': 'Content Editor',
                    'password': hashed_passwords[1]
                }
            }
        },
        'cookie': {
            'expiry_days': 30,
            'key': 'random_signature_key_12345',
            'name': 'auth_cookie'
        },
        'preauthorized': {
            'emails': []
        }
    }
    
    with open(config_path, 'w') as file:
        yaml.dump(default_config, file, default_flow_style=False)

def initialize_session_state():
    """Initialize session state variables for unified dashboard"""
    # Authentication state
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = None
    if 'name' not in st.session_state:
        st.session_state['name'] = None
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    
    # Navigation state
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'Dashboard'
    
    # Cross-page data sharing state
    if 'selected_episode_id' not in st.session_state:
        st.session_state['selected_episode_id'] = None
    if 'selected_episode_data' not in st.session_state:
        st.session_state['selected_episode_data'] = None
    if 'last_processing_folder' not in st.session_state:
        st.session_state['last_processing_folder'] = None
    if 'dashboard_notifications' not in st.session_state:
        st.session_state['dashboard_notifications'] = []
    
    # UI state management
    if 'sidebar_expanded' not in st.session_state:
        st.session_state['sidebar_expanded'] = True
    if 'theme_mode' not in st.session_state:
        st.session_state['theme_mode'] = 'light'
    
    # Performance optimization state
    if 'api_cache' not in st.session_state:
        st.session_state['api_cache'] = {}
    if 'cache_timestamps' not in st.session_state:
        st.session_state['cache_timestamps'] = {}

def render_sidebar():
    """Render unified sidebar navigation with cross-page state management"""
    with st.sidebar:
        # Header with consistent styling
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0; border-bottom: 2px solid #f0f2f6; margin-bottom: 1rem;">
            <h2 style="color: #1f77b4; margin: 0;">🎬 AI-EWG Control Panel</h2>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state['authentication_status']:
            # User welcome with styling
            st.markdown(f"""
            <div style="background: linear-gradient(90deg, #f0f2f6, #ffffff); 
                       padding: 0.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <p style="margin: 0; text-align: center;">
                    <strong>Welcome, {st.session_state['name']}!</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Navigation menu with icons and descriptions
            pages = [
                ("Dashboard", "📊", "System overview and quick actions"),
                ("Process Videos", "🎬", "Upload and process video content"), 
                ("View Outputs", "📁", "Browse generated files and content"),
                ("Clip Management", "✂️", "Configure and manage video clips"),
                ("Corrections", "📝", "Manage transcript corrections"),
                ("Social Media Packages", "📱", "Create social media content"),
                ("System Status", "🔧", "Monitor system health and performance")
            ]
            
            current_page = st.session_state.get('current_page', 'Dashboard')
            
            st.markdown("### Navigation")
            
            for page_name, icon, description in pages:
                # Create styled navigation buttons
                is_current = (page_name == current_page)
                button_style = """
                    background-color: #1f77b4; 
                    color: white; 
                    border: none; 
                    border-radius: 0.5rem;
                    font-weight: bold;
                """ if is_current else """
                    background-color: transparent; 
                    color: #1f77b4; 
                    border: 1px solid #1f77b4; 
                    border-radius: 0.5rem;
                """
                
                if st.button(
                    f"{icon} {page_name}",
                    key=f"nav_{page_name}",
                    width="stretch",
                    help=description
                ):
                    if page_name != current_page:
                        st.session_state['current_page'] = page_name
                        # Add navigation notification
                        add_dashboard_notification(f"Navigated to {page_name}", "info")
                        st.rerun()
            
            # Cross-page state display
            st.markdown("---")
            st.markdown("### Current Context")
            
            # Show selected episode if any
            if st.session_state.get('selected_episode_id'):
                episode_id = st.session_state['selected_episode_id']
                episode_data = st.session_state.get('selected_episode_data', {})
                title = episode_data.get('title', 'Unknown Title')
                
                theme_mode = st.session_state.get('theme_mode', 'light')
                bg_color = "#2a2d3a" if theme_mode == 'dark' else "#e8f4fd"
                text_color = "#fafafa" if theme_mode == 'dark' else "#333"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; padding: 0.5rem; border-radius: 0.5rem; margin-bottom: 0.5rem; color: {text_color};">
                    <small><strong>Selected Episode:</strong></small><br>
                    <small>{title}</small><br>
                    <small style="color: #888;">ID: {episode_id[:12]}...</small>
                </div>
                """, unsafe_allow_html=True)
                
                # Quick actions for selected episode
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📁 View", key="quick_view", width="stretch"):
                        st.session_state['current_page'] = 'View Outputs'
                        st.rerun()
                with col2:
                    if st.button("✂️ Clips", key="quick_clips", width="stretch"):
                        st.session_state['current_page'] = 'Clip Management'
                        st.rerun()
            
            # Show last processing folder if any
            if st.session_state.get('last_processing_folder'):
                folder = st.session_state['last_processing_folder']
                theme_mode = st.session_state.get('theme_mode', 'light')
                bg_color = "#2a3d2a" if theme_mode == 'dark' else "#f0f8e8"
                text_color = "#fafafa" if theme_mode == 'dark' else "#333"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; padding: 0.5rem; border-radius: 0.5rem; margin-bottom: 0.5rem; color: {text_color};">
                    <small><strong>Last Processed:</strong></small><br>
                    <small>{folder}</small>
                </div>
                """, unsafe_allow_html=True)
            
            # System status indicator
            st.markdown("---")
            render_sidebar_system_status()
            
            # Settings and logout
            st.markdown("---")
            st.markdown("### Settings")
            
            # Theme toggle with live switching
            current_theme = st.session_state.get('theme_mode', 'light')
            theme_mode = st.selectbox(
                "Theme:",
                ["Light", "Dark"],
                index=0 if current_theme == 'light' else 1,
                key="theme_selector"
            )
            
            new_theme = theme_mode.lower()
            if new_theme != current_theme:
                st.session_state['theme_mode'] = new_theme
                add_dashboard_notification(f"Switched to {theme_mode} theme", "info")
                st.rerun()
            
            # Deep cleanup button
            if st.button("🧹 Deep Clean", width="stretch", help="Clear all caches and processing state"):
                deep_cleanup_all_state()
                st.rerun()
            
            # Logout button with styling
            if st.button("🚪 Logout", width="stretch", type="secondary"):
                # Clear all session state
                for key in list(st.session_state.keys()):
                    if key not in ['authentication_status', 'name', 'username']:
                        del st.session_state[key]
                
                st.session_state['authentication_status'] = None
                st.session_state['name'] = None
                st.session_state['username'] = None
                st.session_state['current_page'] = 'Dashboard'
                st.rerun()

def render_dashboard_page():
    """Render the main dashboard overview page with system monitoring"""
    from utils.api_client import create_api_client
    from datetime import datetime, timedelta
    
    # Page header with consistent styling
    st.markdown("""
    <div class="dashboard-header">
        <h1 style="margin: 0;">📊 Dashboard Overview</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">
            Unified control panel for video processing and social media automation
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create API client for status checks
    api_client = create_api_client()
    
    # System status indicators with real API connectivity
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Check API connectivity
        health_response = api_client.check_health()
        if health_response.success:
            st.metric("API Status", "🟢 Connected", "localhost:8000")
            api_connected = True
        else:
            st.metric("API Status", "🔴 Disconnected", f"Error: {health_response.error}")
            api_connected = False
    
    with col2:
        # Get episode processing statistics
        if api_connected:
            episodes_response = api_client.list_episodes(limit=100)
            if episodes_response.success and episodes_response.data:
                # Handle different response formats
                if isinstance(episodes_response.data, dict):
                    episodes = episodes_response.data.get('episodes', [])
                elif isinstance(episodes_response.data, list):
                    episodes = episodes_response.data
                else:
                    episodes = []
                    
                # Count episodes processed in the last week
                week_ago = datetime.now() - timedelta(days=7)
                recent_episodes = [ep for ep in episodes if ep.get('updated_at')]
                episodes_this_week = len(recent_episodes)  # Simplified for now
                st.metric("Episodes Processed", str(episodes_this_week), "This week")
            else:
                st.metric("Episodes Processed", "N/A", "API Error")
        else:
            st.metric("Episodes Processed", "N/A", "API Offline")
    
    with col3:
        # Get clip generation statistics
        if api_connected:
            # This would need a dedicated endpoint, for now show placeholder
            st.metric("Clips Generated", "N/A", "Feature pending")
        else:
            st.metric("Clips Generated", "N/A", "API Offline")
    
    with col4:
        # Calculate success rate from recent episodes
        if api_connected and episodes_response.success:
            # Handle different response formats
            if isinstance(episodes_response.data, dict):
                episodes = episodes_response.data.get('episodes', [])
            elif isinstance(episodes_response.data, list):
                episodes = episodes_response.data
            else:
                episodes = []
                
            if episodes:
                successful = len([ep for ep in episodes if ep.get('stage') == 'rendered'])
                total = len(episodes)
                success_rate = (successful / total * 100) if total > 0 else 100
                st.metric("Success Rate", f"{success_rate:.1f}%", f"Last {total} episodes")
            else:
                st.metric("Success Rate", "100%", "No data")
        else:
            st.metric("Success Rate", "N/A", "API Offline")
    
    st.markdown("---")
    
    # Recent Activity Display
    st.subheader("📈 Recent Activity")
    
    # Debug information (can be enabled for troubleshooting)
    if st.checkbox("🐛 Debug API Response", value=False, help="Show API response details for troubleshooting"):
        st.write("**API Response Debug:**")
        st.write(f"- API Connected: {api_connected}")
        st.write(f"- Response Success: {episodes_response.success}")
        st.write(f"- Response Data Type: {type(episodes_response.data)}")
        st.write(f"- Response Data: {episodes_response.data}")
        st.write(f"- Response Error: {episodes_response.error}")
    
    if api_connected:
        # Display recent episodes in a table
        if episodes_response.success:
            if episodes_response.data:
                # Handle different response formats
                if isinstance(episodes_response.data, dict):
                    episodes = episodes_response.data.get('episodes', [])
                elif isinstance(episodes_response.data, list):
                    episodes = episodes_response.data
                else:
                    episodes = []
                
                if episodes:
                    # Prepare data for display
                    recent_data = []
                    for episode in episodes[:10]:  # Show last 10 episodes
                        recent_data.append({
                            'Episode ID': episode.get('episode_id', 'N/A'),
                            'Title': episode.get('title', 'Unknown'),
                            'Show': episode.get('show_name', 'Unknown'),
                            'Stage': episode.get('stage', 'unknown'),
                            'Status': '✅ Complete' if episode.get('stage') == 'rendered' else '🔄 Processing',
                            'Updated': episode.get('updated_at', 'N/A')
                        })
                    
                    if recent_data:
                        df = pd.DataFrame(recent_data)
                        st.dataframe(df, width="stretch", hide_index=True)
                    else:
                        st.info("No recent episodes found.")
                else:
                    st.info("📭 No episodes discovered yet. Use 'Process Videos' to get started.")
            else:
                st.info("📭 No episode data available. The API returned an empty response.")
        else:
            error_msg = episodes_response.error or "API request failed with no error message"
            st.error(f"Failed to load recent activity: {error_msg}")
            
            # Show more helpful information
            st.info("💡 **Troubleshooting:**")
            st.write("- Check if the AI-EWG pipeline API is running on localhost:8000")
            st.write("- Verify the API server is accessible")
            st.write("- Try refreshing the page")
    else:
        st.error("Cannot load recent activity - API connection failed")
        st.write("**Troubleshooting:**")
        st.write("1. Ensure the AI-EWG pipeline API is running on localhost:8000")
        st.write("2. Check if the API server is accessible")
        st.write("3. Verify network connectivity")
    
    st.markdown("---")
    
    # Welcome message and quick actions
    st.subheader("Welcome to the AI-EWG Control Panel")
    st.write("""
    This dashboard provides a unified interface for managing your complete video-to-social workflow.
    Use the sidebar to navigate between different functions:
    
    - **Process Videos**: Upload and process video folders
    - **View Outputs**: Browse generated content and files
    - **Clip Management**: Configure and monitor clip generation
    - **System Status**: Monitor system health and performance
    """)
    
    # Quick action buttons with enhanced functionality
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.subheader("🚀 Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🎥 Process New Videos", width="stretch", type="primary"):
            st.session_state['current_page'] = 'Process Videos'
            add_dashboard_notification("Navigated to video processing", "info")
            st.rerun()
    
    with col2:
        if st.button("📁 View Latest Outputs", width="stretch"):
            st.session_state['current_page'] = 'View Outputs'
            add_dashboard_notification("Navigated to output browser", "info")
            st.rerun()
    
    with col3:
        if st.button("✂️ Manage Clips", width="stretch"):
            st.session_state['current_page'] = 'Clip Management'
            add_dashboard_notification("Navigated to clip management", "info")
            st.rerun()
    
    with col4:
        if st.button("📱 Social Media", width="stretch"):
            st.session_state['current_page'] = 'Social Media Packages'
            add_dashboard_notification("Navigated to social media packages", "info")
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_system_status_page():
    """Render detailed system status and monitoring page"""
    from utils.api_client import create_api_client
    import time
    
    st.header("🔧 System Status & Monitoring")
    
    # Create API client
    api_client = create_api_client()
    
    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("System Health Dashboard")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
        if auto_refresh:
            time.sleep(30)
            st.rerun()
    
    # API Connectivity Section
    st.subheader("🌐 API Connectivity")
    
    # Test API endpoints
    endpoints_to_test = [
        ("/health", "Health Check"),
        ("/status", "System Status"),
        ("/episodes", "Episodes API"),
    ]
    
    connectivity_data = []
    for endpoint, description in endpoints_to_test:
        start_time = time.time()
        if endpoint == "/health":
            response = api_client.check_health()
        elif endpoint == "/status":
            response = api_client.get_system_status()
        elif endpoint == "/episodes":
            response = api_client.list_episodes(limit=1)
        
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        connectivity_data.append({
            'Endpoint': endpoint,
            'Description': description,
            'Status': '✅ OK' if response.success else '❌ Failed',
            'Response Time (ms)': f"{response_time:.1f}",
            'Error': response.error if not response.success else 'None'
        })
    
    df_connectivity = pd.DataFrame(connectivity_data)
    st.dataframe(df_connectivity, width="stretch", hide_index=True)
    
    st.markdown("---")
    
    # Processing Statistics Section
    st.subheader("📊 Processing Statistics")
    
    # Get episodes for statistics
    episodes_response = api_client.list_episodes(limit=100)
    
    if episodes_response.success and episodes_response.data:
        episodes = episodes_response.data if isinstance(episodes_response.data, list) else episodes_response.data.get('episodes', [])
        
        # Statistics calculations
        total_episodes = len(episodes)
        completed_episodes = len([ep for ep in episodes if ep.get('stage') == 'rendered'])
        failed_episodes = len([ep for ep in episodes if ep.get('stage') == 'failed'])
        processing_episodes = total_episodes - completed_episodes - failed_episodes
        
        # Display statistics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Episodes", total_episodes)
        with col2:
            st.metric("Completed", completed_episodes, f"{(completed_episodes/total_episodes*100):.1f}%" if total_episodes > 0 else "0%")
        with col3:
            st.metric("Processing", processing_episodes)
        with col4:
            st.metric("Failed", failed_episodes, f"{(failed_episodes/total_episodes*100):.1f}%" if total_episodes > 0 else "0%")
        
        # Processing stages breakdown
        st.subheader("📈 Processing Stages Breakdown")
        
        stage_counts = {}
        for episode in episodes:
            stage = episode.get('stage', 'unknown')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if stage_counts:
            stage_data = []
            for stage, count in stage_counts.items():
                percentage = (count / total_episodes * 100) if total_episodes > 0 else 0
                stage_data.append({
                    'Stage': stage.title(),
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%"
                })
            
            df_stages = pd.DataFrame(stage_data)
            st.dataframe(df_stages, width="stretch", hide_index=True)
        
    else:
        st.error(f"Failed to load processing statistics: {episodes_response.error}")
    
    st.markdown("---")
    
    # System Resources Section
    st.subheader("💻 System Resources")
    
    # Get system status from API if available
    system_response = api_client.get_system_status()
    
    if system_response.success and system_response.data:
        system_data = system_response.data
        
        # Display system metrics if available
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cpu_usage = system_data.get('cpu_usage', 'N/A')
            st.metric("CPU Usage", f"{cpu_usage}%" if isinstance(cpu_usage, (int, float)) else cpu_usage)
        
        with col2:
            memory_usage = system_data.get('memory_usage', 'N/A')
            st.metric("Memory Usage", f"{memory_usage}%" if isinstance(memory_usage, (int, float)) else memory_usage)
        
        with col3:
            disk_usage = system_data.get('disk_usage', 'N/A')
            st.metric("Disk Usage", f"{disk_usage}%" if isinstance(disk_usage, (int, float)) else disk_usage)
        
        # Additional system info
        if 'uptime' in system_data:
            st.write(f"**System Uptime:** {system_data['uptime']}")
        if 'version' in system_data:
            st.write(f"**API Version:** {system_data['version']}")
    else:
        st.info("System resource information not available from API")
    
    st.markdown("---")
    
    # Error Logs Section
    st.subheader("🚨 Recent Errors & Issues")
    
    # Show failed episodes with error details
    if episodes_response.success and episodes_response.data:
        episodes = episodes_response.data if isinstance(episodes_response.data, list) else episodes_response.data.get('episodes', [])
        failed_episodes = [ep for ep in episodes if ep.get('stage') == 'failed' or ep.get('error')]
        
        if failed_episodes:
            error_data = []
            for episode in failed_episodes[:10]:  # Show last 10 errors
                error_data.append({
                    'Episode ID': episode.get('episode_id', 'N/A'),
                    'Title': episode.get('title', 'Unknown'),
                    'Stage': episode.get('stage', 'unknown'),
                    'Error': episode.get('error', 'No error message'),
                    'Updated': episode.get('updated_at', 'N/A')
                })
            
            df_errors = pd.DataFrame(error_data)
            st.dataframe(df_errors, width="stretch", hide_index=True)
        else:
            st.success("No recent errors found! 🎉")
    else:
        st.error("Cannot load error information - API connection failed")
    
    # Performance and Cache Management Section
    st.markdown("---")
    st.subheader("⚡ Performance & Cache Management")
    
    cache_stats = get_cache_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("API Cache Items", cache_stats['api_cache_size'])
    
    with col2:
        st.metric("File Cache Items", cache_stats['file_cache_size'])
    
    with col3:
        st.metric("Total Cached", cache_stats['total_cached_items'])
    
    # Cache management controls
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear All Caches", width="stretch"):
            clear_all_caches()
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh Status", width="stretch"):
            # Clear status caches for fresh data
            if 'api_cache' in st.session_state:
                api_cache = st.session_state['api_cache']
                cache_timestamps = st.session_state.get('cache_timestamps', {})
                
                # Remove status-related cache entries
                keys_to_remove = []
                for key in api_cache.keys():
                    if 'status' in key or 'health' in key:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    if key in api_cache:
                        del api_cache[key]
                    if key in cache_timestamps:
                        del cache_timestamps[key]
            
            st.rerun()

def apply_dashboard_styling():
    """Apply consistent styling across all dashboard pages with theme support"""
    theme_mode = st.session_state.get('theme_mode', 'light')
    
    if theme_mode == 'dark':
        # Dark theme styles
        st.markdown("""
        <style>
        /* Dark theme main container */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: #0e1117;
            color: #fafafa;
        }
        
        /* Dark theme header */
        .dashboard-header {
            background: linear-gradient(90deg, #1f77b4, #2ca02c);
            color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        /* Dark theme cards */
        .dashboard-card {
            background: #262730;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 1rem;
            border-left: 4px solid #1f77b4;
            color: #fafafa;
        }
        
        /* Dark theme status indicators */
        .status-success { color: #4caf50; font-weight: bold; }
        .status-warning { color: #ff9800; font-weight: bold; }
        .status-error { color: #f44336; font-weight: bold; }
        .status-info { color: #2196f3; font-weight: bold; }
        
        /* Dark theme buttons */
        .stButton > button {
            border-radius: 0.5rem;
            border: 1px solid #1f77b4;
            transition: all 0.3s ease;
            background-color: #262730;
            color: #fafafa;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4);
            background-color: #1f77b4;
        }
        
        /* Dark theme metrics */
        .metric-container {
            background: #262730;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            border: 1px solid #404040;
            color: #fafafa;
        }
        
        /* Dark theme progress bars */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #1f77b4, #2ca02c);
        }
        
        /* Dark theme sidebar */
        .css-1d391kg {
            background-color: #262730;
        }
        
        /* Dark theme tables */
        .dataframe {
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            background-color: #262730;
            color: #fafafa;
        }
        
        /* Dark theme text inputs */
        .stTextInput > div > div > input {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #404040;
        }
        
        /* Dark theme selectbox */
        .stSelectbox > div > div > select {
            background-color: #262730;
            color: #fafafa;
            border: 1px solid #404040;
        }
        
        /* Override Streamlit's default dark theme colors */
        .stApp {
            background-color: #0e1117;
        }
        </style>
        """, unsafe_allow_html=True)
    else:
        # Light theme styles (default)
        st.markdown("""
        <style>
        /* Light theme main container */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: #ffffff;
            color: #262730;
        }
        
        /* Light theme header */
        .dashboard-header {
            background: linear-gradient(90deg, #1f77b4, #2ca02c);
            color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        /* Light theme cards */
        .dashboard-card {
            background: white;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
            border-left: 4px solid #1f77b4;
            color: #262730;
        }
        
        /* Light theme status indicators */
        .status-success { color: #28a745; font-weight: bold; }
        .status-warning { color: #ffc107; font-weight: bold; }
        .status-error { color: #dc3545; font-weight: bold; }
        .status-info { color: #17a2b8; font-weight: bold; }
        
        /* Light theme buttons */
        .stButton > button {
            border-radius: 0.5rem;
            border: 1px solid #1f77b4;
            transition: all 0.3s ease;
            background-color: white;
            color: #262730;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background-color: #1f77b4;
            color: white;
        }
        
        /* Light theme metrics */
        .metric-container {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            border: 1px solid #e9ecef;
            color: #262730;
        }
        
        /* Light theme progress bars */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #1f77b4, #2ca02c);
        }
        
        /* Light theme sidebar */
        .css-1d391kg {
            background-color: #f8f9fa;
        }
        
        /* Light theme tables */
        .dataframe {
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            background-color: white;
            color: #262730;
        }
        </style>
        """, unsafe_allow_html=True)

def render_dashboard_footer():
    """Render consistent footer across all pages"""
    st.markdown("---")
    
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        st.markdown("""
        <div style="text-align: left; color: #666; font-size: 0.8rem;">
            <strong>AI-EWG Control Panel</strong><br>
            Video Processing & Social Media Automation
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # System status indicator
        from utils.api_client import create_api_client
        api_client = create_api_client()
        health_response = api_client.check_health()
        
        status_color = "#28a745" if health_response.success else "#dc3545"
        status_text = "Online" if health_response.success else "Offline"
        
        st.markdown(f"""
        <div style="text-align: center; color: {status_color}; font-size: 0.8rem;">
            <strong>API Status: {status_text}</strong>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Current session info
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_name = st.session_state.get('name', 'Unknown')
        
        st.markdown(f"""
        <div style="text-align: right; color: #666; font-size: 0.8rem;">
            <strong>User:</strong> {user_name}<br>
            <strong>Time:</strong> {current_time}
        </div>
        """, unsafe_allow_html=True)

def render_placeholder_page(page_name: str):
    """Render placeholder content for pages not yet implemented"""
    st.header(f"🚧 {page_name}")
    st.info(f"The {page_name} page is under development and will be implemented in upcoming tasks.")
    
    # Show what will be available
    if page_name == "View Outputs":
        st.write("**Coming soon:**")
        st.write("- Episode results table with filtering")
        st.write("- File organization display")
        st.write("- Content previews (HTML, social packages)")
        st.write("- Direct download links for clips")
    
    elif page_name == "Clip Management":
        st.write("**Coming soon:**")
        st.write("- Clip parameter configuration")
        st.write("- Duration, score threshold, aspect ratio controls")
        st.write("- Clip discovery preview")
        st.write("- Bulk rendering controls")

def main():
    """Main application entry point"""
    # Initialize session state
    initialize_session_state()
    
    # Load authentication configuration
    config = load_config()
    
    # Create authenticator for version 0.4.2 (without preauthorized parameter)
    try:
        authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days']
        )
    except Exception as e:
        st.error(f"Failed to initialize authenticator: {str(e)}")
        st.error("Please ensure streamlit-authenticator is properly installed")
        st.stop()
    
    # Render login form if not authenticated
    if not st.session_state['authentication_status']:
        st.title("🎬 AI-EWG Control Panel")
        st.subheader("Please log in to access the dashboard")
        
        # Handle streamlit-authenticator v0.4.2
        try:
            # For version 0.4.2, login returns Optional[Tuple[name, authentication_status, username]]
            result = authenticator.login(location='main')
            
            if result is not None:
                name, authentication_status, username = result
                
                # Update session state with authentication results
                if authentication_status is not None:
                    st.session_state['authentication_status'] = authentication_status
                if name is not None:
                    st.session_state['name'] = name
                if username is not None:
                    st.session_state['username'] = username
                
        except (TypeError, ValueError) as e:
            st.error(f"Authentication library error: {str(e)}")
            st.warning("The streamlit-authenticator version may be incompatible. Using fallback authentication method.")
            
            # Fallback simple authentication
            with st.form("login_form"):
                username_input = st.text_input("Username")
                password_input = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Login")
                
                if login_button:
                    # Simple credential check
                    valid_users = {
                        'admin': 'admin123',
                        'editor': 'editor123'
                    }
                    
                    if username_input in valid_users and valid_users[username_input] == password_input:
                        st.session_state['authentication_status'] = True
                        st.session_state['name'] = username_input.title()
                        st.session_state['username'] = username_input
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
            
            # Show default credentials for demo
            with st.expander("Demo Credentials"):
                st.write("**Admin User:**")
                st.code("Username: admin\nPassword: admin123")
                st.write("**Editor User:**")
                st.code("Username: editor\nPassword: editor123")
            
            return
        
        # Check authentication status
        if st.session_state.get('authentication_status') == False:
            st.error('Username/password is incorrect')
        elif st.session_state.get('authentication_status') is None:
            st.warning('Please enter your username and password')
            
            # Show default credentials for demo
            with st.expander("Demo Credentials"):
                st.write("**Admin User:**")
                st.code("Username: admin\nPassword: admin123")
                st.write("**Editor User:**")
                st.code("Username: editor\nPassword: editor123")
        
        return
    
    # User is authenticated - render main application
    render_sidebar()
    
    # Apply consistent styling
    apply_dashboard_styling()
    
    # Render dashboard notifications
    render_dashboard_notifications()
    
    # Render current page content with consistent layout
    current_page = st.session_state.get('current_page', 'Dashboard')
    
    # Page content container with consistent styling
    with st.container():
        if current_page == 'Dashboard':
            render_dashboard_page()
        elif current_page == 'Process Videos':
            render_video_processing_page()
        elif current_page == 'View Outputs':
            render_view_outputs_page()
        elif current_page == 'Clip Management':
            render_clip_management_page()
        elif current_page == 'Corrections':
            render_correction_management_page()
        elif current_page == 'Social Media Packages':
            render_social_package_generation_interface()
        elif current_page == 'System Status':
            render_system_status_page()
        else:
            render_placeholder_page(current_page)
    
    # Footer with consistent styling
    render_dashboard_footer()

if __name__ == "__main__":
    main()