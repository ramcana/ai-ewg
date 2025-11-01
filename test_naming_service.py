"""
Test script for naming service

Demonstrates:
1. Episode ID generation
2. Folder path creation
3. Show name mapping
4. Different naming scenarios
"""

from datetime import datetime
from src.core.naming_service import get_naming_service, NamingConfig

def test_naming_service():
    """Test the naming service with various scenarios"""
    
    print("=" * 70)
    print("  NAMING SERVICE TEST")
    print("=" * 70)
    print()
    
    # Get naming service
    naming = get_naming_service()
    
    # Test 1: Full metadata available
    print("📋 Test 1: Full Metadata (AI-extracted)")
    print("-" * 70)
    
    test_cases = [
        ("Forum Daily News", "140", datetime(2024, 10, 27)),
        ("The News Forum", "141", datetime(2024, 10, 28)),
        ("Boom and Bust", "25", datetime(2024, 11, 15)),
        ("Canadian Justice", "S01E05", datetime(2024, 12, 1)),
        ("The LeDrew Show", "99", datetime(2025, 1, 10)),
    ]
    
    for show_name, ep_num, date in test_cases:
        episode_id = naming.generate_episode_id(
            show_name=show_name,
            episode_number=ep_num,
            date=date
        )
        
        folder_path = naming.get_episode_folder_path(
            episode_id=episode_id,
            show_name=show_name,
            date=date
        )
        
        print(f"Show: {show_name:25} Ep: {ep_num:6}")
        print(f"  → Episode ID:  {episode_id}")
        print(f"  → Folder Path: {folder_path}")
        print()
    
    # Test 2: Fallback naming (no show name)
    print("\n📋 Test 2: Fallback Naming (No AI Data)")
    print("-" * 70)
    
    episode_id = naming.generate_episode_id(
        source_filename="newsroom_recording_oct27.mp4",
        date=datetime(2024, 10, 27, 14, 30, 0)
    )
    
    folder_path = naming.get_episode_folder_path(
        episode_id=episode_id,
        date=datetime(2024, 10, 27)
    )
    
    print(f"Source File: newsroom_recording_oct27.mp4")
    print(f"  → Episode ID:  {episode_id}")
    print(f"  → Folder Path: {folder_path}")
    print()
    
    # Test 3: Show name mapping
    print("\n📋 Test 3: Show Name Mapping")
    print("-" * 70)
    
    show_variations = [
        "The News Forum",
        "news forum",
        "NEWSROOM",
        "Forum Daily News",
        "Boom & Bust",
        "Canadian Innovators",
        "Unknown Show Name"
    ]
    
    for show_name in show_variations:
        folder_name = naming.map_show_name(show_name)
        print(f"{show_name:30} → {folder_name}")
    
    # Test 4: List all configured shows
    print("\n📋 Test 4: Configured Show Folders")
    print("-" * 70)
    
    shows = naming.get_show_list()
    print(f"Total shows configured: {len(shows)}")
    print()
    for i, show in enumerate(shows, 1):
        print(f"  {i:2}. {show}")
    
    # Test 5: Parse episode ID
    print("\n\n📋 Test 5: Parse Episode ID")
    print("-" * 70)
    
    episode_ids = [
        "ForumDailyNews_ep140_2024-10-27",
        "BoomAndBust_ep025_2024-11-15",
        "newsroom-recording-oct27_20241027_143000"
    ]
    
    for episode_id in episode_ids:
        parsed = naming.parse_episode_id(episode_id)
        print(f"Episode ID: {episode_id}")
        print(f"  → Show Folder:    {parsed['show_folder']}")
        print(f"  → Episode Number: {parsed['episode_number']}")
        print(f"  → Date:           {parsed['date']}")
        print()
    
    # Test 6: Custom configuration
    print("\n📋 Test 6: Custom Configuration")
    print("-" * 70)
    
    custom_config = NamingConfig(
        folder_structure="{show_folder}",  # Flat structure
        episode_template="{show_folder}_{episode_number}",  # Compact naming
        date_format="%Y%m%d"
    )
    
    custom_naming = get_naming_service(custom_config)
    
    episode_id = custom_naming.generate_episode_id(
        show_name="Forum Daily News",
        episode_number="140",
        date=datetime(2024, 10, 27)
    )
    
    folder_path = custom_naming.get_episode_folder_path(
        episode_id=episode_id,
        show_name="Forum Daily News",
        date=datetime(2024, 10, 27)
    )
    
    print(f"Custom Config:")
    print(f"  → Episode ID:  {episode_id}")
    print(f"  → Folder Path: {folder_path}")
    
    print("\n" + "=" * 70)
    print("  ✅ ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_naming_service()
