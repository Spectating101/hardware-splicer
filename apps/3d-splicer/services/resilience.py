"""
Resilience utilities for production-ready error handling.

Includes retry logic, circuit breaker pattern, and exponential backoff.
"""

import time
import logging
import functools
from typing import Callable, Optional, Tuple, Type
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Reset circuit breaker on successful call"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered - entering CLOSED state")
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Increment failure count and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger_name: Optional[str] = None
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (2.0 = double each time)
        exceptions: Tuple of exceptions to catch and retry
        logger_name: Optional logger name for custom logging

    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=1.0)
        def unstable_api_call():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logging.getLogger(logger_name or func.__module__)
            delay = initial_delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_attempts:
                        _logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    _logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

        return wrapper
    return decorator


def timeout_decorator(seconds: float):
    """
    Decorator to add timeout to function calls.

    Note: This is a simple implementation. For production, consider using
    'func_timeout' library or similar for more robust timeout handling.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"{func.__name__} exceeded timeout of {seconds}s")

            # Set the timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))

            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)  # Disable the alarm

            return result
        return wrapper
    return decorator


class RateLimiter:
    """
    Simple token bucket rate limiter.

    Prevents overwhelming external services with too many requests.
    """

    def __init__(self, requests_per_second: float = 10.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests allowed per second
        """
        self.rate = requests_per_second
        self.tokens = requests_per_second
        self.last_update = time.time()

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire permission to make a request.

        Args:
            blocking: If True, wait until token available

        Returns:
            True if request allowed, False otherwise
        """
        while True:
            self._refill_tokens()

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True

            if not blocking:
                return False

            # Wait for next token
            time.sleep(0.1)

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(
            self.rate,
            self.tokens + (elapsed * self.rate)
        )
        self.last_update = now
