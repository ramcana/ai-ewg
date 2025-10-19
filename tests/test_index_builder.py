"""
Tests for the Index Builder

Tests index generation, cross-reference creation, search optimization,
and validation functionality for navigation and search features.
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime
from pathlib import Path

from src.core.index_builder import (
    IndexBuilder,
    GlobalIndexManager,
    IndexValidator,
    ShowIndex,
    HostIndex,
    GlobalIndex,
    IndexBuildResult
)
from src.core.config import PipelineConfig
from src.core.models import (
    EpisodeObject,
    EpisodeMetadata,
    TranscriptionResult,
    EnrichmentResult,
    EditorialContent,
    SourceInfo,
    MediaInfo,
    ProcessingStage
)


@pytest.fixture
def config():
    """Create test configuration"""
    from src.core.config import SourceConfig, StagingConfig, DiscoveryConfig, ModelConfig, ThresholdConfig, DatabaseConfig, LoggingConfig, ProcessingConfig
    return PipelineConfig(
        sources=[],
        staging=StagingConfig(),
        discovery=DiscoveryConfig(),
        models=ModelConfig(),
        thresholds=ThresholdConfig(),
        database=DatabaseConfig(),
        logging=LoggingConfig(),
        processing=ProcessingConfig()
    )


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_episodes():
    """Create sample episodes for testing"""
    episodes = []
    
    # Episode 1: Tech Talk
    metadata1 = EpisodeMetadata(
        show_name="Tech Talk",
        show_slug="tech-talk",
        season=1,
        episode=1,
        date="2024-01-15",
        topic="Artificial Intelligence",
        topic_slug="artificial-intelligence",
        title="The Future of AI"
    )
    
    transcription1 = TranscriptionResult(
        text="Welcome to Tech Talk. Today we discuss artificial intelligence with Dr. Jane Smith.",
        vtt_content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nWelcome to Tech Talk",
        confidence=0.95
    )
    
    enrichment1 = EnrichmentResult(
        proficiency_scores={
            'scored_people': [
                {
                    'name': 'Dr. Jane Smith',
                    'job_title': 'AI Research Director',
                    'affiliation': 'Tech University',
                    'credibilityBadge': 'Verified Expert',
                    'proficiencyScore': 0.92,
                    'reasoning': 'Leading AI researcher with 15+ years experience'
                }
            ]
        }
    )
    
    editorial1 = EditorialContent(
        key_takeaway="AI will transform industries in the next decade",
        summary="Dr. Jane Smith discusses the future of artificial intelligence and its impact on various industries.",
        topic_tags=["Artificial Intelligence", "Technology", "Future Trends", "Research"]
    )
    
    episode1 = EpisodeObject(
        episode_id="tech-talk-s1e1-2024-01-15-artificial-intelligence",
        content_hash="hash1",
        source=SourceInfo(
            path="/videos/tech-talk-ep1.mp4",
            file_size=1000000,
            last_modified=datetime(2024, 1, 15)
        ),
        media=MediaInfo(duration_seconds=3600),
        metadata=metadata1,
        processing_stage=ProcessingStage.RENDERED,
        transcription=transcription1,
        enrichment=enrichment1,
        editorial=editorial1
    )
    episodes.append(episode1)
    
    # Episode 2: Tech Talk with different guest
    metadata2 = EpisodeMetadata(
        show_name="Tech Talk",
        show_slug="tech-talk",
        season=1,
        episode=2,
        date="2024-01-22",
        topic="Machine Learning",
        topic_slug="machine-learning",
        title="ML in Practice"
    )
    
    enrichment2 = EnrichmentResult(
        proficiency_scores={
            'scored_people': [
                {
                    'name': 'Prof. Bob Johnson',
                    'job_title': 'ML Engineer',
                    'affiliation': 'Data Corp',
                    'credibilityBadge': 'Identified Contributor',
                    'proficiencyScore': 0.85,
                    'reasoning': 'Experienced ML practitioner'
                },
                {
                    'name': 'Dr. Jane Smith',  # Add Dr. Jane Smith to second episode too
                    'job_title': 'AI Research Director',
                    'affiliation': 'Tech University',
                    'credibilityBadge': 'Verified Expert',
                    'proficiencyScore': 0.90,
                    'reasoning': 'Leading AI researcher with 15+ years experience'
                }
            ]
        }
    )
    
    editorial2 = EditorialContent(
        key_takeaway="Machine learning requires careful data preparation",
        summary="Prof. Bob Johnson shares practical insights on implementing machine learning solutions.",
        topic_tags=["Machine Learning", "Data Science", "Technology", "Implementation"]
    )
    
    episode2 = EpisodeObject(
        episode_id="tech-talk-s1e2-2024-01-22-machine-learning",
        content_hash="hash2",
        source=SourceInfo(
            path="/videos/tech-talk-ep2.mp4",
            file_size=1200000,
            last_modified=datetime(2024, 1, 22)
        ),
        media=MediaInfo(duration_seconds=3300),
        metadata=metadata2,
        processing_stage=ProcessingStage.RENDERED,
        transcription=TranscriptionResult(
            text="Today on Tech Talk we explore machine learning with Prof. Bob Johnson.",
            vtt_content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nToday on Tech Talk",
            confidence=0.93
        ),
        enrichment=enrichment2,
        editorial=editorial2
    )
    episodes.append(episode2)
    
    # Episode 3: Different show
    metadata3 = EpisodeMetadata(
        show_name="Business Insights",
        show_slug="business-insights",
        season=2,
        episode=1,
        date="2024-01-20",
        topic="Startup Funding",
        topic_slug="startup-funding",
        title="Raising Capital in 2024"
    )
    
    enrichment3 = EnrichmentResult(
        proficiency_scores={
            'scored_people': [
                {
                    'name': 'Dr. Jane Smith',  # Same guest as episode 1
                    'job_title': 'Venture Partner',
                    'affiliation': 'Innovation Fund',
                    'credibilityBadge': 'Verified Expert',
                    'proficiencyScore': 0.88,
                    'reasoning': 'Experienced investor and advisor'
                }
            ]
        }
    )
    
    editorial3 = EditorialContent(
        key_takeaway="Startup funding landscape has evolved significantly",
        summary="Dr. Jane Smith discusses current trends in startup funding and venture capital.",
        topic_tags=["Startup Funding", "Venture Capital", "Business", "Investment"]
    )
    
    episode3 = EpisodeObject(
        episode_id="business-insights-s2e1-2024-01-20-startup-funding",
        content_hash="hash3",
        source=SourceInfo(
            path="/videos/business-insights-ep1.mp4",
            file_size=900000,
            last_modified=datetime(2024, 1, 20)
        ),
        media=MediaInfo(duration_seconds=2700),
        metadata=metadata3,
        processing_stage=ProcessingStage.RENDERED,
        transcription=TranscriptionResult(
            text="Welcome to Business Insights. Today we discuss startup funding with Dr. Jane Smith.",
            vtt_content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nWelcome to Business Insights",
            confidence=0.91
        ),
        enrichment=enrichment3,
        editorial=editorial3
    )
    episodes.append(episode3)
    
    return episodes


class TestIndexBuilder:
    """Test IndexBuilder functionality"""
    
    def test_init(self, config, temp_output_dir):
        """Test IndexBuilder initialization"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'web_artifacts': str(temp_output_dir / 'web')
            }
        }.get(key, default)
        
        builder = IndexBuilder(mock_config)
        
        assert builder.config == mock_config
        assert builder.output_base == Path(temp_output_dir / 'indices')
        assert builder.output_base.exists()
    
    def test_build_all_indices(self, config, temp_output_dir, sample_episodes):
        """Test building all indices from episodes"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'web_artifacts': str(temp_output_dir / 'web')
            }
        }.get(key, default)
        
        builder = IndexBuilder(mock_config)
        result = builder.build_all_indices(sample_episodes)
        
        assert isinstance(result, IndexBuildResult)
        assert result.total_episodes_processed == 3
        assert len(result.show_indices_updated) == 2  # tech-talk, business-insights
        assert len(result.host_indices_updated) >= 1  # At least dr-jane-smith
        assert result.global_index_updated is True
        assert result.build_time > 0
    
    def test_build_show_index(self, config, temp_output_dir, sample_episodes):
        """Test building index for a specific show"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices')
            }
        }.get(key, default)
        
        builder = IndexBuilder(mock_config)
        
        # Get episodes for tech-talk show
        tech_talk_episodes = [ep for ep in sample_episodes if ep.metadata.show_slug == "tech-talk"]
        
        show_index = builder.build_show_index("tech-talk", tech_talk_episodes)
        
        assert isinstance(show_index, ShowIndex)
        assert show_index.show_slug == "tech-talk"
        assert show_index.show_name == "Tech Talk"
        assert show_index.total_episodes == 2
        assert len(show_index.episodes) == 2
        assert len(show_index.hosts) >= 1
        assert len(show_index.topics) >= 1
        assert show_index.description is not None
    
    def test_build_host_index(self, config, temp_output_dir, sample_episodes):
        """Test building index for a specific host"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices')
            }
        }.get(key, default)
        
        builder = IndexBuilder(mock_config)
        
        # Find appearances for Dr. Jane Smith
        appearances = []
        for episode in sample_episodes:
            if episode.enrichment and episode.enrichment.proficiency_scores:
                scores_data = episode.enrichment.proficiency_scores
                if 'scored_people' in scores_data:
                    for person in scores_data['scored_people']:
                        if person.get('name') == 'Dr. Jane Smith':
                            appearances.append((episode, person))
        
        host_index = builder.build_host_index("dr-jane-smith", appearances)
        
        assert isinstance(host_index, HostIndex)
        assert host_index.host_slug == "dr-jane-smith"
        assert host_index.name == "Dr. Jane Smith"
        assert host_index.total_appearances == 3  # Dr. Jane Smith appears in 3 episodes
        assert len(host_index.shows) >= 1
        assert len(host_index.episodes) == 3
        assert host_index.biography is not None
    
    def test_update_indices_for_episode(self, config, temp_output_dir, sample_episodes):
        """Test updating indices for a new episode"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices')
            }
        }.get(key, default)
        
        builder = IndexBuilder(mock_config)
        
        # Use first episode as the "new" episode
        new_episode = sample_episodes[0]
        
        result = builder.update_indices_for_episode(new_episode, sample_episodes)
        
        assert isinstance(result, IndexBuildResult)
        assert result.total_episodes_processed == 3


