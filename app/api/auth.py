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


@router.get(
    "/check-username",
    summary="Check if username is available",
)
async def check_username(
    username: str,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    """
    Check if a username is available for registration.
    Used for real-time validation in the registration form.
    """
    is_available = await auth_service.check_username_availability(username)
    return {"available": is_available}


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
    summary="Register with Google (new users only) - Step 1",
)
async def google_register(
    request: GoogleAuthRequest,
):
    """
    Register with Google OAuth - Step 1.
    
    Verifies Google token and returns user info for username selection.
    If user already exists, returns 409 asking them to login instead.
    """
    from app.services.google_auth_service import GoogleAuthService
    
    google_service = GoogleAuthService()
    
    try:
        # Verify Google token
        google_info = await google_service.verify_id_token(request.id_token)
        
        # Check if user already exists
        from app.models.user import User
        existing_user = await User.find_one(User.email == google_info['email'])
        
        if existing_user:
            raise AppException(
                message="An account with this email already exists. Please login instead.",
                status_code=409
            )
        
        # Return Google info for frontend to show username popup
        # Frontend will call /google/complete-registration with username
        return {
            "pending": True,
            "email": google_info['email'],
            "name": google_info.get('name', ''),
            "picture": google_info.get('picture', ''),
            "google_id": google_info['sub'],
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


from pydantic import BaseModel

class GoogleCompleteRequest(BaseModel):
    email: str
    google_id: str
    name: str
    picture: str
    username: str


@router.post(
    "/google/complete-registration",
    response_model=TokenResponse,
    summary="Complete Google registration with username - Step 2",
)
async def google_complete_registration(
    request: GoogleCompleteRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Complete Google OAuth registration - Step 2.
    
    Creates user with the chosen username and issues JWT.
    """
    try:
        from app.models.user import User
        
        # Double-check email doesn't exist
        existing_email = await User.find_one(User.email == request.email)
        if existing_email:
            raise AppException(
                message="An account with this email already exists.",
                status_code=409
            )
        
        # Check username availability
        existing_username = await User.find_one(User.username == request.username)
        if existing_username:
            raise AppException(
                message="Username already taken",
                status_code=409
            )
        
        # Create new user
        user = User(
            email=request.email,
            username=request.username,
            oauth_provider="google",
            oauth_id=request.google_id,
            avatar_url=request.picture if request.picture else None,
        )
        
        await user.insert()
        
        # Issue JWT tokens
        return await auth_service.issue_tokens_for_user(user)
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

