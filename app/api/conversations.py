"""
Conversation API routes.
Updated for MongoDB/Beanie ODM.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import (
    CurrentUser,
    get_conversation_service,
    get_message_service,
    get_presence_service,
)
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.presence_service import PresenceService
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationList,
    ConversationMemberResponse,
    AddMemberRequest,
)
from app.models.conversation import ConversationType, ConversationMember
from app.models.user import User
from app.core.exceptions import AppException


router = APIRouter()


@router.get("", response_model=ConversationList, summary="Get user's conversations")
async def get_conversations(
    current_user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    message_service: Annotated[MessageService, Depends(get_message_service)],
    presence_service: Annotated[PresenceService, Depends(get_presence_service)],
) -> ConversationList:
    """Get all conversations for the current user."""
    # get_user_conversations now returns dicts with member details
    conversations_data = await conversation_service.get_user_conversations(str(current_user.id))
    
    # Get all member user IDs for presence check
    all_member_ids = []
    for conv in conversations_data:
        all_member_ids.extend([m["user_id"] for m in conv["members"]])
    
    online_ids = set(await presence_service.get_online_users(list(set(all_member_ids))))
    
    conv_responses = []
    for conv in conversations_data:
        members = []
        for m in conv["members"]:
            members.append(ConversationMemberResponse(
                user_id=m["user_id"],
                username=m["username"],
                avatar_url=m.get("avatar_url"),
                joined_at=conv["created_at"],  # Use conversation created_at as fallback
                is_online=m["user_id"] in online_ids,
            ))
        
        unread_count = await message_service.get_unread_count(conv["id"], str(current_user.id))
        
        conv_responses.append(ConversationResponse(
            id=conv["id"],
            type=conv["type"],
            name=conv.get("name"),
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            members=members,
            unread_count=unread_count,
        ))
    
    return ConversationList(conversations=conv_responses, total=len(conv_responses))


@router.post("", response_model=ConversationResponse, status_code=201, summary="Create a conversation")
async def create_conversation(
    conv_data: ConversationCreate,
    current_user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationResponse:
    """Create a new conversation."""
    try:
        if conv_data.type == ConversationType.DIRECT:
            if len(conv_data.member_ids) != 1:
                raise HTTPException(
                    status_code=422,
                    detail="Direct conversations require exactly one member",
                )
            conversation = await conversation_service.create_direct_conversation(
                user_id=str(current_user.id),
                other_user_id=conv_data.member_ids[0],
            )
        else:
            if not conv_data.name:
                raise HTTPException(
                    status_code=422,
                    detail="Group conversations require a name",
                )
            conversation = await conversation_service.create_group_conversation(
                creator_id=str(current_user.id),
                name=conv_data.name,
                member_ids=conv_data.member_ids,
            )
        
        # Fetch member details
        members = []
        for member_id in conversation.member_ids:
            user = await User.get(member_id)
            if user:
                members.append(ConversationMemberResponse(
                    user_id=str(user.id),
                    username=user.username,
                    avatar_url=user.avatar_url,
                    joined_at=conversation.created_at,
                ))
        
        return ConversationResponse(
            id=str(conversation.id),
            type=conversation.type,
            name=conversation.name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            members=members,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Get conversation by ID")
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    presence_service: Annotated[PresenceService, Depends(get_presence_service)],
) -> ConversationResponse:
    """Get a specific conversation by ID."""
    try:
        conversation = await conversation_service.get_conversation(
            conversation_id,
            str(current_user.id),
        )
        
        member_ids = [str(mid) for mid in conversation.member_ids]
        online_ids = set(await presence_service.get_online_users(member_ids))
        
        # Fetch member details
        members = []
        for member_id in conversation.member_ids:
            user = await User.get(member_id)
            if user:
                members.append(ConversationMemberResponse(
                    user_id=str(user.id),
                    username=user.username,
                    avatar_url=user.avatar_url,
                    joined_at=conversation.created_at,
                    is_online=str(user.id) in online_ids,
                ))
        
        return ConversationResponse(
            id=str(conversation.id),
            type=conversation.type,
            name=conversation.name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            members=members,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{conversation_id}/members", response_model=ConversationMemberResponse, status_code=201, summary="Add member to group")
async def add_member(
    conversation_id: str,
    member_data: AddMemberRequest,
    current_user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationMemberResponse:
    """Add a member to a group conversation."""
    try:
        member = await conversation_service.add_member(
            conversation_id=conversation_id,
            user_id=member_data.user_id,
            added_by=str(current_user.id),
        )
        
        # Fetch user details
        user = await User.get(member.user_id)
        
        return ConversationMemberResponse(
            user_id=str(member.user_id),
            username=user.username if user else member.username,
            avatar_url=user.avatar_url if user else None,
            joined_at=member.joined_at,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{conversation_id}/members/{user_id}", status_code=204, summary="Remove member from group")
async def remove_member(
    conversation_id: str,
    user_id: str,
    current_user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
):
    """Remove a member from a group conversation."""
    try:
        await conversation_service.remove_member(
            conversation_id=conversation_id,
            user_id=user_id,
            removed_by=str(current_user.id),
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
