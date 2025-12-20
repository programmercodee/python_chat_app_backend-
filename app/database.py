"""
Async database connection setup using SQLAlchemy 2.0.
Provides session factory and base model for all database models.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


# Create async engine with connection pooling disabled for serverless compatibility
# For production with persistent servers, remove poolclass=NullPool
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL queries in debug mode
    poolclass=NullPool,
)

# Session factory for creating database sessions
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    All models should inherit from this class.
    """
    pass


async def get_db() -> AsyncSession:
    """
    Dependency for getting async database sessions.
    Use with FastAPI's Depends() for automatic session management.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables.
    Call this on application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Close database connections.
    Call this on application shutdown.
    """
    await engine.dispose()
