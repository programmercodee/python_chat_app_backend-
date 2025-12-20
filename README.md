# Messaging Platform Backend

Real-time messaging platform with end-to-end encryption, built with **FastAPI** and **Socket.IO**.

## Features

- 🔐 **JWT Authentication** - Secure registration and login
- 💬 **Real-time Messaging** - Instant delivery via WebSocket
- 🔒 **End-to-End Encryption** - X25519 + AES-256-GCM
- 👥 **Presence Detection** - Online/offline status
- ⌨️ **Typing Indicators** - Real-time typing status
- 📱 **Contact Management** - Add, accept, block contacts
- 👥 **Group Chats** - Create and manage groups

---

## Quick Start

### 1. Create Database

```sql
CREATE DATABASE chatapp;
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Server

```bash
# From /home/openspace/test directory
uvicorn app.main:socket_app --reload --host 0.0.0.0 --port 8000
```

### 4. Open API Docs

http://localhost:8000/docs

---

## Configuration

Database is configured in `.env`:

```
DATABASE_URL=mysql+aiomysql://root:12345@127.0.0.1:3306/chatapp
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh token |
| GET | `/api/v1/auth/me` | Current user |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/search?q=` | Search users |
| GET | `/api/v1/users/{id}` | Get user |
| PUT | `/api/v1/users/me/public-key` | Set encryption key |

### Contacts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/contacts` | List contacts |
| POST | `/api/v1/contacts` | Add contact |
| GET | `/api/v1/contacts/requests` | Pending requests |
| DELETE | `/api/v1/contacts/{id}` | Remove contact |

### Conversations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/conversations` | List chats |
| POST | `/api/v1/conversations` | Create chat |
| GET | `/api/v1/conversations/{id}` | Get chat |

### Messages
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/messages/conversation/{id}` | Get messages |
| POST | `/api/v1/messages` | Send message |
| POST | `/api/v1/messages/read` | Mark as read |

---

## Socket.IO Events

### Client → Server
| Event | Payload |
|-------|---------|
| `send_message` | `{conversation_id, encrypted_content, nonce}` |
| `typing_start` | `{conversation_id}` |
| `typing_stop` | `{conversation_id}` |
| `message_read` | `{message_ids: [...]}` |

### Server → Client
| Event | Payload |
|-------|---------|
| `new_message` | `{id, sender_id, encrypted_content, ...}` |
| `user_typing` | `{user_id, username, conversation_id}` |
| `user_online` | `{user_id}` |
| `user_offline` | `{user_id}` |

---

## Socket.IO Usage

```javascript
const socket = io('http://localhost:8000', {
  auth: { token: 'your-jwt-token' }
});

socket.on('new_message', (msg) => console.log('New:', msg));

socket.emit('send_message', {
  conversation_id: 'uuid',
  encrypted_content: 'encrypted-base64',
  nonce: 'nonce-base64'
});
```

---

## Project Structure

```
app/
├── main.py          # Entry point
├── config.py        # Settings
├── database.py      # MySQL connection
├── api/             # REST endpoints
├── sockets/         # Real-time handlers
├── models/          # Database tables
├── schemas/         # Validation
├── services/        # Business logic
└── core/            # Utilities
```

---

## Optional: Redis for Presence

For full online/offline and typing indicator support:

```bash
sudo apt install redis-server
sudo systemctl start redis
```

## To kill process on PORT

```bash
sudo kill $(lsof -t -i:8000)
```