class TestGlobalIndexManager:
    """Test GlobalIndexManager functionality"""
    
    def test_init(self, config, temp_output_dir):
        """Test GlobalIndexManager initialization"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True,
                'fields': ['title', 'summary', 'topics']
            }
        }.get(key, default)
        
        manager = GlobalIndexManager(mock_config)
        
        assert manager.config == mock_config
        assert manager.output_base == Path(temp_output_dir / 'indices')
        assert manager.search_base == Path(temp_output_dir / 'search')
        assert manager.enable_search_optimization is True
    
    def test_update_master_indices(self, config, temp_output_dir, sample_episodes):
        """Test updating master indices"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True
            }
        }.get(key, default)
        
        manager = GlobalIndexManager(mock_config)
        
        # Use first episode as the "new" episode
        new_episode = sample_episodes[0]
        
        result = manager.update_master_indices(new_episode, sample_episodes)
        
        assert result['success'] is True
        assert result['cross_references_updated'] >= 0
        assert result['update_time'] > 0
        assert 'statistics' in result
    
    def test_generate_cross_references(self, config, temp_output_dir, sample_episodes):
        """Test cross-reference generation"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices')
            }
        }.get(key, default)
        
        manager = GlobalIndexManager(mock_config)
        
        cross_references = manager.generate_cross_references(sample_episodes)
        
        assert 'show_to_hosts' in cross_references
        assert 'host_to_shows' in cross_references
        assert 'topic_to_episodes' in cross_references
        assert 'episode_to_related' in cross_references
        assert 'guest_networks' in cross_references
        assert 'topic_networks' in cross_references
        
        # Check that tech-talk show has hosts
        assert 'tech-talk' in cross_references['show_to_hosts']
        
        # Check that dr-jane-smith host has shows
        assert 'dr-jane-smith' in cross_references['host_to_shows']
    
    def test_update_search_optimization_metadata(self, config, temp_output_dir, sample_episodes):
        """Test search optimization metadata generation"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True,
                'fields': ['title', 'summary', 'topics', 'guests']
            }
        }.get(key, default)
        
        manager = GlobalIndexManager(mock_config)
        
        result = manager.update_search_optimization_metadata(sample_episodes)
        
        assert result['success'] is True
        assert result['search_documents'] == 3  # All episodes are rendered
        assert result['optimization_time'] > 0
        assert 'search_statistics' in result
        
        # Check that search index file was created
        search_index_path = manager.search_base / 'episodes.json'
        assert search_index_path.exists()
        
        # Check search index content
        with open(search_index_path, 'r', encoding='utf-8') as f:
            search_documents = json.load(f)
        
        assert len(search_documents) == 3
        assert all('searchable_text' in doc for doc in search_documents)
        assert all('search_metadata' in doc for doc in search_documents)
    
    def test_validate_index_consistency(self, config, temp_output_dir, sample_episodes):
        """Test index consistency validation"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True
            }
        }.get(key, default)
        
        manager = GlobalIndexManager(mock_config)
        
        # First build indices
        index_builder = IndexBuilder(config)
        index_builder.build_all_indices(sample_episodes)
        
        # Generate cross-references and search indices
        manager.generate_cross_references(sample_episodes)
        manager.update_search_optimization_metadata(sample_episodes)
        
        # Validate consistency
        result = manager.validate_index_consistency(sample_episodes)
        
        assert 'consistent' in result
        assert 'validation_time' in result
        assert 'index_integrity' in result
        assert 'cross_reference_integrity' in result
        assert 'search_integrity' in result
        assert 'recommendations' in result


class TestIndexValidator:
    """Test IndexValidator functionality"""
    
    def test_init(self, config):
        """Test IndexValidator initialization"""
        validator = IndexValidator(config)
        
        assert validator.config == config
    
    def test_validate_index_consistency(self, config, temp_output_dir, sample_episodes):
        """Test index consistency validation"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices')
            }
        }.get(key, default)
        
        # Build indices first
        builder = IndexBuilder(mock_config)
        builder.build_all_indices(sample_episodes)
        
        # Load indices for validation
        show_indices = {}
        host_indices = {}
        
        # Mock show and host indices
        show_indices['tech-talk'] = ShowIndex(
            show_slug='tech-talk',
            show_name='Tech Talk',
            total_episodes=2,
            seasons={1: 2},
            episodes=[],
            hosts=[],
            topics=[],
            last_updated=datetime.now()
        )
        
        host_indices['dr-jane-smith'] = HostIndex(
            host_slug='dr-jane-smith',
            name='Dr. Jane Smith',
            total_appearances=2,
            shows=[],
            episodes=[],
            topics=[],
            credentials={},
            last_updated=datetime.now()
        )
        
        validator = IndexValidator(mock_config)
        result = validator.validate_index_consistency(show_indices, host_indices, sample_episodes)
        
        assert 'consistent' in result
        assert 'cross_reference_issues' in result
        assert 'data_integrity_issues' in result
        assert 'completeness_issues' in result
        assert 'recommendations' in result


