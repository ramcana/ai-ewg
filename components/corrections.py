"""
Self-Learning Correction System UI Component
Manages transcript corrections with intelligent learning
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

def render_correction_management_page():
    """Render the main correction management interface"""
    st.header("📝 Self-Learning Correction System")
    
    st.markdown("""
    <div style="background-color: #e8f4fd; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <p style="margin: 0;">
            <strong>🎯 Smart Corrections:</strong> This system learns from your corrections and automatically 
            applies them to future transcripts. Supports names, brands, technical terms, and show-specific vocabulary.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs for different functions
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Manage Corrections",
        "➕ Add New Correction",
        "📊 Statistics",
        "⚙️ Settings"
    ])
    
    with tab1:
        render_corrections_list()
    
    with tab2:
        render_add_correction_form()
    
    with tab3:
        render_correction_statistics()
    
    with tab4:
        render_correction_settings()


def render_corrections_list():
    """Display and manage existing corrections"""
    st.subheader("Existing Corrections")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_type = st.selectbox(
            "Type:",
            ["All", "Name", "Brand", "Technical Term", "Phrase", "Location"],
            key="filter_type"
        )
    
    with col2:
        filter_show = st.selectbox(
            "Show:",
            ["All Shows", "TheNewsForum", "BoomAndBust", "EconomicPulse"],
            key="filter_show"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by:",
            ["Most Used", "Recently Added", "Alphabetical", "Confidence"],
            key="sort_by"
        )
    
    with col4:
        search_term = st.text_input("🔍 Search:", placeholder="Search corrections...", key="search_corrections")
    
    # Get corrections from database/file
    corrections = load_corrections()
    
    # Apply filters
    if filter_type != "All":
        corrections = [c for c in corrections if c.get('type') == filter_type.lower().replace(' ', '_')]
    
    if filter_show != "All Shows":
        corrections = [c for c in corrections if c.get('show_name') == filter_show or not c.get('show_name')]
    
    if search_term:
        search_lower = search_term.lower()
        corrections = [c for c in corrections if 
                      search_lower in c.get('original', '').lower() or 
                      search_lower in c.get('corrected', '').lower()]
    
    # Sort corrections
    if sort_by == "Most Used":
        corrections.sort(key=lambda x: x.get('usage_count', 0), reverse=True)
    elif sort_by == "Recently Added":
        corrections.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    elif sort_by == "Alphabetical":
        corrections.sort(key=lambda x: x.get('original', '').lower())
    elif sort_by == "Confidence":
        corrections.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    
    # Display corrections
    if not corrections:
        st.info("No corrections found. Add your first correction in the 'Add New Correction' tab!")
    else:
        st.write(f"**Found {len(corrections)} correction(s)**")
        
        # Display as cards with actions
        for idx, correction in enumerate(corrections):
            render_correction_card(correction, idx)


