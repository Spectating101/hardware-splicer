from functools import wraps
from fastapi import HTTPException, status, Request, Depends
from typing import Callable, Any
import time
from datetime import datetime, timedelta
from loguru import logger
from ...services.usage_tracker import usage_tracker

# In-memory rate limiting storage (use Redis in production)
RATE_LIMIT_STORAGE = {}

class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit exceeded."""
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 1000):
    """
    Decorator for rate limiting API endpoints.
    
    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user information from kwargs
            current_user = kwargs.get('current_user', {})
            user_id = current_user.get('user_id', 'anonymous')
            
            # Get endpoint name
            endpoint = func.__name__
            
            # Check quotas using usage tracker
            quota_status = usage_tracker.check_quotas(user_id)
            
            if quota_status["overall_exceeded"]:
                # Determine retry after time
                retry_after = 60  # Default 1 minute
                if quota_status["minute"]["exceeded"]:
                    retry_after = 60
                elif quota_status["hour"]["exceeded"]:
                    retry_after = 3600
                elif quota_status["day"]["exceeded"]:
                    retry_after = 86400
                
                raise RateLimitExceeded(retry_after)
            
            # Execute the function
            result = await func(*args, **kwargs)
            
            # Track successful request
            usage_tracker.track_request(
                user_id=user_id,
                endpoint=endpoint,
                success=True
            )
            
            return result
        
        return wrapper
    return decorator

def _check_rate_limit(user_id: str, endpoint: str, per_minute: int, per_hour: int) -> bool:
    """
    Check if user has exceeded rate limits.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        per_minute: Requests per minute limit
        per_hour: Requests per hour limit
        
    Returns:
        True if within limits, False if exceeded
    """
    now = datetime.now()
    
    # Check per-minute limit
    minute_key = f"{user_id}:{endpoint}:minute"
    if not _check_window_limit(minute_key, now, timedelta(minutes=1), per_minute):
        return False
    
    # Check per-hour limit
    hour_key = f"{user_id}:{endpoint}:hour"
    if not _check_window_limit(hour_key, now, timedelta(hours=1), per_hour):
        return False
    
    return True

def _check_window_limit(key: str, now: datetime, window: timedelta, limit: int) -> bool:
    """
    Check rate limit for a specific time window.
    
    Args:
        key: Storage key
        now: Current time
        window: Time window
        limit: Request limit
        
    Returns:
        True if within limit, False if exceeded
    """
    if key not in RATE_LIMIT_STORAGE:
        RATE_LIMIT_STORAGE[key] = []
    
    # Clean old requests
    cutoff = now - window
    RATE_LIMIT_STORAGE[key] = [
        req_time for req_time in RATE_LIMIT_STORAGE[key] 
        if req_time > cutoff
    ]
    
    # Check limit
    if len(RATE_LIMIT_STORAGE[key]) >= limit:
        return False
    
    # Add current request
    RATE_LIMIT_STORAGE[key].append(now)
    return True

def _get_retry_after(user_id: str, endpoint: str) -> int:
    """
    Get retry-after time in seconds.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        
    Returns:
        Retry-after time in seconds
    """
    now = datetime.now()
    
    # Check minute window
    minute_key = f"{user_id}:{endpoint}:minute"
    if minute_key in RATE_LIMIT_STORAGE and RATE_LIMIT_STORAGE[minute_key]:
        oldest_request = min(RATE_LIMIT_STORAGE[minute_key])
        retry_after = int((oldest_request + timedelta(minutes=1) - now).total_seconds())
        return max(1, retry_after)
    
    # Check hour window
    hour_key = f"{user_id}:{endpoint}:hour"
    if hour_key in RATE_LIMIT_STORAGE and RATE_LIMIT_STORAGE[hour_key]:
        oldest_request = min(RATE_LIMIT_STORAGE[hour_key])
        retry_after = int((oldest_request + timedelta(hours=1) - now).total_seconds())
        return max(1, retry_after)
    
    return 60  # Default retry after 1 minute

