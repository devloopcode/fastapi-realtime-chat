# Real-Time Chat API

A horizontally scalable real-time chat backend built with **FastAPI**, **WebSockets**, **Redis pub/sub**, and **PostgreSQL**. Architected for use in Discord/Slack-style applications.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Clients (WS + HTTP)                  │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │     FastAPI Instance A     │  ◄── multiple instances
          │  ┌─────────────────────┐  │       can run in parallel
          │  │  ConnectionManager  │  │
          │  │  (in-process dict)  │  │
          │  └──────────┬──────────┘  │
          └─────────────┼─────────────┘
                        │ publish / subscribe
          ┌─────────────▼─────────────┐
          │         Redis              │
          │  ┌────────────────────┐   │
          │  │  Pub/Sub channels  │   │  channel:room:{id}
          │  │  Presence keys     │   │  presence:{user_id}
          │  │  Typing keys (TTL) │   │  typing:{room_id}:{user_id}
          │  └────────────────────┘   │
          └─────────────┬─────────────┘
                        │
          ┌─────────────▼─────────────┐
          │  FastAPI Instance B        │  ◄── receives events
          │  (different process)       │       broadcasts locally
          └────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │       PostgreSQL           │
          │  users, rooms, messages,   │
          │  notifications, tokens     │
          └────────────────────────────┘
```

### Horizontal Scaling

Each FastAPI process maintains its own **in-memory WebSocket registry** (`ConnectionManager`). When a message is sent:

1. It is **persisted to PostgreSQL** via the repository layer.
2. It is **published to a Redis channel** (`channel:room:{room_id}`).
3. **All worker processes** subscribed to that channel receive the event and **broadcast to their local WebSocket connections**.

This means adding more API replicas requires zero configuration — Redis is the fan-out bus.

---

## Tech Stack

| Concern | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| ASGI server | Uvicorn |
| Real-time | WebSockets (native FastAPI) |
| Message bus | Redis pub/sub |
| Presence / Typing | Redis keys with TTL |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Auth | JWT (access + refresh token rotation) |
| Password hashing | bcrypt via passlib |
| Validation | Pydantic v2 |
| Rate limiting | slowapi |
| Testing | pytest-asyncio + httpx AsyncClient |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
real-time-chat/
├── main.py                      # App entry point, lifespan, middleware
├── app/
│   ├── api/v1/endpoints/        # REST route handlers (thin — call services)
│   │   ├── auth.py              # register, login, token refresh
│   │   ├── users.py             # /me, /online
│   │   ├── rooms.py             # CRUD + join/leave
│   │   ├── messages.py          # history, mark-read
│   │   ├── notifications.py     # list, unread count, mark-all-read
│   │   └── upload.py            # image upload
│   ├── websocket/
│   │   ├── router.py            # /ws/chat/{room_id} endpoint + lifecycle
│   │   └── handlers.py          # per-message-type dispatch
│   ├── core/
│   │   ├── config.py            # pydantic-settings from .env
│   │   ├── security.py          # JWT create/decode, bcrypt
│   │   ├── exceptions.py        # custom exception hierarchy + HTTP factories
│   │   └── logging.py           # structlog setup
│   ├── db/
│   │   ├── session.py           # async engine + session factory
│   │   ├── base.py              # DeclarativeBase with UUID PK + timestamps
│   │   └── init_models.py       # imports all models (used by Alembic)
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic request/response + WS protocol
│   ├── repositories/            # DB query layer (services call these)
│   ├── services/                # Business logic
│   │   ├── auth_service.py      # register, login, token rotation
│   │   ├── room_service.py      # create, join, leave, membership checks
│   │   ├── chat_service.py      # send, history, read receipts + Redis publish
│   │   ├── presence_service.py  # Redis-backed online/offline
│   │   ├── typing_service.py    # Redis TTL-based typing indicators
│   │   └── upload_service.py    # image validation + local/S3 storage
│   ├── managers/
│   │   ├── connection_manager.py  # per-process WebSocket registry
│   │   └── redis_manager.py       # Redis client singleton
│   ├── events/
│   │   └── redis_subscriber.py  # background task: subscribe & re-broadcast
│   └── dependencies/
│       ├── auth.py              # get_current_user (HTTP + WebSocket variants)
│       └── database.py          # get_db session dependency
├── tests/                       # pytest-asyncio integration tests
├── alembic/                     # database migrations
├── uploads/images/              # local image storage (swap for S3 in prod)
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — at minimum, change SECRET_KEY

# 2. Start all services (API + PostgreSQL + Redis + migrations)
docker compose up --build

# 3. Open API docs
open http://localhost:8000/docs
```

The `migrate` service runs `alembic upgrade head` before the API starts.

---

## Local Development

