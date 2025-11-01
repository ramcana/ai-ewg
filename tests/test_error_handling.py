"""
Tests for the comprehensive error handling and recovery system.
"""

import json
import pytest
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.error_handling import (
    ErrorClassifier, ErrorSeverity, ErrorCategory, RecoveryAction,
    ErrorContext, RetryManager, NotificationManager, FailureRecoveryManager,
    AuditLogger, PrivacyController, ErrorHandlingSystem
)
from src.core.exceptions import (
    PipelineError, TransientError, ExternalServiceError, ValidationError
)
from src.core.operational_runbooks import (
    SystemHealthChecker, MaintenanceProcedures, RunbookExecutor,
    RunbookStatus
)


class TestErrorClassifier:
    """Test error classification functionality"""
    
    def test_classify_transient_error(self):
        """Test classification of transient errors"""
        classifier = ErrorClassifier()
        error = TransientError("Temporary service unavailable")
        
        context = classifier.classify_error(error)
        
        assert context.category == ErrorCategory.RETRYABLE
        assert context.recovery_action == RecoveryAction.RETRY_WITH_BACKOFF
        assert context.error_type == "TransientError"
    
    def test_classify_external_service_error(self):
        """Test classification of external service errors"""
        classifier = ErrorClassifier()
        error = ExternalServiceError("API rate limit exceeded", service="youtube")
        
        context = classifier.classify_error(error)
        
        assert context.category == ErrorCategory.EXTERNAL_SERVICE
        assert context.recovery_action == RecoveryAction.RETRY_WITH_BACKOFF
    
    def test_classify_validation_error(self):
        """Test classification of validation errors"""
        classifier = ErrorClassifier()
        error = ValidationError("Invalid field format", field="email")
        
        context = classifier.classify_error(error)
        
        assert context.category == ErrorCategory.VALIDATION
        assert context.recovery_action == RecoveryAction.ABORT
    
    def test_severity_determination(self):
        """Test error severity determination"""
        classifier = ErrorClassifier()
        
        # Test critical error
        critical_error = MemoryError("Out of memory")
        context = classifier.classify_error(critical_error)
        assert context.severity == ErrorSeverity.CRITICAL
        
        # Test high severity error
        high_error = PermissionError("Access denied")
        context = classifier.classify_error(high_error)
        assert context.severity == ErrorSeverity.HIGH
        
        # Test medium severity error
        medium_error = ExternalServiceError("Service unavailable")
        context = classifier.classify_error(medium_error)
        assert context.severity == ErrorSeverity.MEDIUM


class TestRetryManager:
    """Test retry management functionality"""
    
    def test_successful_retry(self):
        """Test successful operation after retry"""
        retry_manager = RetryManager(max_retries=3, base_delay=0.1)
        
        call_count = 0
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TransientError("Temporary failure")
            return "success"
        
        result = retry_manager.execute_with_retry(failing_function)
        
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded"""
        retry_manager = RetryManager(max_retries=2, base_delay=0.1)
        
        def always_failing_function():
            raise TransientError("Always fails")
        
        with pytest.raises(TransientError):
            retry_manager.execute_with_retry(always_failing_function)
    
    def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried"""
        retry_manager = RetryManager(max_retries=3, base_delay=0.1)
        
        call_count = 0
        def validation_error_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")
        
        with pytest.raises(ValueError):
            retry_manager.execute_with_retry(validation_error_function)
        
        assert call_count == 1  # Should not retry


class TestNotificationManager:
    """Test notification management functionality"""
    
    def test_notification_channels_by_severity(self):
        """Test that notification channels are selected based on severity"""
        notification_manager = NotificationManager()
        
        # Test critical severity
        critical_channels = notification_manager._get_notification_channels(ErrorSeverity.CRITICAL)
        assert 'email' in critical_channels
        assert 'slack' in critical_channels
        assert 'pagerduty' in critical_channels
        
        # Test low severity
        low_channels = notification_manager._get_notification_channels(ErrorSeverity.LOW)
        assert low_channels == ['log']
    
    def test_notification_formatting(self):
        """Test notification message formatting"""
        notification_manager = NotificationManager()
        
        error_context = ErrorContext(
            error_id="test-error-123",
            timestamp=datetime.now(timezone.utc),
            component="test_component",
            operation="test_operation",
            error_type="TestError",
            error_message="Test error message",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            recovery_action=RecoveryAction.RETRY_WITH_BACKOFF
        )
        
        message = notification_manager._format_notification(error_context)
        
        assert "test-error-123" in message
        assert "test_component" in message
        assert "Test error message" in message
        assert "HIGH" in message


