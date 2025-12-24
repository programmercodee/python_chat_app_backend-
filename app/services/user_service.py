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

    # -----------------------------
    # USERNAME VALIDATION & SELECTION
    # -----------------------------
    
    # Regex pattern: must start with letter, can contain letters/numbers/dots/underscores, must end with alphanumeric
    USERNAME_PATTERN = re.compile(r'^[a-z](?:[a-z0-9._]{1,18}[a-z0-9])?$|^[a-z][a-z0-9]?$')
    
    # Reserved usernames that cannot be used
    RESERVED_USERNAMES = frozenset([
        'admin', 'administrator', 'support', 'system', 'moderator',
        'official', 'help', 'root', 'null', 'undefined', 'api',
        'www', 'mail', 'email', 'test', 'demo', 'guest', 'anonymous',
        'bot', 'robot', 'service', 'account', 'user', 'users'
    ])
    
    @staticmethod
    def normalize_username(username: str) -> str:
        """
        Normalize username: lowercase and trim whitespace.
        """
        return username.lower().strip()
    
    @classmethod
    def validate_username(cls, username: str) -> tuple[bool, str]:
        """
        Validate username against all rules.
        
        Returns:
            (is_valid, error_message)
        """
        # Normalize first
        username = cls.normalize_username(username)
        
        # Length check
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        if len(username) > 20:
            return False, "Username must be at most 20 characters"
        
        # Must start with a letter
        if username[0].isdigit():
            return False, "Username must start with a letter"
        
        # Pattern check
        if not cls.USERNAME_PATTERN.match(username):
            return False, "Username can only contain letters, numbers, dots and underscores"
        
        # No consecutive dots or underscores
        if '..' in username or '__' in username or '._' in username or '_.' in username:
            return False, "Username cannot have consecutive dots or underscores"
        
        # Reserved check
        if username in cls.RESERVED_USERNAMES:
            return False, "This username is reserved"
        
        return True, ""
    
    async def is_username_available(self, username: str) -> bool:
        """
        Check if username is available (case-insensitive).
        """
        normalized = self.normalize_username(username)
        # Case-insensitive search
        existing = await User.find_one(
            {"username": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}}
        )
        return existing is None
    
    async def generate_username_suggestions(self, base_username: str, count: int = 5) -> list[str]:
        """
        Generate available username suggestions when requested username is taken.
        """
        import random
        
        base = self.normalize_username(base_username)
        # Truncate if needed to make room for suffixes
        if len(base) > 16:
            base = base[:16]
        
        suggestions = []
        suffixes = ['_dev', '_app', '_x', '_io', '_me']
        
        attempts = 0
        max_attempts = 30  # Prevent infinite loop
        
        while len(suggestions) < count and attempts < max_attempts:
            attempts += 1
            
            # Strategy 1: Append random digits
            if random.random() < 0.5:
                digits = str(random.randint(1, 9999))
                candidate = f"{base}{digits}"
            # Strategy 2: Append suffix
            elif random.random() < 0.7:
                suffix = random.choice(suffixes)
                candidate = f"{base}{suffix}"
            # Strategy 3: Insert underscore or dot
            else:
                if len(base) > 4:
                    pos = random.randint(2, len(base) - 2)
                    sep = random.choice(['.', '_'])
                    candidate = f"{base[:pos]}{sep}{base[pos:]}"
                else:
                    candidate = f"{base}_{random.randint(1, 99)}"
            
            # Validate and check availability
            is_valid, _ = self.validate_username(candidate)
            if is_valid and await self.is_username_available(candidate):
                if candidate not in suggestions:
                    suggestions.append(candidate)
        
        return suggestions
    
    async def set_username(self, user_id: str, username: str) -> tuple[User | None, str, list[str]]:
        """
        Validate and set username for a user.
        
        Returns:
            (user, error_message, suggestions)
            - If successful: (user, "", [])
            - If validation fails: (None, error_message, [])
            - If taken: (None, "Username is taken", [suggestions...])
        """
        # Normalize
        normalized = self.normalize_username(username)
        
        # Validate
        is_valid, error = self.validate_username(normalized)
        if not is_valid:
            return None, error, []
        
        # Check availability
        user = await self.get_user(user_id)
        
        # If user already has this username, return success
        if user.username and self.normalize_username(user.username) == normalized:
            return user, "", []
        
        # Check if taken by another user
        if not await self.is_username_available(normalized):
            suggestions = await self.generate_username_suggestions(normalized)
            return None, "Username is already taken", suggestions
        
        # Set username
        user.username = normalized
        await user.save()
        
        return user, "", []
