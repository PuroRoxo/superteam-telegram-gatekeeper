"""
Redis-based rate limiter for preventing spam and abuse.
"""

import asyncio
from typing import Optional
import redis.asyncio as redis
from datetime import datetime, timedelta
import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Redis-based rate limiter with sliding window algorithm."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.requests_limit = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_window_seconds
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Rate limiter initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {e}")
            raise
    
    async def is_allowed(self, key: str, custom_limit: Optional[int] = None) -> bool:
        """
        Check if a request is allowed based on rate limits.
        
        Args:
            key: Unique identifier for the rate limit (e.g., user_id)
            custom_limit: Override default request limit
            
        Returns:
            True if request is allowed, False otherwise
        """
        if not self.redis_client:
            logger.warning("Rate limiter not initialized, allowing request")
            return True
        
        try:
            limit = custom_limit or self.requests_limit
            rate_limit_key = f"rate_limit:{key}"
            
            # Get current timestamp
            now = int(datetime.utcnow().timestamp())
            window_start = now - self.window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(rate_limit_key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(rate_limit_key)
            
            # Add current request
            pipe.zadd(rate_limit_key, {str(now): now})
            
            # Set expiry for cleanup
            pipe.expire(rate_limit_key, self.window_seconds + 1)
            
            results = await pipe.execute()
            current_requests = results[1]  # Result of zcard
            
            is_allowed = current_requests < limit
            
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for key: {key}",
                    current_requests=current_requests,
                    limit=limit,
                    window_seconds=self.window_seconds
                )
            
            return is_allowed
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if rate limiter fails
            return True
    
    async def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests for a key in the current window."""
        if not self.redis_client:
            return self.requests_limit
        
        try:
            rate_limit_key = f"rate_limit:{key}"
            now = int(datetime.utcnow().timestamp())
            window_start = now - self.window_seconds
            
            # Clean up old entries and count current
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(rate_limit_key, 0, window_start)
            pipe.zcard(rate_limit_key)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            return max(0, self.requests_limit - current_requests)
            
        except Exception as e:
            logger.error(f"Failed to get remaining requests: {e}")
            return 0
    
    async def reset_user_limit(self, key: str):
        """Reset rate limit for a specific key (admin function)."""
        if not self.redis_client:
            return
        
        try:
            rate_limit_key = f"rate_limit:{key}"
            await self.redis_client.delete(rate_limit_key)
            logger.info(f"Rate limit reset for key: {key}")
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {key}: {e}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Rate limiter connection closed")