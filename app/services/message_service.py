"""
Message service for handling chat messages.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import PydanticObjectId

from app.core.exceptions import NotFoundError, AuthorizationError
from app.models.message import Message
from app.models.conversation import Conversation, ConversationMember
from app.schemas.message import MessageList, MessageResponse


class MessageService:
    """Service for managing chat messages."""
    
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
        sender_oid = PydanticObjectId(sender_id)
        conv_oid = PydanticObjectId(conversation_id)
        
        # Verify sender is member of conversation
        await self._verify_membership(sender_id, conversation_id)
        
        message = Message(
            conversation_id=conv_oid,
            sender_id=sender_oid,
            encrypted_content=encrypted_content,
            nonce=nonce,
            content_type=content_type,
        )
        
        await message.insert()
        
        # Update conversation's updated_at
        conversation = await Conversation.get(conv_oid)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
            await conversation.save()
        
        return message
    
    async def get_message(self, message_id: str, user_id: str) -> Message:
        """Get a single message by ID."""
        try:
            message = await Message.get(PydanticObjectId(message_id))
        except Exception:
            message = None
        
        if not message:
            raise NotFoundError(message="Message not found")
        
        # Verify user has access
        await self._verify_membership(user_id, str(message.conversation_id))
        
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
        conv_oid = PydanticObjectId(conversation_id)
        
        # Verify membership
        await self._verify_membership(user_id, conversation_id)
        
        # Build query
        query = {"conversation_id": conv_oid}
        
        if before:
            query["created_at"] = {"$lt": before}
        
        # Get total count
        total = await Message.find({"conversation_id": conv_oid}).count()
        
        # Get paginated messages (newest first, then reverse)
        offset = (page - 1) * page_size
        messages = await Message.find(query)\
            .sort("-created_at")\
            .skip(offset)\
            .limit(page_size)\
            .to_list()
        
        # Reverse to get chronological order
        messages.reverse()
        
        # Convert to response objects
        message_responses = []
        for m in messages:
            message_responses.append(MessageResponse(
                id=str(m.id),
                conversation_id=str(m.conversation_id),
                sender_id=str(m.sender_id) if m.sender_id else None,
                encrypted_content=m.encrypted_content,
                nonce=m.nonce,
                content_type=m.content_type,
                is_delivered=m.is_delivered,
                is_read=m.is_read,
                created_at=m.created_at
            ))
        
        return MessageList(
            messages=message_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_more=offset + len(messages) < total,
        )
    
    async def mark_as_delivered(self, message_id: str) -> None:
        """Mark a message as delivered."""
        try:
            message = await Message.get(PydanticObjectId(message_id))
            if message:
                message.is_delivered = True
                await message.save()
        except Exception:
            pass
    
    async def mark_as_read(self, message_ids: list[str], user_id: str) -> None:
        """Mark multiple messages as read."""
        user_oid = PydanticObjectId(user_id)
        msg_oids = [PydanticObjectId(mid) for mid in message_ids]
        
        # Update messages that weren't sent by this user
        await Message.find({
            "_id": {"$in": msg_oids},
            "sender_id": {"$ne": user_oid}
        }).update_many({"$set": {"is_read": True}})
        
        # Get conversation IDs for these messages
        messages = await Message.find({"_id": {"$in": msg_oids}}).to_list()
        conv_ids = list(set(m.conversation_id for m in messages))
        
        # Update member's last_read_at
        for conv_id in conv_ids:
            member = await ConversationMember.find_one(
                ConversationMember.conversation_id == conv_id,
                ConversationMember.user_id == user_oid
            )
            if member:
                member.last_read_at = datetime.now(timezone.utc)
                await member.save()
    
    async def get_unread_count(self, conversation_id: str, user_id: str) -> int:
        """Get count of unread messages for a user in a conversation."""
        conv_oid = PydanticObjectId(conversation_id)
        user_oid = PydanticObjectId(user_id)
        
        member = await ConversationMember.find_one(
            ConversationMember.conversation_id == conv_oid,
            ConversationMember.user_id == user_oid
        )
        
        last_read_at = member.last_read_at if member else None
        
        # Count messages after last read
        query = {
            "conversation_id": conv_oid,
            "sender_id": {"$ne": user_oid}
        }
        
        if last_read_at:
            query["created_at"] = {"$gt": last_read_at}
        
        return await Message.find(query).count()
    
    async def _verify_membership(self, user_id: str, conversation_id: str) -> None:
        """Verify user is a member of the conversation."""
        user_oid = PydanticObjectId(user_id)
        conv_oid = PydanticObjectId(conversation_id)
        
        conversation = await Conversation.get(conv_oid)
        
        if not conversation or user_oid not in conversation.member_ids:
            raise AuthorizationError(
                message="You are not a member of this conversation"
            )
