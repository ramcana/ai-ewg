"""
Tests for the Intelligence Chain Orchestrator

Tests the integration and orchestration of the four AI processing utilities:
diarization, entity extraction, disambiguation, and proficiency scoring.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.core.intelligence_chain import (
    IntelligenceChainOrchestrator,
    ChainStageResult,
    IntelligenceChainResult
)
from src.core.config import PipelineConfig, ModelConfig, ThresholdConfig
from src.core.models import EpisodeObject, EpisodeMetadata, SourceInfo, MediaInfo


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing"""
    config = PipelineConfig()
    config.models = ModelConfig(
        whisper="base",
        llm="mistral",
        diarization_device="cpu",
        num_speakers=2
    )
    config.thresholds = ThresholdConfig(
        confidence_min=0.6,
        entity_confidence=0.7
    )
    config.hf_token = "test_token"
    config.ollama_url = "http://localhost:11434"
    config.api_rate_limit_delay = 0.1
    return config


@pytest.fixture
def sample_episode():
    """Create a sample episode for testing"""
    metadata = EpisodeMetadata(
        show_name="Test Show",
        show_slug="test-show",
        season=1,
        episode=1,
        topic="Test Topic"
    )
    
    source = SourceInfo(
        path="/test/video.mp4",
        file_size=1000000,
        last_modified="2024-01-01T00:00:00"
    )
    
    media = MediaInfo(duration_seconds=3600)
    
    return EpisodeObject(
        episode_id="test-show-s1e1-test-topic",
        content_hash="test_hash",
        source=source,
        media=media,
        metadata=metadata
    )


