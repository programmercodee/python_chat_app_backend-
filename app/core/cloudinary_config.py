"""
Cloudinary Configuration.

This module sets up Cloudinary for image uploads.
Cloudinary is a cloud service for storing and transforming images.
"""

import cloudinary
import cloudinary.uploader
from app.config import get_settings


def init_cloudinary():
    """
    Initialize Cloudinary with credentials from environment variables.
    
    Call this once during app startup (in main.py).
    After this, you can use cloudinary.uploader anywhere in the app.
    """
    settings = get_settings()
    
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True  # Always use HTTPS
    )


def upload_image(file_content: bytes, folder: str = "avatars") -> dict:
    """
    Upload an image to Cloudinary.
    
    Args:
        file_content: The raw bytes of the image file
        folder: Cloudinary folder to store the image (default: "avatars")
    
    Returns:
        dict with 'url' and 'public_id' keys
    
    Example:
        result = upload_image(image_bytes, folder="avatars")
        avatar_url = result["url"]  # "https://res.cloudinary.com/..."
    """
    # Upload with automatic format optimization and transformations
    result = cloudinary.uploader.upload(
        file_content,
        folder=folder,
        # Transformations for profile pictures:
        transformation=[
            {
                "width": 400,           # Max width
                "height": 400,          # Max height
                "crop": "fill",         # Crop to fill the dimensions
                "gravity": "face",      # Focus on face if detected
                "quality": "auto:good"  # Automatic quality optimization
            }
        ],
        # Return format
        format="webp",  # Modern, efficient format
        # Overwrite if same public_id
        overwrite=True,
        # Resource type
        resource_type="image"
    )
    
    return {
        "url": result["secure_url"],      # HTTPS URL to the image
        "public_id": result["public_id"]  # Unique ID for deletion later
    }


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary.
    
    Args:
        public_id: The Cloudinary public_id of the image
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False
