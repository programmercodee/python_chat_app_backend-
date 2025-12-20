"""
Message model for storing encrypted messages.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class Message(Base):
    """
    Message model for storing encrypted chat messages.
    
    The server stores only encrypted content - it cannot read message contents.
    """
    
    __tablename__ = "messages"
    
    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=generate_uuid,
    )
    conversation_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[Optional[str]] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Encrypted content - stored as base64 encoded string
    encrypted_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Nonce for AES-GCM decryption
    nonce: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    
    # Content type for proper rendering on client
    content_type: Mapped[str] = mapped_column(
        String(50),
        default="text",
        nullable=False,
    )
    
    # Delivery status
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="sent_messages",
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, sender={self.sender_id})>"
