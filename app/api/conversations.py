"""
Conversation API routes.
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
from app.models.conversation import ConversationType
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
    conversations = await conversation_service.get_user_conversations(current_user.id)
    
    # Get all member user IDs for presence check
    all_member_ids = []
    for conv in conversations:
        all_member_ids.extend([m.user_id for m in conv.members])
    
    online_ids = set(await presence_service.get_online_users(list(set(all_member_ids))))
    
    conv_responses = []
    for conv in conversations:
        members = []
        for m in conv.members:
            members.append(ConversationMemberResponse(
                user_id=m.user_id,
                username=m.user.username,
                avatar_url=m.user.avatar_url,
                joined_at=m.joined_at,
                is_online=m.user_id in online_ids,
            ))
        
        unread_count = await message_service.get_unread_count(conv.id, current_user.id)
        
        conv_responses.append(ConversationResponse(
            id=conv.id,
            type=conv.type,
            name=conv.name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
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
                user_id=current_user.id,
                other_user_id=conv_data.member_ids[0],
            )
        else:
            if not conv_data.name:
                raise HTTPException(
                    status_code=422,
                    detail="Group conversations require a name",
                )
            conversation = await conversation_service.create_group_conversation(
                creator_id=current_user.id,
                name=conv_data.name,
                member_ids=conv_data.member_ids,
            )
        
        members = [
            ConversationMemberResponse(
                user_id=m.user_id,
                username=m.user.username,
                avatar_url=m.user.avatar_url,
                joined_at=m.joined_at,
            )
            for m in conversation.members
        ]
        
        return ConversationResponse(
            id=conversation.id,
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
            current_user.id,
        )
        
        member_ids = [m.user_id for m in conversation.members]
        online_ids = set(await presence_service.get_online_users(member_ids))
        
        members = [
            ConversationMemberResponse(
                user_id=m.user_id,
                username=m.user.username,
                avatar_url=m.user.avatar_url,
                joined_at=m.joined_at,
                is_online=m.user_id in online_ids,
            )
            for m in conversation.members
        ]
        
        return ConversationResponse(
            id=conversation.id,
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
            added_by=current_user.id,
        )
        
        return ConversationMemberResponse(
            user_id=member.user_id,
            username=member.user.username,
            avatar_url=member.user.avatar_url,
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
            removed_by=current_user.id,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
