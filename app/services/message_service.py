"""
Message service for handling chat messages.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, AuthorizationError
from app.models.message import Message
from app.models.conversation import Conversation, ConversationMember
from app.schemas.message import MessageList, MessageResponse


class MessageService:
    """Service for managing chat messages."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_message(
        self,
        sender_id: str,
        conversation_id: str,
        encrypted_content: str,
        nonce: str,
        content_type: str = "text",
    ) -> Message:
        """
        Create a new encrypted message.
        """
        # Verify sender is member of conversation
        await self._verify_membership(sender_id, conversation_id)
        
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            encrypted_content=encrypted_content,
            nonce=nonce,
            content_type=content_type,
        )
        
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        
        # Update conversation's updated_at
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        
        return message
    
    async def get_message(self, message_id: str, user_id: str) -> Message:
        """Get a single message by ID."""
        result = await self.db.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise NotFoundError(message="Message not found")
        
        # Verify user has access
        await self._verify_membership(user_id, message.conversation_id)
        
        return message
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        before: Optional[datetime] = None,
    ) -> MessageList:
        """
        Get paginated messages for a conversation.
        """
        # Verify membership
        await self._verify_membership(user_id, conversation_id)
        
        # Build query
        stmt = select(Message).where(
            Message.conversation_id == conversation_id
        )
        
        if before:
            stmt = stmt.where(Message.created_at < before)
        
        # Order by newest first, then paginate
        stmt = stmt.order_by(Message.created_at.desc())
        
        # Get total count
        count_result = await self.db.execute(
            select(Message.id).where(
                Message.conversation_id == conversation_id
            )
        )
        total = len(count_result.all())
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        
        # Reverse to get chronological order
        messages.reverse()
        
        return MessageList(
            messages=[MessageResponse.model_validate(m) for m in messages],
            total=total,
            page=page,
            page_size=page_size,
            has_more=offset + len(messages) < total,
        )
    
    async def mark_as_delivered(self, message_id: str) -> None:
        """Mark a message as delivered."""
        await self.db.execute(
            update(Message)
            .where(Message.id == message_id)
            .values(is_delivered=True)
        )
    
    async def mark_as_read(self, message_ids: list[str], user_id: str) -> None:
        """Mark multiple messages as read."""
        await self.db.execute(
            update(Message)
            .where(
                and_(
                    Message.id.in_(message_ids),
                    Message.sender_id != user_id,
                )
            )
            .values(is_read=True)
        )
        
        # Update member's last_read_at
        result = await self.db.execute(
            select(Message.conversation_id)
            .where(Message.id.in_(message_ids))
            .distinct()
        )
        conversation_ids = [row[0] for row in result.all()]
        
        for conv_id in conversation_ids:
            await self.db.execute(
                update(ConversationMember)
                .where(
                    and_(
                        ConversationMember.conversation_id == conv_id,
                        ConversationMember.user_id == user_id,
                    )
                )
                .values(last_read_at=datetime.now(timezone.utc))
            )
    
    async def get_unread_count(self, conversation_id: str, user_id: str) -> int:
        """Get count of unread messages for a user in a conversation."""
        result = await self.db.execute(
            select(ConversationMember.last_read_at)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            )
        )
        row = result.first()
        last_read_at = row[0] if row else None
        
        # Count messages after last read
        stmt = select(Message.id).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
            )
        )
        
        if last_read_at:
            stmt = stmt.where(Message.created_at > last_read_at)
        
        result = await self.db.execute(stmt)
        return len(result.all())
    
    async def _verify_membership(self, user_id: str, conversation_id: str) -> None:
        """Verify user is a member of the conversation."""
        result = await self.db.execute(
            select(ConversationMember)
            .where(
                and_(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id == user_id,
                )
            )
        )
        
        if not result.scalar_one_or_none():
            raise AuthorizationError(
                message="You are not a member of this conversation"
            )
