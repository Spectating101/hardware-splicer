from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
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

# JWT secret handling with fail-fast protection in non-debug.
JWT_SECRET = os.getenv("JWT_SECRET") or settings.jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if not JWT_SECRET:
    if settings.debug:
        JWT_SECRET = secrets.token_urlsafe(48)
        logger.info("JWT_SECRET is not configured; generated an ephemeral debug secret for this process")
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
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
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