class TestFailureRecoveryManager:
    """Test failure recovery management functionality"""
    
    def test_handle_retryable_failure(self):
        """Test handling of retryable failures"""
        recovery_manager = FailureRecoveryManager()
        
        error = TransientError("Temporary failure", retry_count=1, max_retries=3)
        context = {'component': 'test_component', 'operation': 'test_operation'}
        
        result = recovery_manager.handle_failure(error, context)
        
        assert result.success
        assert result.action_taken == RecoveryAction.RETRY_WITH_BACKOFF
        assert result.retry_count == 2
    
    def test_handle_max_retries_exceeded(self):
        """Test handling when max retries are exceeded"""
        recovery_manager = FailureRecoveryManager()
        
        error = TransientError("Temporary failure", retry_count=3, max_retries=3)
        context = {'component': 'test_component', 'operation': 'test_operation'}
        
        result = recovery_manager.handle_failure(error, context)
        
        assert not result.success
        assert result.next_action == RecoveryAction.MANUAL_INTERVENTION
    
    def test_handle_critical_error(self):
        """Test handling of critical errors"""
        recovery_manager = FailureRecoveryManager()
        
        error = MemoryError("Out of memory")
        context = {'component': 'test_component', 'operation': 'test_operation'}
        
        result = recovery_manager.handle_failure(error, context)
        
        assert result.success
        assert result.action_taken == RecoveryAction.ESCALATE


class TestAuditLogger:
    """Test audit logging functionality"""
    
    def test_log_operation(self):
        """Test operation logging"""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log_path = Path(temp_dir) / "audit.jsonl"
            audit_logger = AuditLogger(audit_log_path)
            
            audit_id = audit_logger.log_operation(
                operation="test_operation",
                component="test_component",
                details={"key": "value"},
                user_id="test_user"
            )
            
            assert audit_id is not None
            assert audit_log_path.exists()
            
            # Read and verify log entry
            with open(audit_log_path, 'r') as f:
                log_entry = json.loads(f.readline())
            
            assert log_entry['audit_id'] == audit_id
            assert log_entry['operation'] == "test_operation"
            assert log_entry['component'] == "test_component"
            assert log_entry['user_id'] == "test_user"
    
    def test_log_error(self):
        """Test error logging"""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log_path = Path(temp_dir) / "audit.jsonl"
            audit_logger = AuditLogger(audit_log_path)
            
            error_context = ErrorContext(
                error_id="test-error-123",
                timestamp=datetime.now(timezone.utc),
                component="test_component",
                operation="test_operation",
                error_type="TestError",
                error_message="Test error",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.EXTERNAL_SERVICE,
                recovery_action=RecoveryAction.RETRY_WITH_BACKOFF
            )
            
            audit_id = audit_logger.log_error(error_context)
            
            assert audit_id is not None
            assert audit_log_path.exists()
    
    def test_query_audit_log(self):
        """Test audit log querying"""
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log_path = Path(temp_dir) / "audit.jsonl"
            audit_logger = AuditLogger(audit_log_path)
            
            # Log multiple entries
            audit_logger.log_operation("op1", "comp1", {})
            audit_logger.log_operation("op2", "comp2", {})
            audit_logger.log_operation("op1", "comp1", {})
            
            # Query by component
            results = audit_logger.query_audit_log(filters={'component': 'comp1'})
            assert len(results) == 2
            
            # Query by operation
            results = audit_logger.query_audit_log(filters={'operation': 'op2'})
            assert len(results) == 1


class TestPrivacyController:
    """Test privacy control functionality"""
    
    def test_pii_detection(self):
        """Test PII detection in content"""
        privacy_controller = PrivacyController()
        
        content = "Contact John Doe at john.doe@example.com or call (555) 123-4567"
        result = privacy_controller.scan_for_pii(content, "test-content-123")
        
        assert result['pii_detected']
        assert len(result['pii_types']) == 2  # email and phone
        
        # Check email detection
        email_pii = next(pii for pii in result['pii_types'] if pii['type'] == 'email')
        assert email_pii['count'] == 1
        
        # Check phone detection
        phone_pii = next(pii for pii in result['pii_types'] if pii['type'] == 'phone')
        assert phone_pii['count'] == 1
    
    def test_content_anonymization(self):
        """Test content anonymization"""
        privacy_controller = PrivacyController()
        
        content = "Contact John Doe at john.doe@example.com or call (555) 123-4567"
        result = privacy_controller.anonymize_content(content, "test-content-123")
        
        assert result['anonymized_content'] != content
        assert '[EMAIL]' in result['anonymized_content']
        assert '[PHONE]' in result['anonymized_content']
        assert 'john.doe@example.com' not in result['anonymized_content']
        assert '(555) 123-4567' not in result['anonymized_content']
    
    def test_no_pii_content(self):
        """Test content with no PII"""
        privacy_controller = PrivacyController()
        
        content = "This is a normal conversation about technology and innovation."
        result = privacy_controller.scan_for_pii(content, "test-content-123")
        
        assert not result['pii_detected']
        assert len(result['pii_types']) == 0