class TestIntelligenceChainOrchestrator:
    """Test the intelligence chain orchestrator"""
    
    def test_initialization(self, mock_config):
        """Test orchestrator initialization"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        assert orchestrator.config == mock_config
        assert orchestrator.utils_dir.exists()
        assert orchestrator.diarize_script.exists()
        assert orchestrator.extract_entities_script.exists()
        assert orchestrator.disambiguate_script.exists()
        assert orchestrator.score_people_script.exists()
    
    def test_validate_utilities_missing_script(self, mock_config):
        """Test validation fails when utility scripts are missing"""
        with patch.object(Path, 'exists', return_value=False):
            with pytest.raises(Exception) as exc_info:
                IntelligenceChainOrchestrator(mock_config)
            
            assert "Missing utility scripts" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_diarization_stage_success(self, mock_config, sample_episode):
        """Test successful diarization stage"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        # Mock successful diarization output
        mock_diarization_data = {
            "segments": [
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00", "duration": 10.0},
                {"start": 10.0, "end": 20.0, "speaker": "SPEAKER_01", "duration": 10.0}
            ],
            "num_speakers": 2,
            "total_duration": 20.0,
            "device_used": "cpu"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock subprocess execution
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = (b"Success", b"")
                mock_subprocess.return_value = mock_process
                
                # Create mock output file
                segments_file = temp_path / "diarization_segments.json"
                with open(segments_file, 'w') as f:
                    json.dump(mock_diarization_data, f)
                
                result = await orchestrator._run_diarization(
                    "/test/audio.wav", temp_path, sample_episode.episode_id
                )
                
                assert result.success
                assert result.stage == "diarization"
                assert result.data == mock_diarization_data
                assert result.metrics['num_segments'] == 2
                assert result.metrics['num_speakers'] == 2
    
    @pytest.mark.asyncio
    async def test_entity_extraction_stage_success(self, mock_config, sample_episode):
        """Test successful entity extraction stage"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        # Mock successful entity extraction output
        mock_entities_data = {
            "candidates": [
                {
                    "name": "John Doe",
                    "role_guess": "Economist",
                    "org_guess": "Bank of Canada",
                    "confidence": 0.85,
                    "journalistic_relevance": "high"
                }
            ],
            "topics": ["economy", "policy", "inflation"],
            "extraction_method": "llm"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock subprocess execution
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = (b"Success", b"")
                mock_subprocess.return_value = mock_process
                
                # Create mock output file
                entities_file = temp_path / "entities.json"
                with open(entities_file, 'w') as f:
                    json.dump(mock_entities_data, f)
                
                result = await orchestrator._run_entity_extraction(
                    "Test transcript text", temp_path, sample_episode.episode_id
                )
                
                assert result.success
                assert result.stage == "entity_extraction"
                assert len(result.data['candidates']) == 1
                assert result.data['candidates'][0]['name'] == "John Doe"
    
    def test_validate_diarization_quality(self, mock_config):
        """Test diarization quality validation"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        # Test good quality diarization
        good_segments = [
            {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00", "duration": 10.0},
            {"start": 10.0, "end": 20.0, "speaker": "SPEAKER_01", "duration": 10.0},
            {"start": 20.0, "end": 30.0, "speaker": "SPEAKER_00", "duration": 10.0},
            {"start": 30.0, "end": 40.0, "speaker": "SPEAKER_01", "duration": 10.0},
            {"start": 40.0, "end": 50.0, "speaker": "SPEAKER_00", "duration": 10.0}
        ]
        
        validation = orchestrator._validate_diarization({"segments": good_segments})
        
        assert validation['valid']
        assert len(validation['issues']) == 0
        assert validation['quality_score'] > 0.8
        
        # Test poor quality diarization
        poor_segments = [
            {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "duration": 1.0}
        ]
        
        validation = orchestrator._validate_diarization({"segments": poor_segments})
        
        assert not validation['valid']
        assert len(validation['issues']) > 0
        assert validation['quality_score'] < 0.8  # Should be lower than good quality
    
    def test_filter_journalistic_entities(self, mock_config):
        """Test journalistic entity filtering"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        entities_data = {
            "candidates": [
                {
                    "name": "John Doe",
                    "role_guess": "Minister",
                    "confidence": 0.9,
                    "quotes": ["According to our research..."]
                },
                {
                    "name": "Jane Smith", 
                    "role_guess": "",
                    "confidence": 0.4,  # Below threshold
                    "quotes": []
                },
                {
                    "name": "Bob Johnson",
                    "role_guess": "Professor",
                    "confidence": 0.8,
                    "quotes": ["The data shows..."]
                }
            ],
            "topics": ["economy", "policy"]
        }
        
        filtered = orchestrator._filter_journalistic_entities(entities_data)
        
        # Should filter out low confidence candidate
        assert len(filtered['candidates']) == 2
        assert filtered['candidates'][0]['name'] == "John Doe"
        assert filtered['candidates'][0]['journalistic_relevance'] == 'high'  # Minister role
        assert filtered['candidates'][1]['name'] == "Bob Johnson"
        
        # Should have credibility quotes
        assert 'credibility_quotes' in filtered['candidates'][0]
    
    def test_create_enrichment_result(self, mock_config):
        """Test conversion to EnrichmentResult model"""
        orchestrator = IntelligenceChainOrchestrator(mock_config)
        
        # Create mock chain result
        chain_result = IntelligenceChainResult(
            success=True,
            diarization=ChainStageResult(
                stage="diarization",
                success=True,
                data={"segments": []}
            ),
            entities=ChainStageResult(
                stage="entity_extraction", 
                success=True,
                data={"candidates": []}
            ),
            disambiguation=ChainStageResult(
                stage="disambiguation",
                success=True,
                data={"enriched_people": []}
            ),
            proficiency_scores=ChainStageResult(
                stage="proficiency_scoring",
                success=True,
                data={"scored_people": []}
            )
        )
        
        enrichment_result = orchestrator.create_enrichment_result(chain_result)
        
        assert enrichment_result.diarization is not None
        assert enrichment_result.entities is not None
        assert enrichment_result.disambiguation is not None
        assert enrichment_result.proficiency_scores is not None


if __name__ == "__main__":
    pytest.main([__file__])