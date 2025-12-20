"""
Conversation service for managing chats.
"""

from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.models.conversation import Conversation, ConversationMember, ConversationType
from app.models.user import User


class ConversationService:
    """Service for managing conversations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_direct_conversation(
        self,
        user_id: str,
        other_user_id: str,
    ) -> Conversation:
        """
        Create or get existing direct conversation between two users.
        """
        if user_id == other_user_id:
            raise ValidationError(message="Cannot create conversation with yourself")
        
        # Check if direct conversation already exists
        existing = await self._get_direct_conversation(user_id, other_user_id)
        if existing:
            return existing
        
        # Verify other user exists
        result = await self.db.execute(
            select(User).where(User.id == other_user_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(message="User not found")
        
        # Create new conversation
        conversation = Conversation(type=ConversationType.DIRECT)
        self.db.add(conversation)
        await self.db.flush()
        
        # Add both members
        member1 = ConversationMember(
            conversation_id=conversation.id,
            user_id=user_id,
        )
        member2 = ConversationMember(
            conversation_id=conversation.id,
            user_id=other_user_id,
        )
        
        self.db.add(member1)
        self.db.add(member2)
        await self.db.commit()
        
        # Re-fetch with relationships loaded
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.id == conversation.id)
        )
        return result.scalar_one()
    
    async def create_group_conversation(
        self,
        creator_id: str,
        name: str,
        member_ids: list[str],
    ) -> Conversation:
        """
        Create a new group conversation.
        """
        # Ensure creator is included
        all_member_ids = list(set([creator_id] + member_ids))
        
        if len(all_member_ids) < 2:
            raise ValidationError(message="Group must have at least 2 members")
        
        # Verify all members exist
        result = await self.db.execute(
            select(User.id).where(User.id.in_(all_member_ids))
        )
        found_ids = {row[0] for row in result.all()}
        
        if len(found_ids) != len(all_member_ids):
            raise NotFoundError(message="One or more users not found")
        
        # Create conversation
        conversation = Conversation(
            type=ConversationType.GROUP,
            name=name,
        )
        self.db.add(conversation)
        await self.db.flush()
        
        # Add members
        for member_id in all_member_ids:
            member = ConversationMember(
                conversation_id=conversation.id,
                user_id=member_id,
            )
            self.db.add(member)
        
        await self.db.commit()
        
        # Re-fetch with relationships loaded
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.id == conversation.id)
        )
        return result.scalar_one()
    
    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Conversation:
        """
        Get conversation by ID with membership check.
        """
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise NotFoundError(message="Conversation not found")
        
        # Check membership
        is_member = any(m.user_id == user_id for m in conversation.members)
        if not is_member:
            raise AuthorizationError(message="You are not a member of this conversation")
        
        return conversation
    
    async def get_user_conversations(self, user_id: str) -> list[Conversation]:
        """
        Get all conversations for a user.
        """
        # Get conversation IDs for user
        result = await self.db.execute(
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
        )
        conversation_ids = [row[0] for row in result.all()]
        
        if not conversation_ids:
            return []
        
        # Get conversations with members loaded
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.id.in_(conversation_ids))
            .order_by(Conversation.updated_at.desc())
        )
        
        return list(result.scalars().all())
    
    async def add_member(
        self,
        conversation_id: str,
        user_id: str,
        added_by: str,
    ) -> ConversationMember:
        """Add a member to a group conversation."""
        conversation = await self.get_conversation(conversation_id, added_by)
        
        if conversation.type != ConversationType.GROUP:
            raise ValidationError(message="Cannot add members to direct conversations")
        
        # Check if already a member
        existing = await self.db.execute(
            select(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(message="User is already a member")
        
        # Verify user exists
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(message="User not found")
        
        member = ConversationMember(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        self.db.add(member)
        await self.db.commit()
        
        # Re-fetch with relationships
        result = await self.db.execute(
            select(ConversationMember)
            .options(selectinload(ConversationMember.user))
            .where(ConversationMember.id == member.id)
        )
        return result.scalar_one()
    
    async def remove_member(
        self,
        conversation_id: str,
        user_id: str,
        removed_by: str,
    ) -> None:
        """Remove a member from a group conversation."""
        conversation = await self.get_conversation(conversation_id, removed_by)
        
        if conversation.type != ConversationType.GROUP:
            raise ValidationError(message="Cannot remove members from direct conversations")
        
        result = await self.db.execute(
            select(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            )
        )
        member = result.scalar_one_or_none()
        
        if not member:
            raise NotFoundError(message="Member not found in conversation")
        
        await self.db.delete(member)
        await self.db.commit()
    
    async def _get_direct_conversation(
        self,
        user1_id: str,
        user2_id: str,
    ) -> Optional[Conversation]:
        """Get existing direct conversation between two users."""
        # Find conversations where both users are members
        subquery1 = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user1_id)
        )
        subquery2 = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user2_id)
        )
        
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(
                and_(
                    Conversation.type == ConversationType.DIRECT,
                    Conversation.id.in_(subquery1),
                    Conversation.id.in_(subquery2),
                )
            )
        )
        conversations = result.scalars().all()
        
        # Find one that has exactly these two members
        for conv in conversations:
            member_ids = {m.user_id for m in conv.members}
            if member_ids == {user1_id, user2_id}:
                return conv
        
        return None
