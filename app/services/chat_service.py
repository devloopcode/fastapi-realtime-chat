"""
ChatService — orchestrates message persistence, Redis pub/sub fan-out,
notification creation, and read receipts.

Flow for a new message:
  1. Persist to PostgreSQL via MessageRepository.
  2. Serialize to WSOutChatMessage.
  3. Publish to Redis channel `channel:room:{room_id}`.
  4. All FastAPI workers subscribed to that channel receive the event and
     broadcast locally to their WebSocket connections (see events/redis_subscriber.py).
  5. Create notifications for room members who are offline.
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.logging import get_logger
from app.managers.redis_manager import get_redis
from app.models.message import Message
from app.repositories.message_repo import MessageRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.room_repo import RoomRepository
from app.models.notification import NotificationType
from app.schemas.message import MessageResponse, PaginatedMessages
from app.schemas.websocket import WSOutChatMessage

logger = get_logger(__name__)

_ROOM_CHANNEL_PREFIX = "channel:room:"


def _channel(room_id: str) -> str:
    return f"{_ROOM_CHANNEL_PREFIX}{room_id}"


def _message_to_ws(msg: Message) -> dict:
    sender = msg.sender
    return WSOutChatMessage(
        id=str(msg.id),
        room_id=str(msg.room_id),
        sender_id=str(msg.sender_id),
        sender_username=sender.username if sender else "deleted",
        sender_display_name=sender.display_name if sender else None,
        sender_avatar_url=sender.avatar_url if sender else None,
        content=msg.content,
        image_url=msg.image_url,
        created_at=msg.created_at.isoformat(),
    ).model_dump()


def _message_to_response(msg: Message) -> MessageResponse:
    sender = msg.sender
    read_by = [str(r.user_id) for r in (msg.read_receipts or [])]
    return MessageResponse(
        id=msg.id,
        room_id=msg.room_id,
        sender_id=msg.sender_id,
        sender_username=sender.username if sender else None,
        sender_display_name=sender.display_name if sender else None,
        sender_avatar_url=sender.avatar_url if sender else None,
        content=msg.content,
        image_url=msg.image_url,
        is_deleted=msg.is_deleted,
        created_at=msg.created_at,
        read_by=read_by,
    )


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self._messages = MessageRepository(session)
        self._rooms = RoomRepository(session)
        self._notifications = NotificationRepository(session)

    async def send_message(
        self,
        room_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str | None,
        image_url: str | None,
    ) -> MessageResponse:
        is_member = await self._rooms.is_member(room_id, sender_id)
        if not is_member:
            raise AuthorizationError("You are not a member of this room")

        msg = await self._messages.create_with_sender(room_id, sender_id, content, image_url)

        # Publish to Redis for cross-process fan-out
        ws_payload = _message_to_ws(msg)
        r = await get_redis()
        await r.publish(_channel(str(room_id)), json.dumps(ws_payload))

        logger.info("message_sent", room_id=str(room_id), sender_id=str(sender_id), message_id=str(msg.id))
        return _message_to_response(msg)

    async def get_room_history(
        self,
        room_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedMessages:
        is_member = await self._rooms.is_member(room_id, user_id)
        if not is_member:
            raise AuthorizationError("You are not a member of this room")

        messages, total = await self._messages.get_room_messages(room_id, page, page_size)
        items = [_message_to_response(m) for m in reversed(messages)]  # chronological order
        return PaginatedMessages(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )

    async def mark_messages_read(
        self,
        room_id: uuid.UUID,
        user_id: uuid.UUID,
        message_ids: list[uuid.UUID],
    ) -> None:
        is_member = await self._rooms.is_member(room_id, user_id)
        if not is_member:
            raise AuthorizationError("You are not a member of this room")

        await self._messages.mark_read(message_ids, user_id)

        # Publish read receipt event
        r = await get_redis()
        payload = {
            "type": "message_read",
            "room_id": str(room_id),
            "user_id": str(user_id),
            "message_ids": [str(mid) for mid in message_ids],
        }
        await r.publish(_channel(str(room_id)), json.dumps(payload))

    async def get_unread_count(self, room_id: uuid.UUID, user_id: uuid.UUID) -> int:
        is_member = await self._rooms.is_member(room_id, user_id)
        if not is_member:
            raise AuthorizationError("You are not a member of this room")

        return await self._messages.get_unread_count(room_id, user_id)
