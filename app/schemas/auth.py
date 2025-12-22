"""
Authentication schemas for login and token management.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str = Field(min_length=1)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
            }
        }
    )


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        description="Access token expiration time in seconds"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing access token."""
    refresh_token: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class TokenPayload(BaseModel):
    """Schema for decoded JWT token payload."""
    sub: str  # Subject (user ID)
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: str  # Token type (access/refresh)


class GoogleAuthRequest(BaseModel):
    """Schema for Google OAuth authentication request."""
    id_token: str = Field(..., description="Google ID token from frontend")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )
