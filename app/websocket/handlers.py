"""
WebSocket message handlers.

Each handler receives the raw parsed JSON payload, the authenticated user,
and the room_id. Handlers are pure async functions — they call services,
not repositories directly. Side-effects (persistence, Redis publish) live in services.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.typing_service import start_typing, stop_typing

logger = get_logger(__name__)


async def handle_chat_message(
    payload: dict[str, Any],
    user: User,
    room_id: str,
    db: AsyncSession,
) -> None:
    content: str | None = payload.get("content")
    image_url: str | None = payload.get("image_url")

    if not content and not image_url:
        logger.warning("ws_empty_message", user_id=str(user.id), room_id=room_id)
        return

    svc = ChatService(db)
    await svc.send_message(
        room_id=uuid.UUID(room_id),
        sender_id=user.id,
        content=content,
        image_url=image_url,
    )


async def handle_typing_start(
    payload: dict[str, Any],
    user: User,
    room_id: str,
    db: AsyncSession,
) -> None:
    await start_typing(room_id, str(user.id), user.username)


async def handle_typing_stop(
    payload: dict[str, Any],
    user: User,
    room_id: str,
    db: AsyncSession,
) -> None:
    await stop_typing(room_id, str(user.id), user.username)


async def handle_mark_read(
    payload: dict[str, Any],
    user: User,
    room_id: str,
    db: AsyncSession,
) -> None:
    raw_ids: list[str] = payload.get("message_ids", [])
    if not raw_ids:
        return
    try:
        message_ids = [uuid.UUID(mid) for mid in raw_ids]
    except ValueError:
        logger.warning("ws_invalid_message_ids", user_id=str(user.id))
        return

    svc = ChatService(db)
    await svc.mark_messages_read(uuid.UUID(room_id), user.id, message_ids)