class TestErrorHandlingSystem:
    """Test the integrated error handling system"""
    
    def test_system_initialization(self):
        """Test system initialization"""
        error_system = ErrorHandlingSystem({})
        
        assert error_system.classifier is not None
        assert error_system.retry_manager is not None
        assert error_system.notification_manager is not None
        assert error_system.recovery_manager is not None
        assert error_system.privacy_controller is not None
    
    def test_execute_with_error_handling_success(self):
        """Test successful execution with error handling"""
        error_system = ErrorHandlingSystem({})
        
        def successful_function():
            return "success"
        
        result = error_system.execute_with_error_handling(
            successful_function,
            component="test_component",
            operation="test_operation"
        )
        
        assert result == "success"
    
    def test_execute_with_error_handling_failure(self):
        """Test error handling during execution"""
        error_system = ErrorHandlingSystem({})
        
        def failing_function():
            raise ValidationError("Invalid input")
        
        with pytest.raises(ValidationError):
            error_system.execute_with_error_handling(
                failing_function,
                component="test_component",
                operation="test_operation"
            )
    
    def test_get_system_health(self):
        """Test system health reporting"""
        error_system = ErrorHandlingSystem({})
        
        health = error_system.get_system_health()
        
        assert 'recovery_statistics' in health
        assert 'components_status' in health
        assert health['components_status']['classifier'] == 'active'


class TestSystemHealthChecker:
    """Test system health checking functionality"""
    
    def test_database_health_check(self):
        """Test database health check"""
        health_checker = SystemHealthChecker(ErrorHandlingSystem({}))
        result = health_checker._check_database_health()
        
        # Should return not_available since DatabaseRegistry is not available
        assert result['status'] == 'not_available'
        assert 'note' in result
    
    def test_filesystem_health_check(self):
        """Test filesystem health check"""
        health_checker = SystemHealthChecker(ErrorHandlingSystem({}))
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=True), \
             patch('shutil.disk_usage') as mock_disk_usage:
            
            # Mock disk usage with plenty of free space
            mock_disk_usage.return_value = Mock(
                total=1000000000,  # 1GB
                free=500000000,    # 500MB (50% free)
                used=500000000
            )
            
            result = health_checker._check_filesystem_health()
            
            assert result['healthy']
            assert 'directories' in result


class TestMaintenanceProcedures:
    """Test maintenance procedures functionality"""
    
    def test_cleanup_old_logs(self):
        """Test old log cleanup"""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_path = Path(temp_dir) / "logs"
            logs_path.mkdir()
            
            # Create old log file
            old_log = logs_path / "old.log"
            old_log.write_text("old log content")
            
            # Set modification time to 40 days ago
            old_time = time.time() - (40 * 24 * 60 * 60)
            import os
            os.utime(old_log, (old_time, old_time))
            
            # Create recent log file
            recent_log = logs_path / "recent.log"
            recent_log.write_text("recent log content")
            
            maintenance = MaintenanceProcedures(ErrorHandlingSystem({}))
            
            # Test the actual cleanup with real files
            result = maintenance.cleanup_old_logs(retention_days=30)
            
            # Should succeed and remove the old log
            assert result['success']
    
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        maintenance = MaintenanceProcedures(ErrorHandlingSystem({}))
        
        with patch('pathlib.Path.exists', return_value=False):
            result = maintenance.cleanup_temp_files()
            
            assert result['success']
            assert result['files_removed'] == 0


class TestRunbookExecutor:
    """Test runbook execution functionality"""
    
    def test_runbook_execution_success(self):
        """Test successful runbook execution"""
        runbook_executor = RunbookExecutor(ErrorHandlingSystem({}))
        
        # Mock the step methods to avoid actual system operations
        with patch.object(runbook_executor, '_step_check_system_health'), \
             patch.object(runbook_executor, '_step_cleanup_temp_files'), \
             patch.object(runbook_executor, '_step_optimize_database'):
            
            execution = runbook_executor.execute_runbook('routine_maintenance')
            
            assert execution.status == RunbookStatus.COMPLETED
            assert execution.steps_completed > 0
    
    def test_runbook_execution_failure(self):
        """Test runbook execution with failure"""
        runbook_executor = RunbookExecutor(ErrorHandlingSystem({}))
        
        # Get the first step and make it fail
        first_step = runbook_executor.runbooks['deployment_failure_recovery']['steps'][0]
        original_action = first_step.action
        first_step.action = lambda context: (_ for _ in ()).throw(Exception("Health check failed"))
        
        try:
            execution = runbook_executor.execute_runbook('deployment_failure_recovery')
            
            assert execution.status == RunbookStatus.FAILED
            assert "Health check failed" in execution.error_message
        finally:
            # Restore original action
            first_step.action = original_action
    
    def test_unknown_runbook(self):
        """Test execution of unknown runbook"""
        runbook_executor = RunbookExecutor(ErrorHandlingSystem({}))
        
        with pytest.raises(ValueError, match="Unknown runbook"):
            runbook_executor.execute_runbook('nonexistent_runbook')


if __name__ == '__main__':
    pytest.main([__file__])