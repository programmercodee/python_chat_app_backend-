"""
Contacts API routes.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import CurrentUser, get_contact_service, get_presence_service
from app.services.contact_service import ContactService
from app.services.presence_service import PresenceService
from app.schemas.contact import (
    ContactCreate,
    ContactResponse,
    ContactList,
    ContactUserInfo,
    ContactRequest,
    ContactRequestList,
)
from app.models.contact import ContactStatus
from app.core.exceptions import AppException


router = APIRouter()


@router.get("", response_model=ContactList, summary="Get user's contacts")
async def get_contacts(
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
    presence_service: Annotated[PresenceService, Depends(get_presence_service)],
    status: Optional[ContactStatus] = Query(None, description="Filter by status"),
) -> ContactList:
    """Get the current user's contact list."""
    contacts = await contact_service.get_contacts(current_user.id, status)
    
    # Get online status for all contacts
    contact_ids = [c.contact_id for c in contacts]
    online_ids = set(await presence_service.get_online_users(contact_ids))
    
    # Build response with online status
    contact_responses = []
    for contact in contacts:
        contact_user = ContactUserInfo(
            id=contact.contact_user.id,
            username=contact.contact_user.username,
            email=contact.contact_user.email,
            avatar_url=contact.contact_user.avatar_url,
            is_online=contact.contact_id in online_ids,
            last_seen=contact.contact_user.last_seen,
        )
        
        contact_responses.append(ContactResponse(
            id=contact.id,
            user_id=contact.user_id,
            contact_id=contact.contact_id,
            status=contact.status,
            nickname=contact.nickname,
            created_at=contact.created_at,
            contact_user=contact_user,
        ))
    
    return ContactList(contacts=contact_responses, total=len(contact_responses))


@router.post("", response_model=ContactResponse, status_code=201, summary="Add a new contact")
async def add_contact(
    contact_data: ContactCreate,
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactResponse:
    """Add a user as a contact."""
    try:
        contact = await contact_service.add_contact(
            user_id=current_user.id,
            contact_id=contact_data.contact_id,
            nickname=contact_data.nickname,
        )
        
        contact_user = ContactUserInfo(
            id=contact.contact_user.id,
            username=contact.contact_user.username,
            email=contact.contact_user.email,
            avatar_url=contact.contact_user.avatar_url,
            last_seen=contact.contact_user.last_seen,
        )
        
        return ContactResponse(
            id=contact.id,
            user_id=contact.user_id,
            contact_id=contact.contact_id,
            status=contact.status,
            nickname=contact.nickname,
            created_at=contact.created_at,
            contact_user=contact_user,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/requests", response_model=ContactRequestList, summary="Get pending contact requests")
async def get_pending_requests(
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactRequestList:
    """Get pending contact requests from other users."""
    requests = await contact_service.get_pending_requests(current_user.id)
    
    request_list = []
    for req in requests:
        from_user = ContactUserInfo(
            id=req.user.id,
            username=req.user.username,
            email=req.user.email,
            avatar_url=req.user.avatar_url,
            last_seen=req.user.last_seen,
        )
        request_list.append(ContactRequest(
            id=req.id,
            from_user=from_user,
            created_at=req.created_at,
        ))
    
    return ContactRequestList(requests=request_list, total=len(request_list))


@router.post("/requests/{request_id}/accept", response_model=ContactResponse, summary="Accept a contact request")
async def accept_request(
    request_id: str,
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactResponse:
    """Accept a pending contact request."""
    try:
        contact = await contact_service.accept_contact(current_user.id, request_id)
        
        contact_user = ContactUserInfo(
            id=contact.user.id,
            username=contact.user.username,
            email=contact.user.email,
            avatar_url=contact.user.avatar_url,
            last_seen=contact.user.last_seen,
        )
        
        return ContactResponse(
            id=contact.id,
            user_id=contact.user_id,
            contact_id=contact.contact_id,
            status=contact.status,
            nickname=contact.nickname,
            created_at=contact.created_at,
            contact_user=contact_user,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{contact_id}/block", response_model=ContactResponse, summary="Block a user")
async def block_contact(
    contact_id: str,
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactResponse:
    """Block a user."""
    try:
        contact = await contact_service.block_contact(current_user.id, contact_id)
        
        contact_user = ContactUserInfo(
            id=contact.contact_user.id,
            username=contact.contact_user.username,
            email=contact.contact_user.email,
            avatar_url=contact.contact_user.avatar_url,
            last_seen=contact.contact_user.last_seen,
        )
        
        return ContactResponse(
            id=contact.id,
            user_id=contact.user_id,
            contact_id=contact.contact_id,
            status=contact.status,
            nickname=contact.nickname,
            created_at=contact.created_at,
            contact_user=contact_user,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{contact_id}", status_code=204, summary="Remove a contact")
async def remove_contact(
    contact_id: str,
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
):
    """Remove a user from your contacts."""
    try:
        await contact_service.remove_contact(current_user.id, contact_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
