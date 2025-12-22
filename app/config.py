"""
Application configuration using Pydantic Settings.
Loads environment variables with validation and defaults.
"""

from functools import lru_cache
from typing import List
import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "MessagingPlatform"
    debug: bool = False
    secret_key: str
    
    # MongoDB Database
    mongodb_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Cloudinary (Image Upload)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    
    # Socket.IO / CORS - Allow Vite dev server
    socketio_cors_origins: str = '["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]'
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from JSON string."""
        try:
            return json.loads(self.socketio_cors_origins)
        except json.JSONDecodeError:
            return ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    Using lru_cache ensures settings are only loaded once.
    """
    return Settings()


# Export settings instance for easy access
settings = get_settings()
