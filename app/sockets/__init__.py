"""
Socket.IO package.
Handles real-time messaging, presence, and typing indicators.
"""

from app.sockets.manager import socket_manager, sio
from app.sockets.events import register_socket_events

__all__ = [
    "socket_manager",
    "sio",
    "register_socket_events",
]
