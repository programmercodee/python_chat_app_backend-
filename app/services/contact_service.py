"""
Contact service for managing user contacts.
Uses Beanie ODM for MongoDB.
"""

from typing import Optional

from beanie import PydanticObjectId

from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.models.contact import Contact, ContactStatus
from app.models.user import User


class ContactService:
    """Service for managing user contacts."""
    
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
        
        user_oid = PydanticObjectId(user_id)
        contact_oid = PydanticObjectId(contact_id)
        
        # Verify contact user exists
        contact_user = await User.get(contact_oid)
        if not contact_user:
            raise NotFoundError(message="User not found")
        
        # Check if contact already exists
        existing = await Contact.find_one(
            Contact.user_id == user_oid,
            Contact.contact_id == contact_oid
        )
        
        if existing:
            if existing.status == ContactStatus.BLOCKED:
                raise ValidationError(message="You have blocked this user")
            raise ConflictError(message="Contact already exists")
        
        # Check if the other user has already added us
        reverse_contact = await Contact.find_one(
            Contact.user_id == contact_oid,
            Contact.contact_id == user_oid
        )
        
        # If they added us, auto-accept
        status = ContactStatus.ACCEPTED if reverse_contact else ContactStatus.PENDING
        
        contact = Contact(
            user_id=user_oid,
            contact_id=contact_oid,
            nickname=nickname,
            status=status,
            contact_username=contact_user.username,
            contact_email=contact_user.email,
        )
        
        await contact.insert()
        
        # If mutual, accept the reverse contact too
        if reverse_contact and reverse_contact.status == ContactStatus.PENDING:
            reverse_contact.status = ContactStatus.ACCEPTED
            await reverse_contact.save()
        
        return contact
    
    async def accept_contact(self, user_id: str, contact_entry_id: str) -> Contact:
        """Accept a pending contact request."""
        user_oid = PydanticObjectId(user_id)
        
        contact = await Contact.find_one(
            Contact.id == PydanticObjectId(contact_entry_id),
            Contact.contact_id == user_oid,
            Contact.status == ContactStatus.PENDING
        )
        
        if not contact:
            raise NotFoundError(message="Contact request not found")
        
        # Accept the request
        contact.status = ContactStatus.ACCEPTED
        await contact.save()
        
        # Create reverse contact if it doesn't exist
        reverse_contact = await Contact.find_one(
            Contact.user_id == user_oid,
            Contact.contact_id == contact.user_id
        )
        
        # Get the requesting user's info
        requesting_user = await User.get(contact.user_id)
        
        if not reverse_contact:
            reverse_contact = Contact(
                user_id=user_oid,
                contact_id=contact.user_id,
                status=ContactStatus.ACCEPTED,
                contact_username=requesting_user.username if requesting_user else None,
                contact_email=requesting_user.email if requesting_user else None,
            )
            await reverse_contact.insert()
        else:
            reverse_contact.status = ContactStatus.ACCEPTED
            await reverse_contact.save()
        
        return contact
    
    async def block_contact(self, user_id: str, contact_id: str) -> Contact:
        """Block a user."""
        user_oid = PydanticObjectId(user_id)
        contact_oid = PydanticObjectId(contact_id)
        
        contact = await Contact.find_one(
            Contact.user_id == user_oid,
            Contact.contact_id == contact_oid
        )
        
        if contact:
            contact.status = ContactStatus.BLOCKED
            await contact.save()
        else:
            contact = Contact(
                user_id=user_oid,
                contact_id=contact_oid,
                status=ContactStatus.BLOCKED,
            )
            await contact.insert()
        
        return contact
    
    async def remove_contact(self, user_id: str, contact_id: str) -> None:
        """Remove a contact."""
        user_oid = PydanticObjectId(user_id)
        contact_oid = PydanticObjectId(contact_id)
        
        contact = await Contact.find_one(
            Contact.user_id == user_oid,
            Contact.contact_id == contact_oid
        )
        
        if not contact:
            raise NotFoundError(message="Contact not found")
        
        await contact.delete()
    
    async def get_contacts(
        self,
        user_id: str,
        status: Optional[ContactStatus] = None,
    ) -> list[Contact]:
        """Get user's contacts."""
        user_oid = PydanticObjectId(user_id)
        
        query = {"user_id": user_oid}
        if status:
            query["status"] = status.value
        
        contacts = await Contact.find(query).to_list()
        return contacts
    
    async def get_pending_requests(self, user_id: str) -> list[Contact]:
        """Get pending contact requests sent to the user."""
        user_oid = PydanticObjectId(user_id)
        
        contacts = await Contact.find(
            Contact.contact_id == user_oid,
            Contact.status == ContactStatus.PENDING
        ).to_list()
        
        # Fetch the requesting user info for each contact
        for contact in contacts:
            requesting_user = await User.get(contact.user_id)
            if requesting_user:
                contact.contact_username = requesting_user.username
                contact.contact_email = requesting_user.email
        
        return contacts
    
    async def is_blocked(self, user_id: str, other_user_id: str) -> bool:
        """Check if either user has blocked the other."""
        user_oid = PydanticObjectId(user_id)
        other_oid = PydanticObjectId(other_user_id)
        
        blocked = await Contact.find_one({
            "$and": [
                {"status": ContactStatus.BLOCKED.value},
                {
                    "$or": [
                        {"user_id": user_oid, "contact_id": other_oid},
                        {"user_id": other_oid, "contact_id": user_oid}
                    ]
                }
            ]
        })
        
        return blocked is not None
