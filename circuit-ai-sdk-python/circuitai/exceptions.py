"""
Circuit.AI Python SDK Exceptions

Exception handling for the Circuit.AI API.
"""

import requests
from typing import Optional, Dict, Any
from .models import CircuitAIError, AuthenticationError, RateLimitError, APIError


def handle_api_error(response: requests.Response) -> None:
    """
    Handle API error responses and raise appropriate exceptions.
    
    Args:
        response: HTTP response object
        
    Raises:
        AuthenticationError: For 401 errors
        RateLimitError: For 429 errors
        APIError: For other HTTP errors
    """
    status_code = response.status_code
    
    try:
        error_data = response.json()
    except ValueError:
        error_data = {"error": {"message": response.text or "Unknown error"}}
    
    error_info = error_data.get("error", {})
    message = error_info.get("message", f"HTTP {status_code} error")
    error_code = error_info.get("code", None)
    
    if status_code == 401:
        raise AuthenticationError(f"Authentication failed: {message}")
    elif status_code == 429:
        retry_after = response.headers.get("Retry-After", "60")
        raise RateLimitError(f"Rate limit exceeded: {message}. Retry after {retry_after} seconds")
    elif status_code >= 400:
        raise APIError(message, status_code=status_code, error_code=error_code)
    else:
        raise CircuitAIError(f"Unexpected error: {message}")
