"""
Authentication API routes.
Handles user registration, login, and token refresh.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, CurrentUser
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, GoogleAuthRequest
from app.core.exceptions import AppException


router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_data: UserCreate,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    """
    Register a new user account.
    
    - **email**: Valid email address (must be unique)
    - **username**: Username (3-50 chars, alphanumeric + underscore)
    - **password**: Password (min 8 characters)
    """
    try:
        user = await auth_service.register(user_data)
        return UserResponse.model_validate(user)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
)
async def login(
    credentials: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Authenticate with email and password.
    
    Returns access and refresh tokens for API authentication.
    """
    try:
        return await auth_service.login(credentials.email, credentials.password)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Get new access token using refresh token.
    
    Use this when the access token expires.
    """
    try:
        return await auth_service.refresh_tokens(request.refresh_token)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """
    Get the currently authenticated user's profile.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Authenticate with Google",
)
async def google_auth(
    request: GoogleAuthRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Authenticate with Google OAuth.
    
    Flow:
    1. Frontend gets ID token from Google
    2. Backend verifies token with Google
    3. Backend finds or creates user (account linking)
    4. Backend issues our own JWT tokens
    
    Security notes:
    - Email is extracted ONLY from verified token (never trust frontend)
    - Google token is not stored
    - Our own JWT is issued after verification
    """
    from app.services.google_auth_service import GoogleAuthService
    
    google_service = GoogleAuthService()
    
    try:
        # Step 1: Verify Google token (server-side)
        google_info = await google_service.verify_id_token(request.id_token)
        
        # Step 2: Find or create user (account linking)
        user = await google_service.find_or_create_user(google_info)
        
        # Step 3: Issue our JWT tokens
        return await auth_service.issue_tokens_for_user(user)
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
