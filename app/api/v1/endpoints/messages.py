from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, forbidden_exception
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.message import MarkReadRequest, PaginatedMessages
from app.services.chat_service import ChatService

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get(
    "/{room_id}",
    response_model=PaginatedMessages,
    summary="Fetch paginated message history for a room",
)
async def get_messages(
    room_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedMessages:
    svc = ChatService(db)
    try:
        return await svc.get_room_history(room_id, current_user.id, page, page_size)
    except AuthorizationError as exc:
        raise forbidden_exception(exc.message)


@router.post(
    "/{room_id}/read",
    response_model=dict,
    summary="Mark messages as read (REST fallback; WebSocket is preferred)",
)
async def mark_read(
    room_id: uuid.UUID,
    data: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ChatService(db)
    try:
        await svc.mark_messages_read(room_id, current_user.id, data.message_ids)
    except AuthorizationError as exc:
        raise forbidden_exception(exc.message)
    await db.commit()
    return {"marked": len(data.message_ids)}
