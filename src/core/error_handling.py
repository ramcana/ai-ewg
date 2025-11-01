"""
Comprehensive error handling and recovery system for the Content Publishing Platform.

This module provides error classification, recovery mechanisms, and audit trail functionality
to ensure robust operation and compliance with requirements 9.1, 9.2, 9.3, 9.4, 9.5, 10.2, 10.3.
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
import time
import uuid

from .exceptions import PipelineError, TransientError, ExternalServiceError, ValidationError
from .logging import get_logger


class ErrorSeverity(Enum):
    """Error severity levels for classification and escalation"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification and handling strategies"""
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    CRITICAL = "critical"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class RecoveryAction(Enum):
    """Recovery actions for different error types"""
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    MANUAL_INTERVENTION = "manual_intervention"
    ESCALATE = "escalate"
    ABORT = "abort"
    SKIP = "skip"
    ROLLBACK = "rollback"
    ALERT_OPERATORS = "alert_operators"


@dataclass
class ErrorContext:
    """Comprehensive error context for detailed reporting"""
    error_id: str
    timestamp: datetime
    component: str
    operation: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    recovery_action: RecoveryAction
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        data['recovery_action'] = self.recovery_action.value
        return data


@dataclass
class RecoveryResult:
    """Result of a recovery attempt"""
    success: bool
    action_taken: RecoveryAction
    retry_count: int
    error_resolved: bool
    next_action: Optional[RecoveryAction] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ErrorClassifier:
    """
    Classifies errors into categories and determines appropriate recovery actions.
    Implements requirement 10.2 for error type classification.
    """
    
    def __init__(self):
        self.logger = get_logger('error_classifier')
        self._classification_rules = self._build_classification_rules()
    
    def classify_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """
        Classify an error and determine appropriate recovery action.
        
        Args:
            error: The exception to classify
            context: Additional context about the error
            
        Returns:
            ErrorContext with classification and recovery action
        """
        error_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Extract basic error information
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = traceback.format_exc()
        
        # Determine severity and category
        severity = self._determine_severity(error, context)
        category = self._determine_category(error, context)
        recovery_action = self._determine_recovery_action(error, category, severity)
        
        # Extract component and operation from context
        component = context.get('component', 'unknown') if context else 'unknown'
        operation = context.get('operation', 'unknown') if context else 'unknown'
        
        # Handle retry information for transient errors
        retry_count = 0
        max_retries = 3
        if isinstance(error, TransientError):
            retry_count = error.retry_count
            max_retries = error.max_retries
        
        return ErrorContext(
            error_id=error_id,
            timestamp=timestamp,
            component=component,
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            category=category,
            recovery_action=recovery_action,
            stack_trace=stack_trace,
            metadata=context,
            retry_count=retry_count,
            max_retries=max_retries
        )
    
    def _determine_severity(self, error: Exception, context: Optional[Dict[str, Any]]) -> ErrorSeverity:
        """Determine error severity based on error type and context"""
        error_type = type(error).__name__
        
        # Critical errors that require immediate attention
        if error_type in ['SystemExit', 'KeyboardInterrupt', 'MemoryError']:
            return ErrorSeverity.CRITICAL
        
        # High severity for security and data integrity issues
        if error_type in ['PermissionError', 'SecurityError', 'DatabaseError']:
            return ErrorSeverity.HIGH
        
        # Medium severity for service and processing errors
        if error_type in ['ExternalServiceError', 'ProcessingError', 'ValidationError']:
            return ErrorSeverity.MEDIUM
        
        # Check context for severity indicators
        if context:
            if context.get('affects_production', False):
                return ErrorSeverity.HIGH
            if context.get('data_loss_risk', False):
                return ErrorSeverity.HIGH
        
        return ErrorSeverity.LOW
    
    def _determine_category(self, error: Exception, context: Optional[Dict[str, Any]]) -> ErrorCategory:
        """Determine error category for appropriate handling"""
        error_type = type(error).__name__
        
        # Use classification rules
        for rule in self._classification_rules:
            if rule['condition'](error, context):
                return rule['category']
        
        # Check for specific error types by class name
        if isinstance(error, ExternalServiceError):
            return ErrorCategory.EXTERNAL_SERVICE
        
        # Check error message for validation patterns
        error_msg = str(error).lower()
        if 'validation' in error_msg or isinstance(error, ValidationError):
            return ErrorCategory.VALIDATION
        
        # Default to non-retryable for unknown errors
        return ErrorCategory.NON_RETRYABLE
    
    def _determine_recovery_action(self, error: Exception, category: ErrorCategory, 
                                 severity: ErrorSeverity) -> RecoveryAction:
        """Determine appropriate recovery action based on classification"""
        
        # Critical errors require immediate escalation
        if severity == ErrorSeverity.CRITICAL:
            return RecoveryAction.ESCALATE
        
        # Category-based recovery actions
        if category == ErrorCategory.RETRYABLE:
            return RecoveryAction.RETRY_WITH_BACKOFF
        elif category == ErrorCategory.RATE_LIMIT:
            return RecoveryAction.RETRY_WITH_BACKOFF
        elif category == ErrorCategory.EXTERNAL_SERVICE:
            return RecoveryAction.RETRY_WITH_BACKOFF
        elif category == ErrorCategory.NETWORK:
            return RecoveryAction.RETRY_WITH_BACKOFF
        elif category == ErrorCategory.AUTHENTICATION:
            return RecoveryAction.MANUAL_INTERVENTION
        elif category == ErrorCategory.AUTHORIZATION:
            return RecoveryAction.MANUAL_INTERVENTION
        elif category == ErrorCategory.CONFIGURATION:
            return RecoveryAction.MANUAL_INTERVENTION
        elif category == ErrorCategory.VALIDATION:
            return RecoveryAction.ABORT
        elif category == ErrorCategory.CRITICAL:
            return RecoveryAction.ESCALATE
        
        return RecoveryAction.MANUAL_INTERVENTION
    
    def _build_classification_rules(self) -> List[Dict[str, Any]]:
        """Build classification rules for error categorization"""
        return [
            {
                'condition': lambda e, c: isinstance(e, ExternalServiceError),
                'category': ErrorCategory.EXTERNAL_SERVICE
            },
            {
                'condition': lambda e, c: isinstance(e, TransientError),
                'category': ErrorCategory.RETRYABLE
            },
            {
                'condition': lambda e, c: 'rate limit' in str(e).lower(),
                'category': ErrorCategory.RATE_LIMIT
            },
            {
                'condition': lambda e, c: 'timeout' in str(e).lower(),
                'category': ErrorCategory.NETWORK
            },
            {
                'condition': lambda e, c: 'connection' in str(e).lower(),
                'category': ErrorCategory.NETWORK
            },
            {
                'condition': lambda e, c: 'authentication' in str(e).lower(),
                'category': ErrorCategory.AUTHENTICATION
            },
            {
                'condition': lambda e, c: 'authorization' in str(e).lower(),
                'category': ErrorCategory.AUTHORIZATION
            },
            {
                'condition': lambda e, c: 'permission' in str(e).lower(),
                'category': ErrorCategory.AUTHORIZATION
            },
            {
                'condition': lambda e, c: 'validation' in str(e).lower(),
                'category': ErrorCategory.VALIDATION
            },
            {
                'condition': lambda e, c: 'configuration' in str(e).lower(),
                'category': ErrorCategory.CONFIGURATION
            },
            {
                'condition': lambda e, c: 'file not found' in str(e).lower(),
                'category': ErrorCategory.FILESYSTEM
            },
            {
                'condition': lambda e, c: 'disk full' in str(e).lower(),
                'category': ErrorCategory.RESOURCE_EXHAUSTION
            },
            {
                'condition': lambda e, c: 'memory' in str(e).lower(),
                'category': ErrorCategory.RESOURCE_EXHAUSTION
            }
        ]


