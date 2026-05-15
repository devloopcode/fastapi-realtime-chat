"""
WebSocket message protocol schemas.

All messages flowing over the WebSocket are typed JSON objects.
The `type` field determines how the message is dispatched.

Client → Server types:
  chat_message, typing_start, typing_stop, mark_read, ping

Server → Client types:
  chat_message, typing, presence, message_read, notification, pong, error, system
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Client → Server ──────────────────────────────────────────────────────────

class WSChatMessage(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    room_id: str
    content: str | None = None
    image_url: str | None = None


class WSTypingStart(BaseModel):
    type: Literal["typing_start"] = "typing_start"
    room_id: str


class WSTypingStop(BaseModel):
    type: Literal["typing_stop"] = "typing_stop"
    room_id: str


class WSMarkRead(BaseModel):
    type: Literal["mark_read"] = "mark_read"
    room_id: str
    message_ids: list[str]


class WSPing(BaseModel):
    type: Literal["ping"] = "ping"


# ── Server → Client ──────────────────────────────────────────────────────────

class WSOutChatMessage(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    id: str
    room_id: str
    sender_id: str
    sender_username: str
    sender_display_name: str | None
    sender_avatar_url: str | None
    content: str | None
    image_url: str | None
    created_at: str  # ISO 8601


class WSTypingEvent(BaseModel):
    type: Literal["typing"] = "typing"
    room_id: str
    user_id: str
    username: str
    is_typing: bool


class WSPresenceEvent(BaseModel):
    type: Literal["presence"] = "presence"
    user_id: str
    username: str
    status: Literal["online", "offline"]


class WSMessageReadEvent(BaseModel):
    type: Literal["message_read"] = "message_read"
    room_id: str
    message_ids: list[str]
    user_id: str


class WSNotificationEvent(BaseModel):
    type: Literal["notification"] = "notification"
    id: str
    notification_type: str
    content: str
    room_id: str | None
    message_id: str | None


class WSPong(BaseModel):
    type: Literal["pong"] = "pong"


class WSError(BaseModel):
    type: Literal["error"] = "error"
    message: str


class WSSystemMessage(BaseModel):
    type: Literal["system"] = "system"
    content: str
