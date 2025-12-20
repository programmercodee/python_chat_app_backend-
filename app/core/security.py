"""
Security utilities for authentication and password management.
Handles JWT token creation/verification and password hashing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from jose import JWTError, jwt
import bcrypt

from app.config import settings
from app.core.exceptions import AuthenticationError


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string
    """
    # Truncate password to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(
    subject: str | uuid.UUID,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Custom expiration time
        extra_claims: Additional claims to include in the token
        
    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    
    if extra_claims:
        to_encode.update(extra_claims)
    
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str | uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token with longer expiration.
    
    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Custom expiration time
        
    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise AuthenticationError(
                message=f"Invalid token type. Expected {token_type}."
            )
        
        # Check if subject exists
        if not payload.get("sub"):
            raise AuthenticationError(message="Token missing subject claim")
        
        return payload
        
    except JWTError as e:
        raise AuthenticationError(
            message="Could not validate credentials",
            details=str(e),
        )
