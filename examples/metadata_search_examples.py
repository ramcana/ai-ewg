"""
Examples of using the MetadataManager for searching and retrieving episodes

Run this after processing some episodes to see the metadata manager in action.
"""

from pathlib import Path
from src.core.database import DatabaseManager, create_database_manager
from src.core.metadata_manager import MetadataManager
from src.core.config import DatabaseConfig


def example_basic_search():
    """Example: Basic episode search"""
    print("=" * 60)
    print("Example 1: Basic Episode Search")
    print("=" * 60)
    
    # Initialize
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    # Search by show name
    print("\n1. Search episodes from 'Newsroom':")
    results = metadata_mgr.search_episodes(show_name="Newsroom", limit=5)
    for ep in results:
        print(f"  - {ep['title']} ({ep['date']})")
        print(f"    Guests: {', '.join(ep['guest_names'][:3])}")
        print(f"    Topics: {', '.join(ep['topics'][:3])}")
    
    # Search by date range
    print("\n2. Search episodes from October 2024:")
    results = metadata_mgr.search_episodes(
        date_from="2024-10-01",
        date_to="2024-10-31"
    )
    print(f"  Found {len(results)} episodes in October 2024")
    
    # Search by guest
    print("\n3. Search episodes with specific guest:")
    results = metadata_mgr.search_episodes(guest_name="John")
    for ep in results:
        print(f"  - {ep['title']} ({ep['show_name']})")
        print(f"    Guests: {', '.join(ep['guest_names'])}")


def example_full_text_search():
    """Example: Full-text search across transcripts"""
    print("\n" + "=" * 60)
    print("Example 2: Full-Text Search")
    print("=" * 60)
    
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    # Search for keywords
    queries = [
        "climate change",
        "economics policy",
        "technology innovation"
    ]
    
    for query in queries:
        print(f"\nSearching for: '{query}'")
        results = metadata_mgr.full_text_search(query, limit=3)
        print(f"  Found {len(results)} matches:")
        for ep in results:
            print(f"  - {ep['title']} ({ep['show_name']}, {ep['date']})")


def example_load_full_json():
    """Example: Load complete JSON for specific episode"""
    print("\n" + "=" * 60)
    print("Example 3: Load Full Episode JSON")
    print("=" * 60)
    
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    # First, find an episode
    results = metadata_mgr.search_episodes(limit=1)
    if results:
        episode_id = results[0]['episode_id']
        print(f"\nLoading full JSON for: {episode_id}")
        
        # Load complete JSON
        full_data = metadata_mgr.load_episode_json(episode_id)
        
        print(f"  Title: {full_data['metadata']['title']}")
        print(f"  Show: {full_data['metadata']['show_name']}")
        print(f"  Duration: {full_data['media']['duration_seconds']}s")
        
        if 'transcription' in full_data:
            transcript_length = len(full_data['transcription'].get('text', ''))
            print(f"  Transcript length: {transcript_length} characters")
        
        if 'enrichment' in full_data:
            guests = full_data['enrichment'].get('proficiency_scores', {}).get('scored_people', [])
            print(f"  Number of guests: {len(guests)}")


def example_aggregations():
    """Example: Get shows, guests, and topics"""
    print("\n" + "=" * 60)
    print("Example 4: Aggregations (Shows, Guests, Topics)")
    print("=" * 60)
    
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    # Get all shows
    print("\n1. Shows in library:")
    shows = metadata_mgr.get_shows()
    for show in shows:
        duration_hours = show['total_duration_seconds'] / 3600
        print(f"  - {show['show_name']}: {show['episode_count']} episodes "
              f"({duration_hours:.1f} hours total)")
    
    # Get frequent guests
    print("\n2. Top guests (2+ appearances):")
    guests = metadata_mgr.get_guests(min_appearances=2)
    for guest in guests[:10]:
        print(f"  - {guest['name']}: {guest['appearances']} appearances")
    
    # Get popular topics
    print("\n3. Popular topics (2+ occurrences):")
    topics = metadata_mgr.get_topics(min_occurrences=2)
    for topic in topics[:10]:
        print(f"  - {topic['topic']}: {topic['occurrences']} episodes")


def example_statistics():
    """Example: Get overall statistics"""
    print("\n" + "=" * 60)
    print("Example 5: Library Statistics")
    print("=" * 60)
    
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    stats = metadata_mgr.get_statistics()
    
    print(f"\nTotal Episodes: {stats['total_episodes']}")
    print(f"Total Shows: {stats['total_shows']}")
    print(f"Total Duration: {stats['total_duration_seconds'] / 3600:.1f} hours")
    print(f"Average Duration: {stats['average_duration_seconds'] / 60:.1f} minutes")
    print(f"Episodes with Transcript: {stats['episodes_with_transcript']}")
    print(f"Episodes with Enrichment: {stats['episodes_with_enrichment']}")
    print(f"Episodes with Editorial: {stats['episodes_with_editorial']}")
    print(f"Date Range: {stats['earliest_date']} to {stats['latest_date']}")


def example_advanced_filters():
    """Example: Advanced filtering"""
    print("\n" + "=" * 60)
    print("Example 6: Advanced Filtering")
    print("=" * 60)
    
    db_config = DatabaseConfig(path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    metadata_mgr = MetadataManager(
        db_manager.get_connection(),
        Path("data/meta")
    )
    
    # Find long episodes with enrichment
    print("\n1. Episodes longer than 45 minutes with AI enrichment:")
    results = metadata_mgr.search_episodes(
        min_duration=45 * 60,  # 45 minutes in seconds
        has_enrichment=True,
        limit=5
    )
    for ep in results:
        duration_min = ep['duration_seconds'] / 60
        print(f"  - {ep['title']} ({duration_min:.0f} min)")
    
    # Find recent episodes with specific topic
    print("\n2. Recent episodes about 'Economics':")
    results = metadata_mgr.search_episodes(
        topic="Economics",
        date_from="2024-01-01",
        limit=5
    )
    for ep in results:
        print(f"  - {ep['title']} ({ep['date']})")
    
    # Find episodes by show and guest
    print("\n3. Newsroom episodes with specific guest:")
    results = metadata_mgr.search_episodes(
        show_name="Newsroom",
        guest_name="Smith",
        limit=5
    )
    for ep in results:
        print(f"  - {ep['title']}")
        print(f"    Guests: {', '.join(ep['guest_names'])}")


if __name__ == "__main__":
    """Run all examples"""
    try:
        example_basic_search()
        example_full_text_search()
        example_load_full_json()
        example_aggregations()
        example_statistics()
        example_advanced_filters()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Make sure you have:")
        print("  1. Run database migrations (ai-ewg db migrate)")
        print("  2. Processed some episodes (ai-ewg discover && ai-ewg transcribe)")
