"""
Tests for reliability features

Tests retry logic, circuit breakers, resource management, and monitoring.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch

from src.core.reliability import (
    RetryHandler, RetryConfig, CircuitBreaker, CircuitBreakerConfig,
    ReliabilityManager, ServiceHealthMonitor
)
from src.core.resource_manager import (
    ResourceMonitor, ResourceLimits, ConcurrencyController,
    ProcessingQueue, ProcessingTask, Priority
)
from src.core.reliability_integration import (
    PipelineReliabilityManager, PipelineReliabilityConfig
)
from src.core.models import ProcessingStage
from src.core.exceptions import TransientError, ExternalServiceError


class TestRetryHandler:
    """Test retry logic functionality"""
    
    def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt"""
        config = RetryConfig(max_attempts=3)
        handler = RetryHandler(config)
        
        def success_func():
            return "success"
        
        result = handler.retry(success_func)
        assert result == "success"
    
    def test_retry_success_after_failures(self):
        """Test successful execution after initial failures"""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        handler = RetryHandler(config)
        
        call_count = 0
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TransientError("Temporary failure")
            return "success"
        
        result = handler.retry(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    def test_retry_exhaustion(self):
        """Test retry exhaustion"""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        handler = RetryHandler(config)
        
        def always_fail():
            raise TransientError("Always fails")
        
        with pytest.raises(TransientError):
            handler.retry(always_fail)
    
    def test_no_retry_for_non_transient_errors(self):
        """Test that non-transient errors are not retried"""
        config = RetryConfig(max_attempts=3)
        handler = RetryHandler(config)
        
        call_count = 0
        def non_transient_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-transient error")
        
        with pytest.raises(ValueError):
            handler.retry(non_transient_fail)
        
        assert call_count == 1  # Should not retry


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_normal_operation(self):
        """Test normal operation in closed state"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)
        
        def success_func():
            return "success"
        
        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.state.value == "closed"
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures"""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)
        
        def fail_func():
            raise Exception("Test failure")
        
        # First failure
        with pytest.raises(Exception):
            breaker.call(fail_func)
        assert breaker.state.value == "closed"
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            breaker.call(fail_func)
        assert breaker.state.value == "open"
        
        # Third call should be rejected immediately
        with pytest.raises(ExternalServiceError):
            breaker.call(fail_func)


class TestResourceMonitor:
    """Test resource monitoring functionality"""
    
    def test_resource_usage_collection(self):
        """Test resource usage data collection"""
        limits = ResourceLimits(max_memory_percent=50.0)
        monitor = ResourceMonitor(limits)
        
        usage = monitor.get_current_usage()
        
        assert 'memory_percent' in usage
        assert 'cpu_percent' in usage
        assert 'disk_percent' in usage
        assert isinstance(usage['memory_percent'], (int, float))
    
    def test_resource_limit_checking(self):
        """Test resource limit violation detection"""
        limits = ResourceLimits(max_memory_percent=1.0)  # Very low limit
        monitor = ResourceMonitor(limits)
        
        usage = {'memory_percent': 50.0, 'cpu_percent': 10.0}
        violations = monitor.check_limits(usage)
        
        assert 'memory_percent' in violations
        assert violations['memory_percent'] == 50.0


class TestProcessingQueue:
    """Test processing queue functionality"""
    
    def test_task_priority_ordering(self):
        """Test that tasks are processed in priority order"""
        queue = ProcessingQueue()
        
        # Add tasks with different priorities
        low_task = ProcessingTask(
            episode_id="low",
            stage=ProcessingStage.DISCOVERED,
            priority=Priority.LOW,
            created_at=time.time(),
            func=lambda: "low"
        )
        
        high_task = ProcessingTask(
            episode_id="high",
            stage=ProcessingStage.DISCOVERED,
            priority=Priority.HIGH,
            created_at=time.time(),
            func=lambda: "high"
        )
        
        # Add low priority first
        queue.add_task(low_task)
        queue.add_task(high_task)
        
        # High priority should come out first
        first_task = queue.get_task(timeout=1.0)
        assert first_task.episode_id == "high"
        
        second_task = queue.get_task(timeout=1.0)
        assert second_task.episode_id == "low"


class TestPipelineReliabilityManager:
    """Test integrated reliability management"""
    
    def test_initialization(self):
        """Test reliability manager initialization"""
        config = PipelineReliabilityConfig(
            max_concurrent_episodes=1,
            enable_system_monitoring=False  # Disable for testing
        )
        
        manager = PipelineReliabilityManager(config)
        
        # Don't actually initialize to avoid background threads in tests
        # Just test the configuration
        assert manager.config.max_concurrent_episodes == 1
        assert manager.config.enable_system_monitoring is False
    
    def test_system_health_reporting(self):
        """Test system health status reporting"""
        config = PipelineReliabilityConfig(
            enable_system_monitoring=False  # Disable for testing
        )
        
        manager = PipelineReliabilityManager(config)
        manager.initialize()
        
        health = manager.get_system_health()
        
        assert 'timestamp' in health
        assert 'initialized' in health
        assert health['initialized'] is True
        
        # Cleanup
        manager.shutdown()
    
    @patch('src.core.resource_manager.default_concurrency_controller')
    def test_reliability_context(self, mock_controller):
        """Test reliability context manager"""
        config = PipelineReliabilityConfig(
            enable_system_monitoring=False
        )
        
        manager = PipelineReliabilityManager(config)
        manager.initialize()
        
        # Mock resource availability
        mock_controller.resource_monitor.should_allow_new_task.return_value = True
        
        episode_id = "test_episode"
        stage = ProcessingStage.DISCOVERED
        
        with manager.reliability_context(episode_id, stage) as context:
            assert context is manager
        
        # Cleanup
        manager.shutdown()


class TestServiceHealthMonitor:
    """Test service health monitoring"""
    
    def test_service_registration(self):
        """Test service registration and health tracking"""
        monitor = ServiceHealthMonitor()
        
        # Register service
        monitor.register_service("test_service")
        
        # Check initial state
        health = monitor.get_service_health("test_service")
        assert health is not None
        assert health.service_name == "test_service"
        assert health.is_healthy is True
        assert health.failure_count == 0
    
    def test_success_recording(self):
        """Test recording successful service calls"""
        monitor = ServiceHealthMonitor()
        
        monitor.record_success("test_service", 0.5)
        
        health = monitor.get_service_health("test_service")
        assert health.success_count == 1
        assert health.is_healthy is True
        assert len(health.response_times) == 1
        assert health.response_times[0] == 0.5
    
    def test_failure_recording(self):
        """Test recording failed service calls"""
        monitor = ServiceHealthMonitor()
        
        # Record multiple failures
        for i in range(4):
            monitor.record_failure("test_service", f"Error {i}")
        
        health = monitor.get_service_health("test_service")
        assert health.failure_count == 4
        assert health.is_healthy is False  # Should be marked unhealthy after 3+ failures
        assert health.last_error == "Error 3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])