"""
Messages API routes.
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import CurrentUser, get_message_service
from app.services.message_service import MessageService
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageList,
    MessageRead,
    MessagesReadConfirmation,
)
from app.core.exceptions import AppException


router = APIRouter()


@router.get("/conversation/{conversation_id}", response_model=MessageList, summary="Get conversation messages")
async def get_messages(
    conversation_id: str,
    current_user: CurrentUser,
    message_service: Annotated[MessageService, Depends(get_message_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    before: Optional[datetime] = Query(None, description="Get messages before this time"),
) -> MessageList:
    """Get paginated messages for a conversation."""
    try:
        return await message_service.get_conversation_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            before=before,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{message_id}", response_model=MessageResponse, summary="Get a single message")
async def get_message(
    message_id: str,
    current_user: CurrentUser,
    message_service: Annotated[MessageService, Depends(get_message_service)],
) -> MessageResponse:
    """Get a single message by ID."""
    try:
        message = await message_service.get_message(message_id, current_user.id)
        return MessageResponse.model_validate(message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("", response_model=MessageResponse, status_code=201, summary="Send a message (REST)")
async def send_message(
    message_data: MessageCreate,
    current_user: CurrentUser,
    message_service: Annotated[MessageService, Depends(get_message_service)],
) -> MessageResponse:
    """Send an encrypted message via REST API."""
    try:
        message = await message_service.create_message(
            sender_id=current_user.id,
            conversation_id=message_data.conversation_id,
            encrypted_content=message_data.encrypted_content,
            nonce=message_data.nonce,
            content_type=message_data.content_type,
        )
        return MessageResponse.model_validate(message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/read", response_model=MessagesReadConfirmation, summary="Mark messages as read")
async def mark_messages_read(
    read_data: MessageRead,
    current_user: CurrentUser,
    message_service: Annotated[MessageService, Depends(get_message_service)],
) -> MessagesReadConfirmation:
    """Mark multiple messages as read."""
    try:
        await message_service.mark_as_read(read_data.message_ids, current_user.id)
        
        return MessagesReadConfirmation(
            message_ids=read_data.message_ids,
            read_by=current_user.id,
            read_at=datetime.now(),
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