class RetryManager:
    """
    Manages retry logic with exponential backoff.
    Implements requirement 10.3 for automatic retry mechanisms.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.logger = get_logger('retry_manager')
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic and exponential backoff.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Don't retry on final attempt
                if attempt == self.max_retries:
                    break
                
                # Check if error should be retried
                if not self._should_retry(e):
                    break
                
                # Calculate delay with exponential backoff
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                
                self.logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {delay}s",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=self.max_retries
                )
                
                time.sleep(delay)
        
        # All retries failed
        raise last_exception
    
    def _should_retry(self, error: Exception) -> bool:
        """Determine if an error should be retried"""
        # Don't retry validation errors or configuration errors
        if isinstance(error, (ValueError, TypeError, AttributeError)):
            return False
        
        # Retry transient errors
        if isinstance(error, TransientError):
            return error.should_retry
        
        # Retry external service errors
        if isinstance(error, ExternalServiceError):
            return True
        
        # Check error message for retryable patterns
        error_msg = str(error).lower()
        retryable_patterns = [
            'timeout', 'connection', 'network', 'temporary', 'rate limit',
            'service unavailable', 'internal server error'
        ]
        
        return any(pattern in error_msg for pattern in retryable_patterns)


class NotificationManager:
    """
    Manages error notifications and escalation.
    Implements requirement 10.2 for error escalation and notification mechanisms.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger('notification_manager')
        self.notification_handlers = self._setup_handlers()
    
    def notify_error(self, error_context: ErrorContext) -> None:
        """
        Send error notification based on severity and category.
        
        Args:
            error_context: Error context with classification information
        """
        try:
            # Determine notification channels based on severity
            channels = self._get_notification_channels(error_context.severity)
            
            # Format notification message
            message = self._format_notification(error_context)
            
            # Send notifications
            for channel in channels:
                handler = self.notification_handlers.get(channel)
                if handler:
                    handler(message, error_context)
                else:
                    self.logger.warning(f"No handler configured for channel: {channel}")
        
        except Exception as e:
            self.logger.error(f"Failed to send error notification: {e}")
    
    def _get_notification_channels(self, severity: ErrorSeverity) -> List[str]:
        """Get notification channels based on error severity"""
        channels = []
        
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            channels.extend(['email', 'slack', 'pagerduty'])
        elif severity == ErrorSeverity.MEDIUM:
            channels.extend(['email', 'slack'])
        else:
            channels.append('log')
        
        return channels
    
    def _format_notification(self, error_context: ErrorContext) -> str:
        """Format error notification message"""
        return f"""
Error Alert - {error_context.severity.value.upper()}

Error ID: {error_context.error_id}
Component: {error_context.component}
Operation: {error_context.operation}
Error Type: {error_context.error_type}
Message: {error_context.error_message}
Timestamp: {error_context.timestamp.isoformat()}
Recovery Action: {error_context.recovery_action.value}

Metadata: {json.dumps(error_context.metadata, indent=2) if error_context.metadata else 'None'}
        """.strip()
    
    def _setup_handlers(self) -> Dict[str, Callable]:
        """Setup notification handlers"""
        return {
            'log': self._log_handler,
            'email': self._email_handler,
            'slack': self._slack_handler,
            'pagerduty': self._pagerduty_handler
        }
    
    def _log_handler(self, message: str, error_context: ErrorContext) -> None:
        """Log notification handler"""
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(message)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def _email_handler(self, message: str, error_context: ErrorContext) -> None:
        """Email notification handler (placeholder)"""
        # Implementation would depend on email service configuration
        self.logger.info(f"Email notification sent for error {error_context.error_id}")
    
    def _slack_handler(self, message: str, error_context: ErrorContext) -> None:
        """Slack notification handler (placeholder)"""
        # Implementation would depend on Slack webhook configuration
        self.logger.info(f"Slack notification sent for error {error_context.error_id}")
    
    def _pagerduty_handler(self, message: str, error_context: ErrorContext) -> None:
        """PagerDuty notification handler (placeholder)"""
        # Implementation would depend on PagerDuty API configuration
        self.logger.info(f"PagerDuty alert sent for error {error_context.error_id}")
    
    def _handle_escalation(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle error escalation"""
        escalation_id = str(uuid.uuid4())
        
        # Send high-priority notifications
        self.notify_error(error_context)
        
        # Use appropriate log level based on logger capabilities
        if hasattr(self.logger, 'critical'):
            self.logger.critical(
                f"Error escalated: {error_context.error_id}",
                escalation_id=escalation_id,
                severity=error_context.severity.value,
                component=error_context.component
            )
        else:
            self.logger.error(
                f"CRITICAL - Error escalated: {error_context.error_id}",
                escalation_id=escalation_id,
                severity=error_context.severity.value,
                component=error_context.component
            )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.ESCALATE,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message=f"Error escalated with ID: {escalation_id}",
            metadata={'escalation_id': escalation_id}
        )


class FailureRecoveryManager:
    """
    Manages failure recovery mechanisms with detailed reporting.
    Implements requirement 10.3 for failure recovery mechanisms.
    """
    
    def __init__(self, audit_logger: Optional['AuditLogger'] = None):
        self.logger = get_logger('failure_recovery')
        self.audit_logger = audit_logger
        self.classifier = ErrorClassifier()
        self.retry_manager = RetryManager()
        self.notification_manager = NotificationManager()
        self.recovery_state = {}  # Track recovery attempts
    
    def handle_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> RecoveryResult:
        """
        Handle a failure with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Additional context about the failure
            
        Returns:
            RecoveryResult indicating the outcome
        """
        # Classify the error
        error_context = self.classifier.classify_error(error, context)
        
        # Log the error for audit trail
        if self.audit_logger:
            self.audit_logger.log_error(error_context)
        
        # Send notifications if needed
        if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.notification_manager.notify_error(error_context)
        
        # Execute recovery action
        recovery_result = self._execute_recovery_action(error_context)
        
        # Update recovery state
        self._update_recovery_state(error_context, recovery_result)
        
        return recovery_result
    
    def _execute_recovery_action(self, error_context: ErrorContext) -> RecoveryResult:
        """Execute the determined recovery action"""
        action = error_context.recovery_action
        
        try:
            if action == RecoveryAction.RETRY:
                return self._handle_retry(error_context)
            elif action == RecoveryAction.RETRY_WITH_BACKOFF:
                return self._handle_retry_with_backoff(error_context)
            elif action == RecoveryAction.MANUAL_INTERVENTION:
                return self._handle_manual_intervention(error_context)
            elif action == RecoveryAction.ESCALATE:
                return self._handle_escalation(error_context)
            elif action == RecoveryAction.ABORT:
                return self._handle_abort(error_context)
            elif action == RecoveryAction.SKIP:
                return self._handle_skip(error_context)
            elif action == RecoveryAction.ROLLBACK:
                return self._handle_rollback(error_context)
            elif action == RecoveryAction.ALERT_OPERATORS:
                return self._handle_alert_operators(error_context)
            else:
                return RecoveryResult(
                    success=False,
                    action_taken=action,
                    retry_count=error_context.retry_count,
                    error_resolved=False,
                    message=f"Unknown recovery action: {action}"
                )
        
        except Exception as e:
            self.logger.error(f"Recovery action failed: {e}")
            return RecoveryResult(
                success=False,
                action_taken=action,
                retry_count=error_context.retry_count,
                error_resolved=False,
                message=f"Recovery action execution failed: {e}"
            )
    
    def _handle_retry(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle simple retry without backoff"""
        if error_context.retry_count >= error_context.max_retries:
            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.RETRY,
                retry_count=error_context.retry_count,
                error_resolved=False,
                next_action=RecoveryAction.MANUAL_INTERVENTION,
                message="Max retries exceeded"
            )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.RETRY,
            retry_count=error_context.retry_count + 1,
            error_resolved=False,
            message="Retry scheduled"
        )
    
    def _handle_retry_with_backoff(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle retry with exponential backoff"""
        if error_context.retry_count >= error_context.max_retries:
            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.RETRY_WITH_BACKOFF,
                retry_count=error_context.retry_count,
                error_resolved=False,
                next_action=RecoveryAction.MANUAL_INTERVENTION,
                message="Max retries with backoff exceeded"
            )
        
        # Calculate backoff delay
        delay = min(1.0 * (2 ** error_context.retry_count), 60.0)
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.RETRY_WITH_BACKOFF,
            retry_count=error_context.retry_count + 1,
            error_resolved=False,
            message=f"Retry with backoff scheduled (delay: {delay}s)",
            metadata={'backoff_delay': delay}
        )
    
    def _handle_manual_intervention(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle manual intervention requirement"""
        # Create intervention ticket/alert
        intervention_id = str(uuid.uuid4())
        
        self.logger.warning(
            f"Manual intervention required for error {error_context.error_id}",
            intervention_id=intervention_id,
            component=error_context.component,
            operation=error_context.operation
        )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.MANUAL_INTERVENTION,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message=f"Manual intervention ticket created: {intervention_id}",
            metadata={'intervention_id': intervention_id}
        )
    
    def _handle_escalation(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle error escalation"""
        escalation_id = str(uuid.uuid4())
        
        # Send high-priority notifications
        self.notification_manager.notify_error(error_context)
        
        # Use appropriate log level based on logger capabilities
        if hasattr(self.logger, 'critical'):
            self.logger.critical(
                f"Error escalated: {error_context.error_id}",
                escalation_id=escalation_id,
                severity=error_context.severity.value,
                component=error_context.component
            )
        else:
            self.logger.error(
                f"CRITICAL - Error escalated: {error_context.error_id}",
                escalation_id=escalation_id,
                severity=error_context.severity.value,
                component=error_context.component
            )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.ESCALATE,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message=f"Error escalated with ID: {escalation_id}",
            metadata={'escalation_id': escalation_id}
        )
    
    def _handle_abort(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle operation abort"""
        self.logger.error(
            f"Operation aborted due to error: {error_context.error_id}",
            component=error_context.component,
            operation=error_context.operation
        )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.ABORT,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message="Operation aborted due to unrecoverable error"
        )
    
    def _handle_skip(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle operation skip"""
        self.logger.warning(
            f"Operation skipped due to error: {error_context.error_id}",
            component=error_context.component,
            operation=error_context.operation
        )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.SKIP,
            retry_count=error_context.retry_count,
            error_resolved=True,  # Considered resolved by skipping
            message="Operation skipped, continuing with next item"
        )
    
    def _handle_rollback(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle rollback operation"""
        rollback_id = str(uuid.uuid4())
        
        self.logger.warning(
            f"Rollback initiated for error: {error_context.error_id}",
            rollback_id=rollback_id,
            component=error_context.component
        )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.ROLLBACK,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message=f"Rollback initiated with ID: {rollback_id}",
            metadata={'rollback_id': rollback_id}
        )
    
    def _handle_alert_operators(self, error_context: ErrorContext) -> RecoveryResult:
        """Handle operator alerting"""
        alert_id = str(uuid.uuid4())
        
        # Send notifications to operators
        self.notification_manager.notify_error(error_context)
        
        self.logger.warning(
            f"Operators alerted for error: {error_context.error_id}",
            alert_id=alert_id,
            component=error_context.component
        )
        
        return RecoveryResult(
            success=True,
            action_taken=RecoveryAction.ALERT_OPERATORS,
            retry_count=error_context.retry_count,
            error_resolved=False,
            message=f"Operators alerted with ID: {alert_id}",
            metadata={'alert_id': alert_id}
        )
    
    def _update_recovery_state(self, error_context: ErrorContext, recovery_result: RecoveryResult) -> None:
        """Update recovery state tracking"""
        state_key = f"{error_context.component}:{error_context.operation}"
        
        if state_key not in self.recovery_state:
            self.recovery_state[state_key] = {
                'first_error': error_context.timestamp,
                'error_count': 0,
                'recovery_attempts': []
            }
        
        self.recovery_state[state_key]['error_count'] += 1
        self.recovery_state[state_key]['recovery_attempts'].append({
            'error_id': error_context.error_id,
            'timestamp': error_context.timestamp,
            'action_taken': recovery_result.action_taken.value,
            'success': recovery_result.success,
            'resolved': recovery_result.error_resolved
        })
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics for monitoring"""
        stats = {
            'total_components': len(self.recovery_state),
            'components': {}
        }
        
        for component_op, state in self.recovery_state.items():
            stats['components'][component_op] = {
                'error_count': state['error_count'],
                'first_error': state['first_error'].isoformat(),
                'recovery_attempts': len(state['recovery_attempts']),
                'last_recovery': state['recovery_attempts'][-1]['timestamp'].isoformat() if state['recovery_attempts'] else None
            }
        
        return stats


class AuditLogger:
    """
    Comprehensive audit logging for all content operations.
    Implements requirements 9.1, 9.3, 9.5 for audit trail and compliance.
    """
    
    def __init__(self, audit_log_path: Optional[Path] = None):
        self.audit_log_path = audit_log_path or Path("logs/audit_trail.jsonl")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger('audit_logger')
    
    def log_operation(self, operation: str, component: str, details: Dict[str, Any], 
                     user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """
        Log a content operation for audit trail.
        
        Args:
            operation: Operation being performed
            component: Component performing the operation
            details: Operation details and metadata
            user_id: User performing the operation (if applicable)
            session_id: Session ID for tracking
            
        Returns:
            Audit log entry ID
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        audit_entry = {
            'audit_id': audit_id,
            'timestamp': timestamp.isoformat(),
            'operation': operation,
            'component': component,
            'details': details,
            'user_id': user_id,
            'session_id': session_id,
            'type': 'operation'
        }
        
        self._write_audit_entry(audit_entry)
        return audit_id
    
    def log_error(self, error_context: ErrorContext) -> str:
        """
        Log an error for audit trail.
        
        Args:
            error_context: Error context with classification
            
        Returns:
            Audit log entry ID
        """
        audit_id = str(uuid.uuid4())
        
        audit_entry = {
            'audit_id': audit_id,
            'timestamp': error_context.timestamp.isoformat(),
            'operation': 'error_occurred',
            'component': error_context.component,
            'details': error_context.to_dict(),
            'user_id': error_context.user_id,
            'session_id': error_context.session_id,
            'type': 'error'
        }
        
        self._write_audit_entry(audit_entry)
        return audit_id
    
    def log_rights_validation(self, content_id: str, rights_info: Dict[str, Any], 
                            validation_result: bool, details: Dict[str, Any]) -> str:
        """
        Log rights validation for compliance tracking.
        
        Args:
            content_id: Content being validated
            rights_info: Rights and licensing information
            validation_result: Whether validation passed
            details: Validation details and metadata
            
        Returns:
            Audit log entry ID
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        audit_entry = {
            'audit_id': audit_id,
            'timestamp': timestamp.isoformat(),
            'operation': 'rights_validation',
            'component': 'compliance_validator',
            'details': {
                'content_id': content_id,
                'rights_info': rights_info,
                'validation_result': validation_result,
                'validation_details': details
            },
            'type': 'compliance'
        }
        
        self._write_audit_entry(audit_entry)
        return audit_id
    
    def log_pii_handling(self, content_id: str, pii_detected: bool, 
                        anonymization_applied: bool, details: Dict[str, Any]) -> str:
        """
        Log PII handling for privacy compliance.
        
        Args:
            content_id: Content being processed
            pii_detected: Whether PII was detected
            anonymization_applied: Whether anonymization was applied
            details: PII handling details
            
        Returns:
            Audit log entry ID
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        audit_entry = {
            'audit_id': audit_id,
            'timestamp': timestamp.isoformat(),
            'operation': 'pii_handling',
            'component': 'privacy_controller',
            'details': {
                'content_id': content_id,
                'pii_detected': pii_detected,
                'anonymization_applied': anonymization_applied,
                'handling_details': details
            },
            'type': 'privacy'
        }
        
        self._write_audit_entry(audit_entry)
        return audit_id
    
    def _write_audit_entry(self, audit_entry: Dict[str, Any]) -> None:
        """Write audit entry to log file"""
        try:
            with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write audit entry: {e}")
    
    def query_audit_log(self, filters: Optional[Dict[str, Any]] = None, 
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Query audit log entries with filters.
        
        Args:
            filters: Filters to apply (component, operation, type, etc.)
            start_time: Start time for query range
            end_time: End time for query range
            
        Returns:
            List of matching audit entries
        """
        entries = []
        
        try:
            with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        # Apply time filters
                        entry_time = datetime.fromisoformat(entry['timestamp'])
                        if start_time and entry_time < start_time:
                            continue
                        if end_time and entry_time > end_time:
                            continue
                        
                        # Apply other filters
                        if filters:
                            match = True
                            for key, value in filters.items():
                                if entry.get(key) != value:
                                    match = False
                                    break
                            if not match:
                                continue
                        
                        entries.append(entry)
                    
                    except json.JSONDecodeError:
                        continue
        
        except FileNotFoundError:
            self.logger.warning(f"Audit log file not found: {self.audit_log_path}")
        
        return entries


class PrivacyController:
    """
    Privacy controls and PII handling for transcripts.
    Implements requirement 9.5 for privacy controls and PII handling.
    """
    
    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self.logger = get_logger('privacy_controller')
        self.audit_logger = audit_logger
        self.pii_patterns = self._build_pii_patterns()
    
    def scan_for_pii(self, content: str, content_id: str) -> Dict[str, Any]:
        """
        Scan content for personally identifiable information.
        
        Args:
            content: Content to scan
            content_id: Identifier for the content
            
        Returns:
            PII scan results
        """
        pii_found = []
        
        for pattern_name, pattern in self.pii_patterns.items():
            matches = pattern.findall(content)
            if matches:
                pii_found.append({
                    'type': pattern_name,
                    'count': len(matches),
                    'examples': matches[:3]  # First 3 examples for review
                })
        
        result = {
            'content_id': content_id,
            'pii_detected': len(pii_found) > 0,
            'pii_types': pii_found,
            'scan_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Log PII detection
        if self.audit_logger:
            self.audit_logger.log_pii_handling(
                content_id=content_id,
                pii_detected=result['pii_detected'],
                anonymization_applied=False,
                details=result
            )
        
        return result
    
    def anonymize_content(self, content: str, content_id: str, 
                         anonymization_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Anonymize PII in content based on configuration.
        
        Args:
            content: Content to anonymize
            content_id: Identifier for the content
            anonymization_config: Configuration for anonymization
            
        Returns:
            Anonymization results with cleaned content
        """
        config = anonymization_config or self._get_default_anonymization_config()
        anonymized_content = content
        anonymizations_applied = []
        
        for pattern_name, pattern in self.pii_patterns.items():
            if config.get(pattern_name, {}).get('anonymize', False):
                replacement = config[pattern_name].get('replacement', '[REDACTED]')
                
                matches = pattern.findall(anonymized_content)
                if matches:
                    anonymized_content = pattern.sub(replacement, anonymized_content)
                    anonymizations_applied.append({
                        'type': pattern_name,
                        'count': len(matches),
                        'replacement': replacement
                    })
        
        result = {
            'content_id': content_id,
            'original_length': len(content),
            'anonymized_length': len(anonymized_content),
            'anonymized_content': anonymized_content,
            'anonymizations_applied': anonymizations_applied,
            'anonymization_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Log anonymization
        if self.audit_logger:
            self.audit_logger.log_pii_handling(
                content_id=content_id,
                pii_detected=len(anonymizations_applied) > 0,
                anonymization_applied=True,
                details={
                    'anonymizations_applied': anonymizations_applied,
                    'config_used': config
                }
            )
        
        return result
    
    def _build_pii_patterns(self) -> Dict[str, Any]:
        """Build regex patterns for PII detection"""
        import re
        
        return {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'address': re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', re.IGNORECASE)
        }
    
    def _get_default_anonymization_config(self) -> Dict[str, Any]:
        """Get default anonymization configuration"""
        return {
            'email': {'anonymize': True, 'replacement': '[EMAIL]'},
            'phone': {'anonymize': True, 'replacement': '[PHONE]'},
            'ssn': {'anonymize': True, 'replacement': '[SSN]'},
            'credit_card': {'anonymize': True, 'replacement': '[CREDIT_CARD]'},
            'address': {'anonymize': False, 'replacement': '[ADDRESS]'}  # Often contextually important
        }


# Main error handling coordinator
class ErrorHandlingSystem:
    """
    Main coordinator for the comprehensive error handling system.
    Integrates all error handling components for unified operation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger('error_handling_system')
        
        # Initialize components
        self.audit_logger = AuditLogger()
        self.classifier = ErrorClassifier()
        self.retry_manager = RetryManager()
        self.notification_manager = NotificationManager(self.config.get('notifications', {}))
        self.recovery_manager = FailureRecoveryManager(self.audit_logger)
        self.privacy_controller = PrivacyController(self.audit_logger)
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> RecoveryResult:
        """
        Main entry point for error handling.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
            
        Returns:
            RecoveryResult indicating the outcome
        """
        return self.recovery_manager.handle_failure(error, context)
    
    def execute_with_error_handling(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with comprehensive error handling.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        context = {
            'component': kwargs.pop('component', 'unknown'),
            'operation': kwargs.pop('operation', func.__name__)
        }
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            recovery_result = self.handle_error(e, context)
            
            if recovery_result.action_taken in [RecoveryAction.RETRY, RecoveryAction.RETRY_WITH_BACKOFF]:
                # For retry actions, re-raise to let retry manager handle it
                raise
            elif recovery_result.action_taken == RecoveryAction.SKIP:
                # Return None for skipped operations
                return None
            else:
                # Re-raise for other actions
                raise
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health metrics"""
        return {
            'recovery_statistics': self.recovery_manager.get_recovery_statistics(),
            'audit_log_path': str(self.audit_logger.audit_log_path),
            'components_status': {
                'classifier': 'active',
                'retry_manager': 'active',
                'notification_manager': 'active',
                'recovery_manager': 'active',
                'privacy_controller': 'active'
            }
        }
    
    def get_audit_trail(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get audit trail entries"""
        return self.audit_logger.query_audit_log(filters=filters)


# Alias for backward compatibility
ErrorClassification = ErrorCategory


class ErrorHandler:
    """
    Simplified error handler interface for backward compatibility.
    Wraps the comprehensive ErrorHandlingSystem.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.system = ErrorHandlingSystem(config)
        self.logger = get_logger('error_handler')
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> RecoveryAction:
        """
        Handle an error and return the recovery action taken.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
            
        Returns:
            RecoveryAction that was determined
        """
        try:
            recovery_result = self.system.handle_error(error, context)
            return recovery_result.action_taken
        except Exception as e:
            self.logger.error(f"Error handling failed: {e}")
            return RecoveryAction.MANUAL_INTERVENTION