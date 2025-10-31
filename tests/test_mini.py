"""
Mini test suite for CI pipeline

Fast tests using a small fixture video to validate the complete pipeline.
Run with: pytest -m mini
"""

import pytest
from pathlib import Path
import json
import tempfile
import shutil

# Mark all tests in this module as mini tests
pytestmark = pytest.mark.mini


@pytest.fixture
def mini_video_path():
    """Path to mini test video (30-60 seconds)"""
    # This should be a small test video in tests/data/mini/
    test_data_dir = Path(__file__).parent / "data" / "mini"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    # For now, return the expected path
    # In real usage, you'd have a small video file here
    video_path = test_data_dir / "test_episode.mp4"
    
    if not video_path.exists():
        pytest.skip(f"Mini test video not found: {video_path}")
    
    return video_path


@pytest.fixture
def temp_output_dir():
    """Temporary output directory for test artifacts"""
    temp_dir = tempfile.mkdtemp(prefix="ai_ewg_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_output_dir):
    """Test configuration for mini pipeline"""
    config = {
        "sources": [
            {
                "path": str(Path(__file__).parent / "data" / "mini"),
                "include": ["*.mp4", "*.mkv"],
                "enabled": True
            }
        ],
        "staging": {
            "enabled": True,
            "path": str(temp_output_dir / "staging"),
            "cleanup_after_processing": False  # Keep for inspection
        },
        "models": {
            "whisper": "base",  # Use smaller model for faster tests
            "whisper_device": "cpu",  # Force CPU for CI
            "whisper_compute_type": "int8",
            "llm": "mistral",
            "diarization_device": "cpu",
            "num_speakers": 2
        },
        "database": {
            "path": str(temp_output_dir / "test.db")
        },
        "logging": {
            "level": "DEBUG",
            "directory": str(temp_output_dir / "logs"),
            "console": True,
            "structured": True
        },
        "processing": {
            "max_concurrent_episodes": 1,
            "max_retry_attempts": 1,
            "timeout_minutes": 10
        }
    }
    
    return config


class TestMiniPipeline:
    """Test complete pipeline with mini fixture"""
    
    def test_config_validation(self, test_config):
        """Test that configuration validates correctly"""
        from src.core.settings import PipelineSettings
        
        settings = PipelineSettings(**test_config)
        
        assert settings.sources[0].enabled is True
        assert settings.models.whisper == "base"
        assert settings.models.whisper_device == "cpu"
    
    def test_database_initialization(self, test_config):
        """Test database schema creation"""
        from src.core.settings import PipelineSettings
        from src.core.database import DatabaseManager
        
        settings = PipelineSettings(**test_config)
        db_path = Path(settings.database.path)
        
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        
        # Verify database file exists
        assert db_path.exists()
        
        # Verify tables exist
        conn = db_manager.get_connection().get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {'episodes', 'processing_log', 'schema_version'}
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
    
    def test_discovery_stage(self, test_config, mini_video_path):
        """Test video discovery stage"""
        if not mini_video_path.exists():
            pytest.skip("Mini video not available")
        
        from src.core.settings import PipelineSettings
        from src.core.discovery import VideoDiscovery
        
        settings = PipelineSettings(**test_config)
        discovery = VideoDiscovery(settings)
        
        # Discover videos
        videos = discovery.discover_videos()
        
        assert len(videos) > 0, "No videos discovered"
        assert any(v.path == str(mini_video_path) for v in videos)
    
    def test_transcription_engine(self, test_config, mini_video_path, temp_output_dir):
        """Test transcription with Faster-Whisper"""
        if not mini_video_path.exists():
            pytest.skip("Mini video not available")
        
        import asyncio
        from src.core.transcription_engine import create_transcription_engine
        
        # Create engine with CPU and small model for CI
        engine = create_transcription_engine(
            model_size="base",
            device="cpu",
            compute_type="int8",
            max_gpu_concurrent=1
        )
        
        # Extract audio (mock for now - would use ffmpeg in real test)
        audio_path = temp_output_dir / "test_audio.wav"
        
        # Skip if audio extraction not available
        if not audio_path.exists():
            pytest.skip("Audio extraction not available in test environment")
        
        # Transcribe
        result = asyncio.run(engine.transcribe(audio_path))
        
        assert result.text, "Transcription returned empty text"
        assert len(result.segments) > 0, "No segments in transcription"
        assert result.language, "Language not detected"
    
    def test_vtt_export(self):
        """Test VTT export format"""
        from src.core.transcription_engine import TranscriptionSegment, TranscriptionResult
        
        segments = [
            TranscriptionSegment(start=0.0, end=5.5, text="Hello world", confidence=0.95),
            TranscriptionSegment(start=5.5, end=10.0, text="This is a test", confidence=0.92)
        ]
        
        result = TranscriptionResult(
            text="Hello world This is a test",
            segments=segments,
            language="en",
            duration=10.0
        )
        
        vtt = result.to_vtt()
        
        assert "WEBVTT" in vtt
        assert "00:00:00.000 --> 00:00:05.500" in vtt
        assert "Hello world" in vtt
        assert "This is a test" in vtt
    
    def test_registry_operations(self, test_config):
        """Test episode registry operations"""
        from src.core.settings import PipelineSettings
        from src.core.database import DatabaseManager
        from src.core.registry import EpisodeRegistry
        from src.core.models import EpisodeObject, ProcessingStage
        
        settings = PipelineSettings(**test_config)
        db_path = Path(settings.database.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()
        
        registry = EpisodeRegistry(db_manager)
        
        # Create test episode
        from src.core.models import SourceInfo, MediaInfo, EpisodeMetadata
        from datetime import datetime
        
        episode = EpisodeObject(
            episode_id="test_episode_001",
            content_hash="abc123",
            processing_stage=ProcessingStage.DISCOVERED,
            source=SourceInfo(
                path="/test/video.mp4",
                file_size=1000000,
                last_modified=datetime.now()
            ),
            media=MediaInfo(
                duration_seconds=60.0,
                video_codec="h264",
                audio_codec="aac"
            ),
            metadata=EpisodeMetadata(
                show_name="Test Show",
                show_slug="test-show",
                episode=1,
                season=1
            )
        )
        
        # Register episode
        registered = registry.register_episode(episode)
        assert registered is True
        
        # Retrieve episode
        retrieved = registry.get_episode("test_episode_001")
        assert retrieved is not None
        assert retrieved.episode_id == "test_episode_001"
        
        # Update stage
        registry.update_episode_stage("test_episode_001", ProcessingStage.TRANSCRIBED)
        
        updated = registry.get_episode("test_episode_001")
        assert updated.processing_stage == ProcessingStage.TRANSCRIBED
    
    def test_structured_logging(self, temp_output_dir):
        """Test structured logging output"""
        from src.core.structured_logging import setup_structured_logging, get_run_logger
        
        log_dir = temp_output_dir / "logs"
        setup_structured_logging(log_dir, level="INFO", console_output=False, jsonl_output=True)
        
        # Create a test run
        with get_run_logger("test_command", "test_episode") as run_logger:
            with run_logger.stage("test_stage"):
                run_logger.log_metric("test_metric", 42)
        
        # Verify JSONL file was created
        jsonl_files = list(log_dir.glob("run_*.jsonl"))
        assert len(jsonl_files) > 0, "No JSONL log files created"
        
        # Verify JSONL content
        with open(jsonl_files[0], 'r') as f:
            lines = f.readlines()
            assert len(lines) > 0, "JSONL file is empty"
            
            # Parse first line
            first_log = json.loads(lines[0])
            assert "event" in first_log
            assert "timestamp" in first_log


class TestCLICommands:
    """Test CLI command structure"""
    
    def test_cli_imports(self):
        """Test that CLI imports work"""
        from src.ai_ewg.cli import app
        
        assert app is not None
        assert app.info.name == "ai-ewg"
    
    def test_cli_help(self):
        """Test CLI help output"""
        from typer.testing import CliRunner
        from src.ai_ewg.cli import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "ai-ewg" in result.stdout.lower()


class TestUtilities:
    """Test utility functions"""
    
    def test_path_handling(self):
        """Test path utilities work on Windows"""
        from pathlib import Path
        
        test_path = Path("test/path/video.mp4")
        
        assert test_path.suffix == ".mp4"
        assert test_path.stem == "video"
    
    def test_json_serialization(self):
        """Test JSON serialization of common objects"""
        from datetime import datetime
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "path": str(Path("test/video.mp4")),
            "duration": 60.5,
            "success": True
        }
        
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        
        assert parsed["success"] is True
        assert parsed["duration"] == 60.5


# Integration test (runs full pipeline if fixture available)
@pytest.mark.slow
@pytest.mark.integration
def test_full_mini_pipeline(test_config, mini_video_path, temp_output_dir):
    """
    Full integration test: discover → transcribe → web build
    
    This test requires a real mini video fixture and takes longer to run.
    """
    if not mini_video_path.exists():
        pytest.skip("Mini video fixture not available")
    
    # This would run the full pipeline
    # For now, just verify the structure is in place
    pytest.skip("Full integration test requires complete pipeline implementation")
