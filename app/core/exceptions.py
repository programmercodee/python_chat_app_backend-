"""
Custom exception classes for the application.
These exceptions are caught by exception handlers in main.py.
"""

from typing import Any, Optional


class AppException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class AuthenticationError(AppException):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=401, details=details)


class AuthorizationError(AppException):
    """Raised when user lacks permission for an action."""
    
    def __init__(
        self,
        message: str = "Not authorized to perform this action",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=403, details=details)


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=404, details=details)


class ValidationError(AppException):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=422, details=details)


class ConflictError(AppException):
    """Raised when there's a conflict (e.g., duplicate resource)."""
    
    def __init__(
        self,
        message: str = "Resource already exists",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=409, details=details)


class RateLimitExceeded(AppException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
        retry_after: int = 60,
        details: Optional[Any] = None,
    ):
        self.retry_after = retry_after
        super().__init__(message=message, status_code=429, details=details)
