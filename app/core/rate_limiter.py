"""
Redis-based rate limiting utility.
Provides protection against brute force attacks on authentication endpoints.
"""

import logging
from typing import Tuple
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter using Redis with sliding window approach.
    
    Usage:
        limiter = RateLimiter()
        allowed, remaining, retry_after = await limiter.check("forgot:user@email.com", max_requests=3, window=3600)
        if not allowed:
            raise RateLimitExceeded(retry_after=retry_after)
    """
    
    async def check(
        self, 
        key: str, 
        max_requests: int, 
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier (e.g., "forgot:email" or "login:ip")
            max_requests: Maximum number of requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        redis_key = f"ratelimit:{key}"
        
        try:
            # Get current count
            current = await redis_client.client.get(redis_key)
            current_count = int(current) if current else 0
            
            if current_count >= max_requests:
                # Get TTL to know when limit resets
                ttl = await redis_client.client.ttl(redis_key)
                return (False, 0, ttl if ttl > 0 else window_seconds)
            
            # Increment counter
            pipe = redis_client.client.pipeline()
            pipe.incr(redis_key)
            if current_count == 0:
                # Set expiry only on first request
                pipe.expire(redis_key, window_seconds)
            await pipe.execute()
            
            remaining = max_requests - current_count - 1
            return (True, remaining, 0)
            
        except Exception as e:
            logger.error(f"Rate limiter error for {key}: {e}")
            # Fail open - don't block users if Redis fails
            return (True, max_requests, 0)
    
    async def is_locked_out(self, key: str) -> Tuple[bool, int]:
        """
        Check if key is in lockout period.
        
        Returns:
            Tuple of (is_locked, remaining_seconds)
        """
        lockout_key = f"lockout:{key}"
        
        try:
            locked = await redis_client.client.exists(lockout_key)
            if locked:
                ttl = await redis_client.client.ttl(lockout_key)
                return (True, ttl if ttl > 0 else 0)
            return (False, 0)
        except Exception as e:
            logger.error(f"Lockout check error for {key}: {e}")
            return (False, 0)
    
    async def apply_lockout(self, key: str, duration_seconds: int) -> None:
        """
        Apply a lockout period for a key.
        
        Args:
            key: Identifier to lock (e.g., email or IP)
            duration_seconds: How long to lock
        """
        lockout_key = f"lockout:{key}"
        
        try:
            await redis_client.client.setex(lockout_key, duration_seconds, "1")
            logger.warning(f"Lockout applied: {key} for {duration_seconds}s")
        except Exception as e:
            logger.error(f"Failed to apply lockout for {key}: {e}")
    
    async def reset(self, key: str) -> None:
        """
        Reset rate limit counter for a key (e.g., after successful login).
        """
        redis_key = f"ratelimit:{key}"
        try:
            await redis_client.client.delete(redis_key)
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {key}: {e}")


# Singleton instance
rate_limiter = RateLimiter()
