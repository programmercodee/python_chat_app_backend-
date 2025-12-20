"""
Contact model for user contact lists.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class ContactStatus(str, Enum):
    """Status of a contact relationship."""
    PENDING = "pending"    # Request sent, awaiting acceptance
    ACCEPTED = "accepted"  # Contact request accepted
    BLOCKED = "blocked"    # User has blocked this contact


class Contact(Base):
    """
    Contact model for managing user contact lists.
    """
    
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("user_id", "contact_id", name="uq_user_contact"),
    )
    
    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ContactStatus] = mapped_column(
        SQLEnum(ContactStatus),
        default=ContactStatus.PENDING,
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="contacts",
    )
    contact_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[contact_id],
    )
    
    def __repr__(self) -> str:
        return f"<Contact(user={self.user_id}, contact={self.contact_id})>"
