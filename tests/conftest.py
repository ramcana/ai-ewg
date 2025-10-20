"""
Pytest configuration and shared fixtures for AI Video Processing Pipeline tests
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "utils"))


# ========================================
# Environment Configuration
# ========================================

def pytest_configure(config):
    """Configure pytest environment before tests run"""
    # Set environment variables for CI/CD
    os.environ["DIARIZE_DEVICE"] = os.getenv("DIARIZE_DEVICE", "cpu")
    os.environ["MOCK_MODELS"] = os.getenv("MOCK_MODELS", "1")
    os.environ["MOCK_OLLAMA"] = os.getenv("MOCK_OLLAMA", "1")
    os.environ["TESTING"] = "1"
    
    # Suppress warnings
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)


# ========================================
# Skip Markers
# ========================================

def pytest_collection_modifyitems(config, items):
    """Automatically skip GPU tests if GPU not available or explicitly disabled"""
    skip_gpu = os.getenv("SKIP_GPU_TESTS", "0") == "1"
    
    # Check if CUDA is available
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except ImportError:
        has_cuda = False
    
    skip_gpu_marker = pytest.mark.skip(reason="GPU not available or tests disabled")
    
    for item in items:
        # Skip GPU tests if explicitly disabled or no GPU available
        if "gpu" in item.keywords and (skip_gpu or not has_cuda):
            item.add_marker(skip_gpu_marker)


# ========================================
# Directory Fixtures
# ========================================

@pytest.fixture(scope="session")
def project_root_dir():
    """Return project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root_dir):
    """Return test data directory"""
    return project_root_dir / "tests" / "test_data"


@pytest.fixture(scope="session")
def temp_output_dir(tmp_path_factory):
    """Create temporary output directory for tests"""
    return tmp_path_factory.mktemp("output")


# ========================================
# Mock Fixtures for External Services
# ========================================

@pytest.fixture
def mock_ollama_client(monkeypatch):
    """Mock Ollama client for testing without running Ollama service"""
    mock_generate = Mock(return_value={
        "response": '{"entities": ["John Doe", "Example Corp"], "topics": ["AI", "Machine Learning"]}'
    })
    
    # Create mock module if needed
    if os.getenv("MOCK_OLLAMA") == "1":
        try:
            import sys
            if "ollama" not in sys.modules:
                sys.modules["ollama"] = MagicMock()
                sys.modules["ollama"].generate = mock_generate
        except Exception:
            pass
    
    return mock_generate


@pytest.fixture
def mock_whisper_model(monkeypatch):
    """Mock Whisper model for transcription tests"""
    if os.getenv("MOCK_MODELS") == "1":
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "This is a test transcript.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": "This is a test transcript."
                }
            ]
        }
        
        def mock_load_model(model_name, device="cpu"):
            return mock_model
        
        try:
            import whisper
            monkeypatch.setattr(whisper, "load_model", mock_load_model)
        except ImportError:
            pass
        
        return mock_model
    return None


@pytest.fixture
def mock_pyannote_pipeline(monkeypatch):
    """Mock pyannote.audio pipeline for diarization tests"""
    if os.getenv("MOCK_MODELS") == "1":
        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        
        # Mock diarization output
        mock_result.itertracks.return_value = [
            (MagicMock(start=0.0, end=5.0), None, "SPEAKER_00"),
            (MagicMock(start=5.0, end=10.0), None, "SPEAKER_01"),
        ]
        
        mock_pipeline.return_value = mock_result
        
        try:
            from pyannote.audio import Pipeline
            monkeypatch.setattr(Pipeline, "from_pretrained", lambda x, use_auth_token=None: mock_pipeline)
        except ImportError:
            pass
        
        return mock_pipeline
    return None


@pytest.fixture
def mock_wikipedia_api(monkeypatch):
    """Mock Wikipedia/Wikidata API calls"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "query": {
            "pages": {
                "12345": {
                    "title": "Test Person",
                    "extract": "Test Person is a notable individual.",
                }
            }
        }
    }
    mock_response.status_code = 200
    
    if os.getenv("MOCK_MODELS") == "1":
        import requests
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_response)
    
    return mock_response


# ========================================
# Sample Data Fixtures
# ========================================

@pytest.fixture
def sample_transcript():
    """Return sample transcript for testing"""
    return """
    SPEAKER_00: Hello, this is a test transcript.
    SPEAKER_01: Yes, I agree. This is very useful for testing.
    SPEAKER_00: Let's discuss artificial intelligence and machine learning.
    SPEAKER_01: That sounds great. I'm an expert in neural networks.
    """


@pytest.fixture
def sample_episode_metadata():
    """Return sample episode metadata"""
    return {
        "episode_id": "test-2024-001",
        "title": "Test Episode",
        "show": "Test Show",
        "date": "2024-01-01",
        "duration": 120,
        "file_path": "/path/to/test.mp4"
    }


@pytest.fixture
def sample_guest_data():
    """Return sample guest enrichment data"""
    return {
        "name": "Dr. Jane Smith",
        "title": "AI Researcher",
        "organization": "Example University",
        "expertise": ["Machine Learning", "Neural Networks"],
        "credentials": {
            "education": "PhD in Computer Science",
            "publications": 50,
            "h_index": 25
        },
        "proficiency_score": 0.85,
        "verification_badge": "Verified Expert"
    }


# ========================================
# Database Fixtures
# ========================================

@pytest.fixture
def mock_database(tmp_path):
    """Create temporary SQLite database for testing"""
    db_path = tmp_path / "test_pipeline.db"
    
    # Initialize database
    try:
        from src.core.database import Database
        db = Database(str(db_path))
        yield db
        # Cleanup
        if db_path.exists():
            db_path.unlink()
    except ImportError:
        # If database module not available, yield None
        yield None


# ========================================
# Audio/Video Test Files
# ========================================

@pytest.fixture
def sample_audio_file(tmp_path):
    """Create a minimal valid audio file for testing"""
    # This creates a silent WAV file for testing
    audio_path = tmp_path / "test_audio.wav"
    
    try:
        import wave
        import struct
        
        with wave.open(str(audio_path), 'wb') as wav_file:
            # Set parameters: 1 channel, 2 bytes per sample, 16000 Hz
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            
            # Write 1 second of silence
            silence = struct.pack('<h', 0) * 16000
            wav_file.writeframes(silence)
        
        yield audio_path
    except Exception:
        # If wave module fails, just yield the path
        yield audio_path


# ========================================
# Configuration Fixtures
# ========================================

@pytest.fixture
def test_config():
    """Return test configuration"""
    return {
        "processing": {
            "device": "cpu",
            "num_speakers": 2,
            "model": "base"
        },
        "paths": {
            "data_dir": "data",
            "output_dir": "output"
        },
        "api": {
            "rate_limit_delay": 0.1
        }
    }


# ========================================
# Cleanup
# ========================================

@pytest.fixture(autouse=True)
def cleanup_environment():
    """Clean up environment after each test"""
    yield
    # Cleanup code here if needed
    pass
