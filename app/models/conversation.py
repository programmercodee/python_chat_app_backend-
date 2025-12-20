"""
Conversation model for chats.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from beanie import Document, PydanticObjectId
from pydantic import Field


class ConversationType(str, Enum):
    """Type of conversation."""
    DIRECT = "direct"
    GROUP = "group"


class ConversationMember(Document):
    """
    Conversation member document for tracking users in conversations.
    """
    
    conversation_id: PydanticObjectId = Field(..., index=True)
    user_id: PydanticObjectId = Field(..., index=True)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_read_at: Optional[datetime] = None
    
    # Denormalized user info for quick access
    username: Optional[str] = None
    
    class Settings:
        name = "conversation_members"
        indexes = [
            [("conversation_id", 1), ("user_id", 1)],
        ]
    
    def __repr__(self) -> str:
        return f"<ConversationMember(conversation={self.conversation_id}, user={self.user_id})>"


class Conversation(Document):
    """
    Conversation document representing a chat (direct or group).
    """
    
    type: ConversationType = ConversationType.DIRECT
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Store member user IDs for quick lookup
    member_ids: List[PydanticObjectId] = []
    
    class Settings:
        name = "conversations"
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, type={self.type.value})>"
