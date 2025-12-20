"""
Contacts API routes.
Updated for MongoDB/Beanie ODM.
# Force reload trigger: 2025-12-20T20:22
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
from app.models.user import User
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
    contacts = await contact_service.get_contacts(str(current_user.id), status)
    
    # Get online status for all contacts
    contact_ids = [str(c.contact_id) for c in contacts]
    online_ids = set(await presence_service.get_online_users(contact_ids))
    
    # Build response with online status
    contact_responses = []
    for contact in contacts:
        # Get contact attributes
        c_id = contact.id
        c_user_id = contact.user_id
        c_contact_id = contact.contact_id
        c_status = contact.status
        c_nickname = contact.nickname
        c_created_at = contact.created_at
        c_username = getattr(contact, 'contact_username', None)
        c_email = getattr(contact, 'contact_email', None)
        
        # Fetch contact user from database
        contact_user_doc = await User.get(c_contact_id)
        
        # Build user info dict
        user_info_dict = {
            "id": str(contact_user_doc.id) if contact_user_doc else str(c_contact_id),
            "username": contact_user_doc.username if contact_user_doc else (c_username or "Unknown"),
            "email": contact_user_doc.email if contact_user_doc else (c_email or ""),
            "avatar_url": contact_user_doc.avatar_url if contact_user_doc else None,
            "is_online": str(c_contact_id) in online_ids,
            "last_seen": contact_user_doc.last_seen if contact_user_doc else None,
        }
        
        # Build response dict
        response_dict = {
            "id": str(c_id),
            "user_id": str(c_user_id),
            "contact_id": str(c_contact_id),
            "status": c_status,
            "nickname": c_nickname,
            "created_at": c_created_at,
            "contact_user": user_info_dict,
        }
        contact_responses.append(ContactResponse(**response_dict))
    
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
            user_id=str(current_user.id),
            contact_id=contact_data.contact_id,
            nickname=contact_data.nickname,
        )
        
        # Get contact attributes immediately
        c_id = contact.id
        c_user_id = contact.user_id
        c_contact_id = contact.contact_id
        c_status = contact.status
        c_nickname = contact.nickname
        c_created_at = contact.created_at
        c_username = getattr(contact, 'contact_username', None)
        c_email = getattr(contact, 'contact_email', None)
        
        # Fetch contact user from database
        contact_user_doc = await User.get(c_contact_id)
        
        # Build user info dict
        user_info_dict = {
            "id": str(c_contact_id),
            "username": contact_user_doc.username if contact_user_doc else (c_username or "Unknown"),
            "email": contact_user_doc.email if contact_user_doc else (c_email or ""),
            "avatar_url": contact_user_doc.avatar_url if contact_user_doc else None,
            "is_online": False,
            "last_seen": contact_user_doc.last_seen if contact_user_doc else None,
        }
        
        # Build response dict
        response_dict = {
            "id": str(c_id),
            "user_id": str(c_user_id),
            "contact_id": str(c_contact_id),
            "status": c_status,
            "nickname": c_nickname,
            "created_at": c_created_at,
            "contact_user": user_info_dict,
        }
        return ContactResponse(**response_dict)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/requests", response_model=ContactRequestList, summary="Get pending contact requests")
async def get_pending_requests(
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactRequestList:
    """Get pending contact requests from other users."""
    requests = await contact_service.get_pending_requests(str(current_user.id))
    
    request_list = []
    for req in requests:
        # Get the user_id from the request
        req_user_id = req.user_id
        
        # Fetch the requesting user
        from_user_doc = await User.get(req_user_id)
        
        # Build user info dict explicitly
        user_info_dict = {
            "id": str(req_user_id),
            "username": from_user_doc.username if from_user_doc else "Unknown",
            "email": from_user_doc.email if from_user_doc else "",
            "avatar_url": from_user_doc.avatar_url if from_user_doc else None,
            "is_online": False,
            "last_seen": from_user_doc.last_seen if from_user_doc else None,
        }
        
        # Build request dict explicitly
        request_dict = {
            "id": str(req.id),
            "from_user": user_info_dict,
            "created_at": req.created_at,
        }
        request_list.append(ContactRequest(**request_dict))
    
    return ContactRequestList(requests=request_list, total=len(request_list))



@router.post("/requests/{request_id}/accept", response_model=ContactResponse, summary="Accept a contact request")
async def accept_request(
    request_id: str,
    current_user: CurrentUser,
    contact_service: Annotated[ContactService, Depends(get_contact_service)],
) -> ContactResponse:
    """Accept a pending contact request."""
    try:
        contact = await contact_service.accept_contact(str(current_user.id), request_id)
        
        # Get contact attributes immediately
        c_id = contact.id
        c_user_id = contact.user_id
        c_contact_id = contact.contact_id
        c_status = contact.status
        c_nickname = contact.nickname
        c_created_at = contact.created_at
        
        # Fetch the requesting user
        from_user_doc = await User.get(c_user_id)
        
        # Build user info dict
        user_info_dict = {
            "id": str(c_user_id),
            "username": from_user_doc.username if from_user_doc else "Unknown",
            "email": from_user_doc.email if from_user_doc else "",
            "avatar_url": from_user_doc.avatar_url if from_user_doc else None,
            "is_online": False,
            "last_seen": from_user_doc.last_seen if from_user_doc else None,
        }
        
        # Build response dict
        response_dict = {
            "id": str(c_id),
            "user_id": str(c_user_id),
            "contact_id": str(c_contact_id),
            "status": c_status,
            "nickname": c_nickname,
            "created_at": c_created_at,
            "contact_user": user_info_dict,
        }
        return ContactResponse(**response_dict)
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
        contact = await contact_service.block_contact(str(current_user.id), contact_id)
        
        # Get contact attributes immediately
        c_id = contact.id
        c_user_id = contact.user_id
        c_contact_id = contact.contact_id
        c_status = contact.status
        c_nickname = contact.nickname
        c_created_at = contact.created_at
        c_username = getattr(contact, 'contact_username', None)
        c_email = getattr(contact, 'contact_email', None)
        
        # Fetch contact user from database
        contact_user_doc = await User.get(c_contact_id)
        
        # Build user info dict
        user_info_dict = {
            "id": str(c_contact_id),
            "username": contact_user_doc.username if contact_user_doc else (c_username or "Unknown"),
            "email": contact_user_doc.email if contact_user_doc else (c_email or ""),
            "avatar_url": contact_user_doc.avatar_url if contact_user_doc else None,
            "is_online": False,
            "last_seen": contact_user_doc.last_seen if contact_user_doc else None,
        }
        
        # Build response dict
        response_dict = {
            "id": str(c_id),
            "user_id": str(c_user_id),
            "contact_id": str(c_contact_id),
            "status": c_status,
            "nickname": c_nickname,
            "created_at": c_created_at,
            "contact_user": user_info_dict,
        }
        return ContactResponse(**response_dict)
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
        await contact_service.remove_contact(str(current_user.id), contact_id)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
