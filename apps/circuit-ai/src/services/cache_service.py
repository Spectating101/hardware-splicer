import json
import hashlib
import time
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from loguru import logger
import pickle
import threading
from functools import wraps

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only")

class CacheService:
    """Advanced caching service with Redis and in-memory fallback."""
    
    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
        self._lock = threading.Lock()
        
        # Initialize Redis if available
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using in-memory cache")
                self.redis_client = None
        else:
            logger.info("Using in-memory cache only")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and arguments."""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            key_parts.append(str(arg))
        
        # Add keyword arguments (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache."""
        try:
            # Try Redis first
            if self.redis_client:
                value = self.redis_client.get(key)
                if value is not None:
                    self.cache_stats["hits"] += 1
                    return pickle.loads(value)
            
            # Fallback to memory cache
            with self._lock:
                if key in self.memory_cache:
                    cache_entry = self.memory_cache[key]
                    if cache_entry["expires_at"] > datetime.now():
                        self.cache_stats["hits"] += 1
                        return cache_entry["value"]
                    else:
                        # Expired entry, remove it
                        del self.memory_cache[key]
            
            self.cache_stats["misses"] += 1
            return default
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        try:
            ttl = ttl or self.default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl)
            
            # Try Redis first
            if self.redis_client:
                serialized_value = pickle.dumps(value)
                self.redis_client.setex(key, ttl, serialized_value)
                self.cache_stats["sets"] += 1
                return True
            
            # Fallback to memory cache
            with self._lock:
                self.memory_cache[key] = {
                    "value": value,
                    "expires_at": expires_at,
                    "created_at": datetime.now()
                }
                self.cache_stats["sets"] += 1
                return True
                
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            # Try Redis first
            if self.redis_client:
                result = self.redis_client.delete(key)
                if result:
                    self.cache_stats["deletes"] += 1
                    return True
            
            # Fallback to memory cache
            with self._lock:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    self.cache_stats["deletes"] += 1
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            # Try Redis first
            if self.redis_client:
                return bool(self.redis_client.exists(key))
            
            # Fallback to memory cache
            with self._lock:
                if key in self.memory_cache:
                    cache_entry = self.memory_cache[key]
                    if cache_entry["expires_at"] > datetime.now():
                        return True
                    else:
                        # Expired entry, remove it
                        del self.memory_cache[key]
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries, optionally by pattern."""
        try:
            deleted_count = 0
            
            # Try Redis first
            if self.redis_client:
                if pattern:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        deleted_count = self.redis_client.delete(*keys)
                else:
                    self.redis_client.flushdb()
                    deleted_count = -1  # Indicates full clear
            
            # Fallback to memory cache
            with self._lock:
                if pattern:
                    keys_to_delete = [key for key in self.memory_cache.keys() if pattern in key]
                    for key in keys_to_delete:
                        del self.memory_cache[key]
                        deleted_count += 1
                else:
                    deleted_count = len(self.memory_cache)
                    self.memory_cache.clear()
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_rate": round(hit_rate, 2),
            "memory_cache_size": len(self.memory_cache),
            "redis_available": self.redis_client is not None,
            "default_ttl": self.default_ttl
        }
    
    def cleanup_expired(self) -> int:
        """Clean up expired entries from memory cache."""
        try:
            with self._lock:
                current_time = datetime.now()
                expired_keys = [
                    key for key, entry in self.memory_cache.items()
                    if entry["expires_at"] <= current_time
                ]
                
                for key in expired_keys:
                    del self.memory_cache[key]
                
                return len(expired_keys)
                
        except Exception as e:
            logger.error(f"Error cleaning up expired cache entries: {e}")
            return 0

# Global cache service instance
cache_service = CacheService()

def cached(prefix: str, ttl: Optional[int] = None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_service._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

class AnalysisCache:
    """Specialized cache for analysis results."""
    
    def __init__(self):
        self.cache = cache_service
    
    def get_analysis_result(self, image_hash: str, backend: str, enable_ocr: bool) -> Optional[Dict[str, Any]]:
        """Get cached analysis result."""
        key = f"analysis:{image_hash}:{backend}:{enable_ocr}"
        return self.cache.get(key)
    
    def set_analysis_result(self, image_hash: str, backend: str, enable_ocr: bool, result: Dict[str, Any], ttl: int = 3600):
        """Cache analysis result."""
        key = f"analysis:{image_hash}:{backend}:{enable_ocr}"
        return self.cache.set(key, result, ttl)
    
    def get_component_info(self, component_type: str) -> Optional[Dict[str, Any]]:
        """Get cached component information."""
        key = f"component:{component_type}"
        return self.cache.get(key)
    
    def set_component_info(self, component_type: str, info: Dict[str, Any], ttl: int = 86400):
        """Cache component information."""
        key = f"component:{component_type}"
        return self.cache.set(key, info, ttl)
    
    def get_project_recommendations(self, capabilities: List[str]) -> Optional[List[Dict[str, Any]]]:
        """Get cached project recommendations."""
        capabilities_str = "|".join(sorted(capabilities))
        key = f"projects:{hash(capabilities_str)}"
        return self.cache.get(key)
    
    def set_project_recommendations(self, capabilities: List[str], recommendations: List[Dict[str, Any]], ttl: int = 3600):
        """Cache project recommendations."""
        capabilities_str = "|".join(sorted(capabilities))
        key = f"projects:{hash(capabilities_str)}"
        return self.cache.set(key, recommendations, ttl)

    def get_stats(self) -> Dict[str, Any]:
        """Expose underlying cache stats for higher-level services."""
        return self.cache.get_stats()

# Global analysis cache instance
analysis_cache = AnalysisCache()
