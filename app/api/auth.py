"""
Authentication API routes.
Handles user registration, login, and token refresh.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.dependencies import get_auth_service, CurrentUser
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, GoogleAuthRequest
from app.core.exceptions import AppException, RateLimitExceeded
from app.core.rate_limiter import rate_limiter


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
    request: Request,
    credentials: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """
    Authenticate with email and password.
    
    Returns access and refresh tokens for API authentication.
    Rate limited: 5/15min per email, 10/15min per IP
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limits
    email_allowed, _, email_retry = await rate_limiter.check(f"login:email:{credentials.email}", max_requests=5, window_seconds=900)
    ip_allowed, _, ip_retry = await rate_limiter.check(f"login:ip:{client_ip}", max_requests=10, window_seconds=900)
    
    if not email_allowed:
        raise RateLimitExceeded(message="Too many login attempts. Please try again later.", retry_after=email_retry)
    if not ip_allowed:
        raise RateLimitExceeded(message="Too many login attempts from this IP.", retry_after=ip_retry)
    
    try:
        result = await auth_service.login(credentials.email, credentials.password)
        # Reset rate limit on successful login
        await rate_limiter.reset(f"login:email:{credentials.email}")
        return result
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
    Returns validation status, error messages, and suggestions if taken.
    """
    from app.services.user_service import UserService
    user_service = UserService()
    
    # Validate format first
    is_valid, error = UserService.validate_username(username)
    if not is_valid:
        return {
            "available": False,
            "valid": False,
            "error": error,
            "suggestions": []
        }
    
    # Check availability
    is_available = await user_service.is_username_available(username)
    
    if is_available:
        return {
            "available": True,
            "valid": True,
            "error": None,
            "suggestions": []
        }
    else:
        # Generate suggestions
        suggestions = await user_service.generate_username_suggestions(username)
        return {
            "available": False,
            "valid": True,
            "error": "Username is already taken",
            "suggestions": suggestions
        }


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


from pydantic import BaseModel, EmailStr, Field
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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


# ==================== REGISTRATION OTP ====================

class RegisterSendOTPRequest(BaseModel):
    email: EmailStr

class RegisterVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


@router.post("/register/send-otp", summary="Send OTP for email verification during registration")
async def register_send_otp(
    request: Request,
    data: RegisterSendOTPRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """
    Step 1 of registration: Send OTP to verify email.
    - Validates email is not already registered
    - Sends 6-digit OTP to email
    Rate limited: 3/hour per email, 10/hour per IP
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limits
    email_allowed, _, email_retry = await rate_limiter.check(f"reg_otp:email:{data.email}", max_requests=3, window_seconds=3600)
    ip_allowed, _, ip_retry = await rate_limiter.check(f"reg_otp:ip:{client_ip}", max_requests=10, window_seconds=3600)
    
    if not email_allowed:
        raise RateLimitExceeded(message="Too many registration attempts. Please try again later.", retry_after=email_retry)
    if not ip_allowed:
        raise RateLimitExceeded(message="Too many registration attempts from this IP.", retry_after=ip_retry)
    
    try:
        await auth_service.send_registration_otp(data.email)
        return {"message": "OTP sent to your email. Please verify to continue registration."}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/register/verify-otp", summary="Verify OTP and get registration token")
async def register_verify_otp(
    data: RegisterVerifyOTPRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> dict:
    """
    Step 2 of registration: Verify OTP.
    Returns a registration token to complete the registration with username.
    Rate limited: 5 attempts per 10 minutes per email
    """
    # Check rate limit for OTP verification
    allowed, _, retry_after = await rate_limiter.check(f"reg_verify:email:{data.email}", max_requests=5, window_seconds=600)
    
    if not allowed:
        await rate_limiter.apply_lockout(f"reg_verify:{data.email}", duration_seconds=1800)
        raise RateLimitExceeded(message="Too many verification attempts. Please wait 30 minutes.", retry_after=1800)
    
    # Check lockout
    is_locked, lock_remaining = await rate_limiter.is_locked_out(f"reg_verify:{data.email}")
    if is_locked:
        raise RateLimitExceeded(message="Temporarily locked. Please try again later.", retry_after=lock_remaining)
    
    try:
        email_verified_token = await auth_service.verify_registration_otp(data.email, data.otp)
        # Reset rate limit on success
        await rate_limiter.reset(f"reg_verify:email:{data.email}")
        return {"verified": True, "email_verified_token": email_verified_token}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


class CompleteRegistrationRequest(BaseModel):
    email_verified_token: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


@router.post("/register/complete", response_model=TokenResponse, summary="Complete registration with verified email")
async def complete_registration(
    data: CompleteRegistrationRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenResponse:
    """
    Final step of registration: Complete with username and password.
    Requires a valid email_verified_token from OTP verification.
    Returns access and refresh tokens (auto-login).
    """
    try:
        result = await auth_service.complete_registration(data.email_verified_token, data.username, data.password)
        return result
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== FORGOT PASSWORD ====================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)

@router.post("/forgot-password", summary="Initiate password reset flow")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """
    Initiate password reset flow.
    Generates OTP and sends it to the user's email.
    Rate limited: 3/hour per email, 10/hour per IP
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limits
    email_allowed, _, email_retry = await rate_limiter.check(f"forgot:email:{data.email}", max_requests=3, window_seconds=3600)
    ip_allowed, _, ip_retry = await rate_limiter.check(f"forgot:ip:{client_ip}", max_requests=10, window_seconds=3600)
    
    if not email_allowed:
        raise RateLimitExceeded(message="Too many password reset requests. Please try again later.", retry_after=email_retry)
    if not ip_allowed:
        raise RateLimitExceeded(message="Too many password reset requests from this IP.", retry_after=ip_retry)
    
    try:
        await auth_service.forgot_password(data.email)
        return {"message": "If the account exists, an OTP has been sent to your email."}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/verify-otp", summary="Verify OTP and get reset token")
async def verify_otp(
    data: OTPVerifyRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> dict:
    """
    Verify OTP. Returns a temporary reset token if valid.
    Rate limited: 5 attempts per 10 minutes per email
    """
    # Check rate limit for OTP verification (prevents brute force)
    allowed, _, retry_after = await rate_limiter.check(f"otp:email:{data.email}", max_requests=5, window_seconds=600)
    
    if not allowed:
        # Apply lockout after too many failures
        await rate_limiter.apply_lockout(f"otp:{data.email}", duration_seconds=1800)  # 30 min lockout
        raise RateLimitExceeded(message="Too many OTP attempts. Please wait 30 minutes.", retry_after=1800)
    
    # Check if already locked out
    is_locked, lock_remaining = await rate_limiter.is_locked_out(f"otp:{data.email}")
    if is_locked:
        raise RateLimitExceeded(message="Account temporarily locked. Please try again later.", retry_after=lock_remaining)
    
    try:
        reset_token = await auth_service.verify_otp(data.email, data.otp)
        # Reset rate limit on success
        await rate_limiter.reset(f"otp:email:{data.email}")
        return {"reset_token": reset_token}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/reset-password", summary="Reset password using token")
async def reset_password(
    data: ResetPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    token: str = Depends(oauth2_scheme),
):
    """
    Reset password using the secure token obtained from OTP verification.
    """
    try:
        await auth_service.reset_password(token, data.new_password)
        return {"message": "Password reset successfully"}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

