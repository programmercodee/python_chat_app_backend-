"""
Contact service for managing user contacts.
"""

from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.models.contact import Contact, ContactStatus
from app.models.user import User


class ContactService:
    """Service for managing user contacts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_contact(
        self,
        user_id: str,
        contact_id: str,
        nickname: Optional[str] = None,
    ) -> Contact:
        """
        Send a contact request to another user.
        """
        if user_id == contact_id:
            raise ValidationError(message="Cannot add yourself as a contact")
        
        # Verify contact user exists
        result = await self.db.execute(
            select(User).where(User.id == contact_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(message="User not found")
        
        # Check if contact already exists
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_id == contact_id,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            if existing.status == ContactStatus.BLOCKED:
                raise ValidationError(message="You have blocked this user")
            raise ConflictError(message="Contact already exists")
        
        # Check if the other user has already added us
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    Contact.user_id == contact_id,
                    Contact.contact_id == user_id,
                )
            )
        )
        reverse_contact = result.scalar_one_or_none()
        
        # If they added us, auto-accept
        status = ContactStatus.ACCEPTED if reverse_contact else ContactStatus.PENDING
        
        contact = Contact(
            user_id=user_id,
            contact_id=contact_id,
            nickname=nickname,
            status=status,
        )
        
        self.db.add(contact)
        
        # If mutual, accept the reverse contact too
        if reverse_contact and reverse_contact.status == ContactStatus.PENDING:
            reverse_contact.status = ContactStatus.ACCEPTED
        
        await self.db.commit()
        
        # Re-fetch with relationships loaded
        result = await self.db.execute(
            select(Contact)
            .options(selectinload(Contact.contact_user))
            .where(Contact.id == contact.id)
        )
        return result.scalar_one()
    
    async def accept_contact(self, user_id: str, contact_entry_id: str) -> Contact:
        """Accept a pending contact request."""
        result = await self.db.execute(
            select(Contact)
            .options(selectinload(Contact.user))
            .where(
                and_(
                    Contact.id == contact_entry_id,
                    Contact.contact_id == user_id,
                    Contact.status == ContactStatus.PENDING,
                )
            )
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            raise NotFoundError(message="Contact request not found")
        
        # Accept the request
        contact.status = ContactStatus.ACCEPTED
        
        # Create reverse contact if it doesn't exist
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_id == contact.user_id,
                )
            )
        )
        reverse_contact = result.scalar_one_or_none()
        
        if not reverse_contact:
            reverse_contact = Contact(
                user_id=user_id,
                contact_id=contact.user_id,
                status=ContactStatus.ACCEPTED,
            )
            self.db.add(reverse_contact)
        else:
            reverse_contact.status = ContactStatus.ACCEPTED
        
        await self.db.commit()
        
        # Re-fetch with relationships loaded
        result = await self.db.execute(
            select(Contact)
            .options(selectinload(Contact.user))
            .where(Contact.id == contact.id)
        )
        return result.scalar_one()
    
    async def block_contact(self, user_id: str, contact_id: str) -> Contact:
        """Block a user."""
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_id == contact_id,
                )
            )
        )
        contact = result.scalar_one_or_none()
        
        if contact:
            contact.status = ContactStatus.BLOCKED
        else:
            contact = Contact(
                user_id=user_id,
                contact_id=contact_id,
                status=ContactStatus.BLOCKED,
            )
            self.db.add(contact)
        
        await self.db.commit()
        
        # Re-fetch with relationships loaded
        result = await self.db.execute(
            select(Contact)
            .options(selectinload(Contact.contact_user))
            .where(Contact.id == contact.id)
        )
        return result.scalar_one()
    
    async def remove_contact(self, user_id: str, contact_id: str) -> None:
        """Remove a contact."""
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_id == contact_id,
                )
            )
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            raise NotFoundError(message="Contact not found")
        
        await self.db.delete(contact)
        await self.db.commit()
    
    async def get_contacts(
        self,
        user_id: str,
        status: Optional[ContactStatus] = None,
    ) -> list[Contact]:
        """Get user's contacts."""
        stmt = select(Contact).options(
            selectinload(Contact.contact_user)
        ).where(Contact.user_id == user_id)
        
        if status:
            stmt = stmt.where(Contact.status == status)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_pending_requests(self, user_id: str) -> list[Contact]:
        """Get pending contact requests sent to the user."""
        result = await self.db.execute(
            select(Contact)
            .options(selectinload(Contact.user))
            .where(
                and_(
                    Contact.contact_id == user_id,
                    Contact.status == ContactStatus.PENDING,
                )
            )
        )
        return list(result.scalars().all())
    
    async def is_blocked(self, user_id: str, other_user_id: str) -> bool:
        """Check if either user has blocked the other."""
        result = await self.db.execute(
            select(Contact)
            .where(
                and_(
                    or_(
                        and_(
                            Contact.user_id == user_id,
                            Contact.contact_id == other_user_id,
                        ),
                        and_(
                            Contact.user_id == other_user_id,
                            Contact.contact_id == user_id,
                        ),
                    ),
                    Contact.status == ContactStatus.BLOCKED,
                )
            )
        )
        return result.scalar_one_or_none() is not None
