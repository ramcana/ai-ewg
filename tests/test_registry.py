"""Test registry database operations."""

import pytest
from pathlib import Path
from datetime import datetime
from src.ai_ewg.core.registry import Registry
from src.ai_ewg.core.models import EpisodeState, ArtifactKind


@pytest.fixture
def registry(tmp_path):
    """Create a test registry."""
    db_path = tmp_path / "test_registry.db"
    reg = Registry(db_path)
    reg.init_db()
    return reg


@pytest.fixture
def sample_video(tmp_path):
    """Create a sample video file."""
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"fake video content")
    return video_path


def test_registry_init(registry):
    """Test registry initialization."""
    stats = registry.get_stats()
    assert stats["episodes"] == 0
    assert stats["artifacts"] == 0


def test_register_episode(registry, sample_video):
    """Test episode registration."""
    episode = registry.register_episode(
        abs_path=sample_video,
        show="Test Show",
        show_slug="test-show",
        episode_id="test-episode-001",
        episode_title="Test Episode",
    )
    
    assert episode.episode_id == "test-episode-001"
    assert episode.show == "Test Show"
    assert episode.state == EpisodeState.NEW
    assert episode.sha256 is not None


def test_get_episode(registry, sample_video):
    """Test episode retrieval."""
    registry.register_episode(
        abs_path=sample_video,
        show="Test Show",
        show_slug="test-show",
        episode_id="test-episode-001",
    )
    
    episode = registry.get_episode("test-episode-001")
    assert episode is not None
    assert episode.episode_id == "test-episode-001"


def test_update_episode_state(registry, sample_video):
    """Test episode state updates."""
    registry.register_episode(
        abs_path=sample_video,
        show="Test Show",
        show_slug="test-show",
        episode_id="test-episode-001",
    )
    
    registry.update_episode_state("test-episode-001", EpisodeState.TRANSCRIBED)
    
    episode = registry.get_episode("test-episode-001")
    assert episode.state == EpisodeState.TRANSCRIBED


def test_register_artifact(registry, sample_video, tmp_path):
    """Test artifact registration."""
    registry.register_episode(
        abs_path=sample_video,
        show="Test Show",
        show_slug="test-show",
        episode_id="test-episode-001",
    )
    
    artifact_path = tmp_path / "transcript.txt"
    artifact_path.write_text("Test transcript")
    
    artifact = registry.register_artifact(
        episode_id="test-episode-001",
        kind=ArtifactKind.TRANSCRIPT_TXT,
        rel_path=artifact_path,
        model_version="test-model-v1",
    )
    
    assert artifact.kind == ArtifactKind.TRANSCRIPT_TXT
    assert artifact.model_version == "test-model-v1"


def test_get_or_create_person(registry):
    """Test person entity management."""
    person1 = registry.get_or_create_person(
        name="John Doe",
        norm_name="john doe",
        wikidata_id="Q12345",
        confidence=0.95,
    )
    
    assert person1.name == "John Doe"
    assert person1.wikidata_id == "Q12345"
    assert person1.mention_count == 1
    
    # Get same person again
    person2 = registry.get_or_create_person(
        name="John Doe",
        norm_name="john doe",
        wikidata_id="Q12345",
    )
    
    assert person1.id == person2.id
    assert person2.mention_count == 2


def test_entity_cache(registry):
    """Test entity caching."""
    # Cache an entity
    cache = registry.cache_entity(
        norm_name="john doe",
        wikidata_id="Q12345",
        wikipedia_url="https://en.wikipedia.org/wiki/John_Doe",
        metadata_json='{"occupation": "Actor"}',
        confidence=0.95,
    )
    
    assert cache.norm_name == "john doe"
    assert cache.hit_count == 0
    
    # Retrieve from cache
    cached = registry.get_cached_entity("john doe")
    assert cached is not None
    assert cached.wikidata_id == "Q12345"
    assert cached.hit_count == 1


def test_get_episodes_by_state(registry, sample_video):
    """Test filtering episodes by state."""
    # Register multiple episodes
    for i in range(3):
        registry.register_episode(
            abs_path=sample_video,
            show="Test Show",
            show_slug="test-show",
            episode_id=f"test-episode-{i:03d}",
        )
    
    # Update one to TRANSCRIBED
    registry.update_episode_state("test-episode-001", EpisodeState.TRANSCRIBED)
    
    new_episodes = registry.get_episodes_by_state(EpisodeState.NEW)
    transcribed_episodes = registry.get_episodes_by_state(EpisodeState.TRANSCRIBED)
    
    assert len(new_episodes) == 2
    assert len(transcribed_episodes) == 1


def test_registry_stats(registry, sample_video):
    """Test registry statistics."""
    # Register some data
    registry.register_episode(
        abs_path=sample_video,
        show="Test Show",
        show_slug="test-show",
        episode_id="test-episode-001",
    )
    
    registry.get_or_create_person(
        name="John Doe",
        norm_name="john doe",
    )
    
    stats = registry.get_stats()
    assert stats["episodes"] == 1
    assert stats["people"] == 1
    assert stats["state_new"] == 1
