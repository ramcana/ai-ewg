"""
Show Configuration Management Component

Allows users to:
1. View existing show mappings
2. Add new shows before processing
3. Edit show mappings
4. Configure show metadata
"""

import streamlit as st
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


SHOW_CONFIG_FILE = Path("config/show_mappings.json")


def load_show_mappings() -> Dict[str, str]:
    """Load show name mappings from config file"""
    if SHOW_CONFIG_FILE.exists():
        try:
            with open(SHOW_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading show mappings: {e}")
            return get_default_mappings()
    else:
        # Create default mappings file
        default_mappings = get_default_mappings()
        save_show_mappings(default_mappings)
        return default_mappings


def get_default_mappings() -> Dict[str, str]:
    """Get default show name mappings"""
    return {
        # The News Forum shows
        "the news forum": "TheNewsForum",
        "news forum": "TheNewsForum",
        "newsroom": "TheNewsForum",
        "the newsroom": "TheNewsForum",
        
        # Individual shows
        "forum daily news": "ForumDailyNews",
        "daily news": "ForumDailyNews",
        
        "forum daily week": "ForumDailyWeek",
        "daily week": "ForumDailyWeek",
        "fdw": "ForumDailyWeek",
        
        "boom and bust": "BoomAndBust",
        "boom & bust": "BoomAndBust",
        
        "community profile": "CommunityProfile",
        
        "economic pulse": "EconomicPulse",
        
        "freedom forum": "FreedomForum",
        
        "canadian justice": "CanadianJustice",
        
        "counterpoint": "Counterpoint",
        
        "canadian innovators": "CanadianInnovators",
        "innovators": "CanadianInnovators",
        
        "the ledrew show": "TheLeDrewShow",
        "ledrew show": "TheLeDrewShow",
        "ledrew": "TheLeDrewShow",
        
        "my generation": "MyGeneration",
        
        "forum focus": "ForumFocus",
        
        "empowered": "Empowered",
    }


def save_show_mappings(mappings: Dict[str, str]) -> bool:
    """Save show name mappings to config file"""
    try:
        # Ensure config directory exists
        SHOW_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(SHOW_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving show mappings: {e}")
        return False


def slugify_show_name(name: str) -> str:
    """Convert show name to folder-safe slug"""
    # Remove special characters, convert to PascalCase
    words = re.sub(r'[^\w\s-]', '', name).split()
    return ''.join(word.capitalize() for word in words)


def render_show_configuration_page():
    """Main page for show configuration"""
    st.header("📺 Show Configuration")
    
    st.write("""
    Configure show name mappings to ensure videos are properly categorized.
    This helps the AI correctly identify and organize your content.
    """)
    
    # Load current mappings
    mappings = load_show_mappings()
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["📋 Current Shows", "➕ Add New Show", "⚙️ Bulk Edit"])
    
    with tab1:
        render_current_shows(mappings)
    
    with tab2:
        render_add_new_show(mappings)
    
    with tab3:
        render_bulk_edit(mappings)


def render_current_shows(mappings: Dict[str, str]):
    """Display current show mappings"""
    st.subheader("Current Show Mappings")
    
    if not mappings:
        st.info("No show mappings configured yet. Add your first show!")
        return
    
    # Group by target folder
    grouped = {}
    for ai_name, folder_name in mappings.items():
        if folder_name not in grouped:
            grouped[folder_name] = []
        grouped[folder_name].append(ai_name)
    
    st.write(f"**Total Shows:** {len(grouped)}")
    st.write(f"**Total Mappings:** {len(mappings)}")
    
    st.info("💡 **Output Path Structure:** `data/outputs/{ShowFolder}/{Year}/{EpisodeID}/`")
    
    # Display each show
    for folder_name, ai_names in sorted(grouped.items()):
        with st.expander(f"📁 {folder_name} ({len(ai_names)} mappings)", expanded=False):
            # Show example output path
            st.markdown(f"**Example Output Path:**")
            st.code(f"data/outputs/{folder_name}/2025/{folder_name}_ep001_2025-01-15/", language="text")
            
            st.markdown("**AI-Extracted Names that map to this folder:**")
            
            for ai_name in sorted(ai_names):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.write(f"• `{ai_name}` → `{folder_name}`")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{ai_name}", help="Delete this mapping"):
                        if ai_name in mappings:
                            del mappings[ai_name]
                            if save_show_mappings(mappings):
                                st.success(f"Deleted mapping: {ai_name}")
                                st.rerun()


def render_add_new_show(mappings: Dict[str, str]):
    """Add a new show mapping"""
    st.subheader("Add New Show")
    
    st.write("""
    Add a new show by defining:
    1. **AI Name**: How the AI might extract the show name (e.g., "Forum Daily News")
    2. **Folder Name**: The folder name to use for organization (e.g., "ForumDailyNews")
    """)
    
    with st.form("add_show_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            ai_name = st.text_input(
                "AI-Extracted Name",
                placeholder="e.g., Forum Daily News",
                help="How the AI might identify this show in transcripts"
            ).lower().strip()
        
        with col2:
            # Auto-suggest folder name
            suggested_folder = slugify_show_name(ai_name) if ai_name else ""
            folder_name = st.text_input(
                "Folder Name",
                value=suggested_folder,
                placeholder="e.g., ForumDailyNews",
                help="Folder name for file organization (PascalCase recommended)"
            ).strip()
        
        # Show preview of output path
        if folder_name:
            st.markdown("**📁 Files will be saved to:**")
            from datetime import datetime
            year = datetime.now().year
            st.code(f"data/outputs/{folder_name}/{year}/{folder_name}_ep001_{datetime.now().strftime('%Y-%m-%d')}/", language="text")
        
        # Additional aliases
        st.write("**Additional Aliases** (optional)")
        aliases_text = st.text_area(
            "One per line",
            placeholder="daily news\nforum news\nthe daily forum",
            help="Other ways the AI might identify this show"
        )
        
        submitted = st.form_submit_button("➕ Add Show", type="primary", width='stretch')
        
        if submitted:
            if not ai_name or not folder_name:
                st.error("Both AI Name and Folder Name are required!")
            else:
                # Add main mapping
                mappings[ai_name] = folder_name
                
                # Add aliases
                if aliases_text:
                    for alias in aliases_text.split('\n'):
                        alias = alias.lower().strip()
                        if alias:
                            mappings[alias] = folder_name
                
                if save_show_mappings(mappings):
                    st.success(f"✅ Added show: {folder_name}")
                    # Calculate count outside f-string to avoid backslash issue
                    alias_list = aliases_text.split('\n') if aliases_text else []
                    total_mappings = len([ai_name] + alias_list)
                    st.info(f"Mappings added: {total_mappings}")
                    st.rerun()


def render_bulk_edit(mappings: Dict[str, str]):
    """Bulk edit show mappings"""
    st.subheader("Bulk Edit Mappings")
    
    st.write("""
    Edit all mappings as JSON. Be careful - invalid JSON will not be saved.
    """)
    
    # Show current mappings as JSON
    current_json = json.dumps(mappings, indent=2)
    
    edited_json = st.text_area(
        "Edit Mappings (JSON)",
        value=current_json,
        height=400,
        help="Edit the JSON directly. Format: {\"ai_name\": \"FolderName\"}"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Changes", type="primary", width='stretch'):
            try:
                new_mappings = json.loads(edited_json)
                
                # Validate it's a dict
                if not isinstance(new_mappings, dict):
                    st.error("Invalid format: Must be a JSON object")
                else:
                    if save_show_mappings(new_mappings):
                        st.success("✅ Mappings saved successfully!")
                        st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
    
    with col2:
        if st.button("🔄 Reset to Defaults", width='stretch'):
            if st.session_state.get('confirm_reset'):
                default_mappings = get_default_mappings()
                if save_show_mappings(default_mappings):
                    st.success("✅ Reset to default mappings!")
                    st.session_state['confirm_reset'] = False
                    st.rerun()
            else:
                st.session_state['confirm_reset'] = True
                st.warning("Click again to confirm reset")
    
    with col3:
        if st.button("📥 Export", width='stretch'):
            st.download_button(
                label="Download JSON",
                data=current_json,
                file_name=f"show_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


# Import for slugify
import re


if __name__ == "__main__":
    render_show_configuration_page()
