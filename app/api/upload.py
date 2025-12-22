"""
Avatar Upload API Endpoint.

This endpoint handles profile picture uploads using Cloudinary.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.core.cloudinary_config import upload_image
from app.dependencies import get_current_user
from app.models.user import User


# Create the router for upload endpoints
router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a new avatar image for the current user.
    
    HOW IT WORKS:
    1. User sends an image file
    2. We validate it's an image
    3. We upload to Cloudinary (they handle resizing, optimization)
    4. We save the URL to the user's profile
    5. We return the new avatar URL
    
    Args:
        file: The image file (JPG, PNG, WebP, etc.)
        current_user: The authenticated user (from JWT token)
    
    Returns:
        { "avatar_url": "https://res.cloudinary.com/..." }
    """
    
    # STEP 1: Validate the file is an image
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # STEP 2: Check file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    contents = await file.read()
    
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 5MB."
        )
    
    # STEP 3: Upload to Cloudinary
    try:
        result = upload_image(contents, folder="chat_avatars")
        avatar_url = result["url"]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload image: {str(e)}"
        )
    
    # STEP 4: Save the URL to user's profile
    current_user.avatar_url = avatar_url
    await current_user.save()
    
    # STEP 5: Return the new avatar URL
    return {
        "avatar_url": avatar_url,
        "message": "Avatar uploaded successfully!"
    }
