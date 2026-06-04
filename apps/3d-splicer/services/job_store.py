"""
Persistent job storage with Redis backend.

Replaces in-memory job_status dict with production-ready persistent storage.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
import redis

logger = logging.getLogger(__name__)


class JobStore:
    """
    Persistent job storage using Redis.

    Provides atomic operations, TTL support, and survives server restarts.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        ttl_hours: int = 24,
        key_prefix: str = "splicer:job:"
    ):
        """
        Initialize job store.

        Args:
            redis_url: Redis connection URL
            ttl_hours: Time-to-live for job data in hours (default: 24)
            key_prefix: Prefix for Redis keys (default: "splicer:job:")
        """
        self.ttl_seconds = ttl_hours * 3600
        self.key_prefix = key_prefix

        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis: {redis_url}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis connection failed: {e}. Falling back to in-memory storage.")
            self.redis_client = None
            self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, job_id: str) -> str:
        """Get full Redis key for job ID"""
        return f"{self.key_prefix}{job_id}"

    def create_job(
        self,
        job_id: str,
        spec: Dict[str, Any],
        status: str = "pending",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create new job entry.

        Args:
            job_id: Unique job identifier
            spec: Functional specification
            status: Initial status (default: "pending")
            metadata: Optional metadata dictionary
        """
        job_data = {
            "job_id": job_id,
            "spec": spec,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        if self.redis_client:
            try:
                key = self._get_key(job_id)
                self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(job_data)
                )
                logger.info(f"Created job in Redis: {job_id}")
            except redis.RedisError as e:
                logger.error(f"Redis error creating job: {e}")
                raise
        else:
            # In-memory fallback
            self._memory_store[job_id] = job_data

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job data.

        Args:
            job_id: Job identifier

        Returns:
            Job data dictionary or None if not found
        """
        if self.redis_client:
            try:
                key = self._get_key(job_id)
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
                return None
            except redis.RedisError as e:
                logger.error(f"Redis error getting job: {e}")
                return None
        else:
            return self._memory_store.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        progress: Optional[float] = None
    ) -> bool:
        """
        Update job status and data.

        Args:
            job_id: Job identifier
            status: New status (if provided)
            result: Result data (if completed)
            error: Error message (if failed)
            progress: Progress percentage 0-100 (if in progress)

        Returns:
            True if updated successfully, False otherwise
        """
        job_data = self.get_job(job_id)
        if not job_data:
            logger.warning(f"Job not found for update: {job_id}")
            return False

        # Update fields
        if status:
            job_data["status"] = status
        if result:
            job_data["result"] = result
        if error:
            job_data["error"] = error
        if progress is not None:
            job_data["progress"] = progress

        job_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Save back
        if self.redis_client:
            try:
                key = self._get_key(job_id)
                self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(job_data)
                )
                return True
            except redis.RedisError as e:
                logger.error(f"Redis error updating job: {e}")
                return False
        else:
            self._memory_store[job_id] = job_data
            return True

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job data.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        if self.redis_client:
            try:
                key = self._get_key(job_id)
                deleted = self.redis_client.delete(key)
                return deleted > 0
            except redis.RedisError as e:
                logger.error(f"Redis error deleting job: {e}")
                return False
        else:
            return self._memory_store.pop(job_id, None) is not None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional status filter.

        Args:
            status: Filter by status (e.g., "pending", "completed")
            limit: Maximum number of jobs to return

        Returns:
            List of job data dictionaries
        """
        if self.redis_client:
            try:
                pattern = f"{self.key_prefix}*"
                keys = list(self.redis_client.scan_iter(match=pattern, count=limit))
                jobs = []

                for key in keys[:limit]:
                    data = self.redis_client.get(key)
                    if data:
                        job = json.loads(data)
                        if status is None or job.get("status") == status:
                            jobs.append(job)

                return jobs
            except redis.RedisError as e:
                logger.error(f"Redis error listing jobs: {e}")
                return []
        else:
            jobs = list(self._memory_store.values())
            if status:
                jobs = [j for j in jobs if j.get("status") == status]
            return jobs[:limit]

    def cleanup_expired(self) -> int:
        """
        Cleanup expired jobs (TTL handles this automatically in Redis).

        Returns:
            Number of jobs cleaned up
        """
        if not self.redis_client:
            # Manual cleanup for in-memory store
            now = datetime.now(timezone.utc)
            expired_ids = []

            for job_id, job_data in self._memory_store.items():
                created_at = datetime.fromisoformat(job_data.get("created_at", now.isoformat()))
                age = (now - created_at).total_seconds()

                if age > self.ttl_seconds:
                    expired_ids.append(job_id)

            for job_id in expired_ids:
                del self._memory_store[job_id]

            logger.info(f"Cleaned up {len(expired_ids)} expired jobs")
            return len(expired_ids)

        # Redis handles TTL automatically
        return 0

    def health_check(self) -> Dict[str, Any]:
        """
        Check job store health.

        Returns:
            Health status dictionary
        """
        health = {
            "status": "unhealthy",
            "backend": "memory" if not self.redis_client else "redis",
            "connected": False
        }

        if self.redis_client:
            try:
                self.redis_client.ping()
                health["connected"] = True
                health["status"] = "healthy"

                # Get stats
                info = self.redis_client.info("stats")
                health["total_commands"] = info.get("total_commands_processed", 0)
            except redis.RedisError as e:
                health["error"] = str(e)
        else:
            # In-memory is always "healthy" but not persistent
            health["status"] = "degraded"  # Not persistent
            health["job_count"] = len(self._memory_store)

        return health


# Global instance (initialized by app startup)
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get global job store instance"""
    global _job_store
    if _job_store is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _job_store = JobStore(redis_url=redis_url)
    return _job_store


def init_job_store(redis_url: Optional[str] = None) -> JobStore:
    """
    Initialize global job store.

    Args:
        redis_url: Optional Redis URL override

    Returns:
        JobStore instance
    """
    global _job_store
    import os
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _job_store = JobStore(redis_url=url)
    return _job_store
