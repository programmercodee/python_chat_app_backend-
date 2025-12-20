"""
Conversation schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.conversation import ConversationType


# Define MessagePreview FIRST to avoid forward reference issues
class MessagePreview(BaseModel):
    """Preview of last message in conversation."""
    id: str
    sender_id: Optional[str]
    sender_username: Optional[str] = None
    content_type: str
    created_at: datetime
    is_read: bool


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    type: ConversationType = ConversationType.DIRECT
    name: Optional[str] = Field(None, max_length=100)
    member_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of user IDs to add to the conversation"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "direct",
                "member_ids": ["123e4567-e89b-12d3-a456-426614174000"],
            }
        }
    )


class ConversationMemberResponse(BaseModel):
    """Schema for conversation member data."""
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    joined_at: datetime
    is_online: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Schema for conversation response data."""
    id: str
    type: ConversationType
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: list[ConversationMemberResponse] = []
    last_message: Optional[MessagePreview] = None
    unread_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class ConversationList(BaseModel):
    """Schema for list of conversations."""
    conversations: list[ConversationResponse]
    total: int


class ConversationUpdate(BaseModel):
    """Schema for updating conversation (e.g., group name)."""
    name: Optional[str] = Field(None, max_length=100)


class AddMemberRequest(BaseModel):
    """Schema for adding member to group conversation."""
    user_id: str
