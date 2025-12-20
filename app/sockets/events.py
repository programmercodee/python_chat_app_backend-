"""
Socket.IO event handlers.
Handles connect, disconnect, messaging, typing, and presence events.
Uses MongoDB via Beanie ODM.
"""

from datetime import datetime, timezone

from app.sockets.manager import sio, socket_manager
from app.core.security import verify_token
from app.core.exceptions import AuthenticationError
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService
from app.logging_config import logger


def register_socket_events():
    """Register all Socket.IO event handlers."""
    
    # ==================== CONNECTION EVENTS ====================
    
    @sio.event
    async def connect(sid, environ, auth):
        """Handle new socket connection."""
        logger.info(f"[Socket] Connection attempt: {sid}")
        
        if not auth or 'token' not in auth:
            logger.warning(f"[Socket] Rejected {sid}: No token provided")
            return False
        
        try:
            payload = verify_token(auth['token'])
            user_id = payload.get('sub')
            
            if not user_id:
                logger.warning(f"[Socket] Rejected {sid}: Invalid token payload")
                return False
            
            socket_manager.connect(user_id, sid)
            await sio.save_session(sid, {'user_id': user_id})
            
            await sio.emit(
                'user_online',
                {'user_id': user_id, 'timestamp': datetime.now(timezone.utc).isoformat()},
                skip_sid=sid,
            )
            
            logger.info(f"[Socket] ✅ User {user_id} connected ({sid})")
            return True
            
        except AuthenticationError as e:
            logger.warning(f"[Socket] Rejected {sid}: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"[Socket] Error in connect: {e}")
            return False
    
    
    @sio.event
    async def disconnect(sid):
        """Handle socket disconnection."""
        user_id = socket_manager.disconnect(sid)
        
        if user_id:
            await sio.emit(
                'user_offline',
                {'user_id': user_id, 'timestamp': datetime.now(timezone.utc).isoformat()},
            )
            logger.info(f"[Socket] 👋 User {user_id} disconnected")
    
    
    # ==================== MESSAGING EVENTS ====================
    
    @sio.event
    async def send_message(sid, data):
        """Handle sending a message."""
        logger.debug(f"[Socket] send_message from {sid}")
        
        session = await sio.get_session(sid)
        sender_id = session.get('user_id')
        
        if not sender_id:
            logger.warning(f"[Socket] Unauthenticated send_message attempt: {sid}")
            await sio.emit('error', {'message': 'Not authenticated'}, to=sid)
            return
        
        required_fields = ['conversation_id', 'encrypted_content', 'nonce']
        for field in required_fields:
            if field not in data:
                logger.warning(f"[Socket] Missing field '{field}' in send_message")
                await sio.emit('error', {'message': f'Missing field: {field}'}, to=sid)
                return
        
        try:
            # Use MongoDB services (no db session needed)
            message_service = MessageService()
            conversation_service = ConversationService()
            
            message = await message_service.create_message(
                sender_id=sender_id,
                conversation_id=data['conversation_id'],
                encrypted_content=data['encrypted_content'],
                nonce=data['nonce'],
                content_type=data.get('content_type', 'text'),
            )
            
            conversation = await conversation_service.get_conversation(
                data['conversation_id'],
                sender_id,
            )
            
            message_data = {
                'id': str(message.id),
                'conversation_id': str(message.conversation_id),
                'sender_id': sender_id,
                'encrypted_content': message.encrypted_content,
                'nonce': message.nonce,
                'content_type': message.content_type,
                'created_at': message.created_at.isoformat(),
            }
            
            # Emit to all members
            for member_id in conversation.member_ids:
                member_socket = socket_manager.get_socket_id(str(member_id))
                if member_socket:
                    await sio.emit('new_message', message_data, to=member_socket)
                    if str(member_id) != sender_id:
                        await message_service.mark_as_delivered(str(message.id))
            
            logger.info(f"[Socket] 📨 Message {message.id} sent by {sender_id}")
                
        except Exception as e:
            logger.exception(f"[Socket] Error sending message: {e}")
            await sio.emit('error', {'message': 'Failed to send message'}, to=sid)
    
    
    @sio.event
    async def message_read(sid, data):
        """Handle marking messages as read."""
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        
        if not user_id or 'message_ids' not in data:
            return
        
        try:
            message_service = MessageService()
            await message_service.mark_as_read(data['message_ids'], user_id)
            
            await sio.emit(
                'messages_read',
                {
                    'message_ids': data['message_ids'],
                    'read_by': user_id,
                    'read_at': datetime.now(timezone.utc).isoformat(),
                },
                skip_sid=sid,
            )
            
            logger.debug(f"[Socket] User {user_id} read {len(data['message_ids'])} messages")
            
        except Exception as e:
            logger.exception(f"[Socket] Error marking messages read: {e}")
    
    
    # ==================== TYPING EVENTS ====================
    
    @sio.event
    async def typing_start(sid, data):
        """Handle typing indicator start."""
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        
        if not user_id or 'conversation_id' not in data:
            return
        
        try:
            user_service = UserService()
            user = await user_service.get_user(user_id)
            username = user.username
        except Exception:
            username = "Someone"
        
        await sio.emit(
            'user_typing',
            {
                'user_id': user_id,
                'username': username,
                'conversation_id': data['conversation_id'],
            },
            skip_sid=sid,
        )
        
        logger.debug(f"[Socket] {username} is typing")
    
    
    @sio.event
    async def typing_stop(sid, data):
        """Handle typing indicator stop."""
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        
        if not user_id or 'conversation_id' not in data:
            return
        
        await sio.emit(
            'user_stopped_typing',
            {
                'user_id': user_id,
                'conversation_id': data['conversation_id'],
            },
            skip_sid=sid,
        )
    
    
    # ==================== UTILITY EVENTS ====================
    
    @sio.event
    async def ping(sid, data):
        """Simple ping-pong for connection testing."""
        await sio.emit('pong', {'timestamp': datetime.now(timezone.utc).isoformat()}, to=sid)
    
    
    @sio.event
    async def get_online_users(sid, data):
        """Get list of online users."""
        session = await sio.get_session(sid)
        if not session.get('user_id'):
            return
        
        if data and 'user_ids' in data:
            online = [uid for uid in data['user_ids'] if socket_manager.is_online(uid)]
        else:
            online = socket_manager.get_online_users()
        
        await sio.emit('online_users', {'users': online}, to=sid)
    
    
    logger.info("[Socket] Event handlers registered")
