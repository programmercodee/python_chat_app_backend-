"""
Pydantic schemas package.
Exports all request/response schemas for API validation.
"""

from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserPublicKey,
    UserWithPublicKey,
    UserOnlineStatus,
)
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
)
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageList,
    MessageRead,
    MessagesReadConfirmation,
)
from app.schemas.conversation import (
    MessagePreview,
    ConversationCreate,
    ConversationResponse,
    ConversationList,
    ConversationMemberResponse,
    AddMemberRequest,
)
from app.schemas.contact import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    ContactList,
    ContactUserInfo,
    ContactRequest,
    ContactRequestList,
)

__all__ = [
    # User
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "UserPublicKey",
    "UserWithPublicKey",
    "UserOnlineStatus",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    # Message
    "MessageCreate",
    "MessageResponse",
    "MessageList",
    "MessageRead",
    "MessagesReadConfirmation",
    # Conversation
    "MessagePreview",
    "ConversationCreate",
    "ConversationResponse",
    "ConversationList",
    "ConversationMemberResponse",
    "AddMemberRequest",
    # Contact
    "ContactCreate",
    "ContactResponse",
    "ContactUpdate",
    "ContactList",
    "ContactUserInfo",
    "ContactRequest",
    "ContactRequestList",
]
