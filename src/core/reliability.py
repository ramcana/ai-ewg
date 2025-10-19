"""
Reliability features for the Video Processing Pipeline

Implements retry logic, circuit breakers, and service health monitoring
to handle transient failures and protect system resources.
"""

import asyncio
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, TypeVar, Union, List
from dataclasses import dataclass, field
from functools import wraps

from .exceptions import TransientError, ExternalServiceError, PipelineError
from .logging import get_logger

logger = get_logger('pipeline.reliability')

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_strategy: str = "exponential"  # exponential, linear, fixed


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout: float = 30.0


@dataclass
class ServiceHealth:
    """Health status of a service"""
    service_name: str
    is_healthy: bool = True
    last_check: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None
    response_times: List[float] = field(default_factory=list)
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def add_response_time(self, response_time: float) -> None:
        """Add response time measurement"""
        self.response_times.append(response_time)
        # Keep only last 100 measurements
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]


class RetryHandler:
    """Handles retry logic with exponential backoff"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        if self.config.backoff_strategy == "exponential":
            delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        elif self.config.backoff_strategy == "linear":
            delay = self.config.base_delay * attempt
        else:  # fixed
            delay = self.config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry"""
        if attempt >= self.config.max_attempts:
            return False
        
        # Always retry transient errors
        if isinstance(exception, TransientError):
            return exception.should_retry
        
        # Retry specific external service errors
        if isinstance(exception, ExternalServiceError):
            # Retry on 5xx errors, timeouts, connection errors
            if exception.status_code and 500 <= exception.status_code < 600:
                return True
            if "timeout" in str(exception).lower():
                return True
            if "connection" in str(exception).lower():
                return True
        
        # Don't retry configuration or validation errors
        from .exceptions import ConfigurationError, ValidationError
        if isinstance(exception, (ConfigurationError, ValidationError)):
            return False
        
        return False
    
    def retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Executing function {func.__name__}", 
                           attempt=attempt, 
                           max_attempts=self.config.max_attempts)
                
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"Function {func.__name__} succeeded after retry", 
                              attempt=attempt)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self.should_retry(e, attempt):
                    logger.error(f"Function {func.__name__} failed, not retrying", 
                               attempt=attempt, 
                               exception=str(e))
                    raise
                
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    logger.warning(f"Function {func.__name__} failed, retrying", 
                                 attempt=attempt, 
                                 delay=delay, 
                                 exception=str(e))
                    time.sleep(delay)
        
        # All attempts failed
        logger.error(f"Function {func.__name__} failed after all retries", 
                   attempts=self.config.max_attempts, 
                   final_exception=str(last_exception))
        raise last_exception


class CircuitBreaker:
    """Circuit breaker implementation for service protection"""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.lock = threading.Lock()
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset"""
        if self.state != CircuitState.OPEN:
            return False
        
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    def _record_success(self) -> None:
        """Record successful operation"""
        with self.lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    logger.info(f"Circuit breaker {self.name} closed after recovery")
    
    def _record_failure(self, exception: Exception) -> None:
        """Record failed operation"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.warning(f"Circuit breaker {self.name} opened after half-open failure")
            
            elif (self.state == CircuitState.CLOSED and 
                  self.failure_count >= self.config.failure_threshold):
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker {self.name} entering half-open state")
                else:
                    raise ExternalServiceError(
                        f"Circuit breaker {self.name} is open",
                        service=self.name
                    )
        
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Check for timeout
            if duration > self.config.timeout:
                raise ExternalServiceError(
                    f"Operation timed out after {duration:.2f}s",
                    service=self.name
                )
            
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure(e)
            raise
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
            }


