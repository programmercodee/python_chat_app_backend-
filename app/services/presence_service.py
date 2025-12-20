"""
Presence service for tracking online/offline status.
"""

from typing import Optional

from app.core.redis import RedisClient


class PresenceService:
    """
    Service for managing user presence (online/offline status).
    """
    
    def __init__(self, redis: RedisClient):
        self.redis = redis
    
    async def set_online(self, user_id: str, socket_id: str) -> None:
        """Mark user as online and store their socket ID."""
        await self.redis.set_user_session(user_id, socket_id)
        await self.redis.set_user_online(user_id)
    
    async def set_offline(self, user_id: str) -> None:
        """Mark user as offline and remove their session."""
        await self.redis.delete_user_session(user_id)
        await self.redis.set_user_offline(user_id)
    
    async def refresh_online(self, user_id: str) -> None:
        """Refresh user's online status (extends expiry)."""
        await self.redis.set_user_online(user_id)
    
    async def is_online(self, user_id: str) -> bool:
        """Check if a user is currently online."""
        return await self.redis.is_user_online(user_id)
    
    async def get_online_users(self, user_ids: list[str]) -> list[str]:
        """Get which users from a list are currently online."""
        # If Redis is not available, just return empty (no one appears online)
        try:
            return await self.redis.get_online_users(user_ids)
        except Exception:
            # Redis not running, skip online status check
            return []
    
    async def get_socket_id(self, user_id: str) -> Optional[str]:
        """Get socket ID for a user (if online)."""
        return await self.redis.get_user_session(user_id)
    
    async def set_typing(self, user_id: str, conversation_id: str) -> None:
        """Mark user as typing in a conversation."""
        await self.redis.set_typing(user_id, conversation_id)
    
    async def clear_typing(self, user_id: str, conversation_id: str) -> None:
        """Clear typing indicator for user."""
        await self.redis.clear_typing(user_id, conversation_id)
    
    async def get_typing_users(self, conversation_id: str) -> list[str]:
        """Get users currently typing in a conversation."""
        return await self.redis.get_typing_users(conversation_id)
