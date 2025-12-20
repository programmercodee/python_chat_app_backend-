"""
User service for profile management.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.user import UserUpdate


class UserService:
    """Service for managing user profiles."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user(self, user_id: str) -> User:
        """
        Get user by ID.
        
        Raises:
            NotFoundError: If user doesn't exist
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError(message="User not found")
        
        return user
    
    async def get_user_by_username(self, username: str) -> User:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError(message="User not found")
        
        return user
    
    async def update_user(self, user_id: str, update_data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_user(user_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def update_public_key(self, user_id: str, public_key: str) -> User:
        """Update user's public encryption key."""
        user = await self.get_user(user_id)
        user.public_key = public_key
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def get_public_key(self, user_id: str) -> Optional[str]:
        """Get user's public encryption key."""
        user = await self.get_user(user_id)
        return user.public_key
    
    async def update_last_seen(self, user_id: str) -> None:
        """Update user's last seen timestamp."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.last_seen = datetime.now(timezone.utc)
            await self.db.flush()
    
    async def search_users(
        self,
        query: str,
        exclude_user_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[User]:
        """
        Search users by username or email.
        """
        stmt = select(User).where(
            (User.username.ilike(f"%{query}%")) |
            (User.email.ilike(f"%{query}%"))
        ).where(User.is_active == True)
        
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        
        return list(result.scalars().all())
