"""
Comprehensive error handling utilities for Circuit.AI
Provides centralized error handling, logging, and recovery mechanisms
"""

import traceback
import sys
from typing import Optional, Dict, Any, Callable
from functools import wraps
from loguru import logger
from datetime import datetime
from pathlib import Path


class CircuitAIError(Exception):
    """Base exception for Circuit.AI"""
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class ModelLoadError(CircuitAIError):
    """Raised when ML model fails to load"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "MODEL_LOAD_ERROR", details)


class ImageProcessingError(CircuitAIError):
    """Raised when image processing fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "IMAGE_PROCESSING_ERROR", details)


class DetectionError(CircuitAIError):
    """Raised when component detection fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "DETECTION_ERROR", details)


class DatabaseError(CircuitAIError):
    """Raised when database operation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "DATABASE_ERROR", details)


class ValidationError(CircuitAIError):
    """Raised when input validation fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class TimeoutError(CircuitAIError):
    """Raised when operation times out"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "TIMEOUT_ERROR", details)


class ErrorHandler:
    """Centralized error handling and logging"""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

    def _setup_logging(self):
        """Setup structured logging"""
        # Remove default logger
        logger.remove()

        # Console logging (colorized)
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )

        # File logging (JSON for parsing)
        logger.add(
            self.log_dir / "circuit_ai_{time}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="100 MB",
            retention="30 days",
            compression="gz"
        )

        # Error-only file
        logger.add(
            self.log_dir / "errors_{time}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="50 MB",
            retention="90 days"
        )

    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR"
    ):
        """Log error with full context and stack trace"""
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "stack_trace": traceback.format_exc()
        }

        if severity == "CRITICAL":
            logger.critical(f"Critical error occurred: {error_info}")
        elif severity == "ERROR":
            logger.error(f"Error occurred: {error_info}")
        elif severity == "WARNING":
            logger.warning(f"Warning: {error_info}")
        else:
            logger.info(f"Info: {error_info}")

        return error_info

    def handle_exception(
        self,
        error: Exception,
        context: Optional[Dict] = None,
        reraise: bool = True
    ) -> Optional[Dict]:
        """
        Handle exception with logging and optional re-raising

        Args:
            error: The exception to handle
            context: Additional context information
            reraise: Whether to re-raise the exception after logging

        Returns:
            Error information dictionary if not re-raising
        """
        error_info = self.log_error(error, context)

        # Convert known errors to CircuitAI errors
        if isinstance(error, CircuitAIError):
            if reraise:
                raise
            return error.to_dict()

        # Handle specific error types
        if isinstance(error, FileNotFoundError):
            circuit_error = ValidationError(
                f"Required file not found: {error}",
                {"original_error": str(error)}
            )
            if reraise:
                raise circuit_error from error
            return circuit_error.to_dict()

        if isinstance(error, ValueError):
            circuit_error = ValidationError(
                f"Invalid value: {error}",
                {"original_error": str(error)}
            )
            if reraise:
                raise circuit_error from error
            return circuit_error.to_dict()

        # Generic error handling
        if reraise:
            raise
        return error_info


# Global error handler instance
_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_errors(
    default_return: Any = None,
    log_level: str = "ERROR",
    reraise: bool = False
):
    """
    Decorator for automatic error handling

    Args:
        default_return: Value to return if error occurs (if not reraising)
        log_level: Logging level for errors
        reraise: Whether to re-raise exceptions

    Example:
        @handle_errors(default_return=[], log_level="WARNING")
        def process_image(image_path):
            # Processing code that might fail
            return results
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = get_error_handler()
                context = {
                    "function": func.__name__,
                    "args": str(args)[:200],  # Truncate long args
                    "kwargs": str(kwargs)[:200]
                }

                handler.log_error(e, context, severity=log_level)

                if reraise:
                    raise

                return default_return

        return wrapper
    return decorator


def validate_image_input(image_data: Any) -> None:
    """
    Validate image input data

    Raises:
        ValidationError: If image data is invalid
    """
    if image_data is None:
        raise ValidationError("Image data cannot be None")

    if isinstance(image_data, (bytes, bytearray)):
        if len(image_data) == 0:
            raise ValidationError("Image data is empty")
        if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise ValidationError(
                "Image file too large",
                {"size_bytes": len(image_data), "max_bytes": 10 * 1024 * 1024}
            )

    # Additional validation can be added here


def validate_model_path(model_path: Path) -> None:
    """
    Validate model file path

    Raises:
        ValidationError: If model path is invalid
    """
    if not isinstance(model_path, Path):
        model_path = Path(model_path)

    if not model_path.exists():
        raise ValidationError(
            f"Model file not found: {model_path}",
            {"path": str(model_path)}
        )

    if not model_path.is_file():
        raise ValidationError(
            f"Model path is not a file: {model_path}",
            {"path": str(model_path)}
        )

    if model_path.suffix not in ['.pt', '.pth', '.onnx', '.pb']:
        raise ValidationError(
            f"Invalid model file format: {model_path.suffix}",
            {"path": str(model_path), "suffix": model_path.suffix}
        )


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if division fails

    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if division fails

    Returns:
        Result of division or default value
    """
    try:
        if denominator == 0:
            logger.warning(f"Division by zero attempted: {numerator}/{denominator}")
            return default
        return numerator / denominator
    except Exception as e:
        logger.error(f"Error in division: {e}")
        return default


def retry_on_failure(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry function on failure with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @retry_on_failure(max_attempts=3, delay_seconds=2.0)
        def load_model(path):
            # Code that might fail temporarily
            return model
    """
    import time

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = delay_seconds
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}"
                        )

            # All attempts failed
            raise last_exception

        return wrapper
    return decorator


# Context manager for error handling
class ErrorContext:
    """Context manager for handling errors in a block of code"""

    def __init__(self, operation_name: str, reraise: bool = True):
        self.operation_name = operation_name
        self.reraise = reraise
        self.handler = get_error_handler()

    def __enter__(self):
        logger.info(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            context = {"operation": self.operation_name}
            self.handler.log_error(exc_val, context)

            if self.reraise:
                return False  # Re-raise the exception
            return True  # Suppress the exception

        logger.info(f"Completed operation: {self.operation_name}")
        return True


if __name__ == "__main__":
    # Example usage
    handler = get_error_handler()

    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        handler.handle_exception(e, {"test": "context"}, reraise=False)

    # Test decorator
    @handle_errors(default_return=None)
    def test_function():
        raise RuntimeError("Test runtime error")

    result = test_function()
    print(f"Result: {result}")

    # Test retry decorator
    @retry_on_failure(max_attempts=3, delay_seconds=0.5)
    def flaky_function():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Random failure")
        return "Success!"

    try:
        result = flaky_function()
        print(f"Retry result: {result}")
    except Exception as e:
        print(f"Failed after retries: {e}")