def render_correction_card(correction: Dict[str, Any], idx: int):
    """Render a single correction as a card"""
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            # Main correction info
            original = correction.get('original', '')
            corrected = correction.get('corrected', '')
            correction_type = correction.get('type', 'unknown').replace('_', ' ').title()
            
            st.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 0.75rem; border-radius: 0.5rem; border-left: 4px solid #1f77b4;">
                <div style="margin-bottom: 0.5rem;">
                    <span style="background-color: #e3f2fd; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.85rem;">
                        {correction_type}
                    </span>
                </div>
                <div style="font-size: 1.1rem;">
                    <span style="color: #d32f2f; text-decoration: line-through;">{original}</span>
                    <span style="margin: 0 0.5rem;">→</span>
                    <span style="color: #388e3c; font-weight: bold;">{corrected}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Context and stats
            show_name = correction.get('show_name', 'All Shows')
            usage_count = correction.get('usage_count', 0)
            confidence = correction.get('confidence', 1.0)
            
            st.markdown(f"""
            <div style="padding: 0.5rem;">
                <small><strong>Show:</strong> {show_name}</small><br>
                <small><strong>Used:</strong> {usage_count} times</small><br>
                <small><strong>Confidence:</strong> {confidence:.0%}</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Actions
            if st.button("✏️ Edit", key=f"edit_{idx}", help="Edit correction"):
                st.session_state[f'editing_correction_{idx}'] = True
                st.rerun()
            
            if st.button("🗑️ Delete", key=f"delete_{idx}", help="Delete correction"):
                if delete_correction(correction.get('id')):
                    st.success("Correction deleted!")
                    st.rerun()
        
        # Edit form (if editing)
        if st.session_state.get(f'editing_correction_{idx}'):
            with st.expander("Edit Correction", expanded=True):
                render_edit_correction_form(correction, idx)
        
        st.markdown("---")


def render_edit_correction_form(correction: Dict[str, Any], idx: int):
    """Render form to edit an existing correction"""
    with st.form(key=f"edit_form_{idx}"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_original = st.text_input("Original Text:", value=correction.get('original', ''))
            new_corrected = st.text_input("Corrected Text:", value=correction.get('corrected', ''))
        
        with col2:
            new_type = st.selectbox(
                "Type:",
                ["name", "brand", "technical_term", "phrase", "location"],
                index=["name", "brand", "technical_term", "phrase", "location"].index(correction.get('type', 'name'))
            )
            new_show = st.text_input("Show Name (optional):", value=correction.get('show_name', ''))
        
        new_notes = st.text_area("Notes:", value=correction.get('notes', ''))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save Changes", type="primary"):
                updated_correction = {
                    **correction,
                    'original': new_original,
                    'corrected': new_corrected,
                    'type': new_type,
                    'show_name': new_show if new_show else None,
                    'notes': new_notes
                }
                if update_correction(updated_correction):
                    st.success("Correction updated!")
                    del st.session_state[f'editing_correction_{idx}']
                    st.rerun()
        
        with col2:
            if st.form_submit_button("❌ Cancel"):
                del st.session_state[f'editing_correction_{idx}']
                st.rerun()


def render_add_correction_form():
    """Render form to add a new correction"""
    st.subheader("Add New Correction")
    
    st.markdown("""
    <div style="background-color: #fff3e0; padding: 0.75rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <small><strong>💡 Tip:</strong> The system will automatically apply this correction to future transcripts. 
        You can make it show-specific or apply it globally.</small>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form(key="add_correction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Correction Details")
            original_text = st.text_input(
                "Original Text (as it appears in transcript):",
                placeholder="e.g., Teresa Skubik",
                help="The incorrect text that needs to be corrected"
            )
            
            corrected_text = st.text_input(
                "Corrected Text (what it should be):",
                placeholder="e.g., Theresa Skubic",
                help="The correct version of the text"
            )
            
            correction_type = st.selectbox(
                "Correction Type:",
                ["name", "brand", "technical_term", "phrase", "location"],
                format_func=lambda x: x.replace('_', ' ').title(),
                help="Type of correction for better context matching"
            )
        
        with col2:
            st.markdown("### Context & Settings")
            show_name = st.selectbox(
                "Apply to Show:",
                ["All Shows", "TheNewsForum", "BoomAndBust", "EconomicPulse", "CommunityProfile", "FreedomForum"],
                help="Limit correction to specific show or apply globally"
            )
            
            case_sensitive = st.checkbox(
                "Case Sensitive",
                value=False,
                help="Match exact case only"
            )
            
            whole_word_only = st.checkbox(
                "Whole Word Only",
                value=True,
                help="Only match complete words, not partial matches"
            )
            
            confidence = st.slider(
                "Initial Confidence:",
                min_value=0.5,
                max_value=1.0,
                value=1.0,
                step=0.05,
                help="How confident are you in this correction?"
            )
        
        notes = st.text_area(
            "Notes (optional):",
            placeholder="Add any context or notes about this correction...",
            help="Internal notes for reference"
        )
        
        # Preview
        if original_text and corrected_text:
            st.markdown("### Preview")
            st.markdown(f"""
            <div style="background-color: #f5f5f5; padding: 1rem; border-radius: 0.5rem;">
                <div style="font-size: 1.1rem;">
                    <span style="color: #d32f2f; text-decoration: line-through;">{original_text}</span>
                    <span style="margin: 0 0.5rem;">→</span>
                    <span style="color: #388e3c; font-weight: bold;">{corrected_text}</span>
                </div>
                <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;">
                    Type: {correction_type.replace('_', ' ').title()} | 
                    Show: {show_name} | 
                    Confidence: {confidence:.0%}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button("➕ Add Correction", type="primary")
        
        if submitted:
            if not original_text or not corrected_text:
                st.error("Please fill in both original and corrected text!")
            else:
                new_correction = {
                    'original': original_text,
                    'corrected': corrected_text,
                    'type': correction_type,
                    'show_name': show_name if show_name != "All Shows" else None,
                    'case_sensitive': case_sensitive,
                    'whole_word_only': whole_word_only,
                    'confidence': confidence,
                    'notes': notes,
                    'created_at': datetime.now().isoformat(),
                    'usage_count': 0,
                    'success_count': 0,
                    'rejection_count': 0
                }
                
                if save_correction(new_correction):
                    st.success(f"✅ Correction added: {original_text} → {corrected_text}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Failed to save correction. It may already exist.")


def render_correction_statistics():
    """Display statistics about corrections"""
    st.subheader("Correction Statistics")
    
    corrections = load_corrections()
    
    if not corrections:
        st.info("No corrections yet. Add some corrections to see statistics!")
        return
    
    # Overall stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Corrections", len(corrections))
    
    with col2:
        total_usage = sum(c.get('usage_count', 0) for c in corrections)
        st.metric("Total Applications", total_usage)
    
    with col3:
        avg_confidence = sum(c.get('confidence', 0) for c in corrections) / len(corrections) if corrections else 0
        st.metric("Avg Confidence", f"{avg_confidence:.0%}")
    
    with col4:
        active_corrections = len([c for c in corrections if c.get('usage_count', 0) > 0])
        st.metric("Active Corrections", active_corrections)
    
    st.markdown("---")
    
    # Breakdown by type
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### By Type")
        type_counts = {}
        for c in corrections:
            type_name = c.get('type', 'unknown').replace('_', ' ').title()
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        if type_counts:
            df_types = pd.DataFrame([
                {'Type': k, 'Count': v, 'Percentage': f"{v/len(corrections)*100:.1f}%"}
                for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(df_types, hide_index=True, width='stretch')
    
    with col2:
        st.markdown("### By Show")
        show_counts = {}
        for c in corrections:
            show = c.get('show_name') or 'All Shows'
            show_counts[show] = show_counts.get(show, 0) + 1
        
        if show_counts:
            df_shows = pd.DataFrame([
                {'Show': k, 'Count': v, 'Percentage': f"{v/len(corrections)*100:.1f}%"}
                for k, v in sorted(show_counts.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(df_shows, hide_index=True, width='stretch')
    
    st.markdown("---")
    
    # Most used corrections
    st.markdown("### 🔥 Most Used Corrections")
    most_used = sorted(corrections, key=lambda x: x.get('usage_count', 0), reverse=True)[:10]
    
    if most_used and most_used[0].get('usage_count', 0) > 0:
        for idx, correction in enumerate(most_used, 1):
            if correction.get('usage_count', 0) == 0:
                break
            
            col1, col2, col3 = st.columns([1, 5, 2])
            with col1:
                st.markdown(f"**#{idx}**")
            with col2:
                st.markdown(f"`{correction.get('original')}` → **{correction.get('corrected')}**")
            with col3:
                st.markdown(f"Used: **{correction.get('usage_count')}** times")
    else:
        st.info("No corrections have been applied yet.")


def render_correction_settings():
    """Render correction system settings"""
    st.subheader("Correction System Settings")
    
    st.markdown("### Global Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_apply = st.checkbox(
            "Auto-apply corrections during enrichment",
            value=True,
            help="Automatically apply learned corrections to new transcripts"
        )
        
        fuzzy_matching = st.checkbox(
            "Enable fuzzy matching",
            value=True,
            help="Match similar variations of corrections (e.g., 'AI ML' matches 'AI/ML')"
        )
        
        fuzzy_threshold = st.slider(
            "Fuzzy match threshold:",
            min_value=0.7,
            max_value=1.0,
            value=0.85,
            step=0.05,
            help="How similar text must be to match (higher = more strict)",
            disabled=not fuzzy_matching
        )
    
    with col2:
        confidence_threshold = st.slider(
            "Minimum confidence to apply:",
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help="Only apply corrections with confidence above this threshold"
        )
        
        learn_from_usage = st.checkbox(
            "Learn from usage patterns",
            value=True,
            help="Increase confidence of corrections that are frequently used"
        )
        
        suggest_corrections = st.checkbox(
            "Suggest new corrections",
            value=False,
            help="AI suggests potential corrections based on patterns"
        )
    
    st.markdown("---")
    
    st.markdown("### Import/Export")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📥 Import Corrections", width='stretch'):
            st.info("Import feature coming soon!")
    
    with col2:
        if st.button("📤 Export Corrections", width='stretch'):
            corrections = load_corrections()
            if corrections:
                export_data = json.dumps(corrections, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=export_data,
                    file_name=f"corrections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                st.warning("No corrections to export")
    
    with col3:
        if st.button("🗑️ Clear All Corrections", width='stretch'):
            st.warning("This will delete ALL corrections. Are you sure?")
            if st.button("⚠️ Yes, Delete All", type="secondary"):
                clear_all_corrections()
                st.success("All corrections cleared!")
                st.rerun()
    
    st.markdown("---")
    
    # Save settings
    if st.button("💾 Save Settings", type="primary"):
        settings = {
            'auto_apply': auto_apply,
            'fuzzy_matching': fuzzy_matching,
            'fuzzy_threshold': fuzzy_threshold,
            'confidence_threshold': confidence_threshold,
            'learn_from_usage': learn_from_usage,
            'suggest_corrections': suggest_corrections
        }
        save_correction_settings(settings)
        st.success("Settings saved!")


# Helper functions for data management

def load_corrections() -> List[Dict[str, Any]]:
    """Load corrections from file (temporary until database is ready)"""
    corrections_file = Path("data/corrections.json")
    
    if not corrections_file.exists():
        return []
    
    try:
        with open(corrections_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading corrections: {e}")
        return []


def save_correction(correction: Dict[str, Any]) -> bool:
    """Save a new correction"""
    corrections = load_corrections()
    
    # Check for duplicates
    for existing in corrections:
        if (existing.get('original') == correction['original'] and 
            existing.get('show_name') == correction.get('show_name')):
            return False
    
    # Add ID
    correction['id'] = len(corrections) + 1
    corrections.append(correction)
    
    # Save to file
    corrections_file = Path("data/corrections.json")
    corrections_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(corrections_file, 'w', encoding='utf-8') as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving correction: {e}")
        return False


def update_correction(correction: Dict[str, Any]) -> bool:
    """Update an existing correction"""
    corrections = load_corrections()
    
    for idx, existing in enumerate(corrections):
        if existing.get('id') == correction.get('id'):
            corrections[idx] = correction
            break
    
    corrections_file = Path("data/corrections.json")
    try:
        with open(corrections_file, 'w', encoding='utf-8') as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error updating correction: {e}")
        return False


def delete_correction(correction_id: int) -> bool:
    """Delete a correction"""
    corrections = load_corrections()
    corrections = [c for c in corrections if c.get('id') != correction_id]
    
    corrections_file = Path("data/corrections.json")
    try:
        with open(corrections_file, 'w', encoding='utf-8') as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error deleting correction: {e}")
        return False


def clear_all_corrections():
    """Clear all corrections"""
    corrections_file = Path("data/corrections.json")
    if corrections_file.exists():
        corrections_file.unlink()


def save_correction_settings(settings: Dict[str, Any]):
    """Save correction system settings"""
    settings_file = Path("data/correction_settings.json")
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        st.error(f"Error saving settings: {e}")
