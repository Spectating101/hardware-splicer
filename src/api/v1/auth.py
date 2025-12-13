from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional, List, Tuple
import hashlib
import secrets
from datetime import datetime, timedelta
import jwt
from loguru import logger
import os

from src.config import settings

# Security scheme
security = HTTPBearer()

# For development: test API keys can be set via environment variable
# Format: "key1,key2,key3"
TEST_API_KEYS = set(os.getenv("TEST_API_KEYS", "").split(",")) if os.getenv("TEST_API_KEYS") else set()

# In-memory storage (for testing/development - should be replaced with database in production)
_ACTIVE_API_KEYS: Dict[str, Dict] = {}
_RATE_LIMIT_STORAGE: Dict[str, List[datetime]] = {}

# JWT secret handling with fail-fast protection in non-debug
DEFAULT_JWT_SECRET = "change-me-in-production-immediately"
JWT_SECRET = os.getenv("JWT_SECRET") or settings.jwt_secret or DEFAULT_JWT_SECRET
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if JWT_SECRET == DEFAULT_JWT_SECRET:
    if settings.debug:
        logger.warning("⚠️ JWT_SECRET is not configured; using insecure default for debug only")
    else:
        raise RuntimeError("JWT_SECRET is not configured. Set JWT_SECRET env var or settings.jwt_secret for production.")

def verify_api_key(api_key: str) -> Optional[Dict]:
    """
    Verify API key against database or environment.
    
    In production, this should query the database for the API key.
    For now, accept test keys from environment variable.
    
    Args:
        api_key: The API key to verify
        
    Returns:
        User information dict if valid, None if invalid
    """
    if not api_key:
        return None
    
    # Check if it's a test key (for development only)
    if api_key in TEST_API_KEYS:
        return {
            "user_id": "test_user",
            "api_key": api_key,
            "permissions": ["analyze", "read"],
            "key_name": "Test API Key",
            "tier": "test"
        }
    
    # TODO: Query database for API key
    # This is where you would check a proper API key store
    logger.debug(f"API key {api_key[:10]}... not found in database")
    return None

def create_jwt_token(user_id: str, permissions: list, tier: str = "free") -> str:
    """
    Create a JWT token for the user.
    
    Args:
        user_id: User identifier
        permissions: List of user permissions
        tier: Subscription tier (free, pro, enterprise)
        
    Returns:
        JWT token string
    """
    payload = {
        "user_id": user_id,
        "permissions": permissions,
        "tier": tier,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """
    Verify JWT token and return user information.
    
    Args:
        token: JWT token to verify
        
    Returns:
        User information dict if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "user_id": payload["user_id"],
            "permissions": payload["permissions"],
            "tier": payload.get("tier", "free")
        }
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Get current user from API key or JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User information dict
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    
    # Try API key first
    user_info = verify_api_key(token)
    if user_info:
        return user_info
    
    # Try JWT token
    user_info = verify_jwt_token(token)
    if user_info:
        return user_info
    
    # Authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key or token",
        headers={"WWW-Authenticate": "Bearer"},
    )

def require_permission(permission: str):
    """
    Decorator to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    async def permission_checker(current_user: Dict = Depends(get_current_user)) -> Dict:
        if permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    
    return permission_checker

def create_api_key(user_id: str, name: str, permissions: list = None) -> tuple[str, str]:
    """
    Create a new API key for a user.
    
    Args:
        user_id: User identifier
        name: API key name
        permissions: List of permissions (default: ["analyze", "read"])
        
    Returns:
        Tuple of (api_key, key_id)
    """
    if permissions is None:
        permissions = ["analyze", "read"]
    
    # Generate secure API key
    key_id = secrets.token_urlsafe(16)
    api_key = f"ckt_{secrets.token_urlsafe(32)}"
    
    # Store API key (in production, store in database)
    _ACTIVE_API_KEYS[api_key] = {
        "user_id": user_id,
        "name": name,
        "permissions": permissions,
        "created_at": datetime.now(),
        "usage_count": 0,
        "is_active": True
    }
    
    return api_key, key_id

def revoke_api_key(api_key: str) -> bool:
    """
    Revoke an API key.
    
    Args:
        api_key: API key to revoke
        
    Returns:
        True if revoked successfully, False if not found
    """
    if api_key in _ACTIVE_API_KEYS:
        _ACTIVE_API_KEYS[api_key]["is_active"] = False
        return True
    return False

def get_user_api_keys(user_id: str) -> list:
    """
    Get all API keys for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of API key information
    """
    user_keys = []
    for api_key, info in _ACTIVE_API_KEYS.items():
        if info["user_id"] == user_id:
            user_keys.append({
                "key_id": hashlib.sha256(api_key.encode()).hexdigest()[:16],
                "name": info["name"],
                "created_at": info["created_at"].isoformat(),
                "usage_count": info["usage_count"],
                "is_active": info["is_active"],
                "permissions": info["permissions"]
            })
    
    return user_keys

# Rate limiting storage (in production, use Redis)
_RATE_LIMIT_STORAGE_OLD = {}

def check_rate_limit(user_id: str, endpoint: str, limit: int, window: int = 60) -> bool:
    """
    Check if user has exceeded rate limit.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        limit: Request limit per window
        window: Time window in seconds
        
    Returns:
        True if within limit, False if exceeded
    """
    key = f"{user_id}:{endpoint}"
    now = datetime.now()
    
    if key not in _RATE_LIMIT_STORAGE_OLD:
        _RATE_LIMIT_STORAGE_OLD[key] = []
    
    # Clean old requests
    cutoff = now - timedelta(seconds=window)
    _RATE_LIMIT_STORAGE_OLD[key] = [
        req_time for req_time in _RATE_LIMIT_STORAGE_OLD[key] 
        if req_time > cutoff
    ]
    
    # Check limit
    if len(_RATE_LIMIT_STORAGE_OLD[key]) >= limit:
        return False
    
    # Add current request
    _RATE_LIMIT_STORAGE_OLD[key].append(now)
    return True

def get_rate_limit_info(user_id: str, endpoint: str, limit: int, window: int = 60) -> dict:
    """
    Get rate limit information for user and endpoint.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        limit: Request limit per window
        window: Time window in seconds
        
    Returns:
        Rate limit information dict
    """
    key = f"{user_id}:{endpoint}"
    now = datetime.now()
    
    if key not in _RATE_LIMIT_STORAGE_OLD:
        return {
            "limit": limit,
            "remaining": limit,
            "reset_time": (now + timedelta(seconds=window)).isoformat(),
            "window": window
        }
    
    # Clean old requests
    cutoff = now - timedelta(seconds=window)
    _RATE_LIMIT_STORAGE_OLD[key] = [
        req_time for req_time in _RATE_LIMIT_STORAGE_OLD[key] 
        if req_time > cutoff
    ]
    
    remaining = max(0, limit - len(_RATE_LIMIT_STORAGE_OLD[key]))
    reset_time = (_RATE_LIMIT_STORAGE_OLD[key][0] + timedelta(seconds=window)).isoformat() if _RATE_LIMIT_STORAGE_OLD[key] else now.isoformat()
    
    return {
        "limit": limit,
        "remaining": remaining,
        "reset_time": reset_time,
        "window": window
    }
