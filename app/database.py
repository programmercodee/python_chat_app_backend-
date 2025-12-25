"""
MongoDB database connection setup using Motor and Beanie ODM.
Provides async MongoDB client and document initialization.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import settings

# MongoDB client instance
client: AsyncIOMotorClient = None


async def init_db():
    """
    Initialize MongoDB connection and Beanie ODM.
    Call this on application startup.
    """
    global client
    
    # Create MongoDB client with connection pooling for better performance
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=50,              # Max connections in pool
        minPoolSize=5,               # Keep 5 connections ready
        maxIdleTimeMS=45000,         # Close idle connections after 45s
        waitQueueTimeoutMS=5000,     # Timeout if pool exhausted
        serverSelectionTimeoutMS=5000,  # Quick fail on connection issues
    )
    
    # Use explicit database name
    db = client["chat_app"]
    
    # Import all document models
    from app.models.user import User
    from app.models.conversation import Conversation, ConversationMember
    from app.models.message import Message
    from app.models.contact import Contact
    
    # Initialize Beanie with document models
    await init_beanie(
        database=db,
        document_models=[User, Conversation, ConversationMember, Message, Contact]
    )
    
    print(f"Connected to MongoDB database: {db.name}")


async def close_db():
    """
    Close MongoDB connection.
    Call this on application shutdown.
    """
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


def get_client() -> AsyncIOMotorClient:
    """Get the MongoDB client instance."""
    return client
