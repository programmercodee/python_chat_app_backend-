"""
Authentication service for user registration and login.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.core.exceptions import AuthenticationError, ConflictError
from app.models.user import User
from app.schemas.user import UserCreate
from app.schemas.auth import TokenResponse
from app.config import settings


class AuthService:
    """Service for handling authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def register(self, user_data: UserCreate) -> User:
        """
        Register a new user.
        
        Returns:
            Created user instance
        """
        # Check if email already exists
        result = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise ConflictError(message="Email already registered")
        
        # Check if username already exists
        result = await self.db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise ConflictError(message="Username already taken")
        
        # Create new user
        user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def login(self, email: str, password: str) -> TokenResponse:
        """
        Authenticate user and return tokens.
        """
        # Find user by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError(message="Invalid email or password")
        
        if not user.is_active:
            raise AuthenticationError(message="Account is disabled")
        
        # Update last seen
        user.last_seen = datetime.now(timezone.utc)
        await self.db.flush()
        
        # Generate tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Generate new access token using refresh token.
        """
        # Verify refresh token
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        # Verify user still exists and is active
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise AuthenticationError(message="User not found or inactive")
        
        # Generate new tokens
        access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    
    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
