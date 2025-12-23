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
    "/google/login",
    response_model=TokenResponse,
    summary="Login with Google (existing users only)",
)
async def google_login(
    request: GoogleAuthRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Login with Google OAuth - for EXISTING users only.
    
    If user doesn't exist, returns 404 asking them to register first.
    If user exists, links Google and issues JWT.
    """
    from app.services.google_auth_service import GoogleAuthService
    
    google_service = GoogleAuthService()
    
    try:
        # Verify Google token
        google_info = await google_service.verify_id_token(request.id_token)
        
        # Find existing user (raises 404 if not found)
        user = await google_service.find_existing_user(google_info)
        
        # Issue our JWT tokens
        return await auth_service.issue_tokens_for_user(user)
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/google/register",
    response_model=TokenResponse,
    summary="Register with Google (new users only)",
)
async def google_register(
    request: GoogleAuthRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Register with Google OAuth - for NEW users only.
    
    If user already exists, returns 409 asking them to login instead.
    Creates new user with Google and issues JWT.
    """
    from app.services.google_auth_service import GoogleAuthService
    
    google_service = GoogleAuthService()
    
    try:
        # Verify Google token
        google_info = await google_service.verify_id_token(request.id_token)
        
        # Create new user (raises 409 if already exists)
        user = await google_service.create_google_user(google_info)
        
        # Issue our JWT tokens
        return await auth_service.issue_tokens_for_user(user)
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