class TestIndexDataModels:
    """Test index data model functionality"""
    
    def test_show_index_creation(self):
        """Test ShowIndex creation"""
        show_index = ShowIndex(
            show_slug='test-show',
            show_name='Test Show',
            total_episodes=5,
            seasons={1: 3, 2: 2},
            episodes=[],
            hosts=[],
            topics=['Technology', 'Science'],
            last_updated=datetime.now(),
            description='A test show about technology'
        )
        
        assert show_index.show_slug == 'test-show'
        assert show_index.show_name == 'Test Show'
        assert show_index.total_episodes == 5
        assert len(show_index.seasons) == 2
        assert len(show_index.topics) == 2
    
    def test_host_index_creation(self):
        """Test HostIndex creation"""
        host_index = HostIndex(
            host_slug='test-host',
            name='Test Host',
            total_appearances=3,
            shows=[],
            episodes=[],
            topics=['AI', 'ML'],
            credentials={'title': 'Expert'},
            last_updated=datetime.now(),
            biography='A test host biography'
        )
        
        assert host_index.host_slug == 'test-host'
        assert host_index.name == 'Test Host'
        assert host_index.total_appearances == 3
        assert len(host_index.topics) == 2
        assert host_index.biography == 'A test host biography'
    
    def test_global_index_creation(self):
        """Test GlobalIndex creation"""
        global_index = GlobalIndex(
            total_episodes=10,
            total_shows=2,
            total_hosts=5,
            shows=[],
            featured_hosts=[],
            recent_episodes=[],
            popular_topics=[],
            last_updated=datetime.now()
        )
        
        assert global_index.total_episodes == 10
        assert global_index.total_shows == 2
        assert global_index.total_hosts == 5
    
    def test_index_build_result_creation(self):
        """Test IndexBuildResult creation"""
        result = IndexBuildResult(
            show_indices_updated=['show1', 'show2'],
            host_indices_updated=['host1', 'host2'],
            global_index_updated=True,
            total_episodes_processed=5,
            build_time=1.5,
            validation_results={'consistent': True}
        )
        
        assert len(result.show_indices_updated) == 2
        assert len(result.host_indices_updated) == 2
        assert result.global_index_updated is True
        assert result.total_episodes_processed == 5
        assert result.build_time == 1.5


