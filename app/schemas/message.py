"""
Message schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class MessageCreate(BaseModel):
    """Schema for creating a new message (via REST API)."""
    conversation_id: str
    encrypted_content: str = Field(
        ...,
        description="Base64-encoded AES-256-GCM encrypted message content"
    )
    nonce: str = Field(
        ...,
        max_length=32,
        description="Base64-encoded encryption nonce (12 bytes)"
    )
    content_type: str = Field(default="text", max_length=50)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "encrypted_content": "SGVsbG8gV29ybGQh...",
                "nonce": "YWJjZGVmZ2hpamts",
                "content_type": "text",
            }
        }
    )


class MessageSocketCreate(BaseModel):
    """Schema for creating a message via Socket.IO."""
    to: str = Field(..., description="Recipient user ID (for direct messages)")
    encrypted_content: str
    nonce: str
    content_type: str = "text"


class MessageResponse(BaseModel):
    """Schema for message response data."""
    id: str
    conversation_id: str
    sender_id: Optional[str]
    encrypted_content: str
    nonce: str
    content_type: str
    status: str = "sent"  # "sent" | "delivered" | "read"
    is_delivered: bool = False  # Computed for backwards compatibility
    is_read: bool = False  # Computed for backwards compatibility
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MessageList(BaseModel):
    """Schema for paginated message list."""
    messages: list[MessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class MessageDelivered(BaseModel):
    """Schema for message delivery confirmation."""
    message_id: str
    delivered_at: datetime


class MessageRead(BaseModel):
    """Schema for marking messages as read."""
    message_ids: list[str]


class MessagesReadConfirmation(BaseModel):
    """Schema for read receipt confirmation."""
    message_ids: list[str]
    read_by: str
    read_at: datetime
