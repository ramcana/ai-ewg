"""
Error handling utilities for GUI Control Panel

Provides comprehensive error handling, user feedback, and retry mechanisms
for API failures and system operations.
"""

import streamlit as st
import time
import logging
from typing import Callable, Any, Optional, Dict, List
from functools import wraps
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """Error information container"""
    message: str
    severity: ErrorSeverity
    details: Optional[str] = None
    remediation: Optional[str] = None
    retry_possible: bool = False


class ErrorHandler:
    """Centralized error handling and user feedback system"""
    
    @staticmethod
    def display_error(error_info: ErrorInfo, container=None):
        """
        Display error message with appropriate styling and remediation
        
        Args:
            error_info: Error information to display
            container: Streamlit container to display in (optional)
        """
        display_func = container if container else st
        
        if error_info.severity == ErrorSeverity.INFO:
            display_func.info(error_info.message)
        elif error_info.severity == ErrorSeverity.WARNING:
            display_func.warning(error_info.message)
        elif error_info.severity == ErrorSeverity.ERROR:
            display_func.error(error_info.message)
        elif error_info.severity == ErrorSeverity.CRITICAL:
            display_func.error(f"🚨 CRITICAL: {error_info.message}")
        
        # Show details if available
        if error_info.details:
            with display_func.expander("Error Details"):
                st.code(error_info.details)
        
        # Show remediation suggestions
        if error_info.remediation:
            display_func.info(f"💡 **Suggestion:** {error_info.remediation}")
    
    @staticmethod
    def get_api_error_info(error_message: str, status_code: Optional[int] = None) -> ErrorInfo:
        """
        Convert API error to structured error information with remediation
        
        Args:
            error_message: Error message from API
            status_code: HTTP status code (optional)
            
        Returns:
            ErrorInfo: Structured error information
        """
        # Connection errors
        if "Connection failed" in error_message or "ConnectionError" in error_message:
            return ErrorInfo(
                message="Cannot connect to AI-EWG Pipeline API",
                severity=ErrorSeverity.ERROR,
                details=error_message,
                remediation="1. Check if the API server is running on localhost:8000\n2. Verify the server is accessible\n3. Check firewall settings",
                retry_possible=True
            )
        
        # Timeout errors
        if "timeout" in error_message.lower():
            return ErrorInfo(
                message="API request timed out",
                severity=ErrorSeverity.WARNING,
                details=error_message,
                remediation="The server may be busy processing other requests. Try again in a few moments.",
                retry_possible=True
            )
        
        # HTTP status code specific errors
        if status_code:
            if status_code == 404:
                return ErrorInfo(
                    message="Resource not found",
                    severity=ErrorSeverity.WARNING,
                    details=error_message,
                    remediation="The requested episode or resource may not exist. Check the episode ID and try again.",
                    retry_possible=False
                )
            elif status_code == 500:
                return ErrorInfo(
                    message="Server internal error",
                    severity=ErrorSeverity.ERROR,
                    details=error_message,
                    remediation="The server encountered an internal error. Check server logs and try again later.",
                    retry_possible=True
                )
            elif status_code == 503:
                return ErrorInfo(
                    message="Service temporarily unavailable",
                    severity=ErrorSeverity.WARNING,
                    details=error_message,
                    remediation="The server is temporarily overloaded. Wait a few minutes and try again.",
                    retry_possible=True
                )
        
        # Generic error
        return ErrorInfo(
            message="API operation failed",
            severity=ErrorSeverity.ERROR,
            details=error_message,
            remediation="Check the error details and try again. If the problem persists, contact support.",
            retry_possible=True
        )
    
    @staticmethod
    def get_file_error_info(error_message: str, file_path: str = "") -> ErrorInfo:
        """
        Convert file operation error to structured error information
        
        Args:
            error_message: Error message from file operation
            file_path: File path that caused the error
            
        Returns:
            ErrorInfo: Structured error information
        """
        if "FileNotFoundError" in error_message or "No such file" in error_message:
            return ErrorInfo(
                message=f"File not found: {file_path}",
                severity=ErrorSeverity.WARNING,
                details=error_message,
                remediation="Check if the file exists and the path is correct. The file may not have been generated yet.",
                retry_possible=False
            )
        
        if "PermissionError" in error_message or "Permission denied" in error_message:
            return ErrorInfo(
                message=f"Permission denied accessing: {file_path}",
                severity=ErrorSeverity.ERROR,
                details=error_message,
                remediation="Check file permissions and ensure the application has read/write access to the directory.",
                retry_possible=False
            )
        
        if "OSError" in error_message or "IOError" in error_message:
            return ErrorInfo(
                message=f"File system error: {file_path}",
                severity=ErrorSeverity.ERROR,
                details=error_message,
                remediation="Check disk space and file system integrity. The storage device may be full or corrupted.",
                retry_possible=True
            )
        
        return ErrorInfo(
            message=f"File operation failed: {file_path}",
            severity=ErrorSeverity.ERROR,
            details=error_message,
            remediation="Check the error details and file path. Ensure the file system is accessible.",
            retry_possible=True
        )


