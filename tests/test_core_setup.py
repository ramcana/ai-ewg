"""
Tests for core project structure and configuration system
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core import (
    ConfigurationManager,
    PipelineOrchestrator,
    setup_logging,
    PipelineError,
    ConfigurationError,
    ProcessingError,
    ValidationError,
    TransientError
)
from src.core.pipeline import ProcessingStage


class TestExceptions:
    """Test exception classes"""
    
    def test_pipeline_error_basic(self):
        error = PipelineError("Test error")
        assert str(error) == "Test error"
        assert error.context == {}
    
    def test_pipeline_error_with_context(self):
        context = {"key": "value", "number": 42}
        error = PipelineError("Test error", context)
        assert "Test error" in str(error)
        assert "key=value" in str(error)
        assert "number=42" in str(error)
    
    def test_configuration_error(self):
        error = ConfigurationError("Config error", config_key="test.key")
        assert error.config_key == "test.key"
        assert "config_key=test.key" in str(error)
    
    def test_processing_error(self):
        error = ProcessingError("Process error", stage="transcribed", episode_id="test-ep")
        assert error.stage == "transcribed"
        assert error.episode_id == "test-ep"
    
    def test_transient_error_retry_logic(self):
        error = TransientError("Temp error", retry_count=1, max_retries=3)
        assert error.should_retry is True
        
        error = TransientError("Temp error", retry_count=3, max_retries=3)
        assert error.should_retry is False


class TestConfigurationManager:
    """Test configuration management"""
    
    def test_load_default_config(self):
        """Test loading with no config file"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_path)
            config = config_manager.load_config()
            
            assert config is not None
            assert config.models.whisper == "base"
            assert config.processing.max_concurrent_episodes >= 1
            assert len(config.sources) == 1
        finally:
            Path(config_path).unlink()
    
    def test_load_yaml_config(self):
        """Test loading from YAML file"""
        yaml_content = {
            'sources': [{'path': '/test/path', 'enabled': True}],
            'models': {'whisper': 'large', 'llm': 'test-model'},
            'processing': {'max_concurrent_episodes': 5}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_path)
            config = config_manager.load_config()
            
            assert len(config.sources) == 1
            assert config.sources[0].path == '/test/path'
            assert config.models.whisper == 'large'
            assert config.processing.max_concurrent_episodes == 5
        finally:
            Path(config_path).unlink()
    
    def test_env_variable_overrides(self):
        """Test environment variable overrides"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            with patch.dict('os.environ', {
                'OLLAMA_MODEL': 'test-llm',
                'MIN_PUBLISH_SCORE': '0.8',
                'MAX_CONCURRENT_EPISODES': '10'
            }):
                config_manager = ConfigurationManager(config_path)
                config = config_manager.load_config()
                
                assert config.models.llm == 'test-llm'
                assert config.thresholds.publish_score == 0.8
                assert config.processing.max_concurrent_episodes == 10
        finally:
            Path(config_path).unlink()
    
    def test_invalid_yaml_config(self):
        """Test handling of invalid YAML"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_path)
            with pytest.raises(ConfigurationError):
                config_manager.load_config()
        finally:
            Path(config_path).unlink()
    
    def test_validation_errors(self):
        """Test configuration validation"""
        yaml_content = {
            'sources': [],  # Empty sources should fail
            'thresholds': {'confidence_min': 1.5}  # Invalid threshold
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_path)
            with pytest.raises(ConfigurationError):
                config_manager.load_config()
        finally:
            Path(config_path).unlink()


class TestPipelineOrchestrator:
    """Test pipeline orchestrator"""
    
    def test_orchestrator_initialization(self):
        """Test basic orchestrator setup"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            orchestrator = PipelineOrchestrator(config_path=config_path)
            assert orchestrator.config is not None
            assert len(orchestrator._stage_processors) == 5
        finally:
            Path(config_path).unlink()
    
    def test_stage_progression_logic(self):
        """Test stage progression calculation"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            orchestrator = PipelineOrchestrator(config_path=config_path)
            
            # Test normal progression
            stages = orchestrator._get_stages_to_process(
                ProcessingStage.DISCOVERED, 
                ProcessingStage.TRANSCRIBED
            )
            expected = [ProcessingStage.PREPPED, ProcessingStage.TRANSCRIBED]
            assert stages == expected
            
            # Test no progression needed
            stages = orchestrator._get_stages_to_process(
                ProcessingStage.RENDERED, 
                ProcessingStage.TRANSCRIBED
            )
            assert stages == []
        finally:
            Path(config_path).unlink()
    
    @pytest.mark.asyncio
    async def test_single_episode_processing(self):
        """Test processing a single episode"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            orchestrator = PipelineOrchestrator(config_path=config_path)
            
            # Mock the stage processors to avoid actual processing
            async def mock_processor(episode_id):
                pass
            
            for stage in ProcessingStage:
                orchestrator._stage_processors[stage] = mock_processor
            
            # Mock registry methods
            async def mock_get_stage(episode_id):
                return ProcessingStage.DISCOVERED
            
            async def mock_update_stage(episode_id, stage):
                pass
            
            orchestrator._get_episode_stage = mock_get_stage
            orchestrator._update_episode_stage = mock_update_stage
            
            result = await orchestrator.process_episode("test-episode", ProcessingStage.PREPPED)
            
            assert result.success is True
            assert result.episode_id == "test-episode"
            assert result.duration >= 0  # Duration should be non-negative
        finally:
            Path(config_path).unlink()
    
    def test_shutdown_request(self):
        """Test graceful shutdown"""
        # Create a minimal valid config
        yaml_content = {
            'sources': [{'path': '/test/videos', 'enabled': True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_content, f)
            config_path = f.name
        
        try:
            orchestrator = PipelineOrchestrator(config_path=config_path)
            assert orchestrator._shutdown_requested is False
            
            orchestrator.request_shutdown()
            assert orchestrator._shutdown_requested is True
        finally:
            Path(config_path).unlink()


class TestLogging:
    """Test logging infrastructure"""
    
    def test_setup_logging_basic(self):
        """Test basic logging setup"""
        import logging
        
        # Use a unique temp directory and clean up handlers properly
        temp_dir = tempfile.mkdtemp()
        try:
            config = {
                'logging': {
                    'level': 'INFO',
                    'directory': temp_dir,
                    'console': False
                }
            }
            
            # Clear existing handlers first
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
            
            # Should not raise any exceptions
            setup_logging(config)
            
            # Check log file was created
            log_file = Path(temp_dir) / 'pipeline.log'
            assert log_file.exists()
            
            # Clean up handlers
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
                
        finally:
            # Manual cleanup
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                pass  # Ignore cleanup errors in tests
    
    def test_structured_logging(self):
        """Test structured logging format"""
        from src.core.logging import get_logger
        
        logger = get_logger('test')
        
        # Test timer functionality
        logger.start_timer('test_operation')
        duration = logger.end_timer('test_operation', test_param='value')
        
        assert duration >= 0
    
    def test_pipeline_logger_context(self):
        """Test pipeline logger with context"""
        from src.core.logging import get_logger
        
        logger = get_logger('test')
        
        # Should not raise exceptions
        logger.info("Test message", episode_id="test", stage="prep")
        logger.error("Test error", exception=Exception("test"), episode_id="test")
        logger.log_processing_event("test-ep", "transcribed", "completed", 1.5)