from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationResponse, UnreadCount

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="Get notifications for the current user",
)
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    repo = NotificationRepository(db)
    notifications = await repo.get_for_user(current_user.id, unread_only=unread_only, limit=limit)
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.get(
    "/unread-count",
    response_model=UnreadCount,
    summary="Get unread notification count",
)
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCount:
    repo = NotificationRepository(db)
    count = await repo.unread_count(current_user.id)
    return UnreadCount(count=count)


@router.post(
    "/read-all",
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    repo = NotificationRepository(db)
    await repo.mark_all_read(current_user.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
