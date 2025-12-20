"""
Contact schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.contact import ContactStatus


class ContactCreate(BaseModel):
    """Schema for adding a new contact."""
    contact_id: str = Field(..., description="User ID of the contact to add")
    nickname: Optional[str] = Field(None, max_length=50)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contact_id": "123e4567-e89b-12d3-a456-426614174000",
                "nickname": "Best Friend",
            }
        }
    )


class ContactUpdate(BaseModel):
    """Schema for updating a contact."""
    nickname: Optional[str] = Field(None, max_length=50)
    status: Optional[ContactStatus] = None


class ContactUserInfo(BaseModel):
    """Schema for contact's user information."""
    id: str
    username: str
    email: str
    avatar_url: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ContactResponse(BaseModel):
    """Schema for contact response data."""
    id: str
    user_id: str
    contact_id: str
    status: ContactStatus
    nickname: Optional[str] = None
    created_at: datetime
    contact_user: ContactUserInfo
    
    model_config = ConfigDict(from_attributes=True)


class ContactList(BaseModel):
    """Schema for list of contacts."""
    contacts: list[ContactResponse]
    total: int


class ContactRequest(BaseModel):
    """Schema for incoming contact request."""
    id: str
    from_user: ContactUserInfo
    created_at: datetime


class ContactRequestList(BaseModel):
    """Schema for list of pending contact requests."""
    requests: list[ContactRequest]
    total: int
