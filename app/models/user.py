"""
User model for authentication and profile management.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Text, DateTime, Boolean, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.conversation import ConversationMember
    from app.models.message import Message


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class User(Base):
    """
    User model representing a registered user.
    """
    
    __tablename__ = "users"
    
    # Using CHAR(36) for UUID since MySQL doesn't have native UUID type
    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=generate_uuid,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    public_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        foreign_keys="Contact.user_id",
        back_populates="user",
        lazy="selectin",
    )
    conversation_memberships: Mapped[list["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="user",
        lazy="selectin",
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