```bash
# Prerequisites: Python 3.12+, PostgreSQL, Redis

python -m venv venv
source venv/Scripts/activate        # Windows
# source venv/bin/activate           # Mac/Linux

pip install -r requirements.txt
cp .env.example .env                 # edit DATABASE_URL and REDIS_URL

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --reload

# Run tests (no PostgreSQL/Redis needed — uses in-memory SQLite + mocked Redis)
pytest
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Login (returns token pair) |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |

### Users

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/users/me` | Current user profile |
| GET | `/api/v1/users/online` | All online users (Redis-backed) |

### Rooms

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/rooms` | Create room |
| GET | `/api/v1/rooms` | List public rooms |
| GET | `/api/v1/rooms/me` | My rooms |
| GET | `/api/v1/rooms/{id}` | Room detail + members |
| POST | `/api/v1/rooms/{id}/join` | Join room |
| POST | `/api/v1/rooms/{id}/leave` | Leave room |

### Messages

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/messages/{room_id}?page=1&page_size=50` | Paginated history |
| POST | `/api/v1/messages/{room_id}/read` | Mark messages read (REST) |

### Notifications

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/notifications` | List notifications |
| GET | `/api/v1/notifications/unread-count` | Unread count |
| POST | `/api/v1/notifications/read-all` | Mark all read |

### Upload

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/upload/image` | Upload image, get URL |

### WebSocket

```
WS  /ws/chat/{room_id}?token=<access_token>
```

---

## WebSocket Protocol

All messages are JSON objects with a `type` field.

### Client → Server

```json
{"type": "chat_message", "room_id": "uuid", "content": "Hello!"}
{"type": "chat_message", "room_id": "uuid", "image_url": "/uploads/images/x.jpg"}
{"type": "typing_start", "room_id": "uuid"}
{"type": "typing_stop",  "room_id": "uuid"}
{"type": "mark_read",    "room_id": "uuid", "message_ids": ["uuid", ...]}
{"type": "ping"}
```

### Server → Client

```json
{"type": "chat_message", "id": "uuid", "room_id": "uuid",
 "sender_id": "uuid", "sender_username": "alice",
 "content": "Hello!", "image_url": null, "created_at": "2026-01-01T12:00:00Z"}

{"type": "typing",   "room_id": "uuid", "user_id": "uuid",
 "username": "alice", "is_typing": true}

{"type": "presence", "user_id": "uuid", "username": "alice", "status": "online"}

{"type": "message_read", "room_id": "uuid", "message_ids": ["uuid"],
 "user_id": "uuid"}

{"type": "notification", "id": "uuid", "notification_type": "message",
 "content": "...", "room_id": "uuid"}

{"type": "pong"}
{"type": "error", "message": "..."}
```

---

## Redis Key Schema

| Key Pattern | Value | TTL | Purpose |
|---|---|---|---|
| `presence:{user_id}` | username | 300s | Online presence |
| `typing:{room_id}:{user_id}` | username | 5s | Typing indicator (auto-expires) |
| `channel:room:{room_id}` | — | — | Pub/sub channel for messages |
| `channel:typing:{room_id}` | — | — | Pub/sub channel for typing |
| `channel:presence` | — | — | Pub/sub channel for presence |

Typing indicators expire automatically — no "stop typing" event is required for cleanup.

---

## Security

- **JWT**: Access tokens (30 min) + refresh tokens (7 days) with rotation on each refresh. Token hash stored in PostgreSQL for revocation.
- **Passwords**: bcrypt hashing via passlib. Never stored or logged in plaintext.
- **WebSocket auth**: Token passed as `?token=` query param (browsers can't set WS headers).
- **Room access**: Every message send and history fetch verifies room membership at the service layer.
- **File uploads**: Content-type validated + magic byte check to prevent type spoofing. Size limit enforced before writing to disk.
- **Rate limiting**: slowapi middleware on all REST endpoints.
- **CORS**: Explicit origin list from `ALLOWED_ORIGINS` env var.

---

## Scaling

To run multiple API instances:

```yaml
# docker-compose.override.yml
services:
  api:
    deploy:
      replicas: 3
  nginx:
    image: nginx:alpine
    # configure upstream load balancer
```

All instances share the same PostgreSQL and Redis. Redis pub/sub ensures every process delivers messages to its local WebSocket clients regardless of which instance the sender connected to.

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | — | **Required.** Min 32 chars. |
| `DATABASE_URL` | — | `postgresql+asyncpg://...` |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | JSON array |
| `MAX_FILE_SIZE_MB` | `10` | |
| `PRESENCE_TTL_SECONDS` | `300` | |
| `TYPING_TTL_SECONDS` | `5` | |

---

## Running Tests

```bash
# All tests (no external dependencies needed)
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific file
pytest tests/test_auth.py -v
```

Tests use an in-memory SQLite database and mock Redis, so they run without any running infrastructure.
