"""
Circuit.AI Usage Tracking Service

Tracks API usage, enforces quotas, and manages billing.
"""

import redis
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from loguru import logger
import os

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=True
)

# Usage tracking keys
USAGE_PREFIX = "usage:"
QUOTA_PREFIX = "quota:"
USER_PREFIX = "user:"

class UsageTracker:
    """Track and enforce API usage quotas."""
    
    def __init__(self):
        self.redis = redis_client
    
    def track_request(
        self, 
        user_id: str, 
        endpoint: str, 
        success: bool = True,
        analysis_time: float = 0.0,
        components_detected: int = 0
    ) -> Dict[str, Any]:
        """
        Track a single API request.
        
        Args:
            user_id: User identifier
            endpoint: API endpoint called
            success: Whether the request was successful
            analysis_time: Time taken for analysis
            components_detected: Number of components detected
            
        Returns:
            Usage information and quota status
        """
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        
        # Get user's current plan
        user_plan = self.get_user_plan(user_id)
        plan_limits = self.get_plan_limits(user_plan)
        
        # Track usage
        usage_data = {
            "user_id": user_id,
            "endpoint": endpoint,
            "success": success,
            "analysis_time": analysis_time,
            "components_detected": components_detected,
            "timestamp": timestamp
        }
        
        # Store in Redis with TTL
        usage_key = f"{USAGE_PREFIX}{user_id}:{now.strftime('%Y%m%d%H%M')}"
        self.redis.lpush(usage_key, json.dumps(usage_data))
        self.redis.expire(usage_key, 86400)  # 24 hours
        
        # Update counters
        self._update_counters(user_id, endpoint, success, analysis_time, components_detected)
        
        # Check quotas
        quota_status = self.check_quotas(user_id, user_plan)
        
        return {
            "usage": usage_data,
            "quota_status": quota_status,
            "plan": user_plan,
            "limits": plan_limits
        }
    
    def check_quotas(self, user_id: str, plan: str = None) -> Dict[str, Any]:
        """
        Check if user has exceeded their quotas.
        
        Args:
            user_id: User identifier
            plan: User's plan (if not provided, will be fetched)
            
        Returns:
            Quota status information
        """
        if plan is None:
            plan = self.get_user_plan(user_id)
        
        plan_limits = self.get_plan_limits(plan)
        now = datetime.now(timezone.utc)
        
        # Check minute quota
        minute_usage = self._get_usage_count(user_id, "minute", now - timedelta(minutes=1))
        minute_remaining = max(0, plan_limits["requests_per_minute"] - minute_usage)
        minute_exceeded = minute_usage >= plan_limits["requests_per_minute"]
        
        # Check hour quota
        hour_usage = self._get_usage_count(user_id, "hour", now - timedelta(hours=1))
        hour_remaining = max(0, plan_limits["requests_per_hour"] - hour_usage)
        hour_exceeded = hour_usage >= plan_limits["requests_per_hour"]
        
        # Check daily quota
        day_usage = self._get_usage_count(user_id, "day", now - timedelta(days=1))
        day_remaining = max(0, plan_limits["requests_per_month"] // 30 - day_usage)  # Approximate daily
        day_exceeded = day_usage >= (plan_limits["requests_per_month"] // 30)
        
        return {
            "minute": {
                "used": minute_usage,
                "limit": plan_limits["requests_per_minute"],
                "remaining": minute_remaining,
                "exceeded": minute_exceeded
            },
            "hour": {
                "used": hour_usage,
                "limit": plan_limits["requests_per_hour"],
                "remaining": hour_remaining,
                "exceeded": hour_exceeded
            },
            "day": {
                "used": day_usage,
                "limit": plan_limits["requests_per_month"] // 30,
                "remaining": day_remaining,
                "exceeded": day_exceeded
            },
            "overall_exceeded": minute_exceeded or hour_exceeded or day_exceeded
        }
    
    def get_usage_stats(self, user_id: str, period: str = "day") -> Dict[str, Any]:
        """
        Get usage statistics for a user.
        
        Args:
            user_id: User identifier
            period: Time period ("day", "week", "month")
            
        Returns:
            Usage statistics
        """
        now = datetime.now(timezone.utc)
        
        if period == "day":
            start_time = now - timedelta(days=1)
        elif period == "week":
            start_time = now - timedelta(weeks=1)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)
        
        # Get usage data
        usage_data = self._get_usage_data(user_id, start_time, now)
        
        # Calculate statistics
        total_requests = len(usage_data)
        successful_requests = sum(1 for u in usage_data if u.get("success", False))
        failed_requests = total_requests - successful_requests
        total_analysis_time = sum(u.get("analysis_time", 0) for u in usage_data)
        total_components = sum(u.get("components_detected", 0) for u in usage_data)
        
        return {
            "period": period,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests / max(total_requests, 1),
            "total_analysis_time": total_analysis_time,
            "average_analysis_time": total_analysis_time / max(total_requests, 1),
            "total_components_detected": total_components,
            "start_time": start_time.isoformat(),
            "end_time": now.isoformat()
        }
    
    def get_user_plan(self, user_id: str) -> str:
        """
        Get user's current plan.
        
        Args:
            user_id: User identifier
            
        Returns:
            Plan name ("free", "pro", "enterprise")
        """
        # In production, this would query the database
        # For now, return based on user ID pattern or default to free
        user_key = f"{USER_PREFIX}{user_id}"
        plan = self.redis.get(f"{user_key}:plan")
        
        if plan:
            return plan
        
        # Default to free plan
        return "free"
    
    def set_user_plan(self, user_id: str, plan: str) -> bool:
        """
        Set user's plan.
        
        Args:
            user_id: User identifier
            plan: Plan name
            
        Returns:
            Success status
        """
        try:
            user_key = f"{USER_PREFIX}{user_id}"
            self.redis.set(f"{user_key}:plan", plan)
            return True
        except Exception as e:
            logger.error(f"Error setting user plan: {e}")
            return False
    
    def get_plan_limits(self, plan: str) -> Dict[str, int]:
        """
        Get limits for a specific plan.
        
        Args:
            plan: Plan name
            
        Returns:
            Plan limits
        """
        limits = {
            "free": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "requests_per_month": 1000
            },
            "pro": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_month": 10000
            },
            "enterprise": {
                "requests_per_minute": 300,
                "requests_per_hour": 5000,
                "requests_per_month": 50000
            }
        }
        
        return limits.get(plan, limits["free"])
    
    def _update_counters(self, user_id: str, endpoint: str, success: bool, analysis_time: float, components_detected: int):
        """Update Redis counters for usage tracking."""
        now = datetime.now(timezone.utc)
        
        # Update minute counter
        minute_key = f"{QUOTA_PREFIX}{user_id}:minute:{now.strftime('%Y%m%d%H%M')}"
        self.redis.incr(minute_key)
        self.redis.expire(minute_key, 120)  # 2 minutes TTL
        
        # Update hour counter
        hour_key = f"{QUOTA_PREFIX}{user_id}:hour:{now.strftime('%Y%m%d%H')}"
        self.redis.incr(hour_key)
        self.redis.expire(hour_key, 7200)  # 2 hours TTL
        
        # Update day counter
        day_key = f"{QUOTA_PREFIX}{user_id}:day:{now.strftime('%Y%m%d')}"
        self.redis.incr(day_key)
        self.redis.expire(day_key, 172800)  # 2 days TTL
        
        # Update success/failure counters
        if success:
            success_key = f"{QUOTA_PREFIX}{user_id}:success:{now.strftime('%Y%m%d')}"
            self.redis.incr(success_key)
            self.redis.expire(success_key, 172800)
        else:
            failure_key = f"{QUOTA_PREFIX}{user_id}:failure:{now.strftime('%Y%m%d')}"
            self.redis.incr(failure_key)
            self.redis.expire(failure_key, 172800)
    
    def _get_usage_count(self, user_id: str, period: str, start_time: datetime) -> int:
        """Get usage count for a specific period."""
        now = datetime.now(timezone.utc)
        
        if period == "minute":
            pattern = f"{QUOTA_PREFIX}{user_id}:minute:*"
        elif period == "hour":
            pattern = f"{QUOTA_PREFIX}{user_id}:hour:*"
        elif period == "day":
            pattern = f"{QUOTA_PREFIX}{user_id}:day:*"
        else:
            return 0
        
        keys = self.redis.keys(pattern)
        total = 0
        
        for key in keys:
            # Extract timestamp from key
            timestamp_str = key.split(":")[-1]
            try:
                if period == "minute":
                    key_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M")
                elif period == "hour":
                    key_time = datetime.strptime(timestamp_str, "%Y%m%d%H")
                elif period == "day":
                    key_time = datetime.strptime(timestamp_str, "%Y%m%d")
                
                if key_time >= start_time:
                    count = self.redis.get(key)
                    if count:
                        total += int(count)
            except ValueError:
                continue
        
        return total
    
    def _get_usage_data(self, user_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get detailed usage data for a time period."""
        usage_data = []
        
        # Get all usage keys for the user
        pattern = f"{USAGE_PREFIX}{user_id}:*"
        keys = self.redis.keys(pattern)
        
        for key in keys:
            # Extract timestamp from key
            timestamp_str = key.split(":")[-1]
            try:
                key_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M")
                if start_time <= key_time <= end_time:
                    # Get usage data from list
                    data_list = self.redis.lrange(key, 0, -1)
                    for data_str in data_list:
                        try:
                            data = json.loads(data_str)
                            usage_data.append(data)
                        except json.JSONDecodeError:
                            continue
            except ValueError:
                continue
        
        return usage_data

# Global usage tracker instance
usage_tracker = UsageTracker()