class ServiceHealthMonitor:
    """Monitors health of external services"""
    
    def __init__(self):
        self.services: Dict[str, ServiceHealth] = {}
        self.lock = threading.Lock()
    
    def register_service(self, service_name: str) -> None:
        """Register a service for monitoring"""
        with self.lock:
            if service_name not in self.services:
                self.services[service_name] = ServiceHealth(service_name)
                logger.info(f"Registered service for monitoring: {service_name}")
    
    def record_success(self, service_name: str, response_time: float) -> None:
        """Record successful service call"""
        with self.lock:
            if service_name not in self.services:
                self.register_service(service_name)
            
            service = self.services[service_name]
            service.is_healthy = True
            service.success_count += 1
            service.failure_count = 0
            service.last_check = datetime.now()
            service.add_response_time(response_time)
            service.last_error = None
    
    def record_failure(self, service_name: str, error: str) -> None:
        """Record failed service call"""
        with self.lock:
            if service_name not in self.services:
                self.register_service(service_name)
            
            service = self.services[service_name]
            service.failure_count += 1
            service.last_check = datetime.now()
            service.last_error = error
            
            # Mark as unhealthy after multiple failures
            if service.failure_count >= 3:
                service.is_healthy = False
                logger.warning(f"Service {service_name} marked as unhealthy", 
                             failure_count=service.failure_count,
                             last_error=error)
    
    def get_service_health(self, service_name: str) -> Optional[ServiceHealth]:
        """Get health status of a service"""
        with self.lock:
            return self.services.get(service_name)
    
    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all services"""
        with self.lock:
            return {
                name: {
                    'is_healthy': service.is_healthy,
                    'last_check': service.last_check.isoformat() if service.last_check else None,
                    'failure_count': service.failure_count,
                    'success_count': service.success_count,
                    'average_response_time': service.average_response_time,
                    'last_error': service.last_error
                }
                for name, service in self.services.items()
            }
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        service = self.get_service_health(service_name)
        return service.is_healthy if service else True


class ReliabilityManager:
    """Central manager for reliability features"""
    
    def __init__(self):
        self.retry_handlers: Dict[str, RetryHandler] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_monitor = ServiceHealthMonitor()
        self.default_retry_config = RetryConfig()
        self.default_circuit_config = CircuitBreakerConfig()
    
    def get_retry_handler(self, name: str, config: Optional[RetryConfig] = None) -> RetryHandler:
        """Get or create retry handler"""
        if name not in self.retry_handlers:
            self.retry_handlers[name] = RetryHandler(config or self.default_retry_config)
        return self.retry_handlers[name]
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config or self.default_circuit_config)
            self.health_monitor.register_service(name)
        return self.circuit_breakers[name]
    
    def execute_with_reliability(self, 
                               service_name: str,
                               func: Callable[..., T],
                               *args,
                               retry_config: Optional[RetryConfig] = None,
                               circuit_config: Optional[CircuitBreakerConfig] = None,
                               **kwargs) -> T:
        """Execute function with both retry and circuit breaker protection"""
        retry_handler = self.get_retry_handler(f"{service_name}_retry", retry_config)
        circuit_breaker = self.get_circuit_breaker(service_name, circuit_config)
        
        def protected_func(*args, **kwargs):
            start_time = time.time()
            try:
                result = circuit_breaker.call(func, *args, **kwargs)
                response_time = time.time() - start_time
                self.health_monitor.record_success(service_name, response_time)
                return result
            except Exception as e:
                self.health_monitor.record_failure(service_name, str(e))
                raise
        
        return retry_handler.retry(protected_func, *args, **kwargs)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        circuit_states = {
            name: breaker.get_state() 
            for name, breaker in self.circuit_breakers.items()
        }
        
        service_health = self.health_monitor.get_all_health()
        
        # Calculate overall health score
        healthy_services = sum(1 for health in service_health.values() if health['is_healthy'])
        total_services = len(service_health)
        health_score = healthy_services / total_services if total_services > 0 else 1.0
        
        return {
            'health_score': health_score,
            'healthy_services': healthy_services,
            'total_services': total_services,
            'circuit_breakers': circuit_states,
            'service_health': service_health,
            'timestamp': datetime.now().isoformat()
        }


# Decorators for easy use
def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to a function"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        retry_handler = RetryHandler(config)
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_handler.retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


def with_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """Decorator to add circuit breaker protection to a function"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        circuit_breaker = CircuitBreaker(name, config)
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


def with_reliability(service_name: str, 
                    retry_config: Optional[RetryConfig] = None,
                    circuit_config: Optional[CircuitBreakerConfig] = None):
    """Decorator to add both retry and circuit breaker protection"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        manager = ReliabilityManager()
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return manager.execute_with_reliability(
                service_name, func, *args, 
                retry_config=retry_config,
                circuit_config=circuit_config,
                **kwargs
            )
        
        return wrapper
    return decorator


# Global reliability manager instance
reliability_manager = ReliabilityManager()