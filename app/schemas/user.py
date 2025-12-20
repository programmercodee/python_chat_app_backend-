"""
User schemas for request/response validation.
Works with MongoDB ObjectId by converting to string.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserBase(BaseModel):
    """Base schema with common user fields."""
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(min_length=8, max_length=100)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "john_doe",
                "password": "SecurePass123!",
            }
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserResponse(UserBase):
    """Schema for user response data."""
    id: str
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_seen: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('id', mode='before')
    @classmethod
    def convert_id_to_string(cls, v: Any) -> str:
        """Convert MongoDB ObjectId to string."""
        return str(v) if v else ""


class UserPublicKey(BaseModel):
    """Schema for user's public encryption key."""
    public_key: str = Field(
        ...,
        description="Base64-encoded X25519 public key for E2E encryption"
    )


class UserWithPublicKey(UserResponse):
    """User response including public key for encryption."""
    public_key: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserOnlineStatus(BaseModel):
    """Schema for user online status."""
    user_id: str
    is_online: bool
    last_seen: Optional[datetime] = None
