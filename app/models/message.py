"""
Message model for storing encrypted messages.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class Message(Document):
    """
    Message document for storing encrypted chat messages.
    
    The server stores only encrypted content - it cannot read message contents.
    """
    
    conversation_id: PydanticObjectId = Field(..., index=True)
    sender_id: Optional[PydanticObjectId] = Field(None, index=True)
    
    # Encrypted content - stored as base64 encoded string
    encrypted_content: str
    
    # Nonce for AES-GCM decryption
    nonce: str
    

    status: str = "sent"  # "sent" | "delivered" | "read"

    # Content type for proper rendering on client
    content_type: str = "text"
    
    # Delivery status
    is_delivered: bool = False
    is_read: bool = False
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    
    class Settings:
        name = "messages"
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, sender={self.sender_id})>"
