"""
Socket.IO connection manager.
Keeps track of connected users and their socket IDs.
"""

import socketio
from app.config import settings


# Create Socket.IO server
# async_mode="asgi" is required for FastAPI integration
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # Allow all origins for development
    logger=settings.debug,
    engineio_logger=settings.debug,
)


class ConnectionManager:
    """
    Simple manager to track connected users.
    
    Maps user_id -> socket_id for message routing.
    This is an in-memory store for single-server setups.
    For multi-server, use Redis (handled by PresenceService).
    """
    
    def __init__(self):
        # user_id (str) -> socket_id (str)
        self.active_connections: dict[str, str] = {}
        
        # socket_id (str) -> user_id (str) - reverse lookup
        self.socket_to_user: dict[str, str] = {}
    
    def connect(self, user_id: str, socket_id: str) -> None:
        """Register a new connection."""
        # Remove old connection if user reconnects
        if user_id in self.active_connections:
            old_socket = self.active_connections[user_id]
            self.socket_to_user.pop(old_socket, None)
        
        self.active_connections[user_id] = socket_id
        self.socket_to_user[socket_id] = user_id
        print(f"[Socket] User {user_id} connected with socket {socket_id}")
    
    def disconnect(self, socket_id: str) -> str | None:
        """
        Remove a connection.
        Returns the user_id if found.
        """
        user_id = self.socket_to_user.pop(socket_id, None)
        if user_id:
            self.active_connections.pop(user_id, None)
            print(f"[Socket] User {user_id} disconnected")
        return user_id
    
    def get_socket_id(self, user_id: str) -> str | None:
        """Get socket ID for a user (if online)."""
        return self.active_connections.get(user_id)
    
    def get_user_id(self, socket_id: str) -> str | None:
        """Get user ID for a socket."""
        return self.socket_to_user.get(socket_id)
    
    def is_online(self, user_id: str) -> bool:
        """Check if user is connected."""
        return user_id in self.active_connections
    
    def get_online_users(self) -> list[str]:
        """Get list of all online user IDs."""
        return list(self.active_connections.keys())


# Global connection manager instance
socket_manager = ConnectionManager()
