"""
Diagnostic script to check clip discovery issues
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import DatabaseManager, create_database_manager
from src.core.config import DatabaseConfig
from src.core.models import EpisodeObject
from src.core.registry import EpisodeRegistry

def diagnose_episode(episode_id: str):
    """Diagnose clip discovery issues for an episode"""
    print(f"\n🔍 Diagnosing episode: {episode_id}")
    print("=" * 80)
    
    # Initialize database
    db_config = DatabaseConfig(database_path="data/pipeline.db")
    db_manager = create_database_manager(db_config)
    
    # Get episode from database
    registry = EpisodeRegistry(db_manager)
    episode = registry.get_episode(episode_id)
    
    if not episode:
        print(f"❌ Episode not found: {episode_id}")
        return
    
    print(f"\n📊 Episode Info:")
    print(f"   ID: {episode.episode_id}")
    print(f"   Title: {episode.title}")
    print(f"   Stage: {episode.processing_stage}")
    print(f"   Source: {episode.source_path}")
    
    # Check transcription
    print(f"\n📝 Transcription Check:")
    if not episode.transcription:
        print("   ❌ No transcription data")
        return
    
    transcription = episode.transcription
    print(f"   ✅ Transcription exists")
    print(f"   Text length: {len(transcription.text) if transcription.text else 0} chars")
    print(f"   Has segments: {bool(transcription.segments)}")
    print(f"   Segments count: {len(transcription.segments) if transcription.segments else 0}")
    print(f"   Has words: {bool(transcription.words)}")
    print(f"   Words count: {len(transcription.words) if transcription.words else 0}")
    
    # Check words structure
    if transcription.words:
        print(f"\n🔤 Words Sample (first 5):")
        for i, word in enumerate(transcription.words[:5]):
            print(f"   {i+1}. {word}")
            if isinstance(word, dict):
                print(f"      Keys: {word.keys()}")
                print(f"      Word: {word.get('word', 'N/A')}")
                print(f"      Start: {word.get('start', 'N/A')}")
                print(f"      End: {word.get('end', 'N/A')}")
    
    # Try sentence alignment
    print(f"\n🔗 Testing Sentence Alignment:")
    try:
        from src.core.clip_discovery import ClipDiscoveryEngine
        from src.core.clip_registry import ClipRegistry
        
        clip_registry = ClipRegistry(db_manager)
        discovery_engine = ClipDiscoveryEngine(clip_registry)
            
            # Test alignment
            from clip_generation.sentence_alignment import SentenceAlignmentEngine
            alignment_engine = SentenceAlignmentEngine()
            
            sentences = alignment_engine.align_sentences_from_words(transcription.words)
            print(f"   ✅ Aligned {len(sentences)} sentences")
            
            if sentences:
                print(f"\n📄 Sentences Sample (first 3):")
                for i, sent in enumerate(sentences[:3]):
                    print(f"   {i+1}. Text: {sent.text[:100]}...")
                    print(f"      Start: {sent.start_ms}ms, End: {sent.end_ms}ms")
                    print(f"      Duration: {(sent.end_ms - sent.start_ms)/1000:.2f}s")
                    print(f"      Has text: {bool(sent.text)}")
                    print(f"      Text type: {type(sent.text)}")
                    
                # Check for empty texts
                empty_texts = [i for i, s in enumerate(sentences) if not s.text or not s.text.strip()]
                if empty_texts:
                    print(f"\n   ⚠️  Found {len(empty_texts)} sentences with empty text!")
                    print(f"      Indices: {empty_texts[:10]}")
                else:
                    print(f"\n   ✅ All sentences have text content")
                
                # Try topic segmentation
                print(f"\n🎯 Testing Topic Segmentation:")
                try:
                    from clip_generation.topic_segmentation import TopicSegmentationEngine
                    topic_engine = TopicSegmentationEngine()
                    
                    print(f"   Model loaded: {topic_engine.embedding_model is not None}")
                    print(f"   Model name: {topic_engine.model_name}")
                    
                    # Try to create embeddings
                    print(f"   Attempting embedding generation...")
                    embeddings = topic_engine.create_embeddings(sentences, episode_id)
                    print(f"   ✅ Embeddings generated: shape {embeddings.shape}")
                    
                    # Try segmentation
                    print(f"   Attempting topic segmentation...")
                    segments = topic_engine.segment_by_topic(sentences, episode_id)
                    print(f"   ✅ Segmentation successful: {len(segments)} segments")
                    
                except Exception as e:
                    print(f"   ❌ Topic segmentation failed: {e}")
                    import traceback
                    print(f"\n   Traceback:")
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"   ❌ Sentence alignment failed: {e}")
            import traceback
            print(f"\n   Traceback:")
            traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_clip_discovery.py <episode_id>")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    diagnose_episode(episode_id)
