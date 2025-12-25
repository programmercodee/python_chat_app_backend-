"""
Google OAuth service for token verification and user management.
Verifies Google ID tokens server-side and handles account linking.
"""

from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests

from app.config import settings
from app.models.user import User
from app.core.exceptions import AppException


class GoogleAuthService:
    """
    Service for Google OAuth authentication.
    
    Security rules enforced:
    - Always verify token using Google OAuth 2.0
    - Extract email ONLY from verified token (never trust frontend)
    - Never store Google tokens
    - Issue our own JWT after verification
    """
    
    def __init__(self):
        self.client_id = settings.google_client_id
    
    async def verify_id_token(self, token: str) -> dict:
        """
        Verify Google ID token and return user info.
        
        Returns:
            dict with: email, sub (Google user ID), name, picture
            
        Raises:
            AppException if token is invalid
        """
        try:
            # Verify the token using Google's library
            # This checks signature, expiry, audience, issuer
            # clock_skew_in_seconds handles time sync differences between servers
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.client_id,
                clock_skew_in_seconds=10  # Allow 10 seconds clock difference
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise AppException(
                    message="Invalid token issuer",
                    status_code=401
                )
            
            return {
                'email': idinfo['email'],
                'sub': idinfo['sub'],  # Google's unique user ID
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture'),
                'email_verified': idinfo.get('email_verified', False)
            }
            
        except ValueError as e:
            # Token verification failed
            raise AppException(
                message=f"Invalid Google token: {str(e)}",
                status_code=401
            )
    
    async def find_existing_user(self, google_info: dict) -> User:
        """
        Find existing user by email for Google LOGIN.
        Does NOT create new users - they must register first.
        
        Returns:
            User object if exists
            
        Raises:
            AppException if user not found
        """
        email = google_info['email']
        google_id = google_info['sub']
        
        # Check if user exists by email
        existing_user = await User.find_one(User.email == email)
        
        if not existing_user:
            raise AppException(
                message="No account found with this email. Please register first.",
                status_code=404
            )
        
        # Link Google to existing account if not already linked
        if not existing_user.oauth_provider:
            existing_user.oauth_provider = "google"
            existing_user.oauth_id = google_id
            
            # Update avatar if not set
            if not existing_user.avatar_url and google_info.get('picture'):
                existing_user.avatar_url = google_info['picture']
            
            await existing_user.save()
        
        return existing_user
    
    async def create_google_user(self, google_info: dict) -> User:
        """
        Create new user with Google for REGISTRATION.
        
        Returns:
            New User object
            
        Raises:
            AppException if user already exists
        """
        email = google_info['email']
        google_id = google_info['sub']
        
        # Check if user already exists
        existing_user = await User.find_one(User.email == email)
        
        if existing_user:
            raise AppException(
                message="An account with this email already exists. Please login instead.",
                status_code=409
            )
        
        # Create new user with Google
        base_username = google_info['name'].replace(' ', '_') or email.split('@')[0]
        username = await self._generate_unique_username(base_username)
        
        new_user = User(
            email=email,
            username=username,
            password_hash=None,  # OAuth user, no password
            oauth_provider="google",
            oauth_id=google_id,
            avatar_url=google_info.get('picture')
        )
        
        await new_user.insert()
        return new_user
    
    async def _generate_unique_username(self, base: str) -> str:
        """Generate a unique username, appending numbers if needed."""
        import re
        base = re.sub(r'[^a-zA-Z0-9_]', '', base)[:40]
        
        if not base:
            base = "user"
        
        username = base
        counter = 1
        
        while await User.find_one(User.username == username):
            username = f"{base}_{counter}"
            counter += 1
        
        return username
