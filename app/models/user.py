"""
User model for authentication and profile management.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field, EmailStr


class User(Document):
    """
    User document representing a registered user.
    Supports both email/password and OAuth login.
    """
    
    email: Indexed(EmailStr, unique=True)
    username: Indexed(str, unique=True)
    password_hash: Optional[str] = None  # Nullable for OAuth-only users
    
    # OAuth fields (for account linking)
    oauth_provider: Optional[str] = None  # "google" | null
    oauth_id: Optional[str] = None        # Provider's user ID (Google 'sub')
    
    public_key: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: Optional[datetime] = None
    
    class Settings:
        name = "users"
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
