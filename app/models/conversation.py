"""
Conversation and ConversationMember models.
Supports both direct messages and group chats.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class ConversationType(str, Enum):
    """Type of conversation."""
    DIRECT = "direct"  # One-on-one chat
    GROUP = "group"    # Group chat


class Conversation(Base):
    """
    Conversation model representing a chat (direct or group).
    """
    
    __tablename__ = "conversations"
    
    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=generate_uuid,
    )
    type: Mapped[ConversationType] = mapped_column(
        SQLEnum(ConversationType),
        default=ConversationType.DIRECT,
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Relationships
    members: Mapped[list["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, type={self.type.value})>"


class ConversationMember(Base):
    """
    Association table for users in conversations.
    """
    
    __tablename__ = "conversation_members"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
    )
    
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
    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="conversation_memberships",
    )
    
    def __repr__(self) -> str:
        return f"<ConversationMember(conversation={self.conversation_id}, user={self.user_id})>"
