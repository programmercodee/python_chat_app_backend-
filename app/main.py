"""
Main application entry point.
Creates FastAPI app with Socket.IO integration.

Run with: uvicorn app.main:socket_app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio

from app.config import settings
from app.database import init_db, close_db
from app.core.redis import redis_client
from app.core.exceptions import AppException
from app.core.cloudinary_config import init_cloudinary
from app.api import api_router
from app.api.upload import router as upload_router
from app.sockets import sio, register_socket_events
from app.logging_config import logger


# ==================== LIFESPAN (STARTUP/SHUTDOWN) ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("🚀 Starting Messaging Platform...")
    
    # Connect to Redis
    try:
        await redis_client.connect()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")
        logger.warning("   (Presence features will be limited)")
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        raise
    
    # Register socket event handlers
    register_socket_events()
    logger.info("✅ Socket.IO events registered")
    
    # Initialize Cloudinary for image uploads
    try:
        init_cloudinary()
        logger.info("✅ Cloudinary initialized")
    except Exception as e:
        logger.warning(f"⚠️ Cloudinary init failed: {e}")
        logger.warning("   (Avatar uploads may not work)")
    
    logger.info("🎉 Server is ready!")
    logger.info("   API Docs: http://localhost:8000/docs")
    logger.info("   Socket.IO: ws://localhost:8000/socket.io/")
    
    yield  # Server is running
    
    # Shutdown
    logger.info("👋 Shutting down...")
    await redis_client.disconnect()
    await close_db()
    logger.info("✅ Cleanup complete")


# ==================== CREATE APP ====================

app = FastAPI(
    title=settings.app_name,
    description="Real-time messaging platform with end-to-end encryption",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ==================== MIDDLEWARE ====================

# CORS middleware - MUST be added first for preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ==================== ACCESS LOGGING ====================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log only non-2xx responses to reduce noise."""
    response = await call_next(request)
    
    # Only log errors (non-2xx status codes)
    if response.status_code >= 400:
        logger.warning(f"❌ {request.method} {request.url.path} -> {response.status_code}")
    
    return response


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    logger.warning(f"AppException: {exc.message} | Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 Not Found errors."""
    logger.warning(f"404 Not Found: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={"error": "Not found"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"❌ Unhandled error in {request.url.path}: {exc}")
    
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# ==================== ROUTES ====================

app.include_router(api_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")  # Avatar upload endpoint


@app.get("/health", tags=["Health"])
async def health_check():
    """Check if the server is running."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "service": settings.app_name,
    }


@app.get("/", tags=["Root"])
async def root():
    """Welcome message."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "api": "/api/v1",
    }


# ==================== SOCKET.IO INTEGRATION ====================

socket_app = socketio.ASGIApp(
    socketio_server=sio,
    other_asgi_app=app,
    socketio_path="socket.io",
)
