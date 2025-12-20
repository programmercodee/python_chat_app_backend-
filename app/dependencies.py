"""
FastAPI dependencies for authentication and service injection.
Uses Beanie ODM - no database session needed.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from beanie import PydanticObjectId

from app.core.security import verify_token
from app.core.redis import redis_client, RedisClient
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.contact_service import ContactService
from app.services.presence_service import PresenceService


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """
    Get the current authenticated user from JWT token.
    """
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.message),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    auth_service = AuthService()
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


# Type alias for current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]


# Service dependencies - no db session needed with Beanie
def get_auth_service() -> AuthService:
    return AuthService()


def get_user_service() -> UserService:
    return UserService()


def get_message_service() -> MessageService:
    return MessageService()


def get_conversation_service() -> ConversationService:
    return ConversationService()


def get_contact_service() -> ContactService:
    return ContactService()


def get_presence_service() -> PresenceService:
    return PresenceService(redis_client)


def get_redis_client() -> RedisClient:
    return redis_client
