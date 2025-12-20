"""
API package.
Contains all REST API route handlers.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.contacts import router as contacts_router
from app.api.conversations import router as conversations_router
from app.api.messages import router as messages_router


# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(contacts_router, prefix="/contacts", tags=["Contacts"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(messages_router, prefix="/messages", tags=["Messages"])