def get_rate_limit_info(user_id: str, endpoint: str) -> dict:
    """
    Get rate limit information for user and endpoint.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        
    Returns:
        Rate limit information dict
    """
    now = datetime.now()
    
    # Get minute window info
    minute_key = f"{user_id}:{endpoint}:minute"
    minute_requests = 0
    minute_reset = None
    
    if minute_key in RATE_LIMIT_STORAGE:
        cutoff = now - timedelta(minutes=1)
        minute_requests = len([
            req_time for req_time in RATE_LIMIT_STORAGE[minute_key] 
            if req_time > cutoff
        ])
        
        if RATE_LIMIT_STORAGE[minute_key]:
            oldest_request = min(RATE_LIMIT_STORAGE[minute_key])
            minute_reset = (oldest_request + timedelta(minutes=1)).isoformat()
    
    # Get hour window info
    hour_key = f"{user_id}:{endpoint}:hour"
    hour_requests = 0
    hour_reset = None
    
    if hour_key in RATE_LIMIT_STORAGE:
        cutoff = now - timedelta(hours=1)
        hour_requests = len([
            req_time for req_time in RATE_LIMIT_STORAGE[hour_key] 
            if req_time > cutoff
        ])
        
        if RATE_LIMIT_STORAGE[hour_key]:
            oldest_request = min(RATE_LIMIT_STORAGE[hour_key])
            hour_reset = (oldest_request + timedelta(hours=1)).isoformat()
    
    return {
        "minute": {
            "limit": 60,
            "used": minute_requests,
            "remaining": max(0, 60 - minute_requests),
            "reset_time": minute_reset
        },
        "hour": {
            "limit": 1000,
            "used": hour_requests,
            "remaining": max(0, 1000 - hour_requests),
            "reset_time": hour_reset
        }
    }

# Tier-based rate limiting
RATE_LIMIT_TIERS = {
    "free": {
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "requests_per_day": 1000
    },
    "pro": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "requests_per_day": 10000
    },
    "enterprise": {
        "requests_per_minute": 300,
        "requests_per_hour": 5000,
        "requests_per_day": 50000
    }
}

def get_user_tier(user_id: str) -> str:
    """
    Get user's rate limit tier.
    
    Args:
        user_id: User identifier
        
    Returns:
        User tier (free, pro, enterprise)
    """
    # In production, this would query the database
    # For now, return based on user ID pattern
    if user_id.startswith("enterprise_"):
        return "enterprise"
    elif user_id.startswith("pro_"):
        return "pro"
    else:
        return "free"

def tier_based_rate_limit(func: Callable) -> Callable:
    """
    Decorator for tier-based rate limiting.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with tier-based rate limiting
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get('current_user', {})
        user_id = current_user.get('user_id', 'anonymous')
        
        tier = get_user_tier(user_id)
        limits = RATE_LIMIT_TIERS[tier]
        
        endpoint = func.__name__
        
        # Check rate limits
        if not _check_rate_limit(user_id, endpoint, limits["requests_per_minute"], limits["requests_per_hour"]):
            retry_after = _get_retry_after(user_id, endpoint)
            raise RateLimitExceeded(retry_after)
        
        return await func(*args, **kwargs)
    
    return wrapper

# IP-based rate limiting (for additional security)
IP_RATE_LIMIT_STORAGE = {}

def ip_rate_limit(requests_per_minute: int = 30):
    """
    Decorator for IP-based rate limiting.
    
    Args:
        requests_per_minute: Maximum requests per minute per IP
        
    Returns:
        Decorated function with IP rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request object, skip IP rate limiting
                return await func(*args, **kwargs)
            
            # Get client IP
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
            
            # Check IP rate limit
            if not _check_ip_rate_limit(client_ip, requests_per_minute):
                raise RateLimitExceeded(60)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def _check_ip_rate_limit(ip: str, limit: int) -> bool:
    """
    Check IP-based rate limit.
    
    Args:
        ip: Client IP address
        limit: Request limit per minute
        
    Returns:
        True if within limit, False if exceeded
    """
    now = datetime.now()
    key = f"ip:{ip}"
    
    if key not in IP_RATE_LIMIT_STORAGE:
        IP_RATE_LIMIT_STORAGE[key] = []
    
    # Clean old requests
    cutoff = now - timedelta(minutes=1)
    IP_RATE_LIMIT_STORAGE[key] = [
        req_time for req_time in IP_RATE_LIMIT_STORAGE[key] 
        if req_time > cutoff
    ]
    
    # Check limit
    if len(IP_RATE_LIMIT_STORAGE[key]) >= limit:
        return False
    
    # Add current request
    IP_RATE_LIMIT_STORAGE[key].append(now)
    return True
