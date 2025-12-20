"""
Conversation service for managing chats.
Uses Beanie ODM for MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import PydanticObjectId

from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.models.conversation import Conversation, ConversationMember, ConversationType
from app.models.user import User


class ConversationService:
    """Service for managing conversations."""
    
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
        
        user_oid = PydanticObjectId(user_id)
        other_oid = PydanticObjectId(other_user_id)
        
        # Check if direct conversation already exists
        existing = await self._get_direct_conversation(user_id, other_user_id)
        if existing:
            return existing
        
        # Verify other user exists
        other_user = await User.get(other_oid)
        if not other_user:
            raise NotFoundError(message="User not found")
        
        # Get current user
        current_user = await User.get(user_oid)
        
        # Create new conversation
        conversation = Conversation(
            type=ConversationType.DIRECT,
            member_ids=[user_oid, other_oid]
        )
        await conversation.insert()
        
        # Create member entries
        member1 = ConversationMember(
            conversation_id=conversation.id,
            user_id=user_oid,
            username=current_user.username if current_user else None
        )
        member2 = ConversationMember(
            conversation_id=conversation.id,
            user_id=other_oid,
            username=other_user.username
        )
        
        await member1.insert()
        await member2.insert()
        
        return conversation
    
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
        
        # Convert to ObjectIds
        member_oids = [PydanticObjectId(mid) for mid in all_member_ids]
        
        # Verify all members exist
        found_users = await User.find({"_id": {"$in": member_oids}}).to_list()
        found_ids = {user.id for user in found_users}
        
        if len(found_ids) != len(member_oids):
            raise NotFoundError(message="One or more users not found")
        
        # Create conversation
        conversation = Conversation(
            type=ConversationType.GROUP,
            name=name,
            member_ids=member_oids
        )
        await conversation.insert()
        
        # Add member entries
        for user in found_users:
            member = ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
                username=user.username
            )
            await member.insert()
        
        return conversation
    
    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Conversation:
        """
        Get conversation by ID with membership check.
        """
        conv_oid = PydanticObjectId(conversation_id)
        user_oid = PydanticObjectId(user_id)
        
        conversation = await Conversation.get(conv_oid)
        
        if not conversation:
            raise NotFoundError(message="Conversation not found")
        
        # Check membership
        if user_oid not in conversation.member_ids:
            raise AuthorizationError(message="You are not a member of this conversation")
        
        return conversation
    
    async def get_user_conversations(self, user_id: str) -> list[dict]:
        """
        Get all conversations for a user with member details.
        """
        user_oid = PydanticObjectId(user_id)
        
        # Find all conversations where user is a member
        conversations = await Conversation.find(
            {"member_ids": user_oid}
        ).sort("-updated_at").to_list()
        
        result = []
        for conv in conversations:
            # Get member details
            members = await ConversationMember.find(
                ConversationMember.conversation_id == conv.id
            ).to_list()
            
            # Build member info from User collection for latest data
            member_details = []
            for member in members:
                user = await User.get(member.user_id)
                if user:
                    member_details.append({
                        "user_id": str(user.id),
                        "username": user.username,
                        "email": user.email,
                        "avatar_url": user.avatar_url
                    })
            
            result.append({
                "id": str(conv.id),
                "type": conv.type.value,
                "name": conv.name,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "members": member_details
            })
        
        return result
    
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
        
        user_oid = PydanticObjectId(user_id)
        
        # Check if already a member
        if user_oid in conversation.member_ids:
            raise ValidationError(message="User is already a member")
        
        # Verify user exists
        user = await User.get(user_oid)
        if not user:
            raise NotFoundError(message="User not found")
        
        # Add to conversation
        conversation.member_ids.append(user_oid)
        await conversation.save()
        
        # Create member entry
        member = ConversationMember(
            conversation_id=conversation.id,
            user_id=user_oid,
            username=user.username
        )
        await member.insert()
        
        return member
    
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
        
        user_oid = PydanticObjectId(user_id)
        
        if user_oid not in conversation.member_ids:
            raise NotFoundError(message="Member not found in conversation")
        
        # Remove from conversation
        conversation.member_ids.remove(user_oid)
        await conversation.save()
        
        # Remove member entry
        await ConversationMember.find_one(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id == user_oid
        ).delete()
    
    async def _get_direct_conversation(
        self,
        user1_id: str,
        user2_id: str,
    ) -> Optional[Conversation]:
        """Get existing direct conversation between two users."""
        user1_oid = PydanticObjectId(user1_id)
        user2_oid = PydanticObjectId(user2_id)
        
        # Find direct conversation with both users as members
        conversation = await Conversation.find_one({
            "type": ConversationType.DIRECT.value,
            "member_ids": {"$all": [user1_oid, user2_oid]},
            "$expr": {"$eq": [{"$size": "$member_ids"}, 2]}
        })
        
        return conversation
    
    async def update_conversation_timestamp(self, conversation_id: str) -> None:
        """Update the conversation's updated_at timestamp."""
        try:
            conv_oid = PydanticObjectId(conversation_id)
            conversation = await Conversation.get(conv_oid)
            if conversation:
                conversation.updated_at = datetime.now(timezone.utc)
                await conversation.save()
        except Exception:
            pass
