"""
User service for profile management.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional
import re

from beanie import PydanticObjectId

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.user import UserUpdate


class UserService:
    """Service for managing user profiles."""
    
    async def get_user(self, user_id: str) -> User:
        """
        Get user by ID.
        
        Raises:
            NotFoundError: If user doesn't exist
        """
        try:
            user = await User.get(PydanticObjectId(user_id))
        except Exception:
            user = None
        
        if not user:
            raise NotFoundError(message="User not found")
        
        return user
    
    async def get_user_by_username(self, username: str) -> User:
        """Get user by username."""
        user = await User.find_one(User.username == username)
        
        if not user:
            raise NotFoundError(message="User not found")
        
        return user
    
    async def update_user(self, user_id: str, update_data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_user(user_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await user.save()
        return user
    
    async def update_public_key(self, user_id: str, public_key: str) -> User:
        """Update user's public encryption key."""
        user = await self.get_user(user_id)
        user.public_key = public_key
        await user.save()
        return user
    
    async def get_public_key(self, user_id: str) -> Optional[str]:
        """Get user's public encryption key."""
        user = await self.get_user(user_id)
        return user.public_key
    
    async def update_last_seen(self, user_id: str) -> None:
        """Update user's last seen timestamp."""
        try:
            user = await User.get(PydanticObjectId(user_id))
            if user:
                user.last_seen = datetime.now(timezone.utc)
                await user.save()
        except Exception:
            pass
    
    async def search_users(
        self,
        query: str,
        exclude_user_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[User]:
        """
        Search users by username or email.
        """
        # Case-insensitive regex search
        regex_pattern = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
        
        search_query = User.find(
            {
                "$and": [
                    {"is_active": True},
                    {
                        "$or": [
                            {"username": {"$regex": regex_pattern}},
                            {"email": {"$regex": regex_pattern}}
                        ]
                    }
                ]
            }
        )
        
        if exclude_user_id:
            try:
                exclude_oid = PydanticObjectId(exclude_user_id)
                search_query = User.find(
                    {
                        "$and": [
                            {"is_active": True},
                            {"_id": {"$ne": exclude_oid}},
                            {
                                "$or": [
                                    {"username": {"$regex": regex_pattern}},
                                    {"email": {"$regex": regex_pattern}}
                                ]
                            }
                        ]
                    }
                )
            except Exception:
                pass
        
        users = await search_query.limit(limit).to_list()
        return users
