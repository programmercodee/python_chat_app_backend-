"""
User API routes.
Handles user profile management and public key operations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import CurrentUser, get_user_service, get_presence_service
from app.services.user_service import UserService
from app.services.presence_service import PresenceService
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    UserPublicKey,
    UserWithPublicKey,
    UserOnlineStatus,
)
from app.core.exceptions import AppException
from app.services.encryption_service import EncryptionService


router = APIRouter()


@router.get("/search", response_model=list[UserResponse], summary="Search users")
async def search_users(
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
) -> list[UserResponse]:
    """Search for users by username or email."""
    users = await user_service.search_users(
        query=q,
        exclude_user_id=current_user.id,
        limit=limit,
    )
    return [UserResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserWithPublicKey, summary="Get user by ID")
async def get_user(
    user_id: str,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserWithPublicKey:
    """Get a user's profile including their public key for encryption."""
    try:
        user = await user_service.get_user(user_id)
        return UserWithPublicKey.model_validate(user)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/me", response_model=UserResponse, summary="Update current user profile")
async def update_profile(
    update_data: UserUpdate,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Update the current user's profile."""
    try:
        user = await user_service.update_user(current_user.id, update_data)
        return UserResponse.model_validate(user)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/me/public-key", response_model=UserResponse, summary="Update encryption public key")
async def update_public_key(
    key_data: UserPublicKey,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Update the current user's public encryption key."""
    # Validate the public key format
    if not EncryptionService.validate_public_key(key_data.public_key):
        raise HTTPException(status_code=422, detail="Invalid public key format")
    
    try:
        user = await user_service.update_public_key(current_user.id, key_data.public_key)
        return UserResponse.model_validate(user)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{user_id}/public-key", response_model=UserPublicKey, summary="Get user's public key")
async def get_public_key(
    user_id: str,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserPublicKey:
    """Get a user's public encryption key for sending encrypted messages."""
    try:
        public_key = await user_service.get_public_key(user_id)
        if not public_key:
            raise HTTPException(status_code=404, detail="User has not set up encryption")
        return UserPublicKey(public_key=public_key)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{user_id}/status", response_model=UserOnlineStatus, summary="Get user online status")
async def get_user_status(
    user_id: str,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
    presence_service: Annotated[PresenceService, Depends(get_presence_service)],
) -> UserOnlineStatus:
    """Check if a user is currently online."""
    try:
        user = await user_service.get_user(user_id)
        is_online = await presence_service.is_online(user_id)
        
        return UserOnlineStatus(
            user_id=user_id,
            is_online=is_online,
            last_seen=user.last_seen,
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