class TestIndexBuilderIntegration:
    """Integration tests for index builder components"""
    
    def test_full_index_workflow(self, config, temp_output_dir, sample_episodes):
        """Test complete index building workflow"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True,
                'fields': ['title', 'summary', 'topics', 'guests']
            }
        }.get(key, default)
        
        # Step 1: Build initial indices
        builder = IndexBuilder(mock_config)
        build_result = builder.build_all_indices(sample_episodes)
        
        assert build_result.total_episodes_processed == 3
        assert len(build_result.show_indices_updated) == 2
        
        # Step 2: Generate cross-references and search indices
        manager = GlobalIndexManager(mock_config)
        cross_references = manager.generate_cross_references(sample_episodes)
        search_result = manager.update_search_optimization_metadata(sample_episodes)
        
        assert len(cross_references['show_to_hosts']) >= 1
        assert search_result['success'] is True
        
        # Step 3: Validate consistency
        validation_result = manager.validate_index_consistency(sample_episodes)
        
        # Should be consistent since we just built everything
        assert validation_result['consistent'] is True
        
        # Step 4: Update indices with new episode (simulate)
        new_episode = sample_episodes[0]  # Use existing episode as "new"
        update_result = manager.update_master_indices(new_episode, sample_episodes)
        
        assert update_result['success'] is True
        
        # Verify files were created
        indices_dir = Path(temp_output_dir / 'indices')
        assert (indices_dir / 'global.json').exists()
        assert (indices_dir / 'cross_references.json').exists()
        assert (indices_dir / 'shows').exists()
        assert (indices_dir / 'hosts').exists()
        
        search_dir = Path(temp_output_dir / 'search')
        assert (search_dir / 'episodes.json').exists()
        assert (search_dir / 'config.json').exists()
    
    def test_index_file_formats(self, config, temp_output_dir, sample_episodes):
        """Test that generated index files have correct format"""
        # Create a mock config with get method
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'output': {
                'indices': str(temp_output_dir / 'indices'),
                'search': str(temp_output_dir / 'search')
            },
            'search': {
                'enabled': True
            }
        }.get(key, default)
        
        # Build indices
        builder = IndexBuilder(mock_config)
        builder.build_all_indices(sample_episodes)
        
        manager = GlobalIndexManager(mock_config)
        manager.generate_cross_references(sample_episodes)
        manager.update_search_optimization_metadata(sample_episodes)
        
        indices_dir = Path(temp_output_dir / 'indices')
        
        # Test global index format
        with open(indices_dir / 'global.json', 'r', encoding='utf-8') as f:
            global_data = json.load(f)
        
        required_global_fields = [
            'total_episodes', 'total_shows', 'total_hosts',
            'shows', 'featured_hosts', 'recent_episodes',
            'popular_topics', 'last_updated'
        ]
        for field in required_global_fields:
            assert field in global_data
        
        # Test show index format
        show_files = list((indices_dir / 'shows').glob('*.json'))
        assert len(show_files) >= 1
        
        with open(show_files[0], 'r', encoding='utf-8') as f:
            show_data = json.load(f)
        
        required_show_fields = [
            'show_slug', 'show_name', 'total_episodes',
            'seasons', 'episodes', 'hosts', 'topics',
            'description', 'last_updated'
        ]
        for field in required_show_fields:
            assert field in show_data
        
        # Test cross-references format
        with open(indices_dir / 'cross_references.json', 'r', encoding='utf-8') as f:
            cross_ref_data = json.load(f)
        
        required_cross_ref_fields = [
            'show_to_hosts', 'host_to_shows', 'topic_to_episodes',
            'episode_to_related', 'guest_networks', 'topic_networks'
        ]
        for field in required_cross_ref_fields:
            assert field in cross_ref_data
        
        # Test search index format
        search_dir = Path(temp_output_dir / 'search')
        with open(search_dir / 'episodes.json', 'r', encoding='utf-8') as f:
            search_data = json.load(f)
        
        assert isinstance(search_data, list)
        if search_data:
            required_search_fields = [
                'id', 'type', 'title', 'searchable_text', 'search_metadata'
            ]
            for field in required_search_fields:
                assert field in search_data[0]


if __name__ == '__main__':
    pytest.main([__file__])