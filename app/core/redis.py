"""
Redis client for session management, presence tracking, and pub/sub.
"""

from typing import Optional
import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """
    Async Redis client wrapper with connection management.
    Provides methods for common operations used in the messaging platform.
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
    
    async def connect(self) -> None:
        """Initialize Redis connection."""
        self._client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        # Test connection
        await self._client.ping()
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._pubsub:
            await self._pubsub.close()
        if self._client:
            await self._client.close()
    
    @property
    def client(self) -> redis.Redis:
        """Get the Redis client instance."""
        if not self._client:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client
    
    # ==================== Session Management ====================
    
    async def set_user_session(
        self,
        user_id: str,
        socket_id: str,
        expire_seconds: int = 86400,  # 24 hours
    ) -> None:
        """
        Store user's socket session.
        Maps user_id -> socket_id for routing messages.
        """
        await self.client.setex(
            f"session:{user_id}",
            expire_seconds,
            socket_id,
        )
    
    async def get_user_session(self, user_id: str) -> Optional[str]:
        """Get socket ID for a user."""
        return await self.client.get(f"session:{user_id}")
    
    async def delete_user_session(self, user_id: str) -> None:
        """Remove user's session on disconnect."""
        await self.client.delete(f"session:{user_id}")
    
    # ==================== Presence Tracking ====================
    
    async def set_user_online(
        self,
        user_id: str,
        expire_seconds: int = 300,  # 5 minutes, refresh on activity
    ) -> None:
        """Mark user as online with automatic expiry."""
        await self.client.setex(f"online:{user_id}", expire_seconds, "1")
    
    async def set_user_offline(self, user_id: str) -> None:
        """Mark user as offline."""
        await self.client.delete(f"online:{user_id}")
    
    async def is_user_online(self, user_id: str) -> bool:
        """Check if user is online."""
        return await self.client.exists(f"online:{user_id}") > 0
    
    async def get_online_users(self, user_ids: list[str]) -> list[str]:
        """Get list of online users from a list of user IDs."""
        if not user_ids:
            return []
        
        pipeline = self.client.pipeline()
        for user_id in user_ids:
            pipeline.exists(f"online:{user_id}")
        
        results = await pipeline.execute()
        return [
            user_id
            for user_id, is_online in zip(user_ids, results)
            if is_online
        ]
    
    # ==================== Typing Indicators ====================
    
    async def set_typing(
        self,
        user_id: str,
        conversation_id: str,
        expire_seconds: int = 5,
    ) -> None:
        """Mark user as typing in a conversation."""
        await self.client.setex(
            f"typing:{conversation_id}:{user_id}",
            expire_seconds,
            "1",
        )
    
    async def clear_typing(self, user_id: str, conversation_id: str) -> None:
        """Clear typing indicator."""
        await self.client.delete(f"typing:{conversation_id}:{user_id}")
    
    async def get_typing_users(self, conversation_id: str) -> list[str]:
        """Get users currently typing in a conversation."""
        pattern = f"typing:{conversation_id}:*"
        keys = await self.client.keys(pattern)
        return [key.split(":")[-1] for key in keys]
    
    # ==================== Pub/Sub ====================
    
    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""
        await self.client.publish(channel, message)
    
    async def subscribe(self, *channels: str) -> redis.client.PubSub:
        """Subscribe to one or more channels."""
        self._pubsub = self.client.pubsub()
        await self._pubsub.subscribe(*channels)
        return self._pubsub


# Global redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get Redis client."""
    return redis_client
