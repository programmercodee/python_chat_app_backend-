"""
Authentication service for user registration and login.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from beanie import PydanticObjectId
from fastapi.concurrency import run_in_threadpool

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
import secrets
from datetime import timedelta
from app.core.redis import redis_client
from app.services.email_service import email_service


class AuthService:
    """Service for handling authentication operations."""
    
    async def register(self, user_data: UserCreate) -> User:
        """
        Register a new user.
        
        Returns:
            Created user instance
        """
        # Check if email already exists
        existing_email = await User.find_one(User.email == user_data.email)
        if existing_email:
            raise ConflictError(message="Email already registered")
        
        # Check if username already exists
        existing_username = await User.find_one(User.username == user_data.username)
        if existing_username:
            raise ConflictError(message="Username already taken")
        
        # Create new user
        user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
        )
        
        await user.insert()
        return user
    
    async def login(self, email: str, password: str) -> TokenResponse:
        """
        Authenticate user and return tokens.
        """
        # Find user by email
        user = await User.find_one(User.email == email)
        
        # Check if user exists and has a password (OAuth-only users can't login with password)
        if not user:
            raise AuthenticationError(message="Invalid email or password")
        
        if not user.password_hash:
            raise AuthenticationError(message="This account uses Google login. Please sign in with Google.")
        
        # Verify password in threadpool to avoid blocking event loop
        if not await run_in_threadpool(verify_password, password, user.password_hash):
            raise AuthenticationError(message="Invalid email or password")
        
        if not user.is_active:
            raise AuthenticationError(message="Account is disabled")
        
        return await self.issue_tokens_for_user(user)
    
    async def issue_tokens_for_user(self, user: User) -> TokenResponse:
        """
        Issue JWT tokens for a user (used by both password and OAuth login).
        """
        # Update last seen
        user.last_seen = datetime.now(timezone.utc)
        await user.save()
        
        # Generate tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        
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
        try:
            user = await User.get(PydanticObjectId(user_id))
        except Exception:
            user = None
        
        if not user or not user.is_active:
            raise AuthenticationError(message="User not found or inactive")
        
        # Generate new tokens
        access_token = create_access_token(subject=str(user.id))
        new_refresh_token = create_refresh_token(subject=str(user.id))
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    
    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        try:
            return await User.get(PydanticObjectId(user_id))
        except Exception:
            return None
    
    async def check_username_availability(self, username: str) -> bool:
        """
        Check if a username is available.
        
        Returns:
            True if username is available, False if taken
        """
        existing = await User.find_one(User.username == username)
        return existing is None

    async def forgot_password(self, email: str):
        """
        Generate OTP and send email for password reset.
        """
        user = await User.find_one(User.email == email)
        if not user:
            # security: do not reveal if user exists, just return
            return

        if not user.password_hash:
            # Google-only account, cannot reset password
            from app.core.exceptions import ValidationError
            raise ValidationError(message="This account uses Google Sign-In. Please login with Google instead.")

        # Generate 6-digit OTP
        otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Store in Redis (10 minutes)
        await redis_client.client.setex(f"reset_otp:{email}", 600, otp)
        
        # Send email (gracefully handle SMTP failures on some hosting providers)
        try:
            await email_service.send_otp_email(email, otp)
        except Exception as e:
            # Log OTP for testing if email fails (e.g., Render blocks SMTP)
            import logging
            logging.getLogger("app").warning(f"Email failed, OTP for {email}: {otp} | Error: {e}")

    async def verify_otp(self, email: str, otp: str) -> str:
        """
        Verify OTP and return a reset token.
        """
        stored_otp = await redis_client.client.get(f"reset_otp:{email}")
        
        if not stored_otp or stored_otp != otp:
             raise AuthenticationError(message="Invalid or expired OTP")
             
        # Generate temporary reset token (Valid for 5 mins)
        # Using email as subject and marking type as password_reset
        reset_token = create_access_token(
            subject=email, 
            expires_delta=timedelta(minutes=5),
            extra_claims={"type": "password_reset"}  # Override default "access" type
        )
        return reset_token

    async def reset_password(self, reset_token: str, new_password: str):
        """
        Reset password using secure token.
        """
        try:
             # Verify token with password_reset type (prevents using regular access tokens)
             payload = verify_token(reset_token, token_type="password_reset")
             email = payload.get("sub")
        except Exception:
             raise AuthenticationError(message="Invalid or expired token")
             
        user = await User.find_one(User.email == email)
        if not user:
             raise AuthenticationError(message="User not found")
             
        user.password_hash = get_password_hash(new_password)
        await user.save()
        
        # Clean up OTP
        await redis_client.client.delete(f"reset_otp:{email}")