class RetryHandler:
    """Retry mechanism for failed operations with user feedback"""
    
    @staticmethod
    def with_retry(
        operation: Callable,
        max_attempts: int = 3,
        delay_seconds: float = 2.0,
        operation_name: str = "Operation",
        show_progress: bool = True
    ) -> Any:
        """
        Execute operation with retry logic and user feedback
        
        Args:
            operation: Function to execute
            max_attempts: Maximum number of retry attempts
            delay_seconds: Delay between retries in seconds
            operation_name: Name of operation for user feedback
            show_progress: Whether to show progress indicators
            
        Returns:
            Result of successful operation
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                if show_progress and attempt > 0:
                    with st.spinner(f"Retrying {operation_name} (attempt {attempt + 1}/{max_attempts})..."):
                        time.sleep(delay_seconds)
                        result = operation()
                else:
                    result = operation()
                
                # Success
                if show_progress and attempt > 0:
                    st.success(f"✅ {operation_name} succeeded after {attempt + 1} attempts")
                
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"{operation_name} attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_attempts - 1:
                    if show_progress:
                        st.warning(f"⚠️ {operation_name} failed (attempt {attempt + 1}/{max_attempts}). Retrying in {delay_seconds} seconds...")
                    time.sleep(delay_seconds)
                else:
                    # Final attempt failed
                    if show_progress:
                        st.error(f"❌ {operation_name} failed after {max_attempts} attempts")
        
        # All attempts failed
        raise last_exception


class ProgressTracker:
    """Progress tracking with user feedback and error handling"""
    
    def __init__(self, total_items: int, operation_name: str = "Processing"):
        """
        Initialize progress tracker
        
        Args:
            total_items: Total number of items to process
            operation_name: Name of the operation for display
        """
        self.total_items = total_items
        self.operation_name = operation_name
        self.current_item = 0
        self.successful_items = 0
        self.failed_items = 0
        self.errors: List[ErrorInfo] = []
        
        # Create Streamlit components
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.error_container = st.container()
    
    def update(self, item_name: str, success: bool = True, error_info: Optional[ErrorInfo] = None):
        """
        Update progress for a single item
        
        Args:
            item_name: Name of the current item being processed
            success: Whether the item was processed successfully
            error_info: Error information if processing failed
        """
        self.current_item += 1
        
        if success:
            self.successful_items += 1
            self.status_text.text(f"✅ {self.operation_name}: {item_name} ({self.current_item}/{self.total_items})")
        else:
            self.failed_items += 1
            self.status_text.text(f"❌ {self.operation_name}: {item_name} failed ({self.current_item}/{self.total_items})")
            
            if error_info:
                self.errors.append(error_info)
                # Show error in container
                with self.error_container:
                    ErrorHandler.display_error(error_info)
        
        # Update progress bar
        progress = self.current_item / self.total_items
        self.progress_bar.progress(progress)
    
    def complete(self):
        """Mark processing as complete and show summary"""
        self.progress_bar.progress(1.0)
        
        if self.failed_items == 0:
            self.status_text.text(f"🎉 {self.operation_name} completed successfully! ({self.successful_items}/{self.total_items})")
            st.success(f"All {self.total_items} items processed successfully!")
        else:
            self.status_text.text(f"⚠️ {self.operation_name} completed with errors. Success: {self.successful_items}, Failed: {self.failed_items}")
            st.warning(f"Processing completed: {self.successful_items} successful, {self.failed_items} failed")
            
            # Show error summary
            if self.errors:
                with st.expander(f"Error Summary ({len(self.errors)} errors)"):
                    for i, error in enumerate(self.errors, 1):
                        st.write(f"**Error {i}:** {error.message}")
                        if error.remediation:
                            st.write(f"*Suggestion:* {error.remediation}")


def handle_api_operation(operation_name: str):
    """
    Decorator for handling API operations with comprehensive error handling
    
    Args:
        operation_name: Name of the operation for user feedback
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with st.spinner(f"Executing {operation_name}..."):
                    result = func(*args, **kwargs)
                
                # Check if result indicates success
                if hasattr(result, 'success') and not result.success:
                    error_info = ErrorHandler.get_api_error_info(
                        result.error or "Unknown API error",
                        getattr(result, 'status_code', None)
                    )
                    ErrorHandler.display_error(error_info)
                    
                    # Offer retry if possible
                    if error_info.retry_possible:
                        if st.button(f"🔄 Retry {operation_name}"):
                            st.rerun()
                    
                    return result
                
                # Success
                st.success(f"✅ {operation_name} completed successfully!")
                return result
                
            except Exception as e:
                error_info = ErrorHandler.get_api_error_info(str(e))
                ErrorHandler.display_error(error_info)
                
                # Offer retry if possible
                if error_info.retry_possible:
                    if st.button(f"🔄 Retry {operation_name}"):
                        st.rerun()
                
                raise
        
        return wrapper
    return decorator


def safe_file_operation(file_path: str, operation: Callable, operation_name: str = "File operation"):
    """
    Execute file operation with error handling
    
    Args:
        file_path: Path to the file
        operation: File operation function
        operation_name: Name of operation for user feedback
        
    Returns:
        Result of operation or None if failed
    """
    try:
        return operation(file_path)
    except Exception as e:
        error_info = ErrorHandler.get_file_error_info(str(e), file_path)
        ErrorHandler.display_error(error_info)
        return None


# Convenience functions for common error scenarios
def show_connection_error():
    """Show API connection error with remediation"""
    error_info = ErrorInfo(
        message="Cannot connect to AI-EWG Pipeline API",
        severity=ErrorSeverity.ERROR,
        remediation="1. Start the API server: python -m src.api.server\n2. Verify it's running on localhost:8000\n3. Check firewall settings",
        retry_possible=True
    )
    ErrorHandler.display_error(error_info)


def show_processing_error(episode_id: str, error_message: str):
    """Show episode processing error with remediation"""
    error_info = ErrorInfo(
        message=f"Failed to process episode {episode_id}",
        severity=ErrorSeverity.ERROR,
        details=error_message,
        remediation="1. Check episode source files exist\n2. Verify sufficient disk space\n3. Check server logs for details",
        retry_possible=True
    )
    ErrorHandler.display_error(error_info)


def show_success_notification(message: str, details: Optional[str] = None):
    """Show success notification with optional details"""
    st.success(f"✅ {message}")
    if details:
        with st.expander("Details"):
            st.write(details)