"""
Contact model for user contact lists.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class ContactStatus(str, Enum):
    """Status of a contact relationship."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class Contact(Document):
    """
    Contact document for managing user contact lists.
    """
    
    user_id: PydanticObjectId = Field(..., index=True)
    contact_id: PydanticObjectId = Field(..., index=True)
    status: ContactStatus = ContactStatus.PENDING
    nickname: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Denormalized contact user info for quick access
    contact_username: Optional[str] = None
    contact_email: Optional[str] = None
    
    class Settings:
        name = "contacts"
        indexes = [
            [("user_id", 1), ("contact_id", 1)],
        ]
    
    def __repr__(self) -> str:
        return f"<Contact(user={self.user_id}, contact={self.contact_id})>"
