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
            
            # Broadcast online status
            await sio.emit(
                'user_online',
                {'user_id': user_id, 'timestamp': datetime.now(timezone.utc).isoformat()},
                skip_sid=sid,
            )
            
            # Handle offline delivery - mark pending messages as delivered
            try:
                message_service = MessageService()
                delivered_messages = await message_service.mark_messages_delivered_on_connect(user_id)
                
                # Notify senders that their messages were delivered
                for message in delivered_messages:
                    sender_socket = socket_manager.get_socket_id(str(message.sender_id))
                    if sender_socket:
                        await sio.emit('message_status_update', {
                            'message_id': str(message.id),
                            'status': 'delivered',
                        }, to=sender_socket)
                
                if delivered_messages:
                    logger.info(f"[Socket] Delivered {len(delivered_messages)} offline messages to {user_id}")
            except Exception as e:
                logger.exception(f"[Socket] Error handling offline delivery: {e}")
            
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
                'status': message.status,
                'created_at': message.created_at.isoformat(),
            }
            
            # 1. Send ACK back to sender (message_sent event)
            await sio.emit('message_sent', {
                'nonce': data['nonce'],  # For matching pending message
                'message_id': str(message.id),
                'status': 'sent',
                'created_at': message.created_at.isoformat(),
            }, to=sid)
            
            # 2. Emit to other members (not sender)
            for member_id in conversation.member_ids:
                if str(member_id) != sender_id:
                    member_socket = socket_manager.get_socket_id(str(member_id))
                    if member_socket:
                        await sio.emit('new_message', message_data, to=member_socket)
            
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
            updated_messages = await message_service.mark_as_read(data['message_ids'], user_id)
            
            # Notify senders that their messages were read
            for message in updated_messages:
                sender_socket = socket_manager.get_socket_id(str(message.sender_id))
                if sender_socket:
                    await sio.emit('message_status_update', {
                        'message_id': str(message.id),
                        'status': 'read',
                    }, to=sender_socket)
            
            logger.debug(f"[Socket] User {user_id} read {len(updated_messages)} messages")
            
        except Exception as e:
            logger.exception(f"[Socket] Error marking messages read: {e}")
    
    
    @sio.event
    async def message_delivered(sid, data):
        """Handle delivery confirmation from receiver."""
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        
        if not user_id or 'message_id' not in data:
            return
        
        try:
            message_service = MessageService()
            message = await message_service.mark_as_delivered(data['message_id'])
            
            if message:
                # Notify the sender that message was delivered
                sender_socket = socket_manager.get_socket_id(str(message.sender_id))
                if sender_socket:
                    await sio.emit('message_status_update', {
                        'message_id': str(message.id),
                        'status': 'delivered',
                    }, to=sender_socket)
                
                logger.debug(f"[Socket] Message {message.id} delivered to {user_id}")
                
        except Exception as e:
            logger.exception(f"[Socket] Error marking message delivered: {e}")
    
    
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
    
    
    # ==================== VOICE/VIDEO CALL SIGNALING ====================
    # 
    # These events handle WebRTC call setup between two users.
    # The actual audio/video goes peer-to-peer via WebRTC.
    # Socket.IO only handles the "signaling" (connection setup).
    #
    # Call Flow:
    # 1. Caller sends 'call_initiate' → Receiver gets 'incoming_call'
    # 2. Receiver accepts → sends 'call_accept'
    # 3. Caller gets 'call_accepted', creates WebRTC offer
    # 4. Exchange offer/answer/ice-candidates via socket
    # 5. WebRTC connection established → audio/video flows directly
    # 6. Either party sends 'call_end' to finish
    #
    
    @sio.event
    async def call_initiate(sid, data):
        """
        Step 1: Caller initiates a call.
        
        data = {
            'to_user_id': '...',     # Who to call
            'call_type': 'video'     # 'video' or 'audio'
        }
        """
        session = await sio.get_session(sid)
        caller_id = session.get('user_id')
        if not caller_id:
            return
        
        to_user_id = data.get('to_user_id')
        call_type = data.get('call_type', 'video')
        
        logger.info(f"[Call] {caller_id} calling {to_user_id} ({call_type})")
        
        # Check if receiver is online
        receiver_sid = socket_manager.get_socket_id(to_user_id)
        if not receiver_sid:
            # User is offline
            await sio.emit('call_failed', {
                'reason': 'user_offline',
                'message': 'User is not available'
            }, to=sid)
            return
        
        # Get caller info for the incoming call popup
        user_service = UserService()
        caller = await user_service.get_user(caller_id)
        
        # Notify the receiver about incoming call
        await sio.emit('incoming_call', {
            'from_user_id': caller_id,
            'from_username': caller.username if caller else 'Unknown',
            'from_avatar': caller.avatar_url if caller else None,
            'call_type': call_type
        }, to=receiver_sid)
        
        # Confirm to caller that call is ringing
        await sio.emit('call_ringing', {
            'to_user_id': to_user_id
        }, to=sid)
    
    
    @sio.event
    async def call_accept(sid, data):
        """
        Step 2: Receiver accepts the call.
        
        data = { 'to_user_id': '...' }  # The original caller
        """
        session = await sio.get_session(sid)
        receiver_id = session.get('user_id')
        if not receiver_id:
            return
        
        caller_id = data.get('to_user_id')
        caller_sid = socket_manager.get_socket_id(caller_id)
        
        logger.info(f"[Call] {receiver_id} accepted call from {caller_id}")
        
        if caller_sid:
            # Tell caller to start WebRTC offer
            await sio.emit('call_accepted', {
                'from_user_id': receiver_id
            }, to=caller_sid)
    
    
    @sio.event
    async def call_reject(sid, data):
        """
        Receiver rejects the incoming call.
        
        data = { 'to_user_id': '...' }  # The original caller
        """
        session = await sio.get_session(sid)
        receiver_id = session.get('user_id')
        if not receiver_id:
            return
        
        caller_id = data.get('to_user_id')
        caller_sid = socket_manager.get_socket_id(caller_id)
        
        logger.info(f"[Call] {receiver_id} rejected call from {caller_id}")
        
        if caller_sid:
            await sio.emit('call_rejected', {
                'from_user_id': receiver_id
            }, to=caller_sid)
    
    
    @sio.event
    async def call_offer(sid, data):
        """
        Step 3: Caller sends WebRTC offer (SDP).
        
        data = {
            'to_user_id': '...',
            'offer': { ... }  # WebRTC SDP offer
        }
        """
        session = await sio.get_session(sid)
        caller_id = session.get('user_id')
        if not caller_id:
            return
        
        to_user_id = data.get('to_user_id')
        offer = data.get('offer')
        receiver_sid = socket_manager.get_socket_id(to_user_id)
        
        if receiver_sid:
            await sio.emit('call_offer', {
                'from_user_id': caller_id,
                'offer': offer
            }, to=receiver_sid)
    
    
    @sio.event
    async def call_answer(sid, data):
        """
        Step 4: Receiver sends WebRTC answer (SDP).
        
        data = {
            'to_user_id': '...',
            'answer': { ... }  # WebRTC SDP answer
        }
        """
        session = await sio.get_session(sid)
        receiver_id = session.get('user_id')
        if not receiver_id:
            return
        
        to_user_id = data.get('to_user_id')
        answer = data.get('answer')
        caller_sid = socket_manager.get_socket_id(to_user_id)
        
        if caller_sid:
            await sio.emit('call_answer', {
                'from_user_id': receiver_id,
                'answer': answer
            }, to=caller_sid)
    
    
    @sio.event
    async def call_ice_candidate(sid, data):
        """
        Step 5: Exchange ICE candidates for NAT traversal.
        
        Both parties send these as they discover network paths.
        
        data = {
            'to_user_id': '...',
            'candidate': { ... }  # ICE candidate
        }
        """
        session = await sio.get_session(sid)
        sender_id = session.get('user_id')
        if not sender_id:
            return
        
        to_user_id = data.get('to_user_id')
        candidate = data.get('candidate')
        receiver_sid = socket_manager.get_socket_id(to_user_id)
        
        if receiver_sid:
            await sio.emit('call_ice_candidate', {
                'from_user_id': sender_id,
                'candidate': candidate
            }, to=receiver_sid)
    
    
    @sio.event
    async def call_end(sid, data):
        """
        Step 6: Either party ends the call.
        
        data = {
            'to_user_id': '...',
            'reason': 'ended'  # 'ended', 'busy', 'timeout', 'failed'
        }
        """
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        if not user_id:
            return
        
        to_user_id = data.get('to_user_id')
        reason = data.get('reason', 'ended')
        other_sid = socket_manager.get_socket_id(to_user_id)
        
        logger.info(f"[Call] {user_id} ended call with {to_user_id} ({reason})")
        
        if other_sid:
            await sio.emit('call_ended', {
                'from_user_id': user_id,
                'reason': reason
            }, to=other_sid)
    
    
    logger.info("[Socket] Event handlers registered")
