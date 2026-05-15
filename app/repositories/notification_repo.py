from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def get_for_user(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.recipient_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_id == user_id, Notification.is_read == False
            )
        )
        return result.scalar_one()

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.recipient_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.session.flush()

    async def create_notification(
        self,
        recipient_id: uuid.UUID,
        notification_type: NotificationType,
        content: str,
        actor_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> Notification:
        n = Notification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            notification_type=notification_type,
            content=content,
            room_id=room_id,
            message_id=message_id,
        )
        self.session.add(n)
        await self.session.flush()
        await self.session.refresh(n)
        return n
